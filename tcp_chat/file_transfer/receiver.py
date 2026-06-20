"""
文件接收端 —— TCP 客户端

职责:
  1. 通过 bore 隧道连接到发送方
  2. 接收文件元信息 (FILE_INFO)
  3. 检查本地是否有未完成的会话（断线续传）
  4. 向发送方发送位图（只请求缺失的块）
  5. 接收数据块，校验 SHA256，写入文件
  6. 持久化传输进度到会话文件
  7. 最终文件完整性验证
"""

import os
import socket
import hashlib
import threading
import logging
from typing import Optional, Callable

from tcp_chat.file_transfer.protocol import (
    MSG_FILE_INFO, MSG_BITMAP, MSG_CHUNK,
    MSG_ACK, MSG_NACK, MSG_VERIFY, MSG_VERIFIED,
    MSG_ERROR, MSG_DONE,
    send_msg, recv_msg, recv_msg_with_timeout,
    parse_file_info,
    build_bitmap, parse_bitmap,
    parse_chunk,
    build_ack, build_nack,
    build_verify, build_verified, parse_verified,
    build_error, parse_error,
    compute_file_sha256,
    DEFAULT_RECV_TIMEOUT,
)
from tcp_chat.file_transfer.bitmap import Bitmap
from tcp_chat.file_transfer.session import TransferSession

logger = logging.getLogger(__name__)

# 接收缓冲区大小
RECV_BUFFER_SIZE = 256 * 1024  # 256KB

# 连接重试配置
MAX_CONNECT_RETRIES = -1       # -1 = 无限重试
CONNECT_RETRY_DELAY = 2.0      # 初始重试延迟（秒）


