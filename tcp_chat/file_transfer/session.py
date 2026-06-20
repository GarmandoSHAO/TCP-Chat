"""
传输会话持久化 —— 使断线续传在进程/系统崩溃后依然可用

每次接收到 N 个块（或每 T 秒），将位图快照写入磁盘文件。
程序重启后，从磁盘加载会话文件，恢复传输进度。

会话文件格式（JSON）:
  {
    "filename": "ubuntu.iso",
    "filesize": 10737418240,
    "chunk_size": 4194304,
    "total_chunks": 2560,
    "bitmap": "<base64 encoded>",
    "file_sha256": "a1b2c3...",
    "last_update": "2026-06-19T12:34:56"
  }

文件命名约定:
  <output_filename>.ft_session.json
  与目标文件放在同一目录
"""

import json
import os
import base64
import time
from typing import Optional

from tcp_chat.file_transfer.bitmap import Bitmap

# 触发持久化的条件
AUTO_SAVE_CHUNK_INTERVAL = 100   # 每接收 N 个块自动保存
AUTO_SAVE_TIME_INTERVAL = 5.0    # 距上次保存超过 T 秒则自动保存


class TransferSession:
    """
    传输会话 —— 管理传输进度的持久化。

    使用方式:
      session = TransferSession.create(filepath, chunk_size)
      # ... 传输过程中 ...
      session.bitmap.mark(index)
      session.save()  # 或自动保存

    恢复:
      session = TransferSession.load(filepath)
      if session:
          # bitmap 已从磁盘恢复
    """

    def __init__(self):
        self.filename: str = ""
        self.filesize: int = 0
        self.chunk_size: int = 0
        self.total_chunks: int = 0
        self.file_sha256: str = ""
        self.bitmap: Optional[Bitmap] = None
        self._session_path: str = ""
        self._last_save_time: float = 0.0
        self._chunks_since_last_save: int = 0

    # ── 工厂方法 ──────────────────────────────────────

    @classmethod
    def create(
        cls,
        output_path: str,
        filename: str,
        filesize: int,
        chunk_size: int,
        total_chunks: int,
        file_sha256: str,
    ) -> "TransferSession":
        """创建新的传输会话"""
        session = cls()
        session.filename = filename
        session.filesize = filesize
        session.chunk_size = chunk_size
        session.total_chunks = total_chunks
        session.file_sha256 = file_sha256
        session.bitmap = Bitmap(total_chunks)
        session._session_path = cls._session_file_path(output_path)
        session._last_save_time = time.time()
        session.save()
        return session

    @classmethod
    def load(cls, output_path: str) -> Optional["TransferSession"]:
        """
        从磁盘加载传输会话。
        如果会话文件不存在或已损坏，返回 None。
        """
        session_path = cls._session_file_path(output_path)
        if not os.path.exists(session_path):
            return None

        try:
            with open(session_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            session = cls()
            session.filename = data["filename"]
            session.filesize = data["filesize"]
            session.chunk_size = data["chunk_size"]
            session.total_chunks = data["total_chunks"]
            session.file_sha256 = data["file_sha256"]

            session.bitmap = cls._bitmap_from_base64(
                data["total_chunks"], data["bitmap"]
            )

            session._session_path = session_path
            session._last_save_time = time.time()
            return session

        except (json.JSONDecodeError, KeyError, ValueError, TypeError) as e:
            # 会话文件损坏，删除后重新开始
            try:
                os.remove(session_path)
            except OSError:
                pass
            return None

    # ── 持久化 ────────────────────────────────────────

    def save(self) -> None:
        """将会话保存到磁盘"""
        if self.bitmap is None:
            return

        data = {
            "filename": self.filename,
            "filesize": self.filesize,
            "chunk_size": self.chunk_size,
            "total_chunks": self.total_chunks,
            "file_sha256": self.file_sha256,
            "bitmap": self._bitmap_to_base64(),
            "last_update": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }

        # 原子写入：先写临时文件，再重命名
        tmp_path = self._session_path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())

        os.replace(tmp_path, self._session_path)
        self._last_save_time = time.time()
        self._chunks_since_last_save = 0

    def maybe_auto_save(self) -> None:
        """
        根据条件触发自动保存（每 N 块或每 T 秒）。
        在每次接收到一个块后调用。
        """
        self._chunks_since_last_save += 1
        now = time.time()

        if self._chunks_since_last_save >= AUTO_SAVE_CHUNK_INTERVAL:
            self.save()
        elif (now - self._last_save_time) >= AUTO_SAVE_TIME_INTERVAL:
            self.save()

    def delete(self) -> None:
        """删除会话文件（传输完成后清理）"""
        try:
            if os.path.exists(self._session_path):
                os.remove(self._session_path)
        except OSError:
            pass

    def exists_on_disk(self) -> bool:
        """会话文件是否存在于磁盘"""
        return os.path.exists(self._session_path)

    # ── 工具 ──────────────────────────────────────────

    @property
    def output_path(self) -> str:
        """获取会话对应的输出文件路径"""
        if self._session_path.endswith(".ft_session.json"):
            return self._session_path[:-len(".ft_session.json")]
        return self._session_path.replace(".ft_session.json", "")

    @staticmethod
    def _session_file_path(output_path: str) -> str:
        """获取会话文件路径"""
        return output_path + ".ft_session.json"

    def _bitmap_to_base64(self) -> str:
        """将位图序列化为 base64 字符串"""
        return base64.b64encode(bytes(self.bitmap._bits)).decode("ascii")

    @staticmethod
    def _bitmap_from_base64(total_chunks: int, b64: str) -> Bitmap:
        """从 base64 恢复位图"""
        bm = Bitmap(total_chunks)
        raw = base64.b64decode(b64)
        # 直接替换内部 bits
        expected = (total_chunks + 7) // 8
        if len(raw) != expected:
            raise ValueError(f"Bitmap data length mismatch: {len(raw)} vs {expected}")
        bm._bits = bytearray(raw)
        return bm

    def __repr__(self) -> str:
        pct = (self.bitmap.completion_ratio() * 100) if self.bitmap else 0
        return (
            f"TransferSession({self.filename}, "
            f"{pct:.1f}% complete)"
        )
