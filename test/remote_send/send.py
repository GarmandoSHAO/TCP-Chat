#!/usr/bin/env python3
"""
远程文件发送脚本 —— 通过 bore 隧道将文件暴露到公网

用法:
    python send.py test_40g.dat
    python send.py D:/test_40g.dat -c 16          # 16MB 分块
    python send.py test_500m.dat --local           # 本地直连（不走 bore，速度极快）

步骤（公网模式 -- 默认）:
  1. 启动 bore 隧道，获取公网地址 (bore.pub:XXXXX)
  2. 等待接收方连接
  3. bore.pub 是免费中继，带宽有限（通常 1-5 Mbps）

步骤（本地模式 --local）:
  1. 直接监听本地端口（不走 bore）
  2. 同一台机器用 127.0.0.1:<port> 连接
  3. 速度 = 硬盘读写速度，传 40GB 只需几分钟

建议:
  - 测试协议功能 → 用 bore 模式（默认）
  - 测试大文件速度 → 用 --local 模式
  - 生产环境 → 自建 bore 服务器或直接 TCP
"""
import os
import sys
import socket
import threading
import time

# ── 路径设置 ──────────────────────────────────────────
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, _PROJECT_ROOT)

from tcp_chat.file_transfer.sender import FileSender
from tcp_chat.file_transfer.receiver import FileReceiver


# ── 工具 ──────────────────────────────────────────────

def format_size(size: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} PB"


def progress_callback(**kwargs):
    """发送端进度显示"""
    stage = kwargs.get("stage", "")
    msg = kwargs.get("message", "")
    pct = kwargs.get("percent")

    if stage == "transfer_start":
        print(f"  → 开始传输 {msg}")
    elif stage == "sending":
        if pct is not None:
            bar_w = 25
            fill = int(bar_w * pct / 100)
            bar = "█" * fill + "░" * (bar_w - fill)
            print(f"\r  {bar} {pct:.0f}%  {msg}", end="", flush=True)
    elif stage == "verified":
        print(f"\n  ✓ {msg}")
    elif stage == "done":
        print(f"  ✓ {msg}")
    elif stage == "error":
        print(f"\n  ✗ {msg}", file=sys.stderr)
    elif stage == "connected":
        print(f"\n  ✓ {msg}")
    elif stage == "hashing":
        pct = kwargs.get("sha256_progress")
        if pct is not None:
            print(f"\r  计算文件校验和... {pct:.0f}%", end="", flush=True)
    else:
        if msg:
            print(f"  {msg}")


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def main():
    # ── 解析参数 ──
    args = sys.argv[1:]
    filepath = None
    chunk_size_mb = 4
    use_local = False  # --local 参数
    verbose = False

    i = 0
    while i < len(args):
        a = args[i]
        if a == "-c" and i + 1 < len(args):
            chunk_size_mb = float(args[i + 1])
            i += 2
        elif a == "--local":
            use_local = True
            i += 1
        elif a == "-v" or a == "--verbose":
            verbose = True
            i += 1
        elif a.startswith("-"):
            print(f"未知参数: {a}")
            sys.exit(1)
        else:
            filepath = a
            i += 1

    if not filepath:
        print(__doc__)
        sys.exit(1)

    if not os.path.exists(filepath):
        print(f"错误：文件不存在: {filepath}", file=sys.stderr)
        sys.exit(1)

    filepath = os.path.abspath(filepath)
    filesize = os.path.getsize(filepath)
    chunk_size = int(chunk_size_mb * 1024 * 1024)

    # ── Banner ──
    print()
    print("=" * 58)
    print("  文件传输发送端")
    print("=" * 58)
    print(f"  文件: {os.path.basename(filepath)}")
    print(f"  大小: {format_size(filesize)}")
    print(f"  分块: {chunk_size_mb}MB ({filesize // chunk_size + 1} 块)")
    print()

    # ── 启动发送端 ──
    port = find_free_port()
    sender = FileSender(filepath, chunk_size=chunk_size, port=port)
    sender.progress_callback = progress_callback

    try:
        if use_local:
            print("  模式: 本地直连 (不经过 bore)")
            public_addr = sender.start(use_bore=False)
        else:
            print("  正在启动 bore 隧道...")
            public_addr = sender.start(use_bore=True)
        print()

        # ── 显示连接信息 ──
        print("  ┌──────────────────────────────────────────┐")
        if use_local:
            print(f"  │  本地地址: 127.0.0.1:{sender.port:<20}  │")
        else:
            print(f"  │  公网地址: {public_addr:<30}  │")
        print("  ├──────────────────────────────────────────┤")
        print("  │  接收端连接命令:                          │")
        if use_local:
            recv_cmd = f"  │    python test/remote_receive/receive.py 127.0.0.1:{sender.port}  │"
        else:
            recv_cmd = f"  │    python test/remote_receive/receive.py {public_addr}  │"
        print(recv_cmd)
        print("  └──────────────────────────────────────────┘")
        print()
        print("  等待接收方连接..." if verbose else "  等待接收方连接...")

        # ── 等待 ──
        sender.serve_forever()

    except KeyboardInterrupt:
        print("\n  已停止")
    except Exception as e:
        print(f"\n  错误: {e}", file=sys.stderr)
    finally:
        sender.stop()

    print()


if __name__ == "__main__":
    main()
