"""
文件传输模块 — 基于 bore 隧道的大文件断点续传

本模块与 TCP-Chat 主项目解耦，可独立测试。
核心功能：
  - 超大文件（>10GB）分块传输
  - 位图驱动的断点续传
  - 块级 SHA256 校验 + 自动重传
  - 会话持久化（崩溃恢复）
  - bore 隧道自动管理
"""

from tcp_chat.file_transfer.protocol import (
    MAGIC,
    PROTOCOL_VERSION,
    MSG_FILE_INFO,
    MSG_BITMAP,
    MSG_CHUNK,
    MSG_ACK,
    MSG_NACK,
    MSG_VERIFY,
    MSG_VERIFIED,
    MSG_ERROR,
    MSG_DONE,
    encode_msg,
    decode_header,
    recv_msg,
    recv_msg_with_timeout,
    send_msg,
    build_file_info,
    parse_file_info,
    build_bitmap,
    parse_bitmap,
    build_chunk,
    parse_chunk,
    build_ack,
    build_nack,
    build_verify,
    build_verified,
    build_error,
    build_done,
)

from tcp_chat.file_transfer.bitmap import Bitmap

from tcp_chat.file_transfer.session import TransferSession

from tcp_chat.file_transfer.tunnel import BoreTunnel, find_bore

from tcp_chat.file_transfer.sender import FileSender, DEFAULT_CHUNK_SIZE

from tcp_chat.file_transfer.receiver import FileReceiver

__all__ = [
    # Protocol
    "MAGIC", "PROTOCOL_VERSION",
    "MSG_FILE_INFO", "MSG_BITMAP", "MSG_CHUNK",
    "MSG_ACK", "MSG_NACK",
    "MSG_VERIFY", "MSG_VERIFIED", "MSG_ERROR", "MSG_DONE",
    "encode_msg", "decode_header", "recv_msg", "recv_msg_with_timeout", "send_msg",
    "build_file_info", "parse_file_info",
    "build_bitmap", "parse_bitmap",
    "build_chunk", "parse_chunk",
    "build_ack", "build_nack",
    "build_verify", "build_verified", "build_error", "build_done",
    # Core
    "Bitmap", "TransferSession", "BoreTunnel", "find_bore",
    "FileSender", "FileReceiver",
    "DEFAULT_CHUNK_SIZE",
]
