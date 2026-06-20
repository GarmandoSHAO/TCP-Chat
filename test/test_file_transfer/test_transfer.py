"""
文件传输集成测试 —— 模拟发送端与接收端在 localhost 上的完整传输

测试场景:
  1. 正常传输 —— 小文件完整传输并验证 SHA256
  2. 多块传输 —— 多块文件正确组装
  3. 断线续传 —— 通过会话文件恢复传输
  4. 错误处理 —— 连接拒绝、文件不存在等
"""
import os
import socket
import threading
import hashlib
import time
import tempfile
import pytest

from tcp_chat.file_transfer.sender import FileSender, DEFAULT_CHUNK_SIZE
from tcp_chat.file_transfer.receiver import FileReceiver
from tcp_chat.file_transfer.bitmap import Bitmap
from tcp_chat.file_transfer.session import TransferSession


# ── 辅助函数 ──────────────────────────────────────────

def create_test_file(path: str, size: int, seed: int = 42) -> str:
    """创建指定大小的测试文件（可复现内容）"""
    import struct
    with open(path, "wb") as f:
        remaining = size
        pattern = struct.pack("!I", seed) * 256  # 1KB pattern
        while remaining > 0:
            chunk = pattern[:min(remaining, len(pattern))]
            f.write(chunk)
            remaining -= len(chunk)
    return path


def file_sha256(path: str) -> str:
    """计算文件 SHA256"""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            data = f.read(65536)
            if not data:
                break
            h.update(data)
    return h.hexdigest()


