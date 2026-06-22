"""
初始界面 — 创建 / 加入聊天房间的独立窗口
与用户界面 (app.py) 完全分离，通过回调与控制器通信
"""
import socket
import threading
import time
import customtkinter as ctk
from .theme import *
from .icons import TEXT_APP_TITLE
from .icon_manager import set_window_icon
from .start_page import build_start_view
from .create_room_page import build_create_room_view
from .login_page import build_login_view
from ..client import connect_server, scan_network


class InitialInterface:
    """初始界面：创建或加入聊天室的独立 Toplevel 窗口

    生命周期由 AppController 管理：
      - 首次启动时自动打开
      - 用户界面 "+" 按钮重新打开
      - 创建 / 加入房间后自动关闭
      - 关闭时回调 controller.on_initial_closed()
    """

    def __init__(self, root, controller):
        """
        Args:
            root: 主窗口 (ctk.CTk)
            controller: AppController 实例，需提供回调方法
        """
        self.root = root
        self.controller = controller
        self.win = None
        self._tunnel = None
        self._wan_entry = None
        self._public_addr = None

    # ======================== 窗口生命周期 ========================

    def show(self):
        """显示初始界面窗口"""
        if self.win and self.win.winfo_exists():
            self.win.lift()
            self.win.focus_force()
            return

        x = self.root.winfo_x() + 60
        y = self.root.winfo_y() + 40

        win = ctk.CTkToplevel(self.root, fg_color="white")
        win.title(TEXT_APP_TITLE)
        win.geometry(f"420x480+{x}+{y}")
        win.resizable(False, False)
        win.attributes("-topmost", True)
        win.protocol("WM_DELETE_WINDOW", self._on_close)
        self.win = win
        # CTkToplevel 创建后立即设图标
        set_window_icon(win)
        # 额外保险：300ms 后重设一次，确保绕过 CTkToplevel 的 after_idle 覆写
        win.after(300, lambda: set_window_icon(win))
        self._show_start()

    def close(self):
        """关闭初始界面，清理资源"""
        # 清理未移交的隧道
        if self._tunnel:
            try:
                self._tunnel.stop()
            except Exception:
                pass
            self._tunnel = None
        # 销毁窗口
        if self.win and self.win.winfo_exists():
            self.win.destroy()
        self.win = None
        self._wan_entry = None

    def _on_close(self):
        """窗口关闭时通知控制器"""
        self.controller.on_initial_closed()
        self.close()

    def _clear(self):
        """清除窗口内所有子控件"""
        for w in self.win.winfo_children():
            w.destroy()

    # ======================== 页面导航 ========================

    def _show_start(self):
        """启动页：创建房间 / 加入房间 两个大按钮"""
        self._clear()
        build_start_view(self.win, self._show_create, self._show_join)

    def _random_port(self):
        """生成一个随机可用端口（基于时间戳，避免冲突）"""
        base = 10000 + (int(time.time() * 100) % 50000)
        for offset in range(100):
            port = base + offset
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.bind(("127.0.0.1", port))
                s.close()
                return port
            except OSError:
                continue
        return 8888

    def _show_create(self):
        """创建房间配置页（自动分配随机端口）"""
        self._clear()
        frame, entries = build_create_room_view(
            self.win,
            lambda: self._do_create(entries),
            self._show_start,
        )
        self._wan_entry = entries.get("外网IP")

        # 自动分配随机端口，避免多房间冲突
        port = self._random_port()
        addr_entry = entries["局域网IP:端口"]
        local_ip = addr_entry.get().split(":")[0]
        addr_entry.delete(0, "end")
        addr_entry.insert(0, f"{local_ip}:{port}")

        # 启动隧道
        self._start_tunnel(port)

    def _show_join(self):
        """加入房间页：地址输入、扫描、连接"""
        self._clear()
        fields = [
            ("地址:端口", "127.0.0.1:8888", 24),
            ("昵称", "用户", 20),
        ]
        frame, entries, scan_btn, connect_btn, status = build_login_view(
            self.win, fields, lambda: None,
            on_back=self._show_start,
        )
        connect_btn.configure(command=lambda: self._do_join(entries, status))
        if scan_btn:
            scan_btn.configure(command=lambda: self._scan_lan(entries, status))

    # ======================== 创建房间 ========================

    def _do_create(self, entries):
        """执行创建房间操作"""
        nick = entries["昵称"].get().strip() or "用户"
        room_name = entries["房间名称"].get().strip() or "聊天室"
        addr = entries["局域网IP:端口"].get().strip()
        port = 8888
        if ":" in addr:
            p = addr.rsplit(":", 1)[1]
            if p.isdigit():
                port = int(p)

        # 1. 创建独立的 ChatServer 实例并启动
        from ..server import ChatServer
        server = ChatServer(port=port, room_name=room_name)
        server.server_running = True
        server.room_status = 0
        threading.Thread(target=server.start_server, daemon=True).start()

        # 2. 传递隧道给控制器（不再由本界面管理）
        tunnel = self._tunnel
        self._tunnel = None  # 阻止 close() 误关

        # 3. 通知控制器（控制器会启动自动连接，同时传入 server 实例）
        self.controller.on_room_created(nick, "127.0.0.1", port, tunnel, server)

        # 4. 关闭初始界面
        self.close()

    def _start_tunnel(self, port, retries=2):
        """启动隧道穿透（bore / ngrok），结果回填到创建页"""
        from ..tunnel import auto_tunnel
        tunnel = auto_tunnel(port)
        if not tunnel:
            return

        def _run(attempt=0):
            ok, msg = tunnel.start()
            if ok:
                # 无论窗口是否存在都通知控制器更新地址
                try:
                    self.controller._update_tunnel_addr(msg)
                except Exception:
                    pass
                # 窗口还在则回填表单
                if self.win and self.win.winfo_exists():
                    self.win.after(0, lambda a=msg: self._do_fill_wan(a))
            elif attempt < retries:
                import time
                time.sleep(1)
                _run(attempt + 1)

        self._tunnel = tunnel
        threading.Thread(target=_run, daemon=True).start()

    def _do_fill_wan(self, addr):
        """回填外网地址到创建页的表单"""
        self._public_addr = addr
        if self._wan_entry and self.win and self.win.winfo_exists():
            try:
                self._wan_entry.configure(text_color="#000000")
                self._wan_entry.delete(0, "end")
                self._wan_entry.insert(0, addr)
            except Exception:
                pass

    # ======================== 加入房间 ========================

    def _do_join(self, entries, status):
        """执行加入房间操作（在后台线程连接）"""
        addr = entries["地址:端口"].get().strip()
        nick = entries["昵称"].get().strip() or "匿名"
        host, port_str = addr, "8888"
        if ":" in addr:
            parts = addr.rsplit(":", 1)
            host = parts[0]
            if parts[1].isdigit():
                port_str = parts[1]
        try:
            port = int(port_str)
        except ValueError:
            status.configure(text="❌ 地址格式错误")
            return

        # 检查是否已加入同一房间（快速反馈，不用等待连接）
        if self.controller._is_already_in_room(host, port):
            status.configure(
                text="❌ 已在該房間中，不可重複加入", text_color=ERROR_FG)
            return

        status.configure(text="⏳ 连接中...", text_color="#1976d2")

        def _do():
            try:
                sock, welcome, login, room_id, room_name, actual_nick = connect_server(host, port, nick)
                if self.win and self.win.winfo_exists():
                    self.win.after(0, lambda: status.configure(
                        text="✅ 已连接", text_color="#2e7d32"))
                    self.win.after(0, lambda: self.controller.on_room_joined(
                        actual_nick, host, port, sock, welcome, login, room_id, room_name))
                    self.win.after(300, self.close)
            except Exception as e:
                if self.win and self.win.winfo_exists():
                    self.win.after(0, lambda: status.configure(
                        text=f"❌ {e}", text_color=ERROR_FG))

        threading.Thread(target=_do, daemon=True).start()

    # ======================== 局域网扫描 ========================

    def _scan_lan(self, entries, status):
        """扫描局域网内的聊天室"""
        status.configure(
            text="🔍 正在扫描... 剩余 5 秒", text_color="#1976d2")

        # 真实倒计时（每秒更新），扫描完成后停止
        _count = [4]
        _done = [False]

        def _tick():
            if _done[0] or _count[0] <= 0 or not (self.win and self.win.winfo_exists()):
                return
            status.configure(
                text=f"🔍 正在扫描... 剩余 {_count[0]} 秒",
                text_color="#1976d2")
            _count[0] -= 1
            self.win.after(1000, _tick)

        self.win.after(1000, _tick)

        def _do():
            rooms = scan_network(timeout=5)
            _done[0] = True
            if rooms and self.win and self.win.winfo_exists():
                ip = list(rooms.keys())[0]
                name, port = rooms[ip][:2]
                self.win.after(
                    0, lambda: self._apply_scan(entries, status, name, ip, port))
            elif self.win and self.win.winfo_exists():
                self.win.after(0, lambda: status.configure(text="❌ 未发现房间"))

        threading.Thread(target=_do, daemon=True).start()

    def _apply_scan(self, entries, status, name, ip, port):
        """应用扫描结果到输入框"""
        entries["地址:端口"].delete(0, "end")
        entries["地址:端口"].insert(0, f"{ip}:{port}")
        status.configure(text=f"✅ 发现 \"{name}\"", text_color="#2e7d32")
