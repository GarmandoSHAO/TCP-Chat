"""
协议编解码单元测试 —— 覆盖所有消息类型的构建和解析
"""
import pytest
from tcp_chat.file_transfer.protocol import (
    MAGIC, PROTOCOL_VERSION,
    MSG_FILE_INFO, MSG_BITMAP, MSG_CHUNK,
    MSG_ACK, MSG_NACK, MSG_VERIFY, MSG_VERIFIED,
    MSG_ERROR, MSG_DONE,
    HEADER_SIZE,
    encode_msg, decode_header,
    build_file_info, parse_file_info,
    build_bitmap, parse_bitmap,
    build_chunk, parse_chunk,
    build_ack, build_nack, parse_index,
    build_verify, build_verified, parse_verified,
    build_error, parse_error,
    build_done,
    compute_file_sha256,
)
import hashlib
import struct


class TestFrameEncoding:
    """帧编码测试"""

    def test_encode_decode_header(self):
        """编码和解码头部"""
        data = encode_msg(MSG_FILE_INFO, b"hello")
        msg_type, payload_len = decode_header(data)
        assert msg_type == MSG_FILE_INFO
        assert payload_len == 5

    def test_encode_empty_payload(self):
        """空负载编码"""
        data = encode_msg(MSG_DONE)
        msg_type, payload_len = decode_header(data)
        assert msg_type == MSG_DONE
        assert payload_len == 0

    def test_header_size(self):
        """头部固定 8 字节"""
        data = encode_msg(MSG_VERIFY)
        assert len(data) == HEADER_SIZE
        assert HEADER_SIZE == 8

    def test_large_payload(self):
        """大负载（模拟 4MB 块）"""
        payload = b"x" * (4 * 1024 * 1024)
        data = encode_msg(MSG_CHUNK, payload)
        msg_type, payload_len = decode_header(data)
        assert msg_type == MSG_CHUNK
        assert payload_len == len(payload)
        assert len(data) == HEADER_SIZE + len(payload)

    def test_invalid_magic(self):
        """无效魔数"""
        data = b"\x00\x00" + struct.pack("!B B I", PROTOCOL_VERSION, MSG_FILE_INFO, 0)
        result = decode_header(data)
        assert result is None

    def test_invalid_version(self):
        """无效版本号"""
        data = MAGIC + struct.pack("!B B I", 99, MSG_FILE_INFO, 0)
        result = decode_header(data)
        assert result is None

    def test_short_data(self):
        """头部数据不足"""
        result = decode_header(b"\xF1\xBE")
        assert result is None


class TestFileInfo:
    """FILE_INFO 消息测试"""

    def test_build_parse(self):
        """构建和解析"""
        data = build_file_info(
            filename="test.iso",
            filesize=1073741824,
            chunk_size=4194304,
            total_chunks=256,
            file_sha256="abc123",
        )
        msg_type, payload_len = decode_header(data)
        assert msg_type == MSG_FILE_INFO

        info = parse_file_info(data[HEADER_SIZE:])
        assert info["filename"] == "test.iso"
        assert info["filesize"] == 1073741824
        assert info["chunk_size"] == 4194304
        assert info["total_chunks"] == 256
        assert info["file_sha256"] == "abc123"
        assert info["version"] == 1
        assert info["protocol"] == "ft1"

    def test_unicode_filename(self):
        """Unicode 文件名"""
        data = build_file_info(
            filename="😊测试文件.zip",
            filesize=1024,
            chunk_size=4096,
            total_chunks=1,
            file_sha256="",
        )
        info = parse_file_info(data[HEADER_SIZE:])
        assert info["filename"] == "😊测试文件.zip"


