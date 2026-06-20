"""
文件发送端 —— TCP 服务端

职责:
  1. 启动 TCP 服务器，等待接收方连接
  2. 发送文件元信息 (FILE_INFO)
  3. 根据接收方的位图，只发送缺失的数据块
  4. 块级 SHA256 校验 + NACK 重传
  5. 最终文件完整性验证

使用方式（配合 bore）:
    sender = FileSender("ubuntu.iso", chunk_size=4*1024*1024)
    sender.start(port=9000, use_bore=True)
    # 等待接收方连接...
"""

import os
import socket
import threading
import hashlib
import logging
from typing import Optional, Callable

from tcp_chat.file_transfer.protocol import (
    HEADER_SIZE,
    MSG_FILE_INFO, MSG_BITMAP, MSG_CHUNK,
    MSG_ACK, MSG_NACK, MSG_VERIFY, MSG_VERIFIED,
    MSG_ERROR, MSG_DONE,
    send_msg, recv_msg, recv_msg_with_timeout,
    build_file_info, build_bitmap, parse_bitmap,
    build_chunk, build_ack, build_nack,
    build_verify, build_verified,
    build_done, parse_verified, parse_error,
    compute_file_sha256, ACK_TIMEOUT,
)
from tcp_chat.file_transfer.bitmap import Bitmap
from tcp_chat.file_transfer.tunnel import BoreTunnel

logger = logging.getLogger(__name__)

# 默认分块大小: 4MB
DEFAULT_CHUNK_SIZE = 4 * 1024 * 1024

# 每块最大重传次数
MAX_RETRIES_PER_CHUNK = 10

# 监听队列长度
LISTEN_BACKLOG = 5


