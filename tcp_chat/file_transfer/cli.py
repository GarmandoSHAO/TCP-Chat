#!/usr/bin/env python3
"""
文件传输模块 —— 命令行界面
"""
import argparse
import logging
import os
import sys
import threading
import time
import hashlib

from tcp_chat.file_transfer.sender import FileSender, DEFAULT_CHUNK_SIZE
from tcp_chat.file_transfer.receiver import FileReceiver


def setup_logging(verbose: bool = False):
    level = logging.DEBUG if verbose else logging.INFO
    fmt = "%(asctime)s [%(levelname)s] %(message)s"
    datefmt = "%H:%M:%S"
    logging.basicConfig(level=level, format=fmt, datefmt=datefmt)


def progress_callback(**kwargs):
    stage = kwargs.get("stage", "")
    message = kwargs.get("message", "")
    pct = kwargs.get("percent")

    if stage in ("receiving", "sending"):
        if pct is not None:
            bar_width = 30
            filled = int(bar_width * pct / 100)
            bar = "█" * filled + "░" * (bar_width - filled)
            print(f"\r  {bar} {pct:.1f}%  {message}", end="", flush=True)
        else:
            print(f"\r  {message}", end="", flush=True)
    elif stage == "verified":
        print(f"\n  ✓ {message}")
    elif stage == "done":
        print(f"  ✓ {message}")
    elif stage == "error":
        print(f"\n  ✗ {message}", file=sys.stderr)
    elif stage == "hashing":
        pct = kwargs.get("sha256_progress")
        if pct is not None:
            print(f"\r  计算校验和... {pct:.0f}%", end="", flush=True)
    else:
        print(f"  {message}")


# ── send ──────────────────────────────────────────────

def send_cmd(args):
    setup_logging(args.verbose)

    if not os.path.exists(args.file):
        print(f"错误：文件不存在: {args.file}", file=sys.stderr)
        sys.exit(1)

    chunk_size = int(args.chunk_size * 1024 * 1024)
    sender = FileSender(args.file, chunk_size=chunk_size, port=args.port)
    sender.progress_callback = progress_callback

    try:
        public_addr = sender.start(use_bore=args.bore)
        print(f"\n  ━━━ 文件传输服务器 ━━━")
        print(f"  文件: {sender.filename}")
        print(f"  大小: {sender._format_size(sender.filesize)}")
        print(f"  块数: {sender.total_chunks} (每块 {args.chunk_size}MB)")
        if args.bore:
            print(f"  公网地址: {public_addr}")
        else:
            print(f"  本地地址: {public_addr}")
        print(f"  接收端连接命令:")
        if args.bore:
            print(f"    python -m tcp_chat.file_transfer receive {public_addr} -o D:/downloads")
        else:
            print(f"    python -m tcp_chat.file_transfer receive 127.0.0.1:{sender.port} -o D:/downloads")
        print(f"  等待接收方连接...\n")

        sender.serve_forever()
    except KeyboardInterrupt:
        print("\n  已停止")
        sender.stop()


# ── receive ───────────────────────────────────────────

def receive_cmd(args):
    setup_logging(args.verbose)

    if ":" not in args.address:
        print(f"错误：地址格式应为 host:port，例如 bore.pub:12345", file=sys.stderr)
        sys.exit(1)

    host, port_str = args.address.rsplit(":", 1)
    try:
        port = int(port_str)
    except ValueError:
        print(f"错误：端口格式错误: {port_str}", file=sys.stderr)
        sys.exit(1)

    output_dir = args.output or os.getcwd()
    receiver = FileReceiver(output_dir=output_dir, overwrite=args.force)
    receiver.progress_callback = progress_callback

    try:
        print(f"\n  连接到 {host}:{port} ...")
        success = receiver.receive(host, port)
        if success:
            print(f"\n  文件保存到: {os.path.join(output_dir, receiver.filename)}")
        else:
            print(f"\n  传输失败", file=sys.stderr)
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n  已中断")
        receiver.cancel()


# ── generate ──────────────────────────────────────────