class TestChunk:
    """CHUNK 消息测试"""

    def test_build_parse(self):
        """构建和解析"""
        index = 42
        chunk_data = b"hello world this is chunk data"
        sha256_digest = hashlib.sha256(chunk_data).digest()

        data = build_chunk(index, sha256_digest, chunk_data)
        msg_type, _ = decode_header(data)
        assert msg_type == MSG_CHUNK

        parsed_idx, parsed_hash, parsed_data = parse_chunk(data[HEADER_SIZE:])
        assert parsed_idx == index
        assert parsed_hash == sha256_digest
        assert parsed_data == chunk_data

    def test_empty_chunk(self):
        """空块"""
        index = 0
        sha256_digest = hashlib.sha256(b"").digest()
        data = build_chunk(index, sha256_digest, b"")
        parsed_idx, parsed_hash, parsed_data = parse_chunk(data[HEADER_SIZE:])
        assert parsed_idx == 0
        assert parsed_hash == sha256_digest
        assert parsed_data == b""

    def test_large_chunk(self):
        """大块（4MB）"""
        index = 255
        chunk_data = b"x" * (4 * 1024 * 1024)
        sha256_digest = hashlib.sha256(chunk_data).digest()

        data = build_chunk(index, sha256_digest, chunk_data)
        parsed_idx, parsed_hash, parsed_data = parse_chunk(data[HEADER_SIZE:])
        assert parsed_idx == 255
        assert parsed_hash == sha256_digest
        assert parsed_data == chunk_data


class TestAckNack:
    """ACK/NACK 消息测试"""

    def test_ack(self):
        data = build_ack(42)
        msg_type, _ = decode_header(data)
        assert msg_type == MSG_ACK
        idx = parse_index(data[HEADER_SIZE:])
        assert idx == 42

    def test_nack(self):
        data = build_nack(99)
        msg_type, _ = decode_header(data)
        assert msg_type == MSG_NACK
        idx = parse_index(data[HEADER_SIZE:])
        assert idx == 99

    def test_ack_max_index(self):
        """最大索引（2^32 - 1）"""
        data = build_ack(4294967295)
        idx = parse_index(data[HEADER_SIZE:])
        assert idx == 4294967295


class TestVerify:
    """VERIFY/VERIFIED 消息测试"""

    def test_verify(self):
        data = build_verify()
        msg_type, payload_len = decode_header(data)
        assert msg_type == MSG_VERIFY
        assert payload_len == 0
        assert len(data) == HEADER_SIZE

    def test_verified(self):
        file_hash = bytes.fromhex("a" * 64)
        data = build_verified(file_hash)
        msg_type, _ = decode_header(data)
        assert msg_type == MSG_VERIFIED
        parsed_hash = parse_verified(data[HEADER_SIZE:])
        assert parsed_hash == file_hash
        assert len(parsed_hash) == 32


class TestError:
    """ERROR 消息测试"""

    def test_error(self):
        msg = "SHA256 mismatch"
        data = build_error(msg)
        msg_type, _ = decode_header(data)
        assert msg_type == MSG_ERROR
        parsed_msg = parse_error(data[HEADER_SIZE:])
        assert parsed_msg == msg

    def test_error_unicode(self):
        msg = "传输错误：文件不匹配"
        data = build_error(msg)
        parsed_msg = parse_error(data[HEADER_SIZE:])
        assert parsed_msg == msg


class TestDone:
    """DONE 消息测试"""

    def test_done(self):
        data = build_done()
        msg_type, payload_len = decode_header(data)
        assert msg_type == MSG_DONE
        assert payload_len == 0


class TestSha256:
    """SHA256 计算测试"""

    def test_compute_small_file(self, tmp_path):
        """计算小文件 SHA256"""
        f = tmp_path / "test.bin"
        f.write_bytes(b"hello world" * 1000)
        sha256 = compute_file_sha256(str(f))
        assert len(sha256) == 64  # 16 进制字符串
        assert sha256 == hashlib.sha256(b"hello world" * 1000).hexdigest()

    def test_compute_large_file(self, tmp_path):
        """计算略大的文件（多块读取）"""
        data = b"test data pattern " * 100000  # ~1.8MB
        f = tmp_path / "large.bin"
        f.write_bytes(data)

        # 用小缓冲区强制多块读取
        sha256 = compute_file_sha256(str(f), chunk_size=65536)
        assert sha256 == hashlib.sha256(data).hexdigest()

    def test_compute_empty_file(self, tmp_path):
        """空文件"""
        f = tmp_path / "empty.bin"
        f.write_text("")
        sha256 = compute_file_sha256(str(f))
        assert sha256 == hashlib.sha256(b"").hexdigest()

    def test_compute_with_progress(self, tmp_path):
        """带进度回调"""
        data = b"x" * 100000
        f = tmp_path / "progress.bin"
        f.write_bytes(data)

        progress_values = []
        def cb(processed, total):
            progress_values.append(processed)

        sha256 = compute_file_sha256(str(f), progress_callback=cb)
        assert len(progress_values) > 0
        assert progress_values[-1] == len(data)