class FileSender:
    """
    文件发送端 —— 向接收方传输文件

    参数:
        filepath: 要发送的文件路径
        chunk_size: 分块大小（字节），默认 4MB
        port: 本地监听端口
    """

    def __init__(
        self,
        filepath: str,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        port: int = 0,
    ):
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"File not found: {filepath}")
        if not os.path.isfile(filepath):
            raise ValueError(f"Not a file: {filepath}")
        if chunk_size <= 0:
            raise ValueError(f"chunk_size must be > 0, got {chunk_size}")

        self.filepath = os.path.abspath(filepath)
        self.filename = os.path.basename(self.filepath)
        self.filesize = os.path.getsize(self.filepath)
        self.chunk_size = chunk_size
        self.total_chunks = (self.filesize + chunk_size - 1) // chunk_size
        self.port = port or 0  # 0 = 系统自动分配

        # 文件 SHA256（懒计算）
        self._file_sha256: Optional[str] = None
        self._sha256_cache_path = self.filepath + ".sha256"

        # 网络
        self._server_sock: Optional[socket.socket] = None
        self._tunnel: Optional[BoreTunnel] = None
        self._stop_event = threading.Event()

        # 回调
        self.progress_callback: Optional[Callable] = None
        # progress_callback(chunk_index, total_chunks, bytes_sent, total_bytes, message)

    # ── 启动 / 停止 ──────────────────────────────────

    def start(self, port: Optional[int] = None, use_bore: bool = False) -> str:
        """
        启动文件传输服务。

        参数:
            port: 监听端口（覆盖构造时的 port）
            use_bore: 是否通过 bore 暴露到公网

        返回:
            连接地址:
              - use_bore=True:  "bore.pub:xxxxx"
              - use_bore=False: "127.0.0.1:<port>"
        """
        actual_port = port or self.port

        # 创建服务端 socket
        self._server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_sock.bind(("0.0.0.0", actual_port))
        self._server_sock.listen(LISTEN_BACKLOG)
        self.port = self._server_sock.getsockname()[1]

        logger.info("Sender listening on 0.0.0.0:%d", self.port)

        # 启动 bore 隧道
        public_addr = f"127.0.0.1:{self.port}"
        if use_bore:
            self._tunnel = BoreTunnel()
            public_addr = self._tunnel.start(self.port)
            logger.info("Public address: %s", public_addr)

        # 后台预计算文件 SHA256
        self._start_sha256_computation()

        return public_addr

    def stop(self) -> None:
        """停止服务"""
        self._stop_event.set()
        if self._tunnel:
            self._tunnel.stop()
        if self._server_sock:
            try:
                self._server_sock.close()
            except OSError:
                pass

    def serve_forever(self) -> None:
        """
        持续等待接收方连接（阻塞）。
        每次连接处理完毕后继续等待下一个。
        """
        if self._server_sock is None:
            raise RuntimeError("Call start() before serve_forever()")

        self._server_sock.settimeout(1.0)  # 每秒检查 stop_event

        while not self._stop_event.is_set():
            try:
                client_sock, addr = self._server_sock.accept()
                logger.info("Receiver connected from %s", addr)
                self._progress("connected", f"接收方已连接: {addr[0]}:{addr[1]}")

                t = threading.Thread(
                    target=self._handle_receiver,
                    args=(client_sock,),
                    daemon=True,
                )
                t.start()
            except socket.timeout:
                continue
            except OSError:
                break

    # ── 单次传输处理 ──────────────────────────────────

    def _handle_receiver(self, sock: socket.socket) -> None:
        """处理一次接收方连接（完整传输流程）"""
        try:
            # 确保文件 SHA256 已计算
            file_sha256 = self._get_file_sha256()

            # 1. 发送 FILE_INFO
            logger.info("Sending file info: %s (%d bytes, %d chunks)",
                        self.filename, self.filesize, self.total_chunks)
            self._progress("file_info", f"发送文件信息: {self.filename} ({self._format_size(self.filesize)})")
            send_msg(sock, build_file_info(
                filename=self.filename,
                filesize=self.filesize,
                chunk_size=self.chunk_size,
                total_chunks=self.total_chunks,
                file_sha256=file_sha256,
            ))

            # 2. 接收接收方位图
            msg_type, payload = recv_msg(sock)
            if msg_type == MSG_ERROR:
                error_msg = payload.decode("utf-8", errors="replace")
                logger.error("Receiver error: %s", error_msg)
                self._progress("error", f"接收方错误: {error_msg}")
                return

            recv_bitmap = Bitmap(self.total_chunks)
            if msg_type == MSG_BITMAP:
                bitmap_data = parse_bitmap(payload)
                # bitmap_data 是完整的序列化位图（含 total_chunks 头部）
                try:
                    recv_bitmap = Bitmap.from_bytes(bitmap_data)
                except ValueError:
                    logger.warning("Bitmap format mismatch, starting fresh")
                    recv_bitmap = Bitmap(self.total_chunks)
                logger.info("Receiver has %d/%d chunks",
                            recv_bitmap.count_marked(), self.total_chunks)
            else:
                logger.info("No bitmap received, starting fresh")

            # 3. 发送缺失的数据块
            missing = recv_bitmap.missing_indices()
            total_missing = len(missing)
            logger.info("Sending %d missing chunks...", total_missing)
            self._progress("transfer_start", f"开始传输 {total_missing} 个缺失块")

            if total_missing == 0:
                # 所有块都已接收，直接验证
                logger.info("All chunks already received, verifying...")
            else:
                self._send_chunks(sock, missing, recv_bitmap)

            # 4. 发送 VERIFY，请求最终校验
            logger.info("All chunks sent, requesting verification...")
            self._progress("verifying", "正在验证文件完整性...")
            send_msg(sock, build_verify())

            # 5. 接收 VERIFIED
            verify_result = recv_msg_with_timeout(sock, timeout=120)
            if verify_result is None:
                logger.error("Timeout waiting for verification response")
                self._progress("error", "等待验证响应超时")
                return
            msg_type, payload = verify_result
            if msg_type == MSG_VERIFIED:
                received_sha256 = parse_verified(payload).hex()
                if received_sha256 == file_sha256:
                    logger.info("File verification PASSED")
                    self._progress("verified", "文件验证通过 ✓")
                else:
                    logger.warning("File verification FAILED: SHA256 mismatch")
                    send_msg(sock, build_error("SHA256 mismatch"))
                    self._progress("error", "文件验证失败：SHA256 不匹配")
                    return
            elif msg_type == MSG_ERROR:
                error_msg = parse_error(payload)
                logger.error("Receiver verification error: %s", error_msg)
                self._progress("error", f"接收方验证错误: {error_msg}")
                return
            else:
                logger.warning("Unexpected message type %d during verify", msg_type)
                self._progress("error", f"验证阶段收到意外消息类型: {msg_type}")
                return

            # 6. 发送 DONE
            send_msg(sock, build_done())
            logger.info("Transfer completed successfully!")
            self._progress("done", "传输完成 ✓")

        except (ConnectionError, OSError, ValueError) as e:
            logger.error("Transfer failed: %s", e)
            self._progress("error", f"传输失败: {e}")
        finally:
            try:
                sock.close()
            except OSError:
                pass

    def _send_chunks(self, sock: socket.socket, missing_indices: list, bitmap: Optional[Bitmap] = None) -> None:
        """发送缺失的数据块，带 ACK/NACK 重传"""
        f = open(self.filepath, "rb")
        already_marked = bitmap.count_marked() if bitmap else 0
        try:
            for send_order, idx in enumerate(missing_indices):
                if self._stop_event.is_set():
                    raise ConnectionError("Transfer cancelled")

                # 读取块数据
                f.seek(idx * self.chunk_size)
                data = f.read(self.chunk_size)
                if not data:
                    logger.warning("Chunk %d: read empty data, skipping", idx)
                    continue

                # 计算块 SHA256
                chunk_hash = hashlib.sha256(data).digest()

                # 发送块（带重传）
                success = False
                for attempt in range(MAX_RETRIES_PER_CHUNK):
                    if self._stop_event.is_set():
                        raise ConnectionError("Transfer cancelled")

                    send_msg(sock, build_chunk(idx, chunk_hash, data))

                    # 等待 ACK/NACK
                    ack_result = recv_msg_with_timeout(sock, ACK_TIMEOUT)
                    if ack_result is None:
                        # 超时，重传
                        logger.debug("Chunk %d: timeout (attempt %d/%d)",
                                     idx, attempt + 1, MAX_RETRIES_PER_CHUNK)
                        continue
                    resp_type, resp_payload = ack_result
                    if resp_type == MSG_ACK:
                        success = True
                        break
                    elif resp_type == MSG_NACK:
                        logger.debug("Chunk %d: NACK (attempt %d/%d)",
                                     idx, attempt + 1, MAX_RETRIES_PER_CHUNK)
                        continue
                    elif resp_type == MSG_ERROR:
                        error_msg = payload.decode("utf-8", errors="replace")
                        raise ConnectionError(f"Receiver error: {error_msg}")
                    else:
                        logger.warning("Chunk %d: unexpected response type %d",
                                       idx, resp_type)
                        continue

                if not success:
                    raise ConnectionError(
                        f"Chunk {idx}: failed after {MAX_RETRIES_PER_CHUNK} attempts"
                    )

                # 进度回调
                chunks_done = already_marked + send_order + 1
                self._progress("sending",
                               f"正在传输: 第 {chunks_done}/{self.total_chunks} 块 ({chunks_done * self.filesize // self.total_chunks / (1024*1024):.0f}MB)",
                               current_chunk=chunks_done)

        finally:
            f.close()

    # ── SHA256 管理 ──────────────────────────────────

    def _start_sha256_computation(self) -> None:
        """后台预计算文件 SHA256"""
        if self._file_sha256 is not None:
            return

        t = threading.Thread(target=self._compute_sha256_bg, daemon=True)
        t.start()

    def _compute_sha256_bg(self) -> None:
        """后台计算 SHA256"""
        try:
            self._file_sha256 = compute_file_sha256(
                self.filepath,
                progress_callback=self._sha256_progress,
            )
            logger.info("File SHA256 computed: %s", self._file_sha256)
            self._progress("sha256_ready", "文件校验和已计算完成")
        except Exception as e:
            logger.error("SHA256 computation failed: %s", e)

    def _sha256_progress(self, processed: int, total: int) -> None:
        """SHA256 计算进度"""
        pct = processed / total * 100 if total > 0 else 0
        self._progress("hashing", f"计算文件校验和... {pct:.0f}%", sha256_progress=pct)

    def _get_file_sha256(self) -> str:
        """获取文件 SHA256（等待计算完成）"""
        # 先检查缓存
        if self._file_sha256 is not None:
            return self._file_sha256

        # 检查磁盘缓存
        if os.path.exists(self._sha256_cache_path):
            with open(self._sha256_cache_path) as f:
                cached = f.read().strip()
                if cached:
                    self._file_sha256 = cached
                    return cached

        # 等后台计算完成
        compute_file_sha256(self.filepath, progress_callback=self._sha256_progress)
        return self._file_sha256 or ""

    # ── 工具 ──────────────────────────────────────────

    def _progress(self, stage: str, message: str, **kwargs) -> None:
        """触发进度回调"""
        if self.progress_callback:
            self.progress_callback(
                stage=stage,
                message=message,
                filename=self.filename,
                filesize=self.filesize,
                chunk_size=self.chunk_size,
                total_chunks=self.total_chunks,
                **kwargs,
            )

    @staticmethod
    def _format_size(size: int) -> str:
        """格式化文件大小"""
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} PB"
