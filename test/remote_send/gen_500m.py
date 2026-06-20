#!/usr/bin/env python3
"""
生成 500MB 测试文件（快速测试用）

用法:
    python gen_500m.py
    python gen_500m.py D:/test_500m.dat        # 指定路径
    python gen_500m.py D:/test_500m.dat -f     # 强制覆盖

输出: test_500m.dat（默认当前目录）
"""
import os
import sys
import hashlib
import time

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, _PROJECT_ROOT)


def format_size(size: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} PB"


def main():
    args = sys.argv[1:]
    output = "test_500m.dat"
    force = False

    for a in args:
        if a == "-f" or a == "--force":
            force = True
        elif not a.startswith("-"):
            output = a

    target_size = 500 * 1024 * 1024  # 500MB

    if os.path.exists(output):
        if force:
            os.remove(output)
        else:
            print(f"文件已存在: {output}")
            ans = input("覆盖？(y/N): ")
            if ans.lower() != "y":
                print("已取消")
                return
            os.remove(output)

    print("=" * 55)
    print("  文件传输测试 — 生成 500MB 测试文件")
    print("=" * 55)
    print(f"  输出: {output}")
    print(f"  大小: {format_size(target_size)}")
    print()

    start = time.time()
    block = b"x" * (4 * 1024 * 1024)  # 4MB 重复块

    written = 0
    with open(output, "wb") as f:
        while written < target_size:
            remaining = target_size - written
            chunk = block[:min(remaining, len(block))]
            f.write(chunk)
            written += len(chunk)

            pct = written / target_size * 100
            elapsed = time.time() - start
            speed = written / elapsed / 1024 / 1024 if elapsed > 0 else 0
            print(f"\r  进度: {pct:.1f}%  {format_size(written)}  {speed:.0f} MB/s",
                  end="", flush=True)

    elapsed = time.time() - start
    speed = target_size / elapsed / 1024 / 1024
    print(f"\n\n  完成！用时 {elapsed:.1f}s ({speed:.0f} MB/s)")
    print(f"  路径: {os.path.abspath(output)}")

    # SHA256
    h = hashlib.sha256()
    with open(output, "rb") as f:
        while True:
            data = f.read(64 * 1024 * 1024)
            if not data:
                break
            h.update(data)
    print(f"  SHA256: {h.hexdigest()}")

    print(f"\n  建议发送命令:")
    print(f"    python test/remote_send/send.py {output}")
    print()


if __name__ == "__main__":
    main()
