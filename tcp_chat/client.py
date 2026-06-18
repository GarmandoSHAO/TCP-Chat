"""
网络层 — 套接字连接、收发线程、局域网扫描
"""
import socket
import threading
import time
import queue

DISCOVERY_PORT = 9999


def connect_server(host, port, nickname, timeout=5):
    """连接到服务端，完成登录握手，返回 (socket, welcome_msg, login_result)"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    sock.connect((host, port))
    welcome = sock.recv(4096).decode("utf-8")
    sock.sendall(nickname.encode("utf-8"))
    login = sock.recv(4096).decode("utf-8")
    return sock, welcome, login


def start_receive(sock, msg_queue, stop_check):
    """后台接收线程：持续收消息，放入队列。stop_check 是可调用对象，返回 True 时退出"""
    while True:
        if callable(stop_check) and stop_check():
            break
        try:
            sock.settimeout(0.5)
            data = sock.recv(4096)
            if not data:
                msg_queue.put(("DISCONNECTED", "服务器已关闭连接"))
                break
            msg_queue.put(("MESSAGE", data.decode("utf-8")))
        except socket.timeout:
            continue
        except (ConnectionResetError, ConnectionAbortedError, OSError):
            # 如果是主动停止不报错
            if callable(stop_check) and stop_check():
                break
            msg_queue.put(("DISCONNECTED", "与服务器的连接已断开"))
            break


def scan_network(timeout=5):
    """扫描局域网内的聊天室，返回 {ip: (room_name, port)}"""
    rooms = {}
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("0.0.0.0", DISCOVERY_PORT))
        start = time.time()
        while time.time() - start < timeout:
            remaining = timeout - (time.time() - start)
            sock.settimeout(max(0.1, remaining))
            try:
                data, addr = sock.recvfrom(1024)
                msg = data.decode("utf-8")
                if msg.startswith("CHAT_ROOM|"):
                    parts = msg.split("|")
                    if len(parts) == 4:
                        _, room_name, ip, port = parts
                        rooms[ip] = (room_name, int(port))
                        if rooms:  # 扫描到房间立即结束
                            break
            except socket.timeout:
                break
            except Exception:
                break
        sock.close()
    except Exception:
        pass
    return rooms
