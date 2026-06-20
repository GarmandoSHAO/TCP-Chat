"""
位图（Bitmap）—— 追踪文件传输中哪些块已被接收

核心作用：
  断线重连时，接收方将位图发送给发送方，
  发送方只传输标记为「未接收」的块，实现断点续传。

设计：
  - 每个 bit 对应一个 chunk（1=已接收，0=未接收）
  - 总字节数 = (total_chunks + 7) // 8
  - 支持序列化/反序列化，便于网络传输和磁盘持久化

内存开销（10GB 文件，4MB/块）:
  2560 chunks → 320 bytes —— 极低
"""

from typing import List, Tuple


class Bitmap:
    """位图——追踪数据块接收状态"""

    def __init__(self, total_chunks: int):
        if total_chunks < 0:
            raise ValueError(f"total_chunks must be >= 0, got {total_chunks}")
        self.total_chunks = total_chunks
        if total_chunks == 0:
            self._byte_count = 0
            self._bits = bytearray()
            return
        self._byte_count = (total_chunks + 7) // 8
        self._bits = bytearray(self._byte_count)  # 初始全 0

    # ── 状态查询 ──────────────────────────────────────

    def is_marked(self, index: int) -> bool:
        """检查指定块是否已标记为已接收"""
        self._check_index(index)
        byte_idx = index // 8
        bit_idx = index % 8
        return bool(self._bits[byte_idx] & (1 << bit_idx))

    def mark(self, index: int) -> None:
        """标记指定块为已接收"""
        self._check_index(index)
        byte_idx = index // 8
        bit_idx = index % 8
        self._bits[byte_idx] |= (1 << bit_idx)

    def mark_many(self, indices: List[int]) -> None:
        """批量标记"""
        for idx in indices:
            self.mark(idx)

    # ── 缺失块查询 ────────────────────────────────────

    def missing_indices(self) -> List[int]:
        """返回所有未接收的块索引列表（按顺序）"""
        missing = []
        for i in range(self.total_chunks):
            if not self.is_marked(i):
                missing.append(i)
        return missing

    def missing_ranges(self) -> List[Tuple[int, int]]:
        """
        返回缺失的连续区间 [(start, end), ...]。
        每个区间是 [start, end) 左闭右开。
        """
        ranges = []
        i = 0
        while i < self.total_chunks:
            if not self.is_marked(i):
                start = i
                while i < self.total_chunks and not self.is_marked(i):
                    i += 1
                ranges.append((start, i))
            else:
                i += 1
        return ranges

    # ── 统计 ──────────────────────────────────────────

    def count_marked(self) -> int:
        """已接收块数量"""
        return self.total_chunks - self.count_missing()

    def count_missing(self) -> int:
        """未接收块数量"""
        return len(self.missing_indices())

    def completion_ratio(self) -> float:
        """完成比例 0.0 ~ 1.0"""
        if self.total_chunks == 0:
            return 1.0
        return self.count_marked() / self.total_chunks

    def is_complete(self) -> bool:
        """是否所有块都已接收"""
        return self.count_missing() == 0

    # ── 原始字节访问 ──────────────────────────────────

    def raw_bytes(self) -> bytes:
        """获取位图原始字节（仅数据部分，不含头部）"""
        return bytes(self._bits)

    def set_raw_bytes(self, data: bytes) -> None:
        """直接设置位图原始字节"""
        if len(data) != self._byte_count:
            raise ValueError(
                f"Expected {self._byte_count} bytes, got {len(data)}"
            )
        self._bits = bytearray(data)

    # ── 序列化 ────────────────────────────────────────

    def serialize(self) -> bytes:
        """
        序列化为 bytes。
        格式：[total_chunks:4B(BE)][bitmap_data]
        total_chunks 用于接收方校验位图大小。
        """
        import struct
        header = struct.pack("!I", self.total_chunks)
        return header + bytes(self._bits)

    def deserialize(self, data: bytes) -> None:
        """
        从 bytes 反序列化。
        data 格式：[total_chunks:4B(BE)][bitmap_data]
        如果 total_chunks 不匹配，抛出 ValueError。
        """
        import struct
        total = struct.unpack("!I", data[:4])[0]
        if total != self.total_chunks:
            raise ValueError(
                f"Bitmap total_chunks mismatch: expected {self.total_chunks}, got {total}"
            )
        bitmap_bytes = data[4:]
        expected_len = self._byte_count
        if len(bitmap_bytes) != expected_len:
            raise ValueError(
                f"Bitmap data length mismatch: expected {expected_len}, got {len(bitmap_bytes)}"
            )
        self._bits = bytearray(bitmap_bytes)

    @classmethod
    def from_bytes(cls, data: bytes) -> "Bitmap":
        """从序列化数据创建 Bitmap 实例"""
        import struct
        total = struct.unpack("!I", data[:4])[0]
        bm = cls(total)
        bm.deserialize(data)
        return bm

    # ── 内部 ──────────────────────────────────────────

    def _check_index(self, index: int) -> None:
        if index < 0 or index >= self.total_chunks:
            raise IndexError(
                f"Chunk index {index} out of range [0, {self.total_chunks})"
            )

    def __repr__(self) -> str:
        pct = self.completion_ratio() * 100
        return (
            f"Bitmap({self.count_marked()}/{self.total_chunks} chunks, "
            f"{pct:.1f}% complete)"
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Bitmap):
            return NotImplemented
        return (
            self.total_chunks == other.total_chunks
            and self._bits == other._bits
        )
