"""
文件传输二进制协议

帧结构（8 字节定长头部 + 可变长度负载）:
┌──────────┬──────────┬──────────┬──────────────────┐
│ Magic    │ Version  │ Type     │ Payload Length   │
│ 2 bytes  │ 1 byte   │ 1 byte   │ 4 bytes (BE)     │
│ 0xF1 0xBE│ 0x01     │          │                  │
└──────────┴──────────┴──────────┴──────────────────┘
+ 负载（Payload Length 字节）

消息类型:
  1 FILE_INFO  — 文件元信息 (JSON)
  2 BITMAP     — 接收方已接收块位图 (bytes)
  3 CHUNK      — 数据块 [块索引:4B][SHA256:32B][数据]
  4 ACK        — 确认收到某块 [块索引:4B]
  5 NACK       — 块校验失败 [块索引:4B]
  6 VERIFY     — 发送方请求最终校验 (无负载)
  7 VERIFIED   — 最终文件校验通过 [文件SHA256:32B]
  8 ERROR      — 错误信息 (UTF-8)
  9 DONE       — 传输结束 (无负载)
"""

import json
import struct
import socket
import select
from typing import Optional, Tuple

# ── 协议常量 ──────────────────────────────────────────

MAGIC = b"\xF1\xBE"
PROTOCOL_VERSION = 1

MSG_FILE_INFO = 1
MSG_BITMAP = 2
MSG_CHUNK = 3
MSG_ACK = 4
MSG_NACK = 5
MSG_VERIFY = 6
MSG_VERIFIED = 7
MSG_ERROR = 8
MSG_DONE = 9

HEADER_FORMAT = "!2s B B I"  # magic(2) + version(1) + type(1) + length(4)
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)  # 8 bytes

CHUNK_INDEX_FORMAT = "!I"          # 4 bytes
CHUNK_INDEX_SIZE = struct.calcsize(CHUNK_INDEX_FORMAT)
SHA256_SIZE = 32                   # bytes
CHUNK_HEADER_SIZE = CHUNK_INDEX_SIZE + SHA256_SIZE  # 36 bytes

# 默认的 socket 接收超时（秒）
DEFAULT_RECV_TIMEOUT = 30
# 块传输 ACK 等待超时（秒）
ACK_TIMEOUT = 60


# ── 编解码核心 ──────────────────────────────────────

def encode_msg(msg_type: int, payload: bytes = b"") -> bytes:
    """将消息编码为二进制帧"""
    header = struct.pack(HEADER_FORMAT, MAGIC, PROTOCOL_VERSION, msg_type, len(payload))
    return header + payload


def decode_header(data: bytes) -> Optional[Tuple[int, int]]:
    """从字节流中解析头部，返回 (msg_type, payload_length) 或 None"""
    if len(data) < HEADER_SIZE:
        return None
    magic, version, msg_type, payload_len = struct.unpack(HEADER_FORMAT, data[:HEADER_SIZE])
    if magic != MAGIC:
        return None
    if version != PROTOCOL_VERSION:
        return None
    return msg_type, payload_len


def recv_exact(sock: socket.socket, n: int) -> bytes:
    """精确读取 n 字节，遇到 EOF 抛出 ConnectionError"""
    data = bytearray()
    while len(data) < n:
        chunk = sock.recv(n - len(data))
        if not chunk:
            raise ConnectionError("Connection closed by remote peer")
        data.extend(chunk)
    return bytes(data)


def send_msg(sock: socket.socket, data: bytes) -> None:
    """确保完整发送所有数据"""
    total_sent = 0
    while total_sent < len(data):
        sent = sock.send(data[total_sent:])
        if sent == 0:
            raise ConnectionError("Socket send failed (sent 0 bytes)")
        total_sent += sent


def recv_msg(sock: socket.socket) -> Tuple[int, bytes]:
    """阻塞接收一条完整消息，返回 (msg_type, payload)"""
    header = recv_exact(sock, HEADER_SIZE)
    msg_type, payload_len = decode_header(header)
    if msg_type is None:
        raise ValueError(f"Invalid protocol header: {header[:4]!r}")
    payload = recv_exact(sock, payload_len) if payload_len > 0 else b""
    return msg_type, payload


