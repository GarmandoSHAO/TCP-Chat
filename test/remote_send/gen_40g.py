#!/usr/bin/env python3
"""
生成 40GB 测试文件

用法:
    python gen_40g.py
    python gen_40g.py D:/test_40g.dat        # 指定输出路径
    python gen_40g.py D:/test_40g.dat -f     # 强制覆盖

输出: test_40g.dat（默认当前目录）
"""
import os
import sys
import hashlib
import time

# 把项目根目录加入 Python 路径
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, _PROJECT_ROOT)


def format_size(size: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} PB"


def main():
    # 解析参数
    args = sys.argv[1:]
    output = "test_40g.dat"
    force = False

    for a in args:
        if a == "-f" or a == "--force":
            force = True
        elif not a.startswith("-"):
            output = a

    # 目标大小：40GB
    target_size = 40 * 1024 * 1024 * 1024  # 40GB

    # 检查已存在
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
    print("  文件传输测试 — 生成 40GB 测试文件")
    print("=" * 55)
    print(f"  输出: {output}")
    print(f"  大小: {format_size(target_size)}")
    print()

    # 生成文件（使用快速重复模式）
    start = time.time()
    block_size = 64 * 1024 * 1024  # 64MB 缓冲区
    pattern = b"REMOTE_FILE_TRANSFER_TEST_PATTERN_2026\n" * 5000000

    written = 0
    with open(output, "wb") as f:
        while written < target_size:
            remaining = target_size - written
            chunk = pattern[:min(remaining, block_size)]
            f.write(chunk)
            written += len(chunk)

            pct = written / target_size * 100
            elapsed = time.time() - start
            speed = written / elapsed / 1024 / 1024 if elapsed > 0 else 0
            eta = (target_size - written) / speed / 60 if speed > 0 else 0
            print(f"\r  进度: {pct:.1f}%  "
                  f"{format_size(written)}/{format_size(target_size)}  "
                  f"{speed:.0f} MB/s  预计剩余: {eta:.0f} 分", end="", flush=True)

    elapsed = time.time() - start
    speed = target_size / elapsed / 1024 / 1024
    print(f"\n\n  完成！")
    print(f"  用时: {elapsed:.1f} 秒 ({speed:.0f} MB/s)")
    print(f"  路径: {os.path.abspath(output)}")

    # 计算 SHA256（仅验证前 100MB 速度）
    print(f"\n  计算 SHA256（需要几秒）...")
    h = hashlib.sha256()
    with open(output, "rb") as f:
        while True:
            data = f.read(64 * 1024 * 1024)
            if not data:
                break
            h.update(data)
    print(f"  SHA256: {h.hexdigest()}")

    print(f"\n  建议发送命令:")
    chunk_mb = 16 if target_size > 10 * 1024**3 else 4
    print(f"    python test/remote_send/send.py {output} -c {chunk_mb}")
    print()


if __name__ == "__main__":
    main()
