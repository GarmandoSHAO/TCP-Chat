#!/usr/bin/env python3
"""
远程文件接收脚本 —— 通过 bore 隧道从公网接收文件

用法:
    python receive.py bore.pub:54321                    # 通过 bore 接收
    python receive.py 127.0.0.1:9000                    # 本地直连
    python receive.py bore.pub:54321 -o D:/downloads    # 指定保存目录
    python receive.py bore.pub:54321 -o D:/downloads -f # 覆盖已有文件

参数:
    address    发送方地址 (host:port)，支持 bore.pub:xxxxx 或 127.0.0.1:xxxx
    -o         文件保存目录（默认 ./received_files/）
    -f         覆盖已存在的文件
"""
import os
import sys
import hashlib
import time

# ── 路径设置 ──────────────────────────────────────────
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, _PROJECT_ROOT)

from tcp_chat.file_transfer.receiver import FileReceiver


# ── 工具 ──────────────────────────────────────────────

def format_size(size: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} PB"


class ProgressDisplay:
    """接收端进度显示"""

    def __init__(self):
        self.start_time = 0
        self.filename = ""
        self.filesize = 0
        self.last_pct = -1

    def callback(self, **kwargs):
        stage = kwargs.get("stage", "")
        msg = kwargs.get("message", "")
        pct = kwargs.get("percent")

        if stage == "file_info":
            self.filename = kwargs.get("filename", "")
            self.filesize = kwargs.get("filesize", 0)
            self.start_time = time.time()
            print(f"  文件: {self.filename}")
            print(f"  大小: {format_size(self.filesize)}")

        elif stage == "resuming":
            print(f"  ↻ {msg}")

        elif stage == "receiving":
            if pct is not None and pct != self.last_pct:
                self.last_pct = pct
                elapsed = time.time() - self.start_time
                # 智能速度单位
                speed_bps = (pct / 100 * self.filesize) / elapsed if elapsed > 0 else 0
                if speed_bps >= 1024 * 1024:
                    speed_str = f"{speed_bps / 1024 / 1024:.1f} MB/s"
                elif speed_bps >= 1024:
                    speed_str = f"{speed_bps / 1024:.1f} KB/s"
                else:
                    speed_str = f"{speed_bps:.0f} B/s"
                done = format_size(int(pct / 100 * self.filesize))
                total = format_size(self.filesize)
                bar_w = 30
                fill = int(bar_w * pct / 100)
                bar = "█" * fill + "░" * (bar_w - fill)
                eta_sec = (100 - pct) / (pct / elapsed) if pct > 0 and elapsed > 0 else 0
                if eta_sec >= 3600:
                    eta_str = f"{eta_sec/3600:.1f}h"
                elif eta_sec >= 60:
                    eta_str = f"{eta_sec/60:.0f}min"
                else:
                    eta_str = f"{eta_sec:.0f}s"
                print(f"\r  {bar} {pct:5.1f}%  {done}/{total}  {speed_str:>12}  ETA: {eta_str}", end="", flush=True)

        elif stage == "verifying":
            print(f"\n  ↻ 验证文件完整性...")

        elif stage == "verified":
            print(f"\n  ✓ {msg}")
            self._print_result(kwargs)

        elif stage == "done":
            elapsed = time.time() - self.start_time
            speed = self.filesize / elapsed / 1024 / 1024 if elapsed > 0 else 0
            out_path = os.path.join(kwargs.get("output_dir", ""), self.filename)
            print(f"  ✓ {msg}")
            print(f"  用时: {elapsed:.0f}s ({speed:.0f} MB/s)")
            print(f"  保存: {out_path}")

        elif stage == "error":
            print(f"\n  ✗ {msg}", file=sys.stderr)

        elif stage == "cancelled":
            print(f"\n  ⚡ {msg}")

        elif stage == "reconnecting":
            print(f"\n  ↻ {msg}")

        else:
            if msg:
                print(f"  {msg}")

    def _print_result(self, kwargs):
        """传输完成后显示汇总信息"""
        elapsed = time.time() - self.start_time
        speed = self.filesize / elapsed / 1024 / 1024 if elapsed > 0 else 0
        print(f"  用时: {elapsed:.0f}s ({speed:.0f} MB/s)")


def main():
    # ── 解析参数 ──
    args = sys.argv[1:]
    address = None
    output_dir = None
    force = False

    i = 0
    while i < len(args):
        a = args[i]
        if a == "-o" and i + 1 < len(args):
            output_dir = args[i + 1]
            i += 2
        elif a == "-f" or a == "--force":
            force = True
            i += 1
        elif a == "-h" or a == "--help":
            print(__doc__)
            return
        elif a.startswith("-"):
            print(f"未知参数: {a}", file=sys.stderr)
            sys.exit(1)
        else:
            address = a
            i += 1

    if not address:
        print(__doc__)
        sys.exit(1)

    # 解析地址
    if ":" not in address:
        print(f"错误：地址格式应为 host:port，例如 bore.pub:54321", file=sys.stderr)
        sys.exit(1)

    host, port_str = address.rsplit(":", 1)
    try:
        port = int(port_str)
    except ValueError:
        print(f"错误：端口格式错误: {port_str}", file=sys.stderr)
        sys.exit(1)

    # 默认输出目录
    if not output_dir:
        output_dir = os.path.join(os.getcwd(), "received_files")
    os.makedirs(output_dir, exist_ok=True)

    # ── Banner ──
    print()
    print("=" * 58)
    print("  文件传输接收端")
    print("=" * 58)
    print(f"  地址: {address}")
    print(f"  保存: {output_dir}")
    print()

    # ── 启动接收端 ──
    display = ProgressDisplay()
    receiver = FileReceiver(output_dir=output_dir, overwrite=force)
    receiver.progress_callback = display.callback

    try:
        success = receiver.receive(host, port)
        if success:
            out_file = os.path.join(output_dir, receiver.filename)
            print(f"\n  ✓ 传输完成！文件已保存到:")
            print(f"    {out_file}")
            print()
        else:
            print(f"\n  ✗ 传输失败\n", file=sys.stderr)
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n  ⚡ 用户中断")
        receiver.cancel()
    except Exception as e:
        print(f"\n  ✗ 错误: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
