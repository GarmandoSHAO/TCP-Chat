#!/usr/bin/env python3
"""
本地模拟远程传输 —— 完整走 bore 隧道协议，不限速

在同一台机器上模拟真实验远程传输：
  1. 启动 bore server（本地中继）
  2. 启动 bore local 暴露发送端端口
  3. 启动发送端
  4. 用户在另一个终端启动接收端

数据路径:
  send.py → :9000 → bore local → bore server → receive.py
                    ↓                        ↓
              走 bore 隧道协议          走 bore 隧道协议
              但全部 localhost          不经过公网

用法:
    python remote_sim.py                               # 用 test_500m.dat
    python remote_sim.py D:/test_40g.dat -c 16         # 40GB, 16MB分块
    python remote_sim.py D:/test_40g.dat -c 16 --port 9000  # 指定端口

接收端（另一个终端）:
    python ../remote_receive/receive.py 127.0.0.1:<隧道端口>
"""
import os
import sys
import subprocess
import time
import re
import socket
import threading

# ── 路径 ──────────────────────────────────────────────
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, _PROJECT_ROOT)
BORE_EXE = os.path.join(_PROJECT_ROOT, "bore.exe")


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def format_size(size: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} PB"


def main():
    args = sys.argv[1:]
    filepath = None
    chunk_mb = 4
    sender_port = find_free_port()
    control_port = find_free_port()

    i = 0
    while i < len(args):
        a = args[i]
        if a == "-c" and i + 1 < len(args):
            chunk_mb = float(args[i + 1])
            i += 2
        elif a == "--port" and i + 1 < len(args):
            sender_port = int(args[i + 1])
            i += 2
        elif not a.startswith("-"):
            filepath = a
            i += 1
        else:
            print(f"未知参数: {a}")
            sys.exit(1)

    if not filepath:
        for name in ["test_40g.dat", "test_500m.dat"]:
            p = os.path.join(os.path.dirname(__file__), name)
            if os.path.exists(p):
                filepath = p
                break
    if not filepath or not os.path.exists(filepath):
        print("错误：请指定文件路径或先用 gen_500m.py/gen_40g.py 生成测试文件")
        sys.exit(1)

    filesize = os.path.getsize(filepath)

    print()
    print("=" * 62)
    print("  远程传输模拟（本地 bore 中继，不限速）")
    print("=" * 62)
    print(f"  文件: {os.path.basename(filepath)}")
    print(f"  大小: {format_size(filesize)}")
    print(f"  分块: {chunk_mb}MB")
    print()

    processes = []

    try:
        # ── 1. 启动 bore server ──────────────────────
        # bore server 默认监听端口 7835，输出重定向到 DEVNULL 避免 pipe 阻塞
        print(f"  [1/3] 启动 bore server (默认端口 7835)...")
        server_proc = subprocess.Popen(
            [BORE_EXE, "server", "--bind-addr", "127.0.0.1"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        processes.append(("bore server", server_proc))
        time.sleep(1)

        if server_proc.poll() is not None:
            raise RuntimeError("bore server 启动失败（端口 7835 可能被占用）")
        print(f"  ✓ bore server (PID {server_proc.pid})")
        print()

        # ── 2. 启动 bore local 隧道 ──────────────────
        print(f"  [2/3] 启动 bore local (暴露 :{sender_port})...")
        # bore local 默认连接服务器 127.0.0.1:7835
        local_proc = subprocess.Popen(
            [BORE_EXE, "local", str(sender_port), "--to", "127.0.0.1"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        processes.append(("bore local", local_proc))

        # 从 stdout 解析隧道端口
        # bore 0.6.0 输出: "listening at 127.0.0.1:24083"
        tunnel_port = None
        deadline = time.time() + 10
        while time.time() < deadline:
            if local_proc.poll() is not None:
                break
            line = local_proc.stdout.readline()
            if line:
                text = line.decode("utf-8", errors="replace").strip()
                print(f"    {text}")
                # bore 0.6.0 输出格式: "listening at 127.0.0.1:24083"
                m = re.search(r"listening at\s+(\S+):(\d+)", text)
                if m:
                    tunnel_port = int(m.group(2))
                    break

        if tunnel_port is None:
            raise RuntimeError("bore local 未能在 10 秒内获取隧道端口")

        print(f"  ✓ 隧道端口: {tunnel_port}")
        print()

        # ── 3. 启动发送端 ────────────────────────────
        print(f"  [3/3] 启动发送端...")
        chunk_bytes = int(chunk_mb * 1024 * 1024)

        from tcp_chat.file_transfer.sender import FileSender

        sender = FileSender(filepath, chunk_size=chunk_bytes, port=sender_port)
        sender.start(use_bore=False)  # 不走 bore（bore local 已经处理了隧道层）

        t = threading.Thread(target=sender.serve_forever, daemon=True)
        t.start()
        time.sleep(0.3)

        print(f"  ✓ 发送端就绪")
        print()

        # ── 显示连接信息 ─────────────────────────────
        print("  ┌──────────────────────────────────────────────┐")
        print(f"  │  隧道地址（公网模拟）: 127.0.0.1:{tunnel_port:<16}  │")
        print("  ├──────────────────────────────────────────────┤")
        print("  │  接收端命令（另一个终端）:                     │")
        print(f"  │    python test/remote_receive/receive.py     │")
        print(f"  │      127.0.0.1:{tunnel_port}                   │")
        print("  ├──────────────────────────────────────────────┤")
        print("  │  数据路径:                                    │")
        print("  │    发送端 → :{:<5} → bore local              │".format(sender_port))
        print("  │           → bore server → 接收端              │")
        print("  │    全部走 localhost，不限速！                  │")
        print("  └──────────────────────────────────────────────┘")
        print()
        print("  按 Ctrl+C 停止所有进程")
        print()

        # 等待发送端运行
        while sender._server_sock and not sender._stop_event.is_set():
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n  用户中断")
    except Exception as e:
        print(f"\n  错误: {e}", file=sys.stderr)
    finally:
        print("\n  清理进程...")
        for name, proc in processes:
            try:
                proc.terminate()
                proc.wait(timeout=3)
                print(f"  ✓ {name} 已停止")
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass

    print()


if __name__ == "__main__":
    main()
