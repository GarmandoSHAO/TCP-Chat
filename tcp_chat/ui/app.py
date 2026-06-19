"""
应用主控 — ChatClientUI 主类
"""
import tkinter as tk
import customtkinter as ctk
import socket
import threading
import time
import queue
import re
import os
import sys

from ..config import get, get_local_ip
from ..client import connect_server, start_receive, scan_network
from .theme import *
from .widgets import make_draggable
from .start_page import build_start_view
from .create_room_page import build_create_room_view
from .login_page import build_login_view
from .chat_page import build_chat_view

ctk.set_appearance_mode(get("appearance", "light"))
ctk.set_default_color_theme(get("theme", "green"))


class ChatClientUI:
    """聊天室 GUI 客户端"""

    def __init__(self, auto_connect=None):
        self.root = ctk.CTk()
        self.root.title("TCP 聊天室")
        win = get("window", {})
        self.root.geometry(f"{win.get('login_width', 420)}x{win.get('login_height', 480)}")
        self.root.resizable(False, False)
        self.sock = None
        self.nickname = ""
        self.connected = False
        self.msg_queue = queue.Queue()
        self.stop_threads = False
        self.online_users = []
        self._host_id = None
        self._host_name = None
        self._server_thread = None
        self._is_host = False
        self._scale = 1.0
        self._resize_timer = None
        self._base_width = 880
        self._public_addr = None
        self._drag_data = {"x": 0, "y": 0}
        self._blocked_users = set()
        self._private_chat_with = None
        self._tabs = []
        self._active_tab = -1
        if auto_connect:
            host, port, nick = auto_connect
            self.nickname = nick
            self.root.after(200, lambda: self._auto_connect(host, port, nick))
        else:
            self._show_start()
        self._set_window_icon()
        self.root.after(100, self._process_queue)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.bind("<Configure>", self._on_window_resize)

    def _set_window_icon(self):
        try:
            img = tk.PhotoImage(width=16, height=16)
            for x in range(16):
                for y in range(16):
                    c = "#075e54"
                    if 3 <= x <= 12 and 3 <= y <= 12: c = "#ffffff"
                    elif 4 <= x <= 11 and 4 <= y <= 11: c = "#075e54"
                    img.put(c, (x, y))
            self.root.iconphoto(True, img)
            self._icon_img = img
        except Exception:
            pass

    def _clear_views(self, *skip):
        for name in ("start_frame", "create_frame", "login_frame", "loading_frame", "chat_frame"):
            if name in skip: continue
            f = getattr(self, name, None)
            if f:
                try: f.pack_forget()
                except: pass

    def _show_start(self):
        self._clear_views()
        self.start_frame = build_start_view(self.root, self._go_create_config, self._on_join_room)

    def _go_create_config(self):
        self._clear_views()
        self.create_frame, self.create_entries = build_create_room_view(
            self.root, self._on_create_room, self._back_to_start)
        self._wan_entry = self.create_entries.get("外网IP")
        addr = self.create_entries["局域网IP:端口"].get()
        port = get("default_port", 8888)
        if ":" in addr:
            p = addr.rsplit(":", 1)[1]
            if p.isdigit(): port = int(p)
        self._start_tunnel(port)

    def _back_to_start(self):
        if hasattr(self, 'create_frame'): self.create_frame.pack_forget()
        self._show_start()

    def _on_join_room(self):
        self._clear_views()
        fields = [
            ("地址:端口", f"{get('default_host', '127.0.0.1')}:{get('default_port', 8888)}", 24),
            ("昵称", get("default_nickname", "用户"), 20),
        ]
        (self.login_frame, self.login_entries,
         self.scan_btn, self.connect_btn, self.login_status) = build_login_view(
            self.root, fields, self._do_connect)
        self.scan_btn.configure(command=self._scan_network)
        self.connect_btn.configure(command=self._do_connect)
        self.root.update_idletasks()
        self.root.after(100, lambda: self.login_entries["昵称"].focus_set())

    def _show_loading(self, text="⏳ 请稍候..."):
        self._clear_views()
        self.loading_frame = ctk.CTkFrame(self.root, fg_color=WHITE)
        self.loading_frame.pack(fill="both", expand=True)
        ctk.CTkLabel(self.loading_frame, text=text, font=("Segoe UI", 14),
                     text_color="#888888", bg_color=WHITE).pack(expand=True)

    def _switch_to_chat(self, welcome_msg, login_result):
        self.root.unbind("<Return>")
        win = get("window", {})
        if not getattr(self, 'chat_frame', None):
            self.root.geometry(f"{win.get('chat_width', 880)}x{win.get('chat_height', 640)}")
            self.root.minsize(700, 500)
            self.root.resizable(True, True)
            self._clear_views()
            chat = build_chat_view(self.root, self._send_message, self._disconnect, on_menu=self._on_show_menu)
            self.chat_frame = chat["frame"]
            # first chat creation
        else:
            chat = build_chat_view(self.root, self._send_message, self._disconnect, on_menu=self._on_show_menu)
            self.chat_frame.pack_forget()
            chat["frame"].pack(fill="both", expand=True)
            self.chat_frame = chat["frame"]
        self.msg_text = chat["msg_text"]
        self.msg_entry = chat["msg_entry"]
        self.status_bar = chat["status_bar"]
        self.title_label = chat["title_label"]
        self.user_list_inner = chat["user_list_inner"]
        self.tab_container = chat["tab_container"]
        self.user_count_label = chat["user_count"]
        self.send_btn = chat["send_btn"]
        make_draggable(chat["top_bar"], self._drag_data)
        self.title_label.configure(text=f"聊天室 — {self.nickname}")
        self._add_title_context_menu()
        self.connected = True
        if self._is_host:
            try:
                import importlib
                _srv = importlib.import_module("tcp_chat.server")
                _srv.room_status = 1
            except: pass
        if self._active_tab >= 0 and self._active_tab < len(self._tabs):
            t = self._tabs[self._active_tab]
            t["sock"] = self.sock
            t["connected"] = self.connected
            t["nickname"] = self.nickname
            t["chat_frame"] = self.chat_frame
            t["msg_text"] = self.msg_text
            t["msg_entry"] = self.msg_entry
            t["user_list_inner"] = self.user_list_inner
            t["user_count"] = self.user_count_label
            t["status_bar"] = self.status_bar
            t["title_label"] = self.title_label
            t["send_btn"] = self.send_btn
            t["online_users"] = self.online_users
        self._add_system_message("🟢 已连接到聊天室")
        if login_result: self._display_message(login_result)
        self._build_command_menu()
        self.root.lift()
        self.root.focus_force()
        self.msg_entry.focus()

    # ======================== 创建房间 & 隧道 ========================

    def _on_create_room(self):
        nick = self.create_entries["昵称"].get().strip() or get("default_nickname", "用户")
        addr = self.create_entries["局域网IP:端口"].get().strip()
        port = get("default_port", 8888)
        if ":" in addr:
            parts = addr.rsplit(":", 1)
            if parts[1].isdigit(): port = int(parts[1])
        self.nickname = nick
        self._is_host = True
        import importlib
        _srv = importlib.import_module("tcp_chat.server")
        _srv.PORT = port
        self._server_thread = threading.Thread(target=_srv.start_server, daemon=True)
        self._server_thread.start()
        self._clear_views()
        self._show_loading("🚀 正在启动房间...")
        self._auto_connect("127.0.0.1", port, nick)

    def _start_tunnel(self, port, retries=2):
        try:
            import importlib
            _srv = importlib.import_module("tcp_chat.server")
            _srv.server_running = False
            _srv.room_status = 0
        except: pass
        if hasattr(self, '_tunnel') and self._tunnel:
            try: self._tunnel.stop()
            except: pass
        import subprocess as _sp
        try: _sp.run('taskkill /f /im bore.exe', shell=True, capture_output=True)
        except: pass
        from tcp_chat.tunnel import auto_tunnel
        tunnel = auto_tunnel(port)
        if not tunnel: return

        def _run(attempt=0):
            ok, msg = tunnel.start()
            if ok:
                self.root.after(0, lambda a=msg: self._finish_tunnel(a))
            elif attempt < retries:
                import time; time.sleep(1); _run(attempt + 1)
        self._tunnel = tunnel
        threading.Thread(target=_run, daemon=True).start()

    def _finish_tunnel(self, addr):
        self._public_addr = addr
        if hasattr(self, '_wan_entry') and self._wan_entry:
            try:
                self._wan_entry.configure(text_color="#000000")
                self._wan_entry.delete(0, "end")
                self._wan_entry.insert(0, addr)
            except: pass

    # ======================== 连接逻辑 ========================

    def _auto_connect(self, host, port, nickname):
        self.root.after(300, lambda: self._connect_thread(host, port, nickname))

    def _do_connect(self):
        if self.connected: return
        addr = self.login_entries["地址:端口"].get().strip()
        nick = self.login_entries["昵称"].get().strip() or "匿名"
        host, port_str = addr, str(get("default_port", 8888))
        if ":" in addr and not addr.startswith("["):
            parts = addr.rsplit(":", 1)
            host = parts[0]
            if parts[1].isdigit(): port_str = parts[1]
        try: port = int(port_str)
        except:
            self.login_status.configure(text="❌ 地址格式错误 (host:port)"); return
        self.nickname = nick
        self.login_status.configure(text="⏳ 连接中...", text_color="#1976d2")
        self.connect_btn.configure(state="disabled")
        self.scan_btn.configure(state="disabled")
        threading.Thread(target=self._connect_thread, args=(host, port, nick), daemon=True).start()

    def _connect_thread(self, host, port, nick):
        try:
            sock, welcome, login_result = connect_server(host, port, nick)
            self.sock = sock
            self.connected = True
            self.msg_queue.put(("CONNECTED", (welcome, login_result)))
            self.stop_threads = False
            threading.Thread(target=start_receive, args=(sock, self.msg_queue, lambda: self.stop_threads), daemon=True).start()
        except socket.timeout: self.msg_queue.put(("ERROR", "连接超时"))
        except ConnectionRefusedError: self.msg_queue.put(("ERROR", "连接被拒绝"))
        except socket.gaierror: self.msg_queue.put(("ERROR", f"无法解析地址 \"{host}\""))
        except Exception as e: self.msg_queue.put(("ERROR", f"连接失败：{e}"))

    def _scan_network(self):
        self.login_status.configure(text="🔍 正在扫描... 剩余 5 秒", text_color="#1976d2")
        self.scan_btn.configure(state="disabled")
        self._scan_start = time.time()
        self._scan_tick()
        threading.Thread(target=self._scan_thread, daemon=True).start()

    def _scan_tick(self):
        if self.scan_btn.cget("state") == "normal": return
        remaining = max(0, 5 - int(time.time() - self._scan_start))
        self.login_status.configure(text=f"🔍 正在扫描... 剩余 {remaining} 秒", text_color="#1976d2")
        self.root.after(200, self._scan_tick)

    def _scan_thread(self):
        rooms = scan_network(timeout=5)
        if rooms:
            ip = list(rooms.keys())[0]
            name, port = rooms[ip][:2]
            self.msg_queue.put(("SCAN_RESULT", (name, ip, port)))
        else:
            self.msg_queue.put(("SCAN_FAIL", None))

    # ======================== 命令菜单 ========================

    def _build_command_menu(self):
        self.cmd_defs = [("/help", "显示帮助"), ("/list", "查看在线用户"),
                         ("/to <昵称> <消息>", "私聊某人"), ("/quit", "退出"), ("/exit", "退出")]
        self.cmd_popup = ctk.CTkToplevel(self.root)
        self.cmd_popup.overrideredirect(True)
        self.cmd_popup.attributes("-topmost", True)
        self.cmd_popup.withdraw()
        popup_frame = ctk.CTkFrame(self.cmd_popup, corner_radius=8, fg_color="white",
                                   border_width=1, border_color="#d0d0d0")
        popup_frame.pack(fill="both", expand=True)
        self.cmd_listbox = tk.Listbox(popup_frame, font=("Segoe UI", 11), bd=0,
                                       highlightthickness=0, bg="#ffffff", fg="#333333",
                                       activestyle="none", exportselection=False, width=30, height=5)
        self.cmd_listbox.pack(fill="both", expand=True, padx=4, pady=4)
        self._cmd_selected = -1
        self.msg_entry.bind("<KeyRelease>", self._on_cmd_key)
        self.msg_entry.bind("<Up>", self._on_cmd_up)
        self.msg_entry.bind("<Down>", self._on_cmd_down)
        self.msg_entry.bind("<Escape>", lambda e: self._cmd_hide())
        self.msg_entry.bind("<Return>", self._on_return)
        self.cmd_listbox.bind("<Button-1>", self._on_cmd_click)
        self.cmd_listbox.bind("<Double-Button-1>", self._on_cmd_confirm)

    def _cmd_show(self):
        if self.cmd_listbox.size() == 0: return
        x = self.msg_entry.winfo_rootx()
        y = self.msg_entry.winfo_rooty() - self.cmd_popup.winfo_reqheight() - 6
        self.cmd_popup.geometry(f"+{x}+{y}")
        self.cmd_popup.deiconify()
        self._cmd_selected = -1
        self.cmd_listbox.selection_clear(0, tk.END)

    def _cmd_hide(self):
        self.cmd_popup.withdraw()

    def _on_cmd_key(self, event):
        if event.keysym in ("Up", "Down", "Left", "Right", "Return", "Escape"): return
        self.root.after_idle(self._cmd_filter)

    def _cmd_filter(self):
        text = self.msg_entry.get()
        if not text.startswith("/") or " " in text: self._cmd_hide(); return
        partial = text.lower()
        self.cmd_listbox.delete(0, tk.END)
        for cmd, desc in self.cmd_defs:
            if cmd.lower().startswith(partial):
                self.cmd_listbox.insert(tk.END, f"{cmd:<22s}{desc}")
        if self.cmd_listbox.size() > 0: self._cmd_show()
        else: self._cmd_hide()

    def _on_cmd_up(self, event):
        if not self.cmd_popup.winfo_viewable(): return
        size = self.cmd_listbox.size()
        if size == 0: return
        self._cmd_selected = (self._cmd_selected - 1) % size if self._cmd_selected > 0 else size - 1
        self.cmd_listbox.selection_clear(0, tk.END)
        self.cmd_listbox.selection_set(self._cmd_selected)
        return "break"

    def _on_cmd_down(self, event):
        if not self.cmd_popup.winfo_viewable(): return
        size = self.cmd_listbox.size()
        if size == 0: return
        self._cmd_selected = (self._cmd_selected + 1) % size if self._cmd_selected < size - 1 else 0
        self.cmd_listbox.selection_clear(0, tk.END)
        self.cmd_listbox.selection_set(self._cmd_selected)
        return "break"

    def _on_cmd_click(self, event):
        idx = self.cmd_listbox.nearest(event.y)
        if idx >= 0: self._cmd_selected = idx

    def _on_cmd_confirm(self, event):
        self._cmd_insert_selected()

    def _cmd_insert_selected(self):
        if self._cmd_selected < 0 or self._cmd_selected >= self.cmd_listbox.size(): return
        cmd = self.cmd_listbox.get(self._cmd_selected).split()[0]
        self.msg_entry.delete(0, "end")
        self.msg_entry.insert(0, cmd + " ")
        self.msg_entry.icursor(tk.END)
        self._cmd_hide()
        self.msg_entry.focus_set()

    def _on_return(self, event):
        if hasattr(self, 'cmd_popup') and self.cmd_popup.winfo_viewable():
            if self._cmd_selected >= 0: self._cmd_insert_selected(); return "break"
        return self._send_message() or "break"

    # ======================== 多标签 + 弹出开始窗口 ========================

    def _refresh_tabs(self):
        """刷新标签栏（与顶栏同排）"""
        if not hasattr(self, 'tab_container') or not self._tabs:
            return
        for w in self.tab_container.winfo_children():
            w.destroy()
        for i, tab in enumerate(self._tabs):
            if i == self._active_tab:
                continue
            # 每个标签：状态条 + 名称
            frame = ctk.CTkFrame(self.tab_container, fg_color="transparent")
            frame.pack(side="left", padx=(2, 0))
            color = STATUS_GREEN if tab.get("connected") else STATUS_RED
            ctk.CTkFrame(frame, width=3, height=16, fg_color=color,
                         corner_radius=2).pack(side="left", padx=(0, 3))
            btn = ctk.CTkButton(frame, text=tab["name"], font=("Segoe UI", 10),
                                 width=60, height=22, corner_radius=4,
                                 fg_color="#e8e8e8", text_color="#333333",
                                 hover_color="#d0d0d0",
                                 command=lambda idx=i: self._switch_tab(idx))
            btn.pack(side="left")

    def _add_tab(self, name, sock, nickname):
        """添加新标签页"""
        tab_id = len(self._tabs)
        tab = {
            "id": tab_id, "name": name, "sock": sock, "nickname": nickname,
            "connected": True, "online_users": [],
            "msg_text": None, "msg_frame": None,
            "user_list_inner": None, "user_count": None,
            "top_bar": None, "status_bar": None,
            "title_label": None, "msg_entry": None, "send_btn": None,
            "chat_frame": None,
        }
        self._tabs.append(tab)
        self._switch_tab(tab_id)
        return tab_id

    def _switch_tab(self, index):
        """切换到指定标签"""
        if index < 0 or index >= len(self._tabs): return
        # 隐藏当前标签
        if self._active_tab >= 0 and self._active_tab < len(self._tabs):
            old = self._tabs[self._active_tab]
            if old["chat_frame"]:
                try: old["chat_frame"].pack_forget()
                except: pass
        # 显示新标签
        self._active_tab = index
        tab = self._tabs[index]
        if tab["chat_frame"]:
            tab["chat_frame"].pack(fill="both", expand=True)
        # 更新引用
        self.sock = tab["sock"]
        self.nickname = tab["nickname"]
        self.msg_text = tab["msg_text"]
        self.msg_entry = tab["msg_entry"]
        self.online_users = tab["online_users"]
        self.user_list_inner = tab["user_list_inner"]
        self.user_count_label = tab["user_count"]
        self.status_bar = tab["status_bar"]
        self.title_label = tab["title_label"]
        self.send_btn = tab["send_btn"]
        self.connected = tab["connected"]
        if tab["sock"]:
            self.sock = tab["sock"]
        self._refresh_tabs()

    def _on_show_menu(self):
        from .start_page import build_start_view
        from .create_room_page import build_create_room_view
        from .login_page import build_login_view

        win = ctk.CTkToplevel(self.root, fg_color="white")
        win.title("TCP 聊天室")
        win.geometry("420x480+%d+%d" % (self.root.winfo_x() + 60, self.root.winfo_y() + 40))
        win.resizable(False, False)
        win.attributes("-topmost", True)

        def _clear():
            for w in win.winfo_children(): w.destroy()

        def _go_start():
            _clear()
            build_start_view(win, _go_create, _go_join)

        def _go_create():
            _clear()
            frame, e = build_create_room_view(win, lambda: _do_create(e), _go_start)

        def _do_create(entries):
            nick = entries["昵称"].get().strip() or "用户"
            addr = entries["局域网IP:端口"].get().strip()
            port = 8888
            if ":" in addr:
                p = addr.rsplit(":", 1)[1]
                if p.isdigit(): port = int(p)
            import importlib
            _srv = importlib.import_module("tcp_chat.server")
            _srv.PORT = port
            _srv.server_running = True
            _srv.room_status = 0
            threading.Thread(target=_srv.start_server, daemon=True).start()
            self._start_tunnel(port)
            self.nickname = nick
            self._is_host = True
            self._add_tab(nick, None, nick)
            self._auto_connect("127.0.0.1", port, nick)
            _clear()
            ctk.CTkLabel(win, text="🚀 房间已创建！", font=("Segoe UI", 14),
                         bg_color="white").pack(expand=True)
            ctk.CTkButton(win, text="关闭", command=win.destroy).pack(pady=10)

        def _go_join():
            _clear()
            fields = [("地址:端口", "127.0.0.1:8888", 24), ("昵称", "用户", 20)]
            frame, entries, scan_btn, connect_btn, status = build_login_view(win, fields, lambda: None)
            connect_btn.configure(command=lambda: _do_join(entries, status))
            ctk.CTkButton(win, text="← 返回", font=("Segoe UI", 11), width=200, height=30,
                           corner_radius=8, fg_color="white", text_color="#888888",
                           hover_color="#f0f0f0", command=_go_start).pack(pady=(4, 0))

        def _do_join(entries, status):
            addr = entries["地址:端口"].get().strip()
            nick = entries["昵称"].get().strip() or "匿名"
            host, port_str = addr, "8888"
            if ":" in addr:
                parts = addr.rsplit(":", 1)
                host = parts[0]
                if parts[1].isdigit(): port_str = parts[1]
            try: port = int(port_str)
            except: status.configure(text="❌ 地址格式错误"); return
            status.configure(text="⏳ 连接中...", text_color="#1976d2")

            def _do():
                try:
                    sock, welcome, login = connect_server(host, port, nick)
                    self.root.after(0, lambda: status.configure(text="✅ 已连接", text_color="#2e7d32"))
                    self.nickname = nick
                    self.sock = sock
                    self.connected = True
                    self._add_tab(nick, sock, nick)
                    self.msg_queue.put(("CONNECTED", (welcome, login)))
                    self.stop_threads = False
                    threading.Thread(target=start_receive, args=(sock, self.msg_queue, lambda: self.stop_threads), daemon=True).start()
                except Exception as e:
                    self.root.after(0, lambda: status.configure(text=f"❌ {e}", text_color=ERROR_FG))
            threading.Thread(target=_do, daemon=True).start()

        _go_start()

    # ======================== 消息收发 ========================

    def _send_message(self):
        if not self.connected or not self.sock: return
        text = self.msg_entry.get().strip()
        if not text: return
        self._add_chat_message(f"💬 [{self.nickname}]: {text}", is_self=True)
        try:
            self.sock.sendall(text.encode("utf-8"))
            self.msg_entry.delete(0, "end")
            if text.strip().lower() in ("/quit", "/exit"):
                self._add_system_message("正在退出...")
                self._disconnect()
        except OSError:
            self._add_system_message("❌ 发送失败")
            self._disconnect()

    def _process_queue(self):
        try:
            while True:
                msg_type, data = self.msg_queue.get_nowait()
                if msg_type == "CONNECTED": self._switch_to_chat(*data)
                elif msg_type == "MESSAGE": self._display_message(data)
                elif msg_type == "ERROR":
                    if hasattr(self, 'login_status'): self.login_status.configure(text=f"❌ {data}")
                    if hasattr(self, 'connect_btn'): self.connect_btn.configure(state="normal")
                    if hasattr(self, 'scan_btn'): self.scan_btn.configure(state="normal")
                elif msg_type == "DISCONNECTED":
                    self._add_system_message(f"🔴 {data}")
                    self.connected = False
                    if self.sock:
                        try: self.sock.close()
                        except: pass
                    if hasattr(self, 'title_label'): self.title_label.configure(text="聊天室 — 已断开")
                    if hasattr(self, 'status_bar'): self.status_bar.configure(fg_color=STATUS_RED)
                elif msg_type == "SCAN_RESULT":
                    name, ip, port = data
                    self.login_entries["地址:端口"].delete(0, "end")
                    self.login_entries["地址:端口"].insert(0, f"{ip}:{port}")
                    self.login_status.configure(text=f"✅ 发现 \"{name}\"", text_color="#2e7d32")
                    self.scan_btn.configure(state="normal")
                elif msg_type == "SCAN_FAIL":
                    self.login_status.configure(text=f"❌ {data}" if data else "❌ 未发现房间")
                    self.scan_btn.configure(state="normal")
        except queue.Empty: pass
        if not self.stop_threads: self.root.after(100, self._process_queue)

    def _display_message(self, raw_msg):
        raw_msg = raw_msg.strip().replace("\r", "")
        if not raw_msg: return
        for b in self._blocked_users:
            if raw_msg.startswith(f"💬 [{b}]:"): return
            if raw_msg.startswith(f"💬 [私聊]({b}"): return
        if raw_msg.startswith("💬 [私聊]("):
            end = raw_msg.find("]")
            if end > 0:
                s = raw_msg[7:end].split("(")[-1].split(")")[0]
                if s == self._private_chat_with and hasattr(self, '_pc_text'):
                    self._add_to_private_chat(raw_msg, s); return
            self._add_private_message(raw_msg)
        elif raw_msg.startswith("📢") or raw_msg.startswith("🔴"):
            self._add_system_message(re.sub(r'\|(\d+)', '', raw_msg))
            self._update_users_from_join_leave(raw_msg)
        elif any(raw_msg.startswith(p) for p in ("✅", "❌", "🟢")):
            self._add_system_message(raw_msg)
        elif raw_msg.startswith("当前在线"):
            self._parse_user_list(raw_msg)
            self._add_system_message(re.sub(r'\|(\d+)', '', raw_msg) if "|" in raw_msg else raw_msg, skip_parse=True)
        elif "==========" in raw_msg: self._add_system_message(raw_msg)
        else: self._add_chat_message(raw_msg)

    def _add_system_message(self, text, skip_parse=False, tw=None):
        tw = tw or getattr(self, 'msg_text', None)
        if not tw: return
        display = re.sub(r'\|(\d+)', '', text)
        tw.config(state="normal")
        if tw.get("end-2c", "end-1c") != "": tw.insert("end", "\n")
        tw.insert("end", display, ("system",))
        tw.see("end")
        tw.config(state="disabled")
        if "当前在线:" in display and not skip_parse: self._parse_user_list(display)

    def _add_chat_message(self, text, is_self=False):
        self.msg_text.config(state="normal")
        if self.msg_text.get("end-2c", "end-1c") != "": self.msg_text.insert("end", "\n")
        ts = time.strftime("%H:%M")
        self.msg_text.insert("end", f"  {ts}  ", ("timestamp",))
        if text.startswith("💬 ["):
            end = text.find("]", 3)
            if end > 0:
                nick = text[3:end]
                content = text[end + 2:]
                self.msg_text.insert("end", nick + " (我)" if is_self else nick, ("nickname_tag",))
                self.msg_text.insert("end", f"\n{content}", ("normal",))
            else: self.msg_text.insert("end", text, ("normal",))
        else: self.msg_text.insert("end", text, ("normal",))
        self.msg_text.see("end")
        self.msg_text.config(state="disabled")

    def _add_private_message(self, text):
        self.msg_text.config(state="normal")
        if self.msg_text.get("end-2c", "end-1c") != "": self.msg_text.insert("end", "\n")
        self.msg_text.insert("end", f"  {time.strftime('%H:%M')}  ", ("timestamp",))
        self.msg_text.insert("end", text, ("private",))
        self.msg_text.see("end")
        self.msg_text.config(state="disabled")

    def _add_to_private_chat(self, raw_msg, sender):
        if not hasattr(self, '_pc_text') or not self._pc_text: return
        content = raw_msg.split(": ", 1)[1] if ": " in raw_msg else raw_msg
        is_me = "你 → " in raw_msg[:20]
        tw = self._pc_text
        tw.config(state="normal")
        if tw.get("end-2c", "end-1c") != "": tw.insert("end", "\n")
        tw.insert("end", f"  {time.strftime('%H:%M')}  ", "ts")
        tw.insert("end", f"{sender}: {content}\n" if not is_me else f"我: {content}\n", "normal")
        tw.see("end")
        tw.config(state="disabled")

    def _add_title_context_menu(self):
        self._ctx_menu = tk.Menu(self.root, tearoff=False, font=("Segoe UI", 10),
                                 bg="white", fg="#333333", activebackground="#e8f5e9", activeforeground="#075e54")
        self._ctx_menu.add_command(label="🚪 退出房间", command=self._disconnect)
        self._ctx_menu.add_separator()
        self._ctx_menu.add_command(label="🌐 查看本机 IP", command=self._show_ip)
        self.title_label.bind("<Button-3>", self._show_context_menu)
        self.title_label.bind("<Button-2>", self._show_context_menu)

    def _show_context_menu(self, event):
        try: self._ctx_menu.tk_popup(event.x_root, event.y_root)
        finally: self._ctx_menu.grab_release()

    def _show_ip(self):
        from ..config import get_local_ip, get
        ip = f"{get_local_ip()}:{get('default_port', 8888)}"
        pub = getattr(self, '_public_addr', None)
        win = ctk.CTkToplevel(self.root, fg_color="white")
        win.title("网络信息")
        win.geometry("280x160+%d+%d" % (self.root.winfo_x() + 60, self.root.winfo_y() + 80))
        win.resizable(False, False)
        win.attributes("-topmost", True)
        frame = ctk.CTkFrame(win, fg_color="white", corner_radius=0)
        frame.pack(expand=True)

        def copy(text):
            win.clipboard_clear(); win.clipboard_append(text)
            hint.configure(text="✅ 复制成功"); win.after(1500, lambda: hint.configure(text=""))

        def make_row(label, text):
            row = ctk.CTkFrame(frame, fg_color="transparent")
            row.pack(fill="x", pady=4)
            ctk.CTkLabel(row, text=label, font=("Segoe UI", 12), text_color="#333333").pack(side="left", padx=(0, 8))
            ctk.CTkButton(row, text=text, font=("Segoe UI", 12), width=0, height=28,
                           corner_radius=5, fg_color="#e0e0e0", text_color="#333333",
                           hover_color="#d0d0d0", command=lambda t=text: copy(t)).pack(side="left")

        make_row("局域网 IP", ip)
        if pub: make_row("外网地址", pub)
        hint = ctk.CTkLabel(frame, text="", font=("Segoe UI", 10), text_color="#2e7d32")
        hint.pack(pady=(4, 2))
        ctk.CTkButton(frame, text="关闭", font=("Segoe UI", 11), width=70, height=28,
                       corner_radius=5, fg_color="#075e54", command=win.destroy).pack()

    def _toggle_block(self, nick):
        if nick in self._blocked_users: self._blocked_users.discard(nick); self._add_system_message(f"🔓 已取消屏蔽 {nick}")
        else: self._blocked_users.add(nick); self._add_system_message(f"🔒 已屏蔽 {nick}")
        self._update_user_list_display(self.online_users)

    def _start_private_chat(self, nick):
        if self._private_chat_with == nick: return
        self._private_chat_with = nick
        self._build_private_chat_view(nick)

    def _build_private_chat_view(self, nick):
        self._pc_frame = ctk.CTkFrame(self.chat_frame, fg_color="white")
        self._pc_frame.pack(fill="both", expand=True)
        top = ctk.CTkFrame(self._pc_frame, height=38, fg_color="white", corner_radius=0)
        top.pack(fill="x"); top.pack_propagate(False)
        ctk.CTkButton(top, text="← 返回", font=("Segoe UI", 11), width=50, height=28,
                       corner_radius=6, fg_color="white", text_color="#075e54",
                       hover_color="#e8f5e9", command=self._close_private_chat).pack(side="left", padx=4)
        ctk.CTkLabel(top, text=f"💬 私聊: {nick}", font=("Segoe UI", 12, "bold"),
                     text_color="#075e54", bg_color="white").pack(side="left", padx=8)
        mf = ctk.CTkFrame(self._pc_frame, fg_color="white")
        mf.pack(fill="both", expand=True)
        mf.grid_rowconfigure(0, weight=1); mf.grid_columnconfigure(0, weight=1)
        self._pc_text = tk.Text(mf, font=("Segoe UI", 12), wrap="word", state="disabled",
                                 bd=0, padx=14, pady=10, bg="#ffffff", highlightthickness=0)
        self._pc_text.grid(row=0, column=0, sticky="nsew")
        for n, (fg, ft) in [("system", ("#667781", ("Segoe UI", 9, "italic"))),
                             ("normal", ("#000000", ("Segoe UI", 12))),
                             ("nick", ("#075e54", ("Segoe UI", 12, "bold"))),
                             ("ts", ("#999999", ("Segoe UI", 8)))]:
            self._pc_text.tag_configure(n, foreground=fg, font=ft)
        ib = ctk.CTkFrame(self._pc_frame, height=56, fg_color="transparent", corner_radius=0)
        ib.pack(fill="x", padx=10, pady=(6, 10)); ib.pack_propagate(False)
        self._pc_entry = ctk.CTkEntry(ib, font=("Segoe UI", 12), height=38, corner_radius=20, placeholder_text=f"私聊 {nick}...")
        self._pc_entry.pack(side="left", fill="both", expand=True, padx=(0, 8))
        self._pc_entry.bind("<Return>", lambda e: self._send_private(nick, self._pc_entry, self._pc_text))
        ctk.CTkButton(ib, text="发送", font=("Segoe UI", 12, "bold"), width=80, height=38,
                       corner_radius=20, command=lambda: self._send_private(nick, self._pc_entry, self._pc_text)).pack(side="left")
        if hasattr(self, 'msg_entry') and self.msg_entry: self.msg_entry.master.pack_forget()
        self._pc_entry.focus()
        self._add_system_message(f"💬 开始与 {nick} 私聊", tw=self._pc_text)

    def _close_private_chat(self):
        if hasattr(self, '_pc_frame') and self._pc_frame:
            self._pc_frame.destroy(); self._pc_frame = None
        self._private_chat_with = None
        if hasattr(self, 'msg_entry') and self.msg_entry:
            try: self.msg_entry.master.pack(fill="x", padx=10, pady=(6, 10))
            except: pass

    def _send_private(self, nick, entry, tw):
        text = entry.get().strip()
        if not text: return
        tw.config(state="normal")
        if tw.get("end-2c", "end-1c") != "": tw.insert("end", "\n")
        tw.insert("end", f"  {time.strftime('%H:%M')}  ", "ts")
        tw.insert("end", f"你 → {nick}\n{nick}: {text}\n", "normal")
        tw.see("end"); tw.config(state="disabled")
        entry.delete(0, "end")
        try: self.sock.sendall(f"/to {nick} {text}".encode("utf-8"))
        except: self._add_system_message("❌ 发送失败", tw=self._pc_text)

    # ======================== UI 缩放 ========================

    def _on_window_resize(self, event):
        if event.widget != self.root: return
        if not getattr(self, 'chat_frame', None): return
        if self._resize_timer: self.root.after_cancel(self._resize_timer)
        self._resize_timer = self.root.after(150, self._apply_font_scaling)

    def _apply_font_scaling(self):
        if not getattr(self, 'msg_text', None): return
        w = self.root.winfo_width()
        scale = max(0.7, min(2.0, w / self._base_width))
        if abs(scale - self._scale) < 0.05: return
        self._scale = scale
        msg_size = max(10, int(MSG_FONT_SIZE * scale))
        self.msg_text.configure(font=("Segoe UI", msg_size))
        for tag, base in [("normal", msg_size), ("nickname_tag", (msg_size, "bold")),
                          ("system", (max(8, int(10 * scale)), "italic")),
                          ("timestamp", max(7, int(9 * scale)))]:
            self.msg_text.tag_configure(tag, font=("Segoe UI", *(base if isinstance(base, tuple) else (base,))))
        if hasattr(self, 'msg_entry'):
            self.msg_entry.configure(font=("Segoe UI", max(10, int(12 * scale))))
        self._update_user_list_display(self.online_users)

    # ======================== 用户列表 ========================

    def _parse_user_list(self, text):
        if "当前在线:" not in text: return
        raw = [u.strip() for u in text.split("当前在线:", 1)[1].split(",") if u.strip()]
        self.online_users = []; self._host_id = None
        for u in raw:
            is_host = u.startswith("👑"); u2 = u[1:].strip() if is_host else u
            nick, uid = u2, 0
            if "|" in u2:
                parts = u2.rsplit("|", 1); nick = parts[0].strip()
                try: uid = int(parts[1])
                except: pass
            if is_host: self._host_id = uid
            self.online_users.append((nick, uid))
        self._host_name = None
        if self._host_id:
            for n, i in self.online_users:
                if i == self._host_id: self._host_name = n; break
        self._update_user_list_display(self.online_users)

    def _update_user_list_display(self, users):
        if not getattr(self, 'user_list_inner', None): return
        try:
            for w in self.user_list_inner.winfo_children(): w.destroy()
        except: pass
        if not users:
            if getattr(self, 'user_count_label', None):
                self.user_count_label.configure(text="0 人在线")
            return
        ds = max(9, int(12 * self._scale)); ns = max(10, int(12 * self._scale))
        for nick, uid in users:
            row = ctk.CTkFrame(self.user_list_inner, fg_color="transparent")
            row.pack(fill="x", pady=1, padx=6)
            is_host = (uid == self._host_id)
            ctk.CTkLabel(row, text="●", font=("Segoe UI", ds),
                         text_color=HOST_GOLD if is_host else ONLINE_GREEN).pack(side="left", padx=(0, 5))
            lbl = ctk.CTkLabel(row, text=nick, font=("Segoe UI", ns), anchor="w",
                                cursor="hand2" if nick != self.nickname else "")
            lbl.pack(side="left", fill="x", expand=True)
            if nick != self.nickname:
                lbl.bind("<Button-3>", lambda e, n=nick: self._user_cmenu(e, n))
        self.user_count_label.configure(text=f"{len(users)} 人在线")

    def _user_cmenu(self, event, nick):
        m = tk.Menu(self.root, tearoff=False)
        m.add_command(label="私聊", command=lambda n=nick: self._start_private_chat(n))
        m.add_separator()
        if nick in self._blocked_users:
            m.add_command(label="取消屏蔽", command=lambda n=nick: self._toggle_block(n))
        else:
            m.add_command(label="屏蔽", command=lambda n=nick: self._toggle_block(n))
        try: m.post(event.x_root, event.y_root)
        finally: m.grab_release()

    def _update_users_from_join_leave(self, text):
        for kw, add in [("进入了聊天室", True), ("离开了聊天室", False)]:
            if kw not in text: continue
            raw = text.split(kw)[0].strip().lstrip("📢🔴 ").strip()
            if not raw or "|" not in raw: break
            parts = raw.rsplit("|", 1); nick = parts[0].strip()
            try: uid = int(parts[1])
            except: break
            if add: self.online_users.append((nick, uid))
            else: self.online_users = [(n, i) for n, i in self.online_users if i != uid]
            self._update_user_list_display(self.online_users); break

    # ======================== 断开 & 关闭 ========================

    def _disconnect(self):
        self.stop_threads = True; self.connected = False
        if self.sock:
            try: self.sock.shutdown(socket.SHUT_RDWR)
            except: pass
            try: self.sock.close()
            except: pass
            self.sock = None
        if hasattr(self, 'title_label'): self.title_label.configure(text="聊天室 — 已断开")
        if hasattr(self, 'status_bar'): self.status_bar.configure(fg_color=STATUS_RED)
        if hasattr(self, 'msg_entry'): self.msg_entry.configure(state="disabled")
        if hasattr(self, 'send_btn'): self.send_btn.configure(state="disabled")
        if self._is_host:
            try:
                import importlib
                _srv = importlib.import_module("tcp_chat.server")
                _srv.close_room()
            except: pass
            if hasattr(self, '_tunnel') and self._tunnel:
                try: self._tunnel.stop()
                except: pass

    def _on_close(self):
        self.stop_threads = True
        if self.sock:
            try: self.sock.sendall("/quit".encode("utf-8"))
            except: pass
            try: self.sock.close()
            except: pass
        if self._is_host:
            try:
                import importlib
                _srv = importlib.import_module("tcp_chat.server")
                _srv.close_room()
            except: pass
            if hasattr(self, '_tunnel') and self._tunnel:
                try: self._tunnel.stop()
                except: pass
        self.root.destroy()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 4:
        ChatClientUI(auto_connect=(sys.argv[1], int(sys.argv[2]), sys.argv[3])).run()
    else:
        ChatClientUI().run()