def recv_msg_with_timeout(sock: socket.socket, timeout: float = ACK_TIMEOUT) -> Optional[Tuple[int, bytes]]:
    """
    带超时的消息接收。
    返回 (msg_type, payload) 或 None（超时）。
    """
    sock.settimeout(timeout)
    try:
        return recv_msg(sock)
    except socket.timeout:
        return None
    except OSError:
        return None
    finally:
        sock.settimeout(None)  # 恢复阻塞模式


# ── 各消息类型的构建/解析 ──────────────────────────

def build_file_info(
    filename: str, filesize: int,
    chunk_size: int, total_chunks: int,
    file_sha256: str,
) -> bytes:
    """构建 FILE_INFO 消息（JSON 负载）"""
    info = {
        "filename": filename,
        "filesize": filesize,
        "chunk_size": chunk_size,
        "total_chunks": total_chunks,
        "file_sha256": file_sha256,
        "version": 1,
        "protocol": "ft1",
    }
    return encode_msg(MSG_FILE_INFO, json.dumps(info, ensure_ascii=False).encode("utf-8"))


def parse_file_info(payload: bytes) -> dict:
    """解析 FILE_INFO 负载"""
    return json.loads(payload.decode("utf-8"))


def build_bitmap(bitmap_bytes: bytes) -> bytes:
    """构建 BITMAP 消息"""
    return encode_msg(MSG_BITMAP, bitmap_bytes)


def parse_bitmap(payload: bytes) -> bytes:
    """解析 BITMAP 负载，直接返回原始字节"""
    return payload


def build_chunk(index: int, sha256_digest: bytes, data: bytes) -> bytes:
    """
    构建 CHUNK 消息。
    index: 块索引（从 0 开始）
    sha256_digest: 32 字节 SHA256 摘要
    data: 块数据（可变长度，通常为 chunk_size 或更少）
    """
    payload = struct.pack(CHUNK_INDEX_FORMAT, index) + sha256_digest + data
    return encode_msg(MSG_CHUNK, payload)


def parse_chunk(payload: bytes) -> Tuple[int, bytes, bytes]:
    """解析 CHUNK 负载，返回 (index, sha256_digest, data)"""
    index = struct.unpack(CHUNK_INDEX_FORMAT, payload[:CHUNK_INDEX_SIZE])[0]
    sha256_digest = payload[CHUNK_INDEX_SIZE:CHUNK_INDEX_SIZE + SHA256_SIZE]
    data = payload[CHUNK_INDEX_SIZE + SHA256_SIZE:]
    return index, sha256_digest, data


def build_ack(index: int) -> bytes:
    """构建 ACK 消息"""
    return encode_msg(MSG_ACK, struct.pack(CHUNK_INDEX_FORMAT, index))


def build_nack(index: int) -> bytes:
    """构建 NACK 消息"""
    return encode_msg(MSG_NACK, struct.pack(CHUNK_INDEX_FORMAT, index))


def parse_index(payload: bytes) -> int:
    """解析 ACK/NACK 负载中的块索引"""
    return struct.unpack(CHUNK_INDEX_FORMAT, payload)[0]


def build_verify() -> bytes:
    """构建 VERIFY 消息"""
    return encode_msg(MSG_VERIFY)


def build_verified(file_sha256: bytes) -> bytes:
    """构建 VERIFIED 消息（文件级 SHA256）"""
    return encode_msg(MSG_VERIFIED, file_sha256)


def parse_verified(payload: bytes) -> bytes:
    """解析 VERIFIED 负载，返回 32 字节 SHA256"""
    return payload


def build_error(message: str) -> bytes:
    """构建 ERROR 消息"""
    return encode_msg(MSG_ERROR, message.encode("utf-8"))


def parse_error(payload: bytes) -> str:
    """解析 ERROR 负载"""
    return payload.decode("utf-8")


def build_done() -> bytes:
    """构建 DONE 消息"""
    return encode_msg(MSG_DONE)


# ── 工具函数 ──────────────────────────────────────────

def compute_file_sha256(filepath: str, chunk_size: int = 64 * 1024 * 1024,
                        progress_callback=None) -> str:
    """
    计算文件的 SHA256 摘要（16 进制字符串）。
    chunk_size 控制读取缓冲区大小（默认 64MB），不影响协议分块。
    """
    import hashlib
    import os

    h = hashlib.sha256()
    total = os.path.getsize(filepath)
    processed = 0

    with open(filepath, "rb") as f:
        while True:
            data = f.read(chunk_size)
            if not data:
                break
            h.update(data)
            processed += len(data)
            if progress_callback:
                progress_callback(processed, total)

    return h.hexdigest()