class FileReceiver:
    """
    文件接收端 —— 从发送方接收文件

    参数:
        output_dir: 文件保存目录（默认为当前目录）
        overwrite: 是否覆盖已存在的文件
    """

    def __init__(
        self,
        output_dir: str = ".",
        overwrite: bool = False,
    ):
        self.output_dir = os.path.abspath(output_dir)
        os.makedirs(self.output_dir, exist_ok=True)
        self.overwrite = overwrite

        # 文件信息（从发送方获取）
        self.filename: str = ""
        self.filesize: int = 0
        self.chunk_size: int = 0
        self.total_chunks: int = 0
        self.file_sha256: str = ""

        # 传输状态
        self.bitmap: Optional[Bitmap] = None
        self.session: Optional[TransferSession] = None
        self.output_path: str = ""

        # 控制
        self._stop_event = threading.Event()
        self._cancel_requested = False
        self._sock: Optional[socket.socket] = None

        # 回调
        self.progress_callback: Optional[Callable] = None

        # 内部状态
        self._file_obj = None

    # ── 接收主流程 ────────────────────────────────────

    def receive(self, host: str, port: int) -> bool:
        """
        连接发送方并接收文件（带断线自动重连）。

        参数:
            host: 发送方地址（bore.pub 或 IP）
            port: 端口

        返回:
            True = 传输成功, False = 传输被取消或失败
        """
        # 检查是否已在取消状态
        if self._cancel_requested:
            logger.info("Transfer cancelled before start")
            self._progress("cancelled", "传输已取消")
            return False

        self._cancel_requested = False
        self._stop_event.clear()

        retry_delay = CONNECT_RETRY_DELAY
        first_connect = True

        while not self._stop_event.is_set():
            if self._cancel_requested:
                logger.info("Transfer cancelled by user")
                self._progress("cancelled", "传输已取消")
                return False

            try:
                # 连接
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(DEFAULT_RECV_TIMEOUT)
                sock.connect((host, port))
                self._sock = sock
                logger.info("Connected to %s:%d", host, port)

                # 执行传输
                success = self._handle_transfer(sock)
                sock.close()

                if success:
                    return True

                # 传输失败（非取消），等待重连
                if not self._cancel_requested:
                    logger.info("Will retry in %.0fs...", retry_delay)
                    self._progress("reconnecting",
                                   f"连接断开，{retry_delay:.0f}秒后重连...")
                    self._stop_event.wait(retry_delay)
                    retry_delay = min(retry_delay * 2, 30.0)

            except (ConnectionRefusedError, socket.timeout, OSError) as e:
                if first_connect:
                    logger.error("Connection failed: %s", e)
                    self._progress("error", f"连接失败: {e}")
                    return False

                logger.warning("Reconnect failed: %s, retrying in %.0fs...", e, retry_delay)
                self._stop_event.wait(retry_delay)
                retry_delay = min(retry_delay * 2, 30.0)
            finally:
                first_connect = False

        return False

    def cancel(self) -> None:
        """取消传输"""
        self._cancel_requested = True
        self._stop_event.set()
        # 关闭 socket 强制中断阻塞的 recv 调用
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None

    # ── 单次传输处理 ──────────────────────────────────

    def _handle_transfer(self, sock: socket.socket) -> bool:
        """处理一次完整的文件传输（单次 TCP 连接）"""
        try:
            # 1. 接收 FILE_INFO
            msg_type, payload = recv_msg(sock)
            if msg_type != MSG_FILE_INFO:
                logger.error("Expected FILE_INFO, got type %d", msg_type)
                self._progress("error", "协议错误：未收到文件信息")
                return False

            info = parse_file_info(payload)
            self.filename = info["filename"]
            self.filesize = info["filesize"]
            self.chunk_size = info["chunk_size"]
            self.total_chunks = info["total_chunks"]
            self.file_sha256 = info.get("file_sha256", "")

            logger.info("Receiving: %s (%d bytes, %d chunks%s)",
                        self.filename, self.filesize, self.total_chunks,
                        f", SHA256: {self.file_sha256[:16]}..." if self.file_sha256 else "")

            self._progress("file_info",
                           f"文件: {self.filename} ({self._format_size(self.filesize)})")

            # 2. 检查本地会话（断线续传）
            self.output_path = os.path.join(self.output_dir, self.filename)
            self.session = TransferSession.load(self.output_path)

            if self.session:
                # 校验会话是否匹配当前文件
                if (self.session.filesize == self.filesize
                        and self.session.total_chunks == self.total_chunks
                        and self.session.file_sha256 == self.file_sha256):
                    self.bitmap = self.session.bitmap
                    logger.info("Resuming transfer: %d/%d chunks already received",
                                self.bitmap.count_marked(), self.total_chunks)
                    self._progress("resuming",
                                   f"续传: 已接收 {self.bitmap.count_marked()}/{self.total_chunks} 块 "
                                   f"({self.bitmap.completion_ratio()*100:.1f}%)")
                else:
                    # 文件不匹配，重新开始
                    logger.info("Session mismatch or file changed, starting fresh")
                    self.session = None
                    self.bitmap = Bitmap(self.total_chunks)
            else:
                self.bitmap = Bitmap(self.total_chunks)
                logger.info("Starting fresh transfer")

            # 3. 创建文件（预分配空间）
            self._prepare_output_file()

            # 4. 发送 BITMAP
            bitmap_data = self.bitmap.serialize()
            send_msg(sock, build_bitmap(bitmap_data))
            logger.info("Sent bitmap: %d/%d chunks marked",
                        self.bitmap.count_marked(), self.total_chunks)

            # 5. 如果没有会话，创建新的
            if self.session is None and not self.bitmap.is_complete():
                self.session = TransferSession.create(
                    output_path=self.output_path,
                    filename=self.filename,
                    filesize=self.filesize,
                    chunk_size=self.chunk_size,
                    total_chunks=self.total_chunks,
                    file_sha256=self.file_sha256,
                )

            # 6. 接收数据块直至完成（VERIFY + DONE 也在此处理）
            if not self._receive_chunks(sock):
                # 如果不完整且有未完成的会话，保留会话文件以支持续传
                if self.session and not self.bitmap.is_complete():
                    self.session.save()
                return False

            # 传输完成，清理会话
            logger.info("Transfer completed successfully!")
            self._progress("done", "传输完成 ✓")
            if self.session:
                self.session.delete()
                self.session = None
            return True

        except (ConnectionError, OSError, ValueError) as e:
            logger.error("Transfer error: %s", e)
            # 保存会话以备续传
            if self.session:
                try:
                    self.session.save()
                except Exception:
                    pass
            self._progress("error", f"传输错误: {e}")
            return False
        finally:
            self._close_output_file()

    def _receive_chunks(self, sock: socket.socket) -> bool:
        """
        接收数据块循环，直至传输完成。

        处理消息类型:
          - MSG_CHUNK  → 校验 + 写入 + ACK
          - MSG_VERIFY → 最终文件完整性校验 → VERIFIED
          - MSG_DONE   → 传输完成
          - MSG_ERROR  → 发送方报告错误
        """
        while not self._stop_event.is_set():
            msg_type, payload = recv_msg(sock)

            if msg_type == MSG_CHUNK:
                if not self._handle_chunk(sock, payload):
                    return False

            elif msg_type == MSG_VERIFY:
                return self._handle_verify(sock)

            elif msg_type == MSG_DONE:
                return True

            elif msg_type == MSG_ERROR:
                error_msg = parse_error(payload)
                logger.error("Sender error during transfer: %s", error_msg)
                self._progress("error", f"发送方错误: {error_msg}")
                return False

            else:
                logger.warning("Unexpected message type %d, ignoring", msg_type)
                continue

        return False

    def _handle_chunk(self, sock: socket.socket, payload: bytes) -> bool:
        """处理单个数据块"""
        index, chunk_hash, data = parse_chunk(payload)

        # 校验 SHA256
        computed_hash = hashlib.sha256(data).digest()
        if computed_hash != chunk_hash:
            logger.warning("Chunk %d: SHA256 mismatch, requesting NACK", index)
            send_msg(sock, build_nack(index))
            return True  # NACK 不是错误，继续等待重传

        # 写入文件
        if not self._write_chunk_to_file(index, data):
            logger.error("Chunk %d: write failed", index)
            send_msg(sock, build_error(f"Write failed at chunk {index}"))
            return False

        # 更新位图
        self.bitmap.mark(index)

        # 发送 ACK
        send_msg(sock, build_ack(index))

        # 自动保存会话
        if self.session:
            self.session.bitmap.mark(index)
            self.session.maybe_auto_save()

        # 进度回调
        chunks_done = self.bitmap.count_marked()
        pct = self.bitmap.completion_ratio() * 100
        self._progress("receiving",
                       f"接收中: {chunks_done}/{self.total_chunks} 块 ({pct:.1f}%)",
                       percent=pct)
        return True

    def _handle_verify(self, sock: socket.socket) -> bool:
        """处理 VERIFY —— 计算文件 SHA256 并回应"""
        self._progress("verifying", "正在验证文件完整性...")
        received_sha256 = compute_file_sha256(self.output_path)
        logger.info("Computed file SHA256: %s", received_sha256)

        if self.file_sha256 and received_sha256 != self.file_sha256:
            logger.error("File verification FAILED")
            send_msg(sock, build_error("SHA256 mismatch"))
            self._progress("error", "文件验证失败：SHA256 不匹配，请重新传输")
            return False

        # 发送 VERIFIED
        send_msg(sock, build_verified(bytes.fromhex(received_sha256)))
        self._progress("verified", "文件验证通过 ✓")
        logger.info("File verification PASSED")

        # 等待 DONE
        msg_type, payload = recv_msg(sock)
        if msg_type == MSG_DONE:
            return True
        elif msg_type == MSG_ERROR:
            error_msg = parse_error(payload)
            logger.error("Sender error: %s", error_msg)
            self._progress("error", f"发送方错误: {error_msg}")
            return False
        else:
            logger.warning("Expected DONE after VERIFY, got type %d", msg_type)
            return True  # 仍然返回成功，因为文件已验证

    # ── 文件 I/O ──────────────────────────────────────

    def _prepare_output_file(self) -> None:
        """准备输出文件（创建/打开/预分配）"""
        # 检查文件是否已存在
        if os.path.exists(self.output_path) and not self.overwrite:
            if self.session is None:
                # 没有续传会话，询问是否覆盖（通过回调）
                self._progress("confirm", f"文件已存在: {self.filename}")

        # 打开文件
        mode = "r+b" if os.path.exists(self.output_path) else "wb"
        self._file_obj = open(self.output_path, mode)

        # 预分配文件空间（仅新文件或续传中需要）
        if self.filesize > 0:
            try:
                if os.path.getsize(self.output_path) < self.filesize:
                    self._file_obj.truncate(self.filesize)
                    self._file_obj.flush()
                    os.fsync(self._file_obj.fileno())
            except OSError as e:
                logger.warning("File pre-allocation failed: %s (continuing anyway)", e)

    def _write_chunk_to_file(self, index: int, data: bytes) -> bool:
        """将块数据写入文件的正确位置"""
        if self._file_obj is None:
            return False
        try:
            self._file_obj.seek(index * self.chunk_size)
            self._file_obj.write(data)
            return True
        except OSError as e:
            logger.error("Write error at chunk %d: %s", index, e)
            return False

    def _close_output_file(self) -> None:
        """关闭输出文件"""
        if self._file_obj is not None:
            try:
                self._file_obj.flush()
                os.fsync(self._file_obj.fileno())
                self._file_obj.close()
            except OSError:
                pass
            finally:
                self._file_obj = None

    # ── 内部消息构建 ──────────────────────────────────

    @staticmethod
    def _build_ack_msg(index: int) -> bytes:
        return build_ack(index)

    @staticmethod
    def _build_nack_msg(index: int) -> bytes:
        return build_nack(index)

    @staticmethod
    def _build_error_msg(message: str) -> bytes:
        return build_error(message)

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
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} PB"
