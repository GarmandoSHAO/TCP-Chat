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
from .pages import (
    build_start_view,
    build_create_room_view,
    build_login_view,
    build_chat_view,
)

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

        # 状态
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

        # 构建启动页
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

    # ======================== 图标 ========================

    def _set_window_icon(self):
        try:
            img = tk.PhotoImage(width=16, height=16)
            for x in range(16):
                for y in range(16):
                    c = "#075e54"
                    if 3 <= x <= 12 and 3 <= y <= 12:
                        c = "#ffffff"
                    elif 4 <= x <= 11 and 4 <= y <= 11:
                        c = "#075e54"
                    img.put(c, (x, y))
            self.root.iconphoto(True, img)
            self._icon_img = img
        except Exception:
            pass

    # ======================== 页面切换 ========================

    def _clear_views(self, *skip):
        """隐藏所有视图"""
        for name in ("start_frame", "create_frame", "login_frame",
                     "loading_frame", "chat_frame"):
            if name in skip:
                continue
            f = getattr(self, name, None)
            if f:
                try:
                    f.pack_forget()
                except Exception:
                    pass

    def _show_start(self):
        self._clear_views()
        self.start_frame = build_start_view(
            self.root, self._go_create_config, self._on_join_room)

    def _go_create_config(self):
        self._clear_views()
        self.create_frame, self.create_entries = build_create_room_view(
            self.root, self._on_create_room, self._back_to_start)
        self._wan_entry = self.create_entries.get("外网IP")
        # 一进入创建页面就开始连隧道
        addr = self.create_entries["局域网IP:端口"].get()
        port = get("default_port", 8888)
        if ":" in addr:
            p = addr.rsplit(":", 1)[1]
            if p.isdigit():
                port = int(p)
        self._start_tunnel(port)

    def _back_to_start(self):
        if hasattr(self, 'create_frame'):
            self.create_frame.pack_forget()
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
        ctk.CTkLabel(self.loading_frame, text=text,
                     font=("Segoe UI", 14),
                     text_color="#888888",
                     bg_color=WHITE).pack(expand=True)

    def _switch_to_chat(self, welcome_msg, login_result):
        self.root.unbind("<Return>")
        win = get("window", {})
        self.root.geometry(f"{win.get('chat_width', 880)}x{win.get('chat_height', 640)}")
        self.root.minsize(700, 500)
        self.root.resizable(True, True)

        self._clear_views()
        chat = build_chat_view(self.root, self._send_message, self._disconnect)

        self.chat_frame = chat["frame"]
        self.msg_text = chat["msg_text"]
        self.msg_entry = chat["msg_entry"]
        self.status_dot = chat["status_dot"]
        self.title_label = chat["title_label"]
        self.user_list_inner = chat["user_list_inner"]
        self.user_count_label = chat["user_count"]
        self.send_btn = chat["send_btn"]

        # 拖拽
        make_draggable(chat["top_bar"], self._drag_data)

        self.title_label.configure(text=f"聊天室 — {self.nickname}")
        self._add_title_context_menu()
        self.connected = True

        # 房主进入聊天室后开放房间
        if self._is_host:
            try:
                import importlib
                _srv = importlib.import_module("tcp_chat.server")
                _srv.room_status = 1
            except Exception:
                pass

        self._add_system_message("🟢 已连接到聊天室")
        if login_result:
            self._display_message(login_result)

        self._build_command_menu()
        self.root.lift()
        self.root.focus_force()
        self.msg_entry.focus()

    # ======================== 创建房间 ========================

    def _on_create_room(self):
        nick = self.create_entries["昵称"].get().strip() or get("default_nickname", "用户")
        addr = self.create_entries["局域网IP:端口"].get().strip()
        port = get("default_port", 8888)
        if ":" in addr:
            parts = addr.rsplit(":", 1)
            if parts[1].isdigit():
                port = int(parts[1])
        self.nickname = nick
        self._is_host = True

        # 启动服务端（线程）
        import importlib
        _srv = importlib.import_module("tcp_chat.server")
        _srv.PORT = port
        self._server_thread = threading.Thread(
            target=_srv.start_server, daemon=True)
        self._server_thread.start()

        self._clear_views()
        self._show_loading("🚀 正在启动房间...")
        self._auto_connect("127.0.0.1", port, nick)

    def _start_tunnel(self, port, retries=2):
        """自动启动 bore 隧道（静默，失败不阻塞）"""
        # 确保旧服务端和旧隧道已停
        try:
            import importlib
            _srv = importlib.import_module("tcp_chat.server")
            _srv.server_running = False
            _srv.room_status = 0
        except Exception:
            pass
        if hasattr(self, '_tunnel') and self._tunnel:
            try:
                self._tunnel.stop()
            except Exception:
                pass
        from tcp_chat.tunnel import auto_tunnel
        tunnel = auto_tunnel(port)
        if not tunnel:
            return

        def _run(attempt=0):
            ok, msg = tunnel.start()
            if ok:
                self.root.after(0, lambda a=msg: self._finish_tunnel(a))
            elif attempt < retries:
                import time
                time.sleep(1)
                _run(attempt + 1)
            else:
                pass

        self._tunnel = tunnel
        threading.Thread(target=_run, daemon=True).start()

    def _finish_tunnel(self, addr):
        """隧道建立完成"""
        self._public_addr = addr
        if hasattr(self, '_wan_entry') and self._wan_entry:
            try:
                self._wan_entry.configure(text_color="#000000")  # 黑色
                self._wan_entry.delete(0, "end")
                self._wan_entry.insert(0, addr)
            except Exception:
                pass
        else:
            pass

    # ======================== 连接逻辑 ========================

    def _auto_connect(self, host, port, nickname):
        """自动连接（创建房间后用）"""
        self.root.after(300, lambda: self._connect_thread(host, port, nickname))

    def _do_connect(self):
        if self.connected:
            return
        addr = self.login_entries["地址:端口"].get().strip()
        nick = self.login_entries["昵称"].get().strip() or "匿名"
        host, port_str = addr, str(get("default_port", 8888))
        if ":" in addr and not addr.startswith("["):
            parts = addr.rsplit(":", 1)
            host = parts[0]
            if parts[1].isdigit():
                port_str = parts[1]
        try:
            port = int(port_str)
        except ValueError:
            self.login_status.configure(text="❌ 地址格式错误 (host:port)")
            return
        self.nickname = nick
        self.login_status.configure(text="⏳ 连接中...", text_color="#1976d2")
        self.connect_btn.configure(state="disabled")
        self.scan_btn.configure(state="disabled")
        t = threading.Thread(target=self._connect_thread,
                             args=(host, port, nick), daemon=True)
        t.start()

    def _connect_thread(self, host, port, nick):
        try:
            sock, welcome, login_result = connect_server(host, port, nick)

            self.sock = sock
            self.connected = True
            self.msg_queue.put(("CONNECTED", (welcome, login_result)))
            self.stop_threads = False
            t = threading.Thread(target=start_receive,
                                 args=(sock, self.msg_queue, lambda: self.stop_threads),
                                 daemon=True)
            t.start()
        except socket.timeout:
            self.msg_queue.put(("ERROR", "连接超时，请检查服务器地址和端口"))
        except ConnectionRefusedError:
            self.msg_queue.put(("ERROR", "连接被拒绝，服务器可能未启动"))
        except socket.gaierror:
            self.msg_queue.put(("ERROR", f"无法解析地址 \"{host}\""))
        except Exception as e:
            self.msg_queue.put(("ERROR", f"连接失败：{e}"))

    def _scan_network(self):
        self.login_status.configure(text="🔍 正在扫描... 剩余 5 秒", text_color="#1976d2")
        self.scan_btn.configure(state="disabled")
        self._scan_start = time.time()
        self._scan_tick()
        t = threading.Thread(target=self._scan_thread, daemon=True)
        t.start()

    def _scan_tick(self):
        if self.scan_btn.cget("state") == "normal":
            return
        elapsed = time.time() - self._scan_start
        remaining = max(0, 5 - int(elapsed))
        self.login_status.configure(
            text=f"🔍 正在扫描... 剩余 {remaining} 秒", text_color="#1976d2")
        self.root.after(200, self._scan_tick)

    def _scan_thread(self):
        rooms = scan_network(timeout=5)
        if rooms:
            ip = list(rooms.keys())[0]
            name, port, status = rooms[ip]
            self.msg_queue.put(("SCAN_RESULT", (name, ip, port, status)))
        else:
            self.msg_queue.put(("SCAN_FAIL", None))

    # ======================== 命令菜单 ========================

    def _build_command_menu(self):
        """输入 / 后弹出指令菜单"""
        self.cmd_defs = [
            ("/help", "显示帮助"),
            ("/list", "查看在线用户"),
            ("/to <昵称> <消息>", "私聊某人"),
            ("/quit", "退出聊天室"),
            ("/exit", "退出聊天室"),
        ]
        self.cmd_popup = ctk.CTkToplevel(self.root)
        self.cmd_popup.overrideredirect(True)
        self.cmd_popup.attributes("-topmost", True)
        self.cmd_popup.withdraw()

        popup_frame = ctk.CTkFrame(self.cmd_popup, corner_radius=8,
                                   fg_color="white", border_width=1,
                                   border_color="#d0d0d0")
        popup_frame.pack(fill="both", expand=True)
        self.cmd_listbox = tk.Listbox(popup_frame, font=("Segoe UI", 11),
                                       bd=0, highlightthickness=0,
                                       bg="#ffffff", fg="#333333",
                                       activestyle="none",
                                       exportselection=False,
                                       width=30, height=5)
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
        if self.cmd_listbox.size() == 0:
            return
        x = self.msg_entry.winfo_rootx()
        y = self.msg_entry.winfo_rooty() - self.cmd_popup.winfo_reqheight() - 6
        self.cmd_popup.geometry(f"+{x}+{y}")
        self.cmd_popup.deiconify()
        self._cmd_selected = -1
        self.cmd_listbox.selection_clear(0, tk.END)

    def _cmd_hide(self):
        self.cmd_popup.withdraw()

    def _on_cmd_key(self, event):
        if event.keysym in ("Up", "Down", "Left", "Right", "Return", "Escape"):
            return
        self.root.after_idle(self._cmd_filter)

    def _cmd_filter(self):
        text = self.msg_entry.get()
        if not text.startswith("/") or " " in text:
            self._cmd_hide()
            return
        partial = text.lower()
        self.cmd_listbox.delete(0, tk.END)
        for cmd, desc in self.cmd_defs:
            if cmd.lower().startswith(partial):
                display = f"{cmd:<22s}{desc}"
                self.cmd_listbox.insert(tk.END, display)
        if self.cmd_listbox.size() > 0:
            self._cmd_show()
        else:
            self._cmd_hide()

    def _on_cmd_up(self, event):
        if not self.cmd_popup.winfo_viewable():
            return
        size = self.cmd_listbox.size()
        if size == 0:
            return
        self._cmd_selected = (self._cmd_selected - 1) % size if self._cmd_selected > 0 else size - 1
        self.cmd_listbox.selection_clear(0, tk.END)
        self.cmd_listbox.selection_set(self._cmd_selected)
        self.cmd_listbox.activate(self._cmd_selected)
        return "break"

    def _on_cmd_down(self, event):
        if not self.cmd_popup.winfo_viewable():
            return
        size = self.cmd_listbox.size()
        if size == 0:
            return
        self._cmd_selected = (self._cmd_selected + 1) % size if self._cmd_selected < size - 1 else 0
        self.cmd_listbox.selection_clear(0, tk.END)
        self.cmd_listbox.selection_set(self._cmd_selected)
        self.cmd_listbox.activate(self._cmd_selected)
        return "break"

    def _on_cmd_click(self, event):
        idx = self.cmd_listbox.nearest(event.y)
        if idx >= 0:
            self._cmd_selected = idx
            self.cmd_listbox.selection_clear(0, tk.END)
            self.cmd_listbox.selection_set(idx)

    def _on_cmd_confirm(self, event):
        self._cmd_insert_selected()

    def _cmd_insert_selected(self):
        if self._cmd_selected < 0 or self._cmd_selected >= self.cmd_listbox.size():
            return
        display = self.cmd_listbox.get(self._cmd_selected)
        cmd = display.split()[0]
        self.msg_entry.delete(0, "end")
        self.msg_entry.insert(0, cmd + " ")
        self.msg_entry.icursor(tk.END)
        self._cmd_hide()
        self.msg_entry.focus_set()

    def _add_title_context_menu(self):
        """标题标签右键菜单：退出房间 / 查看IP"""
        self._ctx_menu = tk.Menu(self.root, tearoff=False,
                                 font=("Segoe UI", 10),
                                 bg="white", fg="#333333",
                                 activebackground="#e8f5e9",
                                 activeforeground="#075e54")
        self._ctx_menu.add_command(label="🚪 退出房间",
                                   command=self._disconnect)
        self._ctx_menu.add_separator()
        self._ctx_menu.add_command(label="🌐 查看本机 IP",
                                   command=self._show_ip)

        self.title_label.bind("<Button-3>", self._show_context_menu)
        self.title_label.bind("<Button-2>", self._show_context_menu)  # macOS

    def _show_context_menu(self, event):
        """显示右键菜单"""
        try:
            self._ctx_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self._ctx_menu.grab_release()

    def _show_ip(self):
        """弹出 IP 窗口，按钮点击复制到剪贴板"""
        from tcp_chat.config import get_local_ip, get
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
            win.clipboard_clear()
            win.clipboard_append(text)
            hint.configure(text="✅ 复制成功")
            win.after(1500, lambda: hint.configure(text=""))

        def make_row(label, text):
            row = ctk.CTkFrame(frame, fg_color="transparent")
            row.pack(fill="x", pady=4)
            ctk.CTkLabel(row, text=label, font=("Segoe UI", 12),
                         text_color="#333333").pack(side="left", padx=(0, 8))
            ctk.CTkButton(row, text=text, font=("Segoe UI", 12),
                           width=0, height=28, corner_radius=5,
                           fg_color="#e0e0e0", text_color="#333333",
                           hover_color="#d0d0d0",
                           command=lambda t=text: copy(t)).pack(side="left")

        make_row("局域网 IP", ip)
        if pub:
            make_row("外网地址", pub)

        hint = ctk.CTkLabel(frame, text="", font=("Segoe UI", 10),
                            text_color="#2e7d32")
        hint.pack(pady=(4, 2))

        ctk.CTkButton(frame, text="关闭",
                       font=("Segoe UI", 11),
                       width=70, height=28, corner_radius=5,
                       fg_color="#075e54",
                       command=win.destroy).pack()

    def _on_return(self, event):
        """回车：菜单打开时选命令，否则发送消息"""
        if hasattr(self, 'cmd_popup') and self.cmd_popup.winfo_viewable():
            if self._cmd_selected >= 0:
                self._cmd_insert_selected()
                return "break"
        return self._send_message() or "break"

    # ======================== 消息收发 ========================

    def _send_message(self):
        if not self.connected or not self.sock:
            return
        text = self.msg_entry.get().strip()
        if not text:
            return
        display_msg = f"💬 [{self.nickname}]: {text}"
        self._add_chat_message(display_msg, is_self=True)
        try:
            self.sock.sendall(text.encode("utf-8"))
            self.msg_entry.delete(0, "end")
            if text.strip().lower() in ("/quit", "/exit"):
                self._add_system_message("正在退出聊天室...")
                self._disconnect()
        except OSError:
            self._add_system_message("❌ 发送失败")
            self._disconnect()

    # ======================== UI 更新 ========================

    def _process_queue(self):
        try:
            while True:
                msg_type, data = self.msg_queue.get_nowait()
                if msg_type == "CONNECTED":
                    self._switch_to_chat(*data)
                elif msg_type == "MESSAGE":
                    self._display_message(data)
                elif msg_type == "ERROR":
                    if hasattr(self, 'login_status'):
                        self.login_status.configure(text=f"❌ {data}")
                    if hasattr(self, 'connect_btn'):
                        self.connect_btn.configure(state="normal")
                    if hasattr(self, 'scan_btn'):
                        self.scan_btn.configure(state="normal")
                elif msg_type == "DISCONNECTED":
                    self._add_system_message(f"🔴 {data}")
                    self.connected = False
                    if self.sock:
                        try:
                            self.sock.close()
                        except Exception:
                            pass
                    if hasattr(self, 'title_label'):
                        self.title_label.configure(text="聊天室 — 已断开")
                    if hasattr(self, 'status_dot'):
                        self.status_dot.configure(text_color=STATUS_RED)
                elif msg_type == "SCAN_RESULT":
                    name, ip, port = data
                    self.login_entries["地址:端口"].delete(0, "end")
                    self.login_entries["地址:端口"].insert(0, f"{ip}:{port}")
                    self.login_status.configure(
                        text=f"✅ 发现 \"{name}\" — 已填入地址", text_color="#2e7d32")
                    self.scan_btn.configure(state="normal")
                elif msg_type == "SCAN_FAIL":
                    if data:
                        self.login_status.configure(text=f"❌ 扫描失败：{data}")
                    else:
                        self.login_status.configure(text="❌ 未发现任何房间")
                    self.scan_btn.configure(state="normal")
        except queue.Empty:
            pass
        if not self.stop_threads:
            self.root.after(100, self._process_queue)

    def _display_message(self, raw_msg):
        raw_msg = raw_msg.strip().replace("\r", "")
        if not raw_msg:
            return

        if raw_msg.startswith("💬 [私聊]("):
            self._add_private_message(raw_msg)
        elif raw_msg.startswith("📢") or raw_msg.startswith("🔴"):
            display = re.sub(r'\|(\d+)', '', raw_msg)
            self._add_system_message(display)
            self._update_users_from_join_leave(raw_msg)
        elif any(raw_msg.startswith(p) for p in ("✅", "❌", "🟢")):
            self._add_system_message(raw_msg)
        elif raw_msg.startswith("当前在线"):
            self._parse_user_list(raw_msg)
            display = re.sub(r'\|(\d+)', '', raw_msg) if "|" in raw_msg else raw_msg
            self._add_system_message(display, skip_parse=True)
        elif "==========" in raw_msg:
            self._add_system_message(raw_msg)
        else:
            self._add_chat_message(raw_msg)

    def _add_system_message(self, text, skip_parse=False):
        display = re.sub(r'\|(\d+)', '', text)
        self.msg_text.config(state="normal")
        if self.msg_text.get("end-2c", "end-1c") != "":
            self.msg_text.insert("end", "\n")
        self.msg_text.insert("end", display, ("system",))
        self.msg_text.see("end")
        self.msg_text.config(state="disabled")
        if "当前在线:" in text and not skip_parse:
            self._parse_user_list(text)

    def _add_chat_message(self, text, is_self=False):
        self.msg_text.config(state="normal")
        if self.msg_text.get("end-2c", "end-1c") != "":
            self.msg_text.insert("end", "\n")
        ts = time.strftime("%H:%M")
        self.msg_text.insert("end", f"  {ts}  ", ("timestamp",))
        if text.startswith("💬 ["):
            end = text.find("]", 3)
            if end > 0:
                nick = text[3:end]
                content = text[end + 2:]
                display_nick = f"{nick} (我)" if is_self else nick
                self.msg_text.insert("end", display_nick, ("nickname_tag",))
                self.msg_text.insert("end", f"\n{content}", ("normal",))
            else:
                self.msg_text.insert("end", text, ("normal",))
        else:
            self.msg_text.insert("end", text, ("normal",))
        self.msg_text.see("end")
        self.msg_text.config(state="disabled")

    def _add_private_message(self, text):
        self.msg_text.config(state="normal")
        if self.msg_text.get("end-2c", "end-1c") != "":
            self.msg_text.insert("end", "\n")
        ts = time.strftime("%H:%M")
        self.msg_text.insert("end", f"  {ts}  ", ("timestamp",))
        self.msg_text.insert("end", text, ("private",))
        self.msg_text.see("end")
        self.msg_text.config(state="disabled")

    def _parse_user_list(self, text):
        if "当前在线:" not in text:
            return
        users_part = text.split("当前在线:", 1)[1].strip()
        raw = [u.strip() for u in users_part.split(",") if u.strip()]
        self.online_users = []
        self._host_id = None
        for raw_u in raw:
            is_host = raw_u.startswith("👑")
            u = raw_u[1:].strip() if is_host else raw_u
            nick, uid = u, 0
            if "|" in u:
                parts = u.rsplit("|", 1)
                nick = parts[0].strip()
                try:
                    uid = int(parts[1])
                except ValueError:
                    pass
            if is_host:
                self._host_id = uid
            self.online_users.append((nick, uid))
        self._host_name = None
        if self._host_id:
            for n, i in self.online_users:
                if i == self._host_id:
                    self._host_name = n
                    break
        self._update_user_list_display(self.online_users)

    def _update_user_list_display(self, users):
        for w in self.user_list_inner.winfo_children():
            w.destroy()
        if not users:
            self.user_count_label.configure(text="0 人在线")
            return
        dot_size = max(9, int(12 * self._scale))
        name_size = max(10, int(12 * self._scale))
        for nick, uid in users:
            row = ctk.CTkFrame(self.user_list_inner, fg_color="transparent")
            row.pack(fill="x", pady=1, padx=6)
            is_host = (uid == self._host_id)
            dot_color = HOST_GOLD if is_host else ONLINE_GREEN
            ctk.CTkLabel(row, text="●", font=("Segoe UI", dot_size),
                         text_color=dot_color).pack(side="left", padx=(0, 5))
            ctk.CTkLabel(row, text=nick, font=("Segoe UI", name_size),
                         anchor="w").pack(side="left", fill="x", expand=True)
            if is_host:
                ctk.CTkLabel(row, text="👑", font=("Segoe UI", dot_size),
                             bg_color="transparent").pack(side="left", padx=(2, 0))
        self.user_count_label.configure(text=f"{len(users)} 人在线")

    def _update_users_from_join_leave(self, text):
        for keyword, add in [("进入了聊天室", True), ("离开了聊天室", False)]:
            if keyword not in text:
                continue
            raw = text.split(keyword)[0].strip().lstrip("📢🔴 ").strip()
            if not raw or "|" not in raw:
                break
            parts = raw.rsplit("|", 1)
            nick = parts[0].strip()
            try:
                uid = int(parts[1])
            except ValueError:
                break
            if add:
                self.online_users.append((nick, uid))
            else:
                self.online_users = [(n, i) for n, i in self.online_users if i != uid]
            self._update_user_list_display(self.online_users)
            break

    # ======================== 窗口缩放 ========================

    def _on_window_resize(self, event):
        if event.widget != self.root:
            return
        if not getattr(self, 'chat_frame', None):
            return
        if self._resize_timer:
            self.root.after_cancel(self._resize_timer)
        self._resize_timer = self.root.after(150, self._apply_font_scaling)

    def _apply_font_scaling(self):
        if not getattr(self, 'msg_text', None):
            return
        w = self.root.winfo_width()
        scale = max(0.7, min(2.0, w / self._base_width))
        if abs(scale - self._scale) < 0.05:
            return
        self._scale = scale
        msg_size = max(10, int(MSG_FONT_SIZE * scale))
        self.msg_text.configure(font=("Segoe UI", msg_size))
        for tag, base in [("normal", msg_size), ("nickname_tag", (msg_size, "bold")),
                          ("system", (max(8, int(10 * scale)), "italic")),
                          ("timestamp", max(7, int(9 * scale)))]:
            if isinstance(base, int):
                self.msg_text.tag_configure(tag, font=("Segoe UI", base))
            else:
                self.msg_text.tag_configure(tag, font=("Segoe UI", *base))
        if hasattr(self, 'msg_entry'):
            self.msg_entry.configure(font=("Segoe UI", max(10, int(12 * scale))))
        self._update_user_list_display(self.online_users)

    # ======================== 断开与关闭 ========================

    def _disconnect(self):
        self.stop_threads = True
        self.connected = False
        if self.sock:
            try:
                self.sock.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None
        if hasattr(self, 'title_label'):
            self.title_label.configure(text="聊天室 — 已断开")
        if hasattr(self, 'status_dot'):
            self.status_dot.configure(text_color=STATUS_RED)
        if hasattr(self, 'msg_entry'):
            self.msg_entry.configure(state="disabled")
        if hasattr(self, 'send_btn'):
            self.send_btn.configure(state="disabled")
        # 房主断开时关闭房间 + 隧道
        if self._is_host:
            try:
                import importlib
                _srv = importlib.import_module("tcp_chat.server")
                _srv.close_room()
            except Exception:
                pass
            if hasattr(self, '_tunnel') and self._tunnel:
                try:
                    self._tunnel.stop()
                except Exception:
                    pass
    def _on_close(self):
        self.stop_threads = True
        if self.sock:
            try:
                self.sock.sendall("/quit".encode("utf-8"))
            except Exception:
                pass
            try:
                self.sock.close()
            except Exception:
                pass
        # 房主关闭窗口时也停服务端
        if self._is_host:
            try:
                import importlib
                _srv = importlib.import_module("tcp_chat.server")
                _srv.server_running = False
            except Exception:
                pass
            if hasattr(self, '_tunnel') and self._tunnel:
                try:
                    self._tunnel.stop()
                except Exception:
                    pass
        self.root.destroy()

    def run(self):
        self.root.mainloop()
