"""
Bitmap 单元测试 —— 覆盖所有位图操作
"""
import pytest
from tcp_chat.file_transfer.bitmap import Bitmap


class TestBitmap:
    """位图核心功能测试"""

    def test_create_empty(self):
        """创建位图，所有块应为未接收"""
        bm = Bitmap(100)
        assert bm.total_chunks == 100
        assert bm.count_marked() == 0
        assert bm.count_missing() == 100
        assert bm.completion_ratio() == 0.0
        assert not bm.is_complete()

    def test_mark_and_check(self):
        """标记和检查单个块"""
        bm = Bitmap(100)
        bm.mark(0)
        assert bm.is_marked(0)
        assert not bm.is_marked(1)
        assert bm.count_marked() == 1
        assert bm.count_missing() == 99

    def test_mark_all(self):
        """标记所有块"""
        bm = Bitmap(100)
        for i in range(100):
            bm.mark(i)
        assert bm.is_complete()
        assert bm.completion_ratio() == 1.0
        assert bm.count_marked() == 100
        assert bm.count_missing() == 0

    def test_missing_indices_fresh(self):
        """新位图应返回所有索引"""
        bm = Bitmap(50)
        missing = bm.missing_indices()
        assert missing == list(range(50))

    def test_missing_indices_partial(self):
        """部分标记后，缺失索引应正确"""
        bm = Bitmap(10)
        bm.mark(0)
        bm.mark(2)
        bm.mark(4)
        bm.mark(9)
        missing = bm.missing_indices()
        assert missing == [1, 3, 5, 6, 7, 8]

    def test_missing_ranges(self):
        """缺失区间应正确"""
        bm = Bitmap(10)
        bm.mark(0)
        bm.mark(1)
        bm.mark(2)   # 已接收 0-2
        # 3 缺失
        bm.mark(4)   # 4 已接收
        # 5 缺失
        bm.mark(6)
        bm.mark(7)
        bm.mark(8)
        bm.mark(9)   # 已接收 6-9

        ranges = bm.missing_ranges()
        assert ranges == [(3, 4), (5, 6)]

    def test_mark_out_of_range(self):
        """标记越界应抛出异常"""
        bm = Bitmap(10)
        with pytest.raises(IndexError):
            bm.mark(10)
        with pytest.raises(IndexError):
            bm.mark(-1)

    def test_index_out_of_range(self):
        """查询越界应抛出异常"""
        bm = Bitmap(10)
        with pytest.raises(IndexError):
            bm.is_marked(100)

    def test_single_chunk_file(self):
        """只有一个块的文件"""
        bm = Bitmap(1)
        assert not bm.is_marked(0)
        assert bm.count_missing() == 1
        bm.mark(0)
        assert bm.is_complete()

    def test_large_bitmap(self):
        """大位图（模拟 10GB/4MB = 2560 块）"""
        bm = Bitmap(2560)
        # 标记前 1000 块
        for i in range(1000):
            bm.mark(i)
        assert bm.count_marked() == 1000
        assert bm.count_missing() == 1560


class TestBitmapSerialization:
    """位图序列化/反序列化测试"""

    def test_roundtrip(self):
        """序列化再反序列化应得到相同的位图"""
        bm1 = Bitmap(100)
        bm1.mark(0)
        bm1.mark(50)
        bm1.mark(99)

        data = bm1.serialize()
        bm2 = Bitmap.from_bytes(data)

        assert bm2.total_chunks == 100
        assert bm2.is_marked(0)
        assert bm2.is_marked(50)
        assert bm2.is_marked(99)
        assert not bm2.is_marked(1)
        assert bm1 == bm2

    def test_empty_bitmap_roundtrip(self):
        """空位图序列化再反序列化"""
        bm1 = Bitmap(100)
        data = bm1.serialize()
        bm2 = Bitmap.from_bytes(data)
        assert bm1 == bm2
        assert bm2.count_marked() == 0

    def test_full_bitmap_roundtrip(self):
        """满位图序列化再反序列化"""
        bm1 = Bitmap(100)
        for i in range(100):
            bm1.mark(i)
        data = bm1.serialize()
        bm2 = Bitmap.from_bytes(data)
        assert bm1 == bm2
        assert bm2.is_complete()

    def test_deserialize_mismatch(self):
        """序列化数据与目标 total_chunks 不匹配应报错"""
        bm1 = Bitmap(100)
        data = bm1.serialize()

        bm2 = Bitmap(50)
        with pytest.raises(ValueError):
            bm2.deserialize(data)

    def test_raw_bytes_access(self):
        """原始字节访问和设置"""
        bm = Bitmap(16)  # 16 chunks = 2 bytes
        bm.mark(0)       # bit 0
        bm.mark(7)       # bit 7
        bm.mark(15)      # bit 15

        raw = bm.raw_bytes()
        assert len(raw) == 2

        # 新位图从原始字节恢复
        bm2 = Bitmap(16)
        bm2.set_raw_bytes(raw)
        assert bm2.is_marked(0)
        assert bm2.is_marked(7)
        assert bm2.is_marked(15)
        assert not bm2.is_marked(1)

    def test_mark_many(self):
        """批量标记"""
        bm = Bitmap(100)
        bm.mark_many([0, 1, 2, 10, 50, 99])
        assert bm.count_marked() == 6
        for i in [0, 1, 2, 10, 50, 99]:
            assert bm.is_marked(i)

    def test_bitmap_repr(self):
        """__repr__ 输出可读"""
        bm = Bitmap(100)
        bm.mark(0)
        r = repr(bm)
        assert "1/100" in r
        assert "1.0%" in r


class TestBitmapEdgeCases:
    """边界情况"""

    def test_total_chunks_1(self):
        """1 个块"""
        bm = Bitmap(1)
        assert not bm.is_complete()
        bm.mark(0)
        assert bm.is_complete()
        data = bm.serialize()
        bm2 = Bitmap.from_bytes(data)
        assert bm2.is_complete()

    def test_total_chunks_8(self):
        """8 个块（刚好 1 字节）"""
        bm = Bitmap(8)
        for i in range(8):
            bm.mark(i)
        assert bm.is_complete()
        assert len(bm.raw_bytes()) == 1

    def test_total_chunks_9(self):
        """9 个块（1 字节 + 1 bit）"""
        bm = Bitmap(9)
        for i in range(9):
            bm.mark(i)
        assert bm.is_complete()
        assert len(bm.raw_bytes()) == 2

    def test_zero_chunks(self):
        """total_chunks = 0 应创建空位图"""
        bm = Bitmap(0)
        assert bm.total_chunks == 0
        assert bm.count_marked() == 0
        assert bm.count_missing() == 0
        assert bm.is_complete()
        assert bm.completion_ratio() == 1.0

    def test_negative_chunks_raises(self):
        """total_chunks 负数应抛出异常"""
        with pytest.raises(ValueError):
            Bitmap(-1)
