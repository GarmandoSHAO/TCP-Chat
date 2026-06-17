"""
☆ 网络聊天室 — 客户端 ☆
基于 TCP Socket 的聊天室客户端
支持群聊、私聊、在线用户列表
"""

import socket
import threading
import os


# ========== 配置 ==========
SERVER_HOST = "127.0.0.1"   # 服务端 IP（本机测试用）
SERVER_PORT = 8888           # 服务端端口


def clear_input_line():
    """清空当前输入行（让消息完整显示而不重叠）"""
    print(f"\r{'':50s}\r", end="", flush=True)


def receive_messages(sock: socket.socket):
    """后台线程：持续接收服务端消息并打印"""
    while True:
        try:
            data = sock.recv(4096)
            if not data:
                clear_input_line()
                print("[连接已断开]")
                break
            msg = data.decode("utf-8")
            clear_input_line()
            print(msg, end="", flush=True)
            print(">>> ", end="", flush=True)
        except (ConnectionResetError, ConnectionAbortedError, OSError):
            clear_input_line()
            print("[连接已断开]")
            break


def start_client():
    """启动客户端"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    try:
        sock.connect((SERVER_HOST, SERVER_PORT))
    except ConnectionRefusedError:
        print(f"❌ 无法连接到服务器 {SERVER_HOST}:{SERVER_PORT}")
        print("   请确认服务端已启动")
        return

    print(f"✅ 已连接到聊天室 {SERVER_HOST}:{SERVER_PORT}")

    # ---- 登录：主线程收发，避免线程竞争 ----
    data = sock.recv(1024)
    print(data.decode("utf-8"), end="")
    nickname = input().strip()
    sock.sendall(nickname.encode("utf-8"))

    # 接收登录结果
    data = sock.recv(4096)
    print(data.decode("utf-8"), end="")

    # ---- 登录完成，启动接收线程 ----
    recv_thread = threading.Thread(target=receive_messages, args=(sock,), daemon=True)
    recv_thread.start()

    # ---- 主循环：发送消息 ----
    try:
        while True:
            user_input = input(">>> ")
            if not user_input:
                continue
            sock.sendall(user_input.encode("utf-8"))
            if user_input.strip().lower() in ("/quit", "/exit"):
                break
    except (KeyboardInterrupt, EOFError):
        print("\n👋 正在退出...")
        try:
            sock.sendall("/quit".encode("utf-8"))
        except:
            pass
    finally:
        sock.close()


if __name__ == "__main__":
    start_client()
