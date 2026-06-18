"""
☆ 网络聊天室 — 客户端 ☆
基于 TCP Socket 的聊天室客户端
支持群聊、私聊、在线用户列表
支持局域网自动发现房间
"""

import socket
import threading
import time
import sys

# ========== 配置 ==========
DISCOVERY_PORT = 9999              # UDP 广播发现端口
TCP_PORT = 8888                     # TCP 连接端口


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


def discover_rooms(timeout=5):
    """通过 UDP 广播发现局域网内的聊天室"""
    print("\n🔍 正在扫描局域网内的聊天室...\n")

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind(("0.0.0.0", DISCOVERY_PORT))
    except OSError:
        return {}

    sock.settimeout(timeout)

    rooms = {}  # {ip: (room_name, port)}
    start_time = time.time()

    try:
        while True:
            # 检查总耗时是否已超时（不能只靠 settimeout，因为广播持续到达会不断重置超时）
            elapsed = time.time() - start_time
            if elapsed >= timeout:
                break

            # 动态缩短 timeout，保证总耗时不超过设定值
            remaining = timeout - elapsed
            sock.settimeout(remaining)

            try:
                data, addr = sock.recvfrom(1024)
                message = data.decode("utf-8")

                # 解析房间信息格式: CHAT_ROOM|房间名|IP|端口
                if message.startswith("CHAT_ROOM|"):
                    parts = message.split("|")
                    if len(parts) == 4:
                        _, room_name, ip, port = parts
                        rooms[ip] = (room_name, int(port))
            except socket.timeout:
                break
            except Exception:
                break
    finally:
        sock.close()

    return rooms


def display_rooms(rooms):
    """显示发现的房间列表"""
    if not rooms:
        print("❌ 未发现任何房间")
        return None
    
    print("=" * 50)
    print("📍 发现以下房间：")
    print("=" * 50)
    
    room_list = list(rooms.items())
    for idx, (ip, (room_name, port)) in enumerate(room_list, 1):
        print(f"{idx}. {room_name:20s} [{ip}:{port}]")
    
    print("=" * 50)
    print(f"请输入房间号加入（1-{len(room_list)}），或按 Enter 重新扫描: ", end="")
    
    choice = input().strip()
    
    if not choice:
        return None
    
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(room_list):
            ip, (room_name, port) = room_list[idx]
            return ip, port
        else:
            print(f"❌ 请输入 1-{len(room_list)} 之间的数字")
            return None
    except ValueError:
        print("❌ 请输入有效的房间号")
        return None


def connect_to_room(host, port):
    """连接到指定的房间"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    
    try:
        print(f"\n正在连接 {host}:{port}...\n")
        sock.connect((host, port))
        return sock
    except ConnectionRefusedError:
        print(f"❌ 无法连接到服务器 {host}:{port}")
        print("   服务器可能已关闭")
        return None
    except socket.gaierror:
        print(f"❌ 地址 {host} 无效或无法解析")
        return None
    except OSError as e:
        print(f"❌ 连接失败：{e}")
        return None


def start_client():
    """启动客户端"""
    print("=" * 50)
    print("🟢 聊天室客户端 - 局域网发现")
    print("=" * 50)
    
    while True:
        # 发现房间
        rooms = discover_rooms(timeout=5)
        
        if not rooms:
            print("\n❌ 未发现任何房间")
            print("请确认：")
            print("1. 至少有一个聊天室服务端在运行")
            print("2. 与服务端在同一局域网内")
            print("\n请稍后重试... (按 Ctrl+C 退出)")
            time.sleep(2)
            print("\n")
            continue
        
        # 显示房间列表
        result = display_rooms(rooms)
        if result is None:
            continue
        
        host, port = result
        
        # 连接到房间
        sock = connect_to_room(host, port)
        if sock is None:
            print("\n按 Enter 重新扫描...")
            input()
            continue
        
        # ---- 登录：主线程收发，避免线程竞争 ----
        data = sock.recv(1024)
        print(data.decode("utf-8"), end="")
        nickname = input().strip()
        if not nickname:
            nickname = "用户"
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
        
        print("\n连接已关闭")
        print("按 Enter 返回房间列表...")
        input()


if __name__ == "__main__":
    try:
        start_client()
    except KeyboardInterrupt:
        print("\n\n👋 已退出客户端")
        sys.exit(0)