def find_free_port() -> int:
    """找可用端口"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


# ── 进度捕获回调 ─────────────────────────────────────

class ProgressCollector:
    """收集进度回调以便断言"""
    def __init__(self):
        self.events = []
        self.lock = threading.Lock()

    def callback(self, **kwargs):
        with self.lock:
            self.events.append(dict(kwargs))

    def has_stage(self, stage: str) -> bool:
        with self.lock:
            return any(e.get("stage") == stage for e in self.events)


# ── 测试类 ────────────────────────────────────────────

class TestSmallFileTransfer:
    """小文件传输测试"""

    # 每个测试方法独立运行，使用自己的 tmp dir
    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        self.src_file = os.path.join(tmp_path, "source.bin")
        self.port = find_free_port()

    def _run_transfer(self, output_dir=None):
        """运行一次完整的发送→接收流程"""
        if output_dir is None:
            output_dir = os.path.dirname(self.src_file)

        sender = FileSender(self.src_file, port=self.port)
        sender.start(use_bore=False)

        # serve_forever 在后台线程运行
        t = threading.Thread(target=sender.serve_forever, daemon=True)
        t.start()

        # 等待服务启动
        time.sleep(0.2)

        receiver = FileReceiver(output_dir=output_dir, overwrite=True)
        success = receiver.receive("127.0.0.1", self.port)
        sender.stop()

        # 接收到的文件路径 = output_dir/filename（filename 来自 FILE_INFO 的 basename）
        received_path = os.path.join(output_dir, "source.bin")
        return success, received_path

    def test_transfer_1k(self):
        """传输 1KB 文件"""
        create_test_file(self.src_file, 1024)
        success, received = self._run_transfer()
        assert success
        assert os.path.exists(received)
        assert os.path.getsize(received) == 1024
        assert file_sha256(self.src_file) == file_sha256(received)

    def test_transfer_4k_exact(self):
        """传输恰好 4KB（等于块大小）"""
        create_test_file(self.src_file, 4096)
        success, received = self._run_transfer()
        assert success
        assert os.path.getsize(received) == 4096
        assert file_sha256(self.src_file) == file_sha256(received)

    def test_transfer_4k_plus(self):
        """传输 4KB+1byte（略超一块）"""
        create_test_file(self.src_file, 4097)
        success, received = self._run_transfer()
        assert success
        assert os.path.getsize(received) == 4097
        assert file_sha256(self.src_file) == file_sha256(received)

    def test_transfer_empty_file(self):
        """传输空文件"""
        create_test_file(self.src_file, 0)
        success, received = self._run_transfer()
        assert success
        assert os.path.exists(received)
        assert os.path.getsize(received) == 0


class TestMultiChunkTransfer:
    """多块传输测试"""

    CHUNK_SIZE = 64 * 1024  # 64KB（加快测试）

    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        self.src_file = os.path.join(tmp_path, "source.bin")
        self.port = find_free_port()

    def _run(self, output_dir=None):
        if output_dir is None:
            output_dir = os.path.dirname(self.src_file)
        sender = FileSender(self.src_file, chunk_size=self.CHUNK_SIZE, port=self.port)
        sender.start(use_bore=False)
        t = threading.Thread(target=sender.serve_forever, daemon=True)
        t.start()
        time.sleep(0.2)
        receiver = FileReceiver(output_dir=output_dir, overwrite=True)
        success = receiver.receive("127.0.0.1", self.port)
        sender.stop()
        return success, os.path.join(output_dir, "source.bin")

    def test_3_chunks(self):
        """3 块传输"""
        create_test_file(self.src_file, self.CHUNK_SIZE * 3)
        success, received = self._run()
        assert success
        assert file_sha256(self.src_file) == file_sha256(received)

    def test_5_chunks_unaligned(self):
        """5 块 + 余数"""
        create_test_file(self.src_file, self.CHUNK_SIZE * 5 + 12345)
        success, received = self._run()
        assert success
        assert file_sha256(self.src_file) == file_sha256(received)

    def test_10_chunks_with_progress(self):
        """10 块 + 进度回调验证"""
        create_test_file(self.src_file, self.CHUNK_SIZE * 10)
        sender = FileSender(self.src_file, chunk_size=self.CHUNK_SIZE, port=self.port)
        sender.start(use_bore=False)
        t = threading.Thread(target=sender.serve_forever, daemon=True)
        t.start()
        time.sleep(0.2)

        progress = ProgressCollector()
        receiver = FileReceiver(output_dir=os.path.dirname(self.src_file), overwrite=True)
        receiver.progress_callback = progress.callback
        success = receiver.receive("127.0.0.1", self.port)
        sender.stop()

        assert success
        assert progress.has_stage("file_info")
        assert progress.has_stage("verified")
        assert file_sha256(self.src_file) == file_sha256(
            os.path.join(os.path.dirname(self.src_file), "source.bin")
        )


class TestResumeTransfer:
    """断线续传测试"""

    CHUNK_SIZE = 64 * 1024  # 64KB

    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        self.src = os.path.join(tmp_path, "source.bin")
        self.dst = os.path.join(tmp_path, "source.bin")  # 接收方输出
        self.port = find_free_port()

    def test_resume_with_session_file(self):
        """
        基于会话文件的断线续传：
        创建会话标记部分块已接收，发送端应只传缺失的块
        """
        total_chunks = 8
        file_size = self.CHUNK_SIZE * total_chunks
        create_test_file(self.src, file_size)

        # 用不同路径做接收方输出（避免覆盖源文件）
        dst_file = self.dst  # will be overwritten by receiver
        # 使用一个临时文件名来存储部分数据，不与发送方冲突
        partial_dir = os.path.join(os.path.dirname(self.src), "partial")
        os.makedirs(partial_dir, exist_ok=True)
        partial_dst = os.path.join(partial_dir, "source.bin")

        # 创建会话 + 部分数据文件
        session = TransferSession.create(
            output_path=partial_dst,
            filename="source.bin",
            filesize=file_size,
            chunk_size=self.CHUNK_SIZE,
            total_chunks=total_chunks,
            file_sha256=file_sha256(self.src),
        )
        for i in range(4):
            session.bitmap.mark(i)
        session.save()

        # 写入前 4 块数据到目标文件
        with open(partial_dst, "wb") as f:
            f.truncate(file_size)

        src_data = open(self.src, "rb").read()
        with open(partial_dst, "r+b") as f:
            for i in range(4):
                offset = i * self.CHUNK_SIZE
                f.seek(offset)
                f.write(src_data[offset:offset + self.CHUNK_SIZE])

        # 启动发送端
        sender = FileSender(self.src, chunk_size=self.CHUNK_SIZE, port=self.port)
        sender.start(use_bore=False)
        t = threading.Thread(target=sender.serve_forever, daemon=True)
        t.start()
        time.sleep(0.2)

        progress = ProgressCollector()
        receiver = FileReceiver(output_dir=partial_dir, overwrite=True)
        receiver.progress_callback = progress.callback
        success = receiver.receive("127.0.0.1", self.port)
        sender.stop()

        assert success, "续传应成功"
        assert progress.has_stage("resuming"), "应触发续传阶段"
        assert file_sha256(self.src) == file_sha256(partial_dst), \
            "续传文件应与源文件完全一致"

    def test_resume_already_complete(self):
        """
        文件已全部接收，再次传输应直接通过验证
        """
        total_chunks = 4
        file_size = self.CHUNK_SIZE * total_chunks
        create_test_file(self.src, file_size)

        dst_dir = os.path.join(os.path.dirname(self.src), "already_done")
        os.makedirs(dst_dir, exist_ok=True)
        dst_file = os.path.join(dst_dir, "source.bin")

        # 创建完整会话 + 完整文件
        session = TransferSession.create(
            output_path=dst_file,
            filename="source.bin",
            filesize=file_size,
            chunk_size=self.CHUNK_SIZE,
            total_chunks=total_chunks,
            file_sha256=file_sha256(self.src),
        )
        for i in range(total_chunks):
            session.bitmap.mark(i)
        session.save()

        # 写入完整文件
        with open(dst_file, "wb") as f:
            f.write(open(self.src, "rb").read())

        # 启动发送端
        sender = FileSender(self.src, chunk_size=self.CHUNK_SIZE, port=self.port)
        sender.start(use_bore=False)
        t = threading.Thread(target=sender.serve_forever, daemon=True)
        t.start()
        time.sleep(0.2)

        progress = ProgressCollector()
        receiver = FileReceiver(output_dir=dst_dir, overwrite=True)
        receiver.progress_callback = progress.callback
        success = receiver.receive("127.0.0.1", self.port)
        sender.stop()

        assert success
        assert progress.has_stage("verified"), "应触发验证阶段"


class TestErrorHandling:
    """错误处理测试"""

    def test_file_not_found(self):
        """文件不存在应抛出 FileNotFoundError"""
        with pytest.raises(FileNotFoundError):
            FileSender("/nonexistent/file.iso")

    def test_connection_refused(self, tmp_path):
        """连接被拒绝不应抛出异常，应返回 False"""
        receiver = FileReceiver(output_dir=str(tmp_path))
        success = receiver.receive("127.0.0.1", 1)
        assert not success

    def test_cancel_before_connect(self, tmp_path):
        """连接前取消应返回 False"""
        receiver = FileReceiver(output_dir=str(tmp_path))
        # 取消标志设为 True 后，receive 应在循环开始处返回
        receiver._cancel_requested = True
        receiver._stop_event.set()
        success = receiver.receive("127.0.0.1", 12345)
        assert not success


class TestLargeTransfer:
    """较大文件传输测试"""

    CHUNK_SIZE = 256 * 1024  # 256KB

    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        self.src = os.path.join(tmp_path, "large.bin")
        self.port = find_free_port()

    def test_50_chunks_integrity(self):
        """50 块文件完整性"""
        file_size = self.CHUNK_SIZE * 50  # ~12.5MB
        create_test_file(self.src, file_size)

        sender = FileSender(self.src, chunk_size=self.CHUNK_SIZE, port=self.port)
        sender.start(use_bore=False)
        t = threading.Thread(target=sender.serve_forever, daemon=True)
        t.start()
        time.sleep(0.3)

        receiver = FileReceiver(output_dir=os.path.dirname(self.src), overwrite=True)
        success = receiver.receive("127.0.0.1", self.port)
        sender.stop()

        assert success
        assert file_sha256(self.src) == file_sha256(
            os.path.join(os.path.dirname(self.src), "large.bin")
        )
