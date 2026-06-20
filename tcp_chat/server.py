"""
☆ 网络聊天室 — 服务端 ☆
基于 TCP Socket 的多客户端聊天室服务器
支持多人同时在线、群聊、私聊、在线用户列表
支持局域网自动发现
"""

import socket
import threading
import time
import random
import logging

logger = logging.getLogger(__name__)

# ========== 配置常量 ==========
HOST = "0.0.0.0"                    # 监听所有网卡
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


class ChatServer:
    """聊天室服务端 — 每个实例管理一个独立的聊天房间"""

    def __init__(self, port: int = 8888, room_name: str = "聊天室"):
        self.PORT = port
        self.room_name = room_name
        self.HOST = HOST
        self.DISCOVERY_PORT = DISCOVERY_PORT
        self.BROADCAST_ADDRESS = BROADCAST_ADDRESS
        self.LOCAL_IP = LOCAL_IP

        # ---- 每个房间独立的状态 ----
        self.clients = {}            # {conn: nickname}
        self.lock = threading.Lock()
        self.host_conn = None        # 房主连接
        self.next_user_id = 1        # 自增用户 ID
        self.user_ids = {}           # {conn: user_id}
        self.room_status = 0         # 1=开放, 0=关闭（默认关闭）
        self.server_running = False  # 服务端运行标志
        self.room_id = ""            # 房间唯一 ID（启动时根据时间生成）

    def broadcast(self, message: str, sender_conn=None):
        """群发消息（可选排除发送者）"""
        with self.lock:
            for conn in list(self.clients.keys()):
                if conn != sender_conn:
                    try:
                        conn.sendall(message.encode("utf-8"))
                    except:
                        pass

    def close_room(self):
        """关闭房间：踢出所有成员，标记状态为 0"""
        self.room_status = 0
        with self.lock:
            for conn in list(self.clients.keys()):
                try:
                    conn.sendall("🔴 房间已关闭\n".encode("utf-8"))
                    conn.close()
                except:
                    pass
            self.clients.clear()
            self.host_conn = None
            self.user_ids.clear()

    def send_to(self, target_nick: str, message: str):
        """私聊发送"""
        with self.lock:
            for conn, nick in self.clients.items():
                if nick == target_nick:
                    try:
                        conn.sendall(message.encode("utf-8"))
                        return True
                    except:
                        return False
        return False

    def list_users(self) -> str:
        """返回在线用户列表字符串（带隐藏 ID 供客户端追踪）"""
        with self.lock:
            items = []
            for conn, nick in self.clients.items():
                uid = self.user_ids.get(conn, 0)
                if conn == self.host_conn:
                    items.append(f"👑{nick}|{uid}")
                else:
                    items.append(f"{nick}|{uid}")
        return "当前在线: " + ", ".join(items) if items else "当前没有其他在线用户"

    def handle_client(self, conn: socket.socket, addr):
        """处理单个客户端通信"""
        nickname = None
        user_id = None
        logger.info("新连接: %s (room=%s)", addr, self.room_name)
        try:
            # ---- 检查房间状态（房主自连允许通过） ----
            if self.room_status == 0 and addr[0] != "127.0.0.1":
                logger.warning("房间未开放，拒绝连接: %s", addr)
                conn.sendall("🔴 房间已关闭或尚未开放\n".encode("utf-8"))
                conn.close()
                return

            # ---- 欢迎 & 登录 ----
            conn.sendall(f"🟢 欢迎来到「{self.room_name}」！(房间号: {self.room_id})\n请输入你的昵称: ".encode("utf-8"))
            nickname = conn.recv(1024).decode("utf-8").strip()
            if not nickname:
                nickname = f"用户{addr[1]}"
                logger.warning("昵称为空，使用默认: %s", nickname)
            else:
                logger.info("客户端输入昵称: %s", nickname)

            # 重复昵称自动重命名：用户 → 用户1 → 用户2 ...
            with self.lock:
                existing_nicks = set(self.clients.values())
                if nickname in existing_nicks:
                    base = nickname
                    suffix = 1
                    while f"{base}{suffix}" in existing_nicks:
                        suffix += 1
                    new_nick = f"{base}{suffix}"
                    conn.sendall(f"⚠️ 昵称 \"{nickname}\" 已被使用，已自动改为 \"{new_nick}\"\n".encode("utf-8"))
                    nickname = new_nick

            with self.lock:
                # 分配唯一 ID
                user_id = self.next_user_id
                self.next_user_id += 1
                self.clients[conn] = nickname
                self.user_ids[conn] = user_id
                # 第一个连接的用户设为房主
                if self.host_conn is None:
                    self.host_conn = conn
            self.broadcast(f"📢 {nickname}|{user_id} 进入了聊天室", conn)
            conn.sendall(f"✅ 登录成功！输入 /help 查看命令帮助\n📊 房间状态: {'🟢 开放' if self.room_status else '🔴 关闭'} (码:{self.room_status})\n{self.list_users()}\n".encode("utf-8"))
            logger.info("用户登录成功: %s (uid=%d, host=%s)", nickname, user_id, conn == self.host_conn)

            # ---- 主循环 ----
            while True:
                data = conn.recv(4096)
                if not data:
                    logger.info("用户 %s 连接关闭(recv空)", nickname)
                    break
                msg = data.decode("utf-8").strip()
                if not msg:
                    continue
                logger.debug("收到消息 from %s: %s", nickname, msg[:80])

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
                        conn.sendall((self.list_users() + "\n").encode("utf-8"))

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
                                success = self.send_to(target, f"💬 [私聊]({nickname}): {content}\n")
                                if success:
                                    conn.sendall(f"💬 [私聊](你 → {target}): {content}\n".encode("utf-8"))
                                    logger.info("私聊: %s -> %s: %s", nickname, target, content[:50])
                                else:
                                    conn.sendall(f"❌ 用户 \"{target}\" 不在线或不存在\n".encode("utf-8"))
                                    logger.warning("私聊失败: %s -> %s (用户不在线)", nickname, target)
                    else:
                        conn.sendall(f"❌ 未知命令 \"{cmd}\"。输入 /help 查看帮助\n".encode("utf-8"))
                else:
                    # 群聊消息
                    self.broadcast(f"💬 [{nickname}]: {msg}\n", conn)
                    logger.debug("群聊: %s: %s", nickname, msg[:50])

        except (ConnectionResetError, ConnectionAbortedError, OSError) as e:
            logger.warning("连接异常: %s %s", nickname, e)
            pass
        finally:
            # ---- 清理 ----
            with self.lock:
                if conn in self.clients:
                    del self.clients[conn]
                if conn in self.user_ids:
                    del self.user_ids[conn]
                if conn == self.host_conn:
                    self.host_conn = None  # 房主离开，重置
            if nickname and user_id:
                logger.info("用户离开: %s (uid=%d)", nickname, user_id)
                self.broadcast(f"🔴 {nickname}|{user_id} 离开了聊天室\n")
            try:
                conn.close()
            except:
                pass
            logger.info("连接关闭: %s — %s", addr, nickname or '未知')
            print(f"[断开] {addr} — {nickname or '未知'}")

    def broadcast_discovery(self):
        """启动 UDP 广播线程，让客户端发现此服务器"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

        while True:
            try:
                if self.room_status == 1:
                    msg = f"CHAT_ROOM|{self.room_name}|{self.LOCAL_IP}|{self.PORT}|1|{self.room_id}".encode("utf-8")
                    sock.sendto(msg, (self.BROADCAST_ADDRESS, self.DISCOVERY_PORT))
                    sock.sendto(msg, ("127.0.0.1", self.DISCOVERY_PORT))
                    if self.LOCAL_IP != "127.0.0.1":
                        sock.sendto(msg, (self.LOCAL_IP, self.DISCOVERY_PORT))
                time.sleep(2)
            except Exception as e:
                print(f"[广播错误] {e}")
                time.sleep(2)

    def start_server(self):
        """启动服务端"""
        self.server_running = True
        self.room_status = 0  # 默认关闭，房主进入聊天后才开放
        self.room_id = f"RM{int(time.time())}{random.randint(100, 999)}"
        logger.info("服务端启动: room=%s port=%d room_id=%s", self.room_name, self.PORT, self.room_id)
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((self.HOST, self.PORT))
        server.listen(10)
        server.settimeout(1)  # 1秒超时，让 accept() 可被 Ctrl+C 中断
        print(f"🚀 聊天室服务端已启动！")
        print(f"   房间名称: {self.room_name}")
        print(f"   本机 IP: {self.LOCAL_IP}")
        print(f"   监听端口: {self.PORT}")
        print(f"   广播端口: {self.DISCOVERY_PORT}")
        print(f"   等待客户端连接...\n")

        # 启动广播发现线程
        discovery_thread = threading.Thread(target=self.broadcast_discovery, daemon=True)
        discovery_thread.start()
        print(f"📡 房间广播已启动，客户端可以搜索到此房间\n")

        try:
            while self.server_running:
                try:
                    conn, addr = server.accept()
                except socket.timeout:
                    continue  # 超时重试，让 KeyboardInterrupt 有机会被捕获
                print(f"[新连接] {addr}")
                t = threading.Thread(target=self.handle_client, args=(conn, addr), daemon=True)
                t.start()
        except KeyboardInterrupt:
            print("\n🛑 服务端关闭中...")
        finally:
            self.close_room()
            server.close()
            print("✅ 服务端已关闭")


# ========== 兼容旧式直接运行 ==========
if __name__ == "__main__":
    import sys
    port = 8888
    name = "聊天室"
    if len(sys.argv) >= 2:
        try:
            port = int(sys.argv[1])
        except ValueError:
            name = sys.argv[1]
    if len(sys.argv) >= 3:
        try:
            port = int(sys.argv[2])
        except ValueError:
            pass
    ChatServer(port=port, room_name=name).start_server()