def parse_size(s: str) -> int:
    """解析文件大小字符串，如 10G, 500M, 2T"""
    s = s.strip().upper()
    if s.endswith("T"):
        return int(float(s[:-1]) * 1024 ** 4)
    elif s.endswith("G"):
        return int(float(s[:-1]) * 1024 ** 3)
    elif s.endswith("GB"):
        return int(float(s[:-2]) * 1024 ** 3)
    elif s.endswith("M"):
        return int(float(s[:-1]) * 1024 ** 2)
    elif s.endswith("MB"):
        return int(float(s[:-2]) * 1024 ** 2)
    elif s.endswith("K"):
        return int(float(s[:-1]) * 1024)
    elif s.endswith("KB"):
        return int(float(s[:-2]) * 1024)
    else:
        return int(s)


def generate_cmd(args):
    """生成测试文件"""
    size = parse_size(args.size)
    if size <= 0:
        print("错误：文件大小必须大于 0", file=sys.stderr)
        sys.exit(1)

    output_path = args.output
    if os.path.exists(output_path):
        if not args.force:
            print(f"错误：文件已存在: {output_path} （使用 -f 覆盖）", file=sys.stderr)
            sys.exit(1)
        os.remove(output_path)

    print(f"\n  生成测试文件: {output_path}")
    print(f"  目标大小: {format_size(size)}")
    print(f"  写入中... (使用快速模式，不生成随机数据)")

    start = time.time()
    block_size = 64 * 1024 * 1024  # 64MB 缓冲区
    pattern = b"FILE_TRANSFER_TEST_PATTERN_0123456789_ABCDEFGHIJ\n" * 1000000

    written = 0
    with open(output_path, "wb") as f:
        while written < size:
            remaining = size - written
            chunk = pattern[:min(remaining, len(pattern), block_size)]
            f.write(chunk)
            written += len(chunk)
            pct = written / size * 100
            elapsed = time.time() - start
            speed = written / elapsed / 1024 / 1024 if elapsed > 0 else 0
            print(f"\r  进度: {pct:.1f}%  ({format_size(written)}/{format_size(size)})  {speed:.0f} MB/s", end="", flush=True)

    elapsed = time.time() - start
    speed = size / elapsed / 1024 / 1024 if elapsed > 0 else 0
    actual_size = os.path.getsize(output_path)
    sha256 = compute_sha256(output_path)
    print(f"\n  完成！用时 {elapsed:.1f}s ({speed:.0f} MB/s)")
    print(f"  实际大小: {format_size(actual_size)}")
    print(f"  SHA256: {sha256}")
    print(f"  发送命令:")
    chunk_mb = args.chunk or 4
    print(f"    python -m tcp_chat.file_transfer.cli send {output_path} -c {chunk_mb}")


def compute_sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            data = f.read(64 * 1024 * 1024)
            if not data:
                break
            h.update(data)
    return h.hexdigest()


# ── selftest ──────────────────────────────────────────

def selftest_cmd(args):
    """
    本地自测：在同一台机器上运行发送端和接收端，
    验证文件传输完整性。
    """
    import tempfile
    import socket

    test_size = parse_size(args.size)
    chunk_size = int(args.chunk * 1024 * 1024)

    print(f"\n  ━━━ 自测模式 ━━━")
    print(f"  测试文件大小: {format_size(test_size)}")
    print(f"  分块大小: {args.chunk}MB")
    print()

    # 创建临时目录
    tmp = tempfile.mkdtemp(prefix="ft_selftest_")
    src = os.path.join(tmp, "source.bin")
    dst_dir = os.path.join(tmp, "received")
    os.makedirs(dst_dir, exist_ok=True)

    try:
        # 1. 生成测试文件
        print(f"  [1/4] 生成测试文件...")
        block = b"x" * min(test_size, 4 * 1024 * 1024)
        with open(src, "wb") as f:
            remaining = test_size
            while remaining > 0:
                chunk = block[:min(remaining, len(block))]
                f.write(chunk)
                remaining -= len(chunk)

        actual_size = os.path.getsize(src)
        print(f"        大小: {format_size(actual_size)}")

        # 2. 找可用端口
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
        s.close()

        # 3. 启动发送端
        print(f"  [2/4] 启动发送端 (端口 {port})...")
        sender = FileSender(src, chunk_size=chunk_size, port=port)
        sender.start(use_bore=False)
        t = threading.Thread(target=sender.serve_forever, daemon=True)
        t.start()
        time.sleep(0.3)

        # 4. 接收端接收
        print(f"  [3/4] 启动接收端...")
        results = {}

        def capture_progress(**kwargs):
            stage = kwargs.get("stage")
            if stage == "receiving":
                pct = kwargs.get("percent", 0)
                print(f"\r        接收进度: {pct:.1f}%", end="", flush=True)
            elif stage == "verified":
                results["verified"] = True
            elif stage == "error":
                results["error"] = kwargs.get("message", "")
            elif stage == "done":
                results["done"] = True

        receiver = FileReceiver(output_dir=dst_dir, overwrite=True)
        receiver.progress_callback = capture_progress
        success = receiver.receive("127.0.0.1", port)
        sender.stop()

        print()

        if not success:
            print(f"  [失败] 传输返回失败")
            if "error" in results:
                print(f"         错误: {results['error']}")
            sys.exit(1)

        # 5. 验证
        print(f"  [4/4] 验证文件完整性...")
        dst_file = os.path.join(dst_dir, "source.bin")

        if not os.path.exists(dst_file):
            print(f"  [失败] 接收到的文件不存在")
            sys.exit(1)

        dst_size = os.path.getsize(dst_file)
        if dst_size != actual_size:
            print(f"  [失败] 大小不匹配: 源 {actual_size} ≠ 接收 {dst_size}")
            sys.exit(1)

        print(f"  接收到的文件: {format_size(dst_size)}")
        print(f"  校验 SHA256...")

        src_sha = compute_sha256(src)
        dst_sha = compute_sha256(dst_file)

        if src_sha == dst_sha:
            print(f"  SHA256: 一致 ✓")
            print(f"\n  ✓ 自测通过！文件传输完整性验证成功。")
        else:
            print(f"  SHA256: 不匹配 ✗")
            print(f"    源: {src_sha}")
            print(f"    接收: {dst_sha}")
            sys.exit(1)

    finally:
        # 清理临时文件
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)
        if not args.keep:
            print(f"  临时文件已清理")


