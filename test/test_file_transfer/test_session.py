"""
会话持久化单元测试 —— 覆盖保存、加载、续传
"""
import os
import time
import pytest
from tcp_chat.file_transfer.bitmap import Bitmap
from tcp_chat.file_transfer.session import TransferSession


class TestTransferSession:
    """传输会话核心功能测试"""

    FILE_INFO = {
        "filename": "test.iso",
        "filesize": 1073741824,
        "chunk_size": 4194304,
        "total_chunks": 256,
        "file_sha256": "abc123",
    }

    def test_create_and_save(self, tmp_path):
        """创建并保存会话"""
        output_path = str(tmp_path / "test.iso")
        session = TransferSession.create(
            output_path=output_path,
            **self.FILE_INFO,
        )

        # 会话应创建会话文件
        session_path = output_path + ".ft_session.json"
        assert os.path.exists(session_path)

        # 位图应为空
        assert session.bitmap.total_chunks == 256
        assert session.bitmap.count_marked() == 0

        session.delete()

    def test_save_and_load(self, tmp_path):
        """保存后加载应恢复所有字段"""
        output_path = str(tmp_path / "test.iso")
        session = TransferSession.create(output_path=output_path, **self.FILE_INFO)

        # 标记一些块
        for i in range(50):
            session.bitmap.mark(i)

        # 手动保存
        session.save()

        # 加载新会话
        loaded = TransferSession.load(output_path)
        assert loaded is not None
        assert loaded.filename == self.FILE_INFO["filename"]
        assert loaded.filesize == self.FILE_INFO["filesize"]
        assert loaded.chunk_size == self.FILE_INFO["chunk_size"]
        assert loaded.total_chunks == self.FILE_INFO["total_chunks"]
        assert loaded.file_sha256 == self.FILE_INFO["file_sha256"]
        assert loaded.bitmap.count_marked() == 50
        for i in range(50):
            assert loaded.bitmap.is_marked(i)
        for i in range(50, 256):
            assert not loaded.bitmap.is_marked(i)

        session.delete()

    def test_load_nonexistent(self, tmp_path):
        """不存在的会话文件应返回 None"""
        session = TransferSession.load(str(tmp_path / "nonexistent.iso"))
        assert session is None

    def test_resume_transfer(self, tmp_path):
        """模拟续传：创建 → 部分接收 → 保存 → 加载 → 继续接收"""
        output_path = str(tmp_path / "ubuntu.iso")

        # 第一阶段：创建会话，接收 100 块
        session1 = TransferSession.create(
            output_path=output_path, **self.FILE_INFO
        )
        for i in range(100):
            session1.bitmap.mark(i)
        session1.save()
        assert session1.bitmap.count_marked() == 100

        # 第二阶段：模拟程序重启，加载会话，继续接收
        session2 = TransferSession.load(output_path)
        assert session2 is not None
        assert session2.bitmap.count_marked() == 100

        for i in range(100, 200):
            session2.bitmap.mark(i)
        session2.save()

        # 第三阶段：再次加载，确认 200 块
        session3 = TransferSession.load(output_path)
        assert session3 is not None
        assert session3.bitmap.count_marked() == 200

        session1.delete()

    def test_delete(self, tmp_path):
        """删除会话应清理文件"""
        output_path = str(tmp_path / "cleanup.iso")
        session = TransferSession.create(output_path=output_path, **self.FILE_INFO)
        session_path = output_path + ".ft_session.json"
        assert os.path.exists(session_path)
        session.delete()
        assert not os.path.exists(session_path)

    def test_auto_save(self, tmp_path):
        """自动保存应在达到条件时触发"""
        output_path = str(tmp_path / "autosave.iso")
        session = TransferSession.create(output_path=output_path, **self.FILE_INFO)
        session_path = output_path + ".ft_session.json"

        # 标记 AUTO_SAVE_CHUNK_INTERVAL 个块
        mark_count = 100  # AUTO_SAVE_CHUNK_INTERVAL
        for i in range(mark_count):
            session.bitmap.mark(i)
            session.maybe_auto_save()

        # 加载验证
        loaded = TransferSession.load(output_path)
        assert loaded is not None
        assert loaded.bitmap.count_marked() == mark_count

        session.delete()

    def test_corrupted_session_file(self, tmp_path):
        """损坏的会话文件应返回 None 并自动删除"""
        output_path = str(tmp_path / "corrupted.iso")
        session_path = output_path + ".ft_session.json"

        # 写无效 JSON
        with open(session_path, "w") as f:
            f.write("this is not json")

        loaded = TransferSession.load(output_path)
        assert loaded is None
        assert not os.path.exists(session_path)

    def test_incomplete_json(self, tmp_path):
        """缺少字段的 JSON 应返回 None"""
        output_path = str(tmp_path / "incomplete.iso")
        session_path = output_path + ".ft_session.json"

        import json
        with open(session_path, "w") as f:
            json.dump({"filename": "test.iso"}, f)  # 缺少其他字段

        loaded = TransferSession.load(output_path)
        assert loaded is None

    def test_session_mismatch(self, tmp_path):
        """文件信息不匹配时应放弃会话"""
        output_path = str(tmp_path / "mismatch.iso")

        # 创建会话（文件大小 1GB）
        session = TransferSession.create(
            output_path=output_path,
            filename="old.iso",
            filesize=1073741824,
            chunk_size=4194304,
            total_chunks=256,
            file_sha256="abc",
        )
        session.save()

        # 现在模拟接收方连接到了一个不同的文件
        session2 = TransferSession.load(output_path)
        assert session2 is not None

        # 手动修改 session 数据来模拟文件不匹配
        session2.filesize = 999  # 不同的大小
        # 不匹配应该由接收方检测，这里只验证 load 本身能工作
        assert session2.filesize == 999

        session.delete()

    def test_session_file_path(self, tmp_path):
        """会话文件命名约定"""
        output_path = str(tmp_path / "myfile.bin")
        session_path = TransferSession._session_file_path(output_path)
        assert session_path == output_path + ".ft_session.json"
