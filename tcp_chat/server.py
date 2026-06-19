"""
☆ 网络聊天室 — 服务端 ☆
基于 TCP Socket 的多客户端聊天室服务器
支持多人同时在线、群聊、私聊、在线用户列表
支持局域网自动发现
"""

import socket
import threading
import time

# ========== 配置 ==========
HOST = "0.0.0.0"                    # 监听所有网卡
PORT = 8888                         # TCP 端口号
DISCOVERY_PORT = 9999              # UDP 广播发现端口
BROADCAST_ADDRESS = "255.255.255.255"  # 广播地址

# ========== 获取本机 IP ==========
def get_local_ip():
    """获取本机局域网 IP 地址"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

LOCAL_IP = get_local_ip()

# ========== 全局状态 ==========
clients = {}                        # {conn: nickname}
lock = threading.Lock()
room_name = "聊天室"               # 房间名称
host_conn = None                    # 房主连接
next_user_id = 1                   # 自增用户 ID
user_ids = {}                       # {conn: user_id}
room_status = 1                     # 1=开放, 0=关闭


def broadcast(message: str, sender_conn=None):
    """群发消息（可选排除发送者）"""
    with lock:
        for conn in list(clients.keys()):
            if conn != sender_conn:
                try:
                    conn.sendall(message.encode("utf-8"))
                except:
                    pass


def close_room():
    """关闭房间：踢出所有成员，标记状态为 0"""
    global room_status, clients, host_conn, user_ids
    room_status = 0
    with lock:
        for conn in list(clients.keys()):
            try:
                conn.sendall("🔴 房间已关闭\n".encode("utf-8"))
                conn.close()
            except:
                pass
        clients.clear()
        host_conn = None
        user_ids.clear()


def send_to(target_nick: str, message: str):
    """私聊发送"""
    with lock:
        for conn, nick in clients.items():
            if nick == target_nick:
                try:
                    conn.sendall(message.encode("utf-8"))
                    return True
                except:
                    return False
    return False


def list_users() -> str:
    """返回在线用户列表字符串（带隐藏 ID 供客户端追踪）"""
    with lock:
        items = []
        for conn, nick in clients.items():
            uid = user_ids.get(conn, 0)
            if conn == host_conn:
                items.append(f"👑{nick}|{uid}")
            else:
                items.append(f"{nick}|{uid}")
    return "当前在线: " + ", ".join(items) if items else "当前没有其他在线用户"


def handle_client(conn: socket.socket, addr):
    """处理单个客户端通信"""
    global host_conn, next_user_id
    nickname = None
    user_id = None
    try:
        # ---- 欢迎 & 登录 ----
        conn.sendall("🟢 欢迎来到聊天室！请输入你的昵称: ".encode("utf-8"))
        nickname = conn.recv(1024).decode("utf-8").strip()
        if not nickname:
            nickname = f"用户{addr[1]}"

        with lock:
            # 分配唯一 ID
            user_id = next_user_id
            next_user_id += 1
            clients[conn] = nickname
            user_ids[conn] = user_id
            # 第一个连接的用户设为房主
            if host_conn is None:
                host_conn = conn
        broadcast(f"📢 {nickname}|{user_id} 进入了聊天室", conn)
        conn.sendall(f"✅ 登录成功！输入 /help 查看命令帮助\n{list_users()}\n".encode("utf-8"))

        # ---- 主循环 ----
        while True:
            data = conn.recv(4096)
            if not data:
                break
            msg = data.decode("utf-8").strip()
            if not msg:
                continue

            # 解析命令
            if msg.startswith("/"):
                parts = msg.split(maxsplit=1)
                cmd = parts[0].lower()

                if cmd == "/quit" or cmd == "/exit":
                    conn.sendall("👋 再见！正在断开连接...\n".encode("utf-8"))
                    break

                elif cmd == "/help":
                    help_text = (
                        "\n========== 命令帮助 ==========\n"
                        "/help          — 显示本帮助\n"
                        "/list          — 查看在线用户\n"
                        "/quit 或 /exit — 退出聊天室\n"
                        "/to <昵称> <消息> — 私聊某人\n"
                        "直接输入文字 — 群聊\n"
                        "==============================\n"
                    )
                    conn.sendall(help_text.encode("utf-8"))

                elif cmd == "/list":
                    conn.sendall((list_users() + "\n").encode("utf-8"))

                elif cmd == "/to" and len(parts) > 1:
                    # /to 昵称 消息
                    rest = parts[1]
                    space_idx = rest.find(" ")
                    if space_idx == -1:
                        conn.sendall("❌ 格式: /to <昵称> <消息>\n".encode("utf-8"))
                    else:
                        target = rest[:space_idx]
                        content = rest[space_idx + 1:].strip()
                        if not content:
                            conn.sendall("❌ 消息不能为空\n".encode("utf-8"))
                        else:
                            success = send_to(target, f"💬 [私聊]({nickname}): {content}\n")
                            if success:
                                conn.sendall(f"💬 [私聊](你 → {target}): {content}\n".encode("utf-8"))
                            else:
                                conn.sendall(f"❌ 用户 \"{target}\" 不在线或不存在\n".encode("utf-8"))
                else:
                    conn.sendall(f"❌ 未知命令 \"{cmd}\"。输入 /help 查看帮助\n".encode("utf-8"))
            else:
                # 群聊消息
                broadcast(f"💬 [{nickname}]: {msg}\n", conn)

    except (ConnectionResetError, ConnectionAbortedError, OSError):
        pass
    finally:
        # ---- 清理 ----
        with lock:
            if conn in clients:
                del clients[conn]
            if conn in user_ids:
                del user_ids[conn]
            if conn == host_conn:
                host_conn = None  # 房主离开，重置
        if nickname and user_id:
            broadcast(f"🔴 {nickname}|{user_id} 离开了聊天室\n")
        try:
            conn.close()
        except:
            pass
        print(f"[断开] {addr} — {nickname or '未知'}")


def broadcast_discovery():
    """启动 UDP 广播线程，让客户端发现此服务器"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    
    message = f"CHAT_ROOM|{room_name}|{LOCAL_IP}|{PORT}".encode("utf-8")
    
    while True:
        try:
            # 每 2 秒发送一次广播
            sock.sendto(message, (BROADCAST_ADDRESS, DISCOVERY_PORT))
            time.sleep(2)
        except Exception as e:
            print(f"[广播错误] {e}")
            time.sleep(2)


def start_server():
    """启动服务端"""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen(10)
    server.settimeout(1)  # 1秒超时，让 accept() 可被 Ctrl+C 中断
    print(f"🚀 聊天室服务端已启动！")
    print(f"   房间名称: {room_name}")
    print(f"   本机 IP: {LOCAL_IP}")
    print(f"   监听端口: {PORT}")
    print(f"   广播端口: {DISCOVERY_PORT}")
    print(f"   等待客户端连接...\n")

    # 启动广播发现线程
    discovery_thread = threading.Thread(target=broadcast_discovery, daemon=True)
    discovery_thread.start()
    print(f"📡 房间广播已启动，客户端可以搜索到此房间\n")

    try:
        while server_running:
            try:
                conn, addr = server.accept()
            except socket.timeout:
                continue  # 超时重试，让 KeyboardInterrupt 有机会被捕获
            print(f"[新连接] {addr}")
            t = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
            t.start()
    except KeyboardInterrupt:
        print("\n🛑 服务端关闭中...")
    finally:
        close_room()
        server.close()
        print("✅ 服务端已关闭")


if __name__ == "__main__":
    start_server()