# ── 工具 ──────────────────────────────────────────────

def format_size(size: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} PB"


def main():
    parser = argparse.ArgumentParser(
        description="文件传输模块 —— 基于 bore 隧道的大文件断点续传",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 生成 10GB 测试文件
  %(prog)s generate testfile.dat --size 10G

  # 发送（局域网测试）
  %(prog)s send testfile.dat --port 9000

  # 发送（公网，需要 bore.exe）
  %(prog)s send testfile.dat --bore

  # 接收
  %(prog)s receive bore.pub:12345 --output D:/downloads

  # 本地自测（快速验证）
  %(prog)s selftest --size 100M

  # 本地自测（大数据量）
  %(prog)s selftest --size 5G --chunk 16
        """,
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="详细日志输出")

    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # send
    send_p = subparsers.add_parser("send", help="发送文件")
    send_p.add_argument("file", help="要发送的文件路径")
    send_p.add_argument("-p", "--port", type=int, default=0, help="本地监听端口（默认自动分配）")
    send_p.add_argument("--bore", action="store_true", help="通过 bore 隧道暴露到公网")
    send_p.add_argument("-c", "--chunk-size", type=float, default=4, help="分块大小（MB），默认 4MB")

    # receive
    recv_p = subparsers.add_parser("receive", help="接收文件")
    recv_p.add_argument("address", help="发送方地址（host:port）")
    recv_p.add_argument("-o", "--output", help="文件保存目录（默认当前目录）")
    recv_p.add_argument("-f", "--force", action="store_true", help="覆盖已存在的文件")

    # generate
    gen_p = subparsers.add_parser("generate", help="生成测试文件")
    gen_p.add_argument("output", help="输出文件路径")
    gen_p.add_argument("-s", "--size", default="1G", help="文件大小，如 10G、500M、2T（默认 1G）")
    gen_p.add_argument("-c", "--chunk", type=float, default=4, help="推荐分块大小（MB），用于提示发送命令")
    gen_p.add_argument("-f", "--force", action="store_true", help="覆盖已存在的文件")

    # selftest
    test_p = subparsers.add_parser("selftest", help="本地自测（发送+接收+校验）")
    test_p.add_argument("-s", "--size", default="500M", help="测试文件大小（默认 500M）")
    test_p.add_argument("-c", "--chunk", type=float, default=4, help="分块大小 MB（默认 4）")
    test_p.add_argument("--keep", action="store_true", help="保留临时文件（调试用）")

    args = parser.parse_args()

    if args.command == "send":
        send_cmd(args)
    elif args.command == "receive":
        receive_cmd(args)
    elif args.command == "generate":
        generate_cmd(args)
    elif args.command == "selftest":
        selftest_cmd(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
