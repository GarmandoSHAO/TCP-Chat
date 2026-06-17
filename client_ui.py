"""
☆ TCP 聊天室 — GUI 客户端 (CustomTkinter) ☆
现代风格界面，支持消息显示、在线用户、私聊等
"""
import customtkinter as ctk
import tkinter as tk  # 仅用于 Text 标签功能
import socket
import threading
import time
import queue

# ========== 配置 ==========
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8888
DISCOVERY_PORT = 9999

ctk.set_appearance_mode("light")
ctk.set_default_color_theme("green")


class ChatClientUI:
    """聊天室 GUI 客户端（CustomTkinter）"""

    # ---------- 颜色 ----------
    SYSTEM_FG = "#667781"
    PRIVATE_FG = "#8e24aa"
    ERROR_FG = "#d32f2f"
    NICKNAME_FG = "#075e54"
    TIMESTAMP_FG = "#999999"

    def __init__(self):
        self.root = ctk.CTk()
        self.root.title("TCP 聊天室")
        self.root.geometry("420x480")
        self.root.resizable(False, False)  # 登录界面固定大小

        # ---- 网络状态 ----
        self.sock = None
        self.nickname = ""
        self.connected = False
        self.msg_queue = queue.Queue()
        self.stop_threads = False
        self.online_users = []  # 本地维护的用户列表

        # ---- 构建界面 ----
        self._build_login_view()

        # ---- 轮询 ----
        self.root.after(100, self._process_queue)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ======================== 登录界面 ========================

    def _build_login_view(self):
        """登录界面（居中卡片式）"""
        self.login_frame = ctk.CTkFrame(self.root, fg_color="transparent")
        self.login_frame.pack(fill="both", expand=True)

        # 居中卡片（用 pack 替代 place，保证焦点事件正常）
        card = ctk.CTkFrame(self.login_frame, fg_color="white",
                            corner_radius=16, border_width=0)
        card.pack(expand=True)

        # 图标 + 标题
        ctk.CTkLabel(card, text="💬", font=("Segoe UI", 40)).pack(pady=(30, 0))
        ctk.CTkLabel(card, text="TCP 聊天室", font=("Segoe UI", 22, "bold"),
                     text_color=("#1a1a1a", "#ffffff")).pack(pady=(4, 2))
        ctk.CTkLabel(card, text="连接到聊天服务器",
                     font=("Segoe UI", 11),
                     text_color=("#888888", "#aaaaaa")).pack(pady=(0, 24))

        # 表单
        form = ctk.CTkFrame(card, fg_color="transparent")
        form.pack(padx=40, pady=(0, 20))

        fields = [
            ("服务器地址", DEFAULT_HOST, 20),
            ("端口", str(DEFAULT_PORT), 8),
            ("昵称", "", 20),
        ]
        self.login_entries = {}

        for label, default, width in fields:
            row = ctk.CTkFrame(form, fg_color="transparent")
            row.pack(fill="x", pady=6)

            ctk.CTkLabel(row, text=label, width=75, anchor="e",
                         font=("Segoe UI", 11),
                         text_color=("#555555", "#cccccc")).pack(side="left", padx=(0, 10))

            # 用 tk.Entry 代替 CTkEntry，避免部分 Windows 上文字输入不刷新问题
            entry_frame = ctk.CTkFrame(row, fg_color=("#e8e8e8", "#333333"),
                                       corner_radius=8, height=32)
            entry_frame.pack(side="left", fill="x", expand=True)
            entry_frame.pack_propagate(False)

            entry = tk.Entry(entry_frame, font=("Segoe UI", 12),
                             bd=0, highlightthickness=0,
                             bg="#e8e8e8", fg="#000000",
                             insertbackground="#000000",
                             relief="flat")
            entry.insert(0, default)
            entry.pack(fill="both", expand=True, padx=8, pady=2)
            self.login_entries[label] = entry

            # 每个输入框单独绑定回车
            entry.bind("<Return>", lambda e: self._do_connect())

        # 按钮
        btn_row = ctk.CTkFrame(card, fg_color="transparent")
        btn_row.pack(pady=(6, 20))

        self.scan_btn = ctk.CTkButton(btn_row, text="🔍 扫描局域网",
                                      font=("Segoe UI", 11),
                                      width=130, height=34,
                                      corner_radius=8,
                                      fg_color=("#e8e8e8", "#333333"),
                                      text_color=("#333333", "#ffffff"),
                                      hover_color=("#d0d0d0", "#444444"),
                                      command=self._scan_network)
        self.scan_btn.pack(side="left", padx=(0, 10))

        self.connect_btn = ctk.CTkButton(btn_row, text="🚀 连接",
                                         font=("Segoe UI", 12, "bold"),
                                         width=120, height=34,
                                         corner_radius=8,
                                         command=self._do_connect)
        self.connect_btn.pack(side="left")

        # 状态
        self.login_status = ctk.CTkLabel(card, text="", font=("Segoe UI", 10),
                                         text_color=self.ERROR_FG)
        self.login_status.pack(pady=(0, 24))

        # 强制刷新并在窗口显示后聚焦昵称输入框
        self.root.update_idletasks()
        self.root.after(100, lambda: self.login_entries["昵称"].focus_set())

    # ======================== 聊天界面 ========================

    def _build_chat_view(self):
        """聊天主界面"""
        self.chat_frame = ctk.CTkFrame(self.root, fg_color="transparent")
        self.chat_frame.pack(fill="both", expand=True)

        # ---- 顶部栏 ----
        title_bar = ctk.CTkFrame(self.chat_frame, height=48, corner_radius=0,
                                 fg_color=("#075e54", "#1a1a2e"))
        title_bar.pack(fill="x")
        title_bar.pack_propagate(False)

        self.status_dot = ctk.CTkLabel(title_bar, text="●",
                                        font=("Segoe UI", 16),
                                        text_color="#76d275")
        self.status_dot.pack(side="left", padx=(14, 2))

        self.title_label = ctk.CTkLabel(title_bar,
                                         text="聊天室 — 连接中...",
                                         font=("Segoe UI", 14, "bold"),
                                         text_color="white")
        self.title_label.pack(side="left", padx=4)

        self.disconnect_btn = ctk.CTkButton(title_bar, text="✕ 断开",
                                             font=("Segoe UI", 11),
                                             width=70, height=28,
                                             corner_radius=14,
                                             fg_color="transparent",
                                             text_color="white",
                                             hover_color=("#005048", "#2a2a4e"),
                                             command=self._disconnect)
        self.disconnect_btn.pack(side="right", padx=14)

        # ---- 主体 ----
        main_area = ctk.CTkFrame(self.chat_frame, fg_color="transparent")
        main_area.pack(fill="both", expand=True, padx=0, pady=0)

        # ====== 左侧：消息 ======
        msg_container = ctk.CTkFrame(main_area, fg_color="transparent")
        msg_container.pack(side="left", fill="both", expand=True, padx=(0, 0))

        # 分割线
        separator = ctk.CTkFrame(main_area, width=1, fg_color="#d0d0d0",
                                 corner_radius=0)
        separator.pack(side="left", fill="y")

        # 使用 tk.Text 内嵌于 CTkFrame（保留彩色标签功能）
        msg_frame = ctk.CTkFrame(msg_container, fg_color="white", corner_radius=0)
        msg_frame.pack(fill="both", expand=True)

        # 用 grid 布局 text + scrollbar，避免显示/隐藏滚动条时布局错位
        msg_frame.grid_rowconfigure(0, weight=1)
        msg_frame.grid_columnconfigure(0, weight=1)

        self.msg_text = tk.Text(msg_frame,
                                font=("Segoe UI", 10),
                                wrap="word",
                                state="disabled",
                                bd=0, padx=14, pady=10,
                                bg="#ffffff",
                                highlightthickness=0)
        self.msg_text.grid(row=0, column=0, sticky="nsew")

        # 配置标签
        self.msg_text.tag_configure("system", foreground=self.SYSTEM_FG,
                                    font=("Segoe UI", 9, "italic"))
        self.msg_text.tag_configure("private", foreground=self.PRIVATE_FG,
                                    font=("Segoe UI", 10))
        self.msg_text.tag_configure("error", foreground=self.ERROR_FG,
                                    font=("Segoe UI", 10, "bold"))
        self.msg_text.tag_configure("timestamp", foreground=self.TIMESTAMP_FG,
                                    font=("Segoe UI", 8))
        self.msg_text.tag_configure("nickname_tag", foreground=self.NICKNAME_FG,
                                    font=("Segoe UI", 10, "bold"))
        self.msg_text.tag_configure("normal", foreground="#000000",
                                    font=("Segoe UI", 10))

        # 滚动条（自动隐藏：内容少于一屏时隐藏 + 停止滚动后慢慢淡去）
        scrollbar = ctk.CTkScrollbar(msg_frame, command=self.msg_text.yview,
                                     orientation="vertical",
                                     corner_radius=6)
        scrollbar.grid(row=0, column=1, sticky="ns", padx=(0, 2))
        self._scrollbar_timer = None

        def _show_scrollbar_temp():
            """滚轮滚动时临时显示滚动条，1.5s 后隐藏"""
            first, last = self.msg_text.yview()
            need_show = (first != "0.0" or last != "1.0")
            if need_show:
                scrollbar.grid()
            # 取消之前定时器
            if self._scrollbar_timer:
                self.root.after_cancel(self._scrollbar_timer)
                self._scrollbar_timer = None
            if need_show:
                self._scrollbar_timer = self.root.after(1500, scrollbar.grid_remove)

        def _on_text_scroll(first, last):
            """文本视图变化时更新滑块位置，内容一屏内直接隐藏"""
            scrollbar.set(first, last)
            if first == "0.0" and last == "1.0":
                if self._scrollbar_timer:
                    self.root.after_cancel(self._scrollbar_timer)
                    self._scrollbar_timer = None
                scrollbar.grid_remove()

        self.msg_text.config(yscrollcommand=_on_text_scroll)
        # 初始隐藏
        scrollbar.grid_remove()

        # 鼠标滚轮绑定
        def _on_mousewheel(event):
            self.msg_text.yview_scroll(int(-1 * event.delta / 120), "units")
            _show_scrollbar_temp()
            return "break"
        self.msg_text.bind("<MouseWheel>", _on_mousewheel)
        msg_frame.bind("<MouseWheel>", _on_mousewheel)

        # ====== 右侧：用户列表 ======
        user_frame = ctk.CTkFrame(main_area, width=190, fg_color="white",
                                  corner_radius=0, border_width=0)
        user_frame.pack(side="right", fill="y")
        user_frame.pack_propagate(False)

        self._build_user_panel(user_frame)

        # ---- 底部输入 ----
        input_bar = ctk.CTkFrame(self.chat_frame, height=56, fg_color="transparent",
                                 corner_radius=0)
        input_bar.pack(fill="x", padx=10, pady=(6, 10))
        input_bar.pack_propagate(False)

        self.msg_entry = ctk.CTkEntry(input_bar, font=("Segoe UI", 12),
                                       height=38, corner_radius=20,
                                       placeholder_text="输入消息...")
        self.msg_entry.pack(side="left", fill="both", expand=True, padx=(0, 8))
        self.msg_entry.bind("<Return>", lambda e: self._send_message() or "break")

        self.send_btn = ctk.CTkButton(input_bar, text="发送",
                                       font=("Segoe UI", 12, "bold"),
                                       width=80, height=38,
                                       corner_radius=20,
                                       command=self._send_message)
        self.send_btn.pack(side="left")

    def _build_user_panel(self, parent):
        """右侧用户列表面板（Canvas + CTkLabel，支持绿点和自动隐藏滚动条）"""
        header_frame = ctk.CTkFrame(parent, fg_color="transparent")
        header_frame.pack(fill="x", padx=14, pady=(16, 2))

        ctk.CTkLabel(header_frame, text="🟢 在线用户",
                     font=("Segoe UI", 12, "bold"),
                     text_color=("#075e54", "#ffffff")).pack(anchor="w")

        self.user_count_label = ctk.CTkLabel(header_frame, text="0 人在线",
                                              font=("Segoe UI", 10),
                                              text_color=("#999999", "#888888"))
        self.user_count_label.pack(anchor="w", pady=(2, 0))

        # 容器
        list_container = ctk.CTkFrame(parent, fg_color="transparent")
        list_container.pack(fill="both", expand=True, padx=6, pady=(6, 6))
        list_container.grid_rowconfigure(0, weight=1)
        list_container.grid_columnconfigure(0, weight=1)

        # Canvas 做滚动容器
        canvas = tk.Canvas(list_container, bd=0, highlightthickness=0,
                           bg="#ffffff")
        canvas.grid(row=0, column=0, sticky="nsew")

        # 内层 Frame 放用户行
        self.user_list_inner = ctk.CTkFrame(canvas, fg_color="transparent")
        canvas.create_window((0, 0), window=self.user_list_inner, anchor="nw",
                             tags="inner")

        # 滚动区域自适应
        def _configure_inner(event):
            canvas.configure(scrollregion=canvas.bbox("all"))
            # 让 inner 宽度始终等于 canvas 宽度
            canvas.itemconfig("inner", width=canvas.winfo_width())
        self.user_list_inner.bind("<Configure>", _configure_inner)
        canvas.bind("<Configure>", _configure_inner)

        # 自动隐藏滚动条
        user_scroll = ctk.CTkScrollbar(list_container, orientation="vertical",
                                       command=canvas.yview, corner_radius=6)
        user_scroll.grid(row=0, column=1, sticky="ns")
        user_scroll.grid_remove()
        self._user_scroll_timer = None

        def _user_scroll_show():
            first, last = canvas.yview()
            if first != "0.0" or last != "1.0":
                user_scroll.grid()

        def _user_scroll_hide_delayed():
            if self._user_scroll_timer:
                self.root.after_cancel(self._user_scroll_timer)
            self._user_scroll_timer = self.root.after(1500, user_scroll.grid_remove)

        def _on_user_scroll(first, last):
            user_scroll.set(first, last)
            if first == "0.0" and last == "1.0":
                if self._user_scroll_timer:
                    self.root.after_cancel(self._user_scroll_timer)
                    self._user_scroll_timer = None
                user_scroll.grid_remove()

        def _on_user_mousewheel(event):
            canvas.yview_scroll(int(-1 * event.delta / 120), "units")
            _user_scroll_show()
            _user_scroll_hide_delayed()
            return "break"

        canvas.configure(yscrollcommand=_on_user_scroll)
        canvas.bind("<MouseWheel>", _on_user_mousewheel)
        list_container.bind("<MouseWheel>", _on_user_mousewheel)

    def _update_user_list_display(self, users):
        """重建用户列表"""
        for w in self.user_list_inner.winfo_children():
            w.destroy()

        if not users:
            self.user_count_label.configure(text="0 人在线")
            return

        for user in users:
            row = ctk.CTkFrame(self.user_list_inner, fg_color="transparent")
            row.pack(fill="x", pady=1, padx=6)

            # 绿色圆点
            ctk.CTkLabel(row, text="●", font=("Segoe UI", 12),
                         text_color="#4caf50").pack(side="left", padx=(0, 5))
            # 用户名
            ctk.CTkLabel(row, text=user, font=("Segoe UI", 11),
                         anchor="w").pack(side="left", fill="x", expand=True)

        self.user_count_label.configure(text=f"{len(users)} 人在线")

        self.user_count_label.configure(text=f"{len(users)} 人在线")

    # ======================== 连接逻辑 ========================

    def _do_connect(self):
        # 防止重复连接（切换聊天后按回车误触发）
        if self.connected:
            return
        host = self.login_entries["服务器地址"].get().strip()
        port_str = self.login_entries["端口"].get().strip()
        nick = self.login_entries["昵称"].get().strip()

        if not host:
            self.login_status.configure(text="❌ 请输入服务器地址")
            return
        try:
            port = int(port_str)
        except ValueError:
            self.login_status.configure(text="❌ 端口必须是数字")
            return
        if not nick:
            self.login_status.configure(text="❌ 请输入昵称")
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
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect((host, port))
            data = sock.recv(4096)
            welcome = data.decode("utf-8")
            sock.sendall(nick.encode("utf-8"))
            data = sock.recv(4096)
            login_result = data.decode("utf-8")

            self.sock = sock
            self.connected = True
            self.msg_queue.put(("CONNECTED", (welcome, login_result)))

            self.stop_threads = False
            t = threading.Thread(target=self._receive_thread, daemon=True)
            t.start()

        except socket.timeout:
            self.msg_queue.put(("ERROR", "连接超时，请检查服务器地址和端口"))
        except ConnectionRefusedError:
            self.msg_queue.put(("ERROR", "连接被拒绝，服务器可能未启动"))
        except socket.gaierror:
            self.msg_queue.put(("ERROR", f"无法解析地址 \"{host}\""))
        except Exception as e:
            self.msg_queue.put(("ERROR", f"连接失败：{e}"))

    def _receive_thread(self):
        while not self.stop_threads:
            try:
                self.sock.settimeout(0.5)
                data = self.sock.recv(4096)
                if not data:
                    self.msg_queue.put(("DISCONNECTED", "服务器已关闭连接"))
                    break
                self.msg_queue.put(("MESSAGE", data.decode("utf-8")))
            except socket.timeout:
                continue
            except (ConnectionResetError, ConnectionAbortedError, OSError):
                if not self.stop_threads:
                    self.msg_queue.put(("DISCONNECTED", "与服务器的连接已断开"))
                break

    def _scan_network(self):
        self.scan_start_time = time.time()
        self.login_status.configure(text="🔍 正在扫描... 剩余 5 秒", text_color="#1976d2")
        self.scan_btn.configure(state="disabled")
        # 启动倒计时更新
        self._scan_countdown_tick()
        t = threading.Thread(target=self._scan_thread, daemon=True)
        t.start()

    def _scan_countdown_tick(self):
        """每 200ms 更新倒计时"""
        if self.scan_btn.cget("state") == "normal":
            return  # 扫描已结束（按钮已恢复）
        elapsed = time.time() - self.scan_start_time
        remaining = max(0, 5 - int(elapsed))
        self.login_status.configure(
            text=f"🔍 正在扫描... 剩余 {remaining} 秒",
            text_color="#1976d2")
        self.root.after(200, self._scan_countdown_tick)

    def _scan_thread(self):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("0.0.0.0", DISCOVERY_PORT))
            sock.settimeout(5)

            rooms = {}
            start_time = time.time()
            while time.time() - start_time < 5:
                try:
                    remaining = 5 - (time.time() - start_time)
                    sock.settimeout(max(0.1, remaining))
                    data, addr = sock.recvfrom(1024)
                    msg = data.decode("utf-8")
                    if msg.startswith("CHAT_ROOM|"):
                        parts = msg.split("|")
                        if len(parts) == 4:
                            _, room_name, ip, port = parts
                            rooms[ip] = (room_name, int(port))
                except socket.timeout:
                    break
                except Exception:
                    break
            sock.close()

            if rooms:
                ip = list(rooms.keys())[0]
                name, port = rooms[ip]
                self.msg_queue.put(("SCAN_RESULT", (name, ip, port)))
            else:
                self.msg_queue.put(("SCAN_FAIL", None))
        except Exception as e:
            self.msg_queue.put(("SCAN_FAIL", str(e)))

    # ======================== 发送消息 ========================

    def _send_message(self):
        if not self.connected or not self.sock:
            return
        text = self.msg_entry.get().strip()
        if not text:
            return

        try:
            # 本地回显（服务端广播会排除发送者，不加这句自己看不到消息）
            display_msg = f"💬 [{self.nickname}]: {text}"
            self._add_chat_message(display_msg, is_self=True)

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
                    welcome, login_result = data
                    self._switch_to_chat(welcome, login_result)

                elif msg_type == "MESSAGE":
                    self._display_message(data)

                elif msg_type == "ERROR":
                    self.login_status.configure(text=f"❌ {data}")
                    self.connect_btn.configure(state="normal")
                    self.scan_btn.configure(state="normal")

                elif msg_type == "DISCONNECTED":
                    self._add_system_message(f"🔴 {data}")
                    self.connected = False
                    if self.sock:
                        try:
                            self.sock.close()
                        except Exception:
                            pass
                    self.title_label.configure(text="聊天室 — 已断开")
                    self.status_dot.configure(text_color="#f44336")

                elif msg_type == "SCAN_RESULT":
                    name, ip, port = data
                    self.login_entries["服务器地址"].delete(0, "end")
                    self.login_entries["服务器地址"].insert(0, ip)
                    self.login_entries["端口"].delete(0, "end")
                    self.login_entries["端口"].insert(0, str(port))
                    self.login_status.configure(text=f"✅ 发现 \"{name}\" — 已填入地址",
                                                text_color="#2e7d32")
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

    def _switch_to_chat(self, welcome_msg, login_result):
        # 取消登录界面的回车绑定，防止误触重连
        self.root.unbind("<Return>")

        # 展开窗口到聊天大小
        self.root.geometry("880x640")
        self.root.minsize(700, 500)
        self.root.resizable(True, True)

        self.login_frame.pack_forget()
        self._build_chat_view()

        self.title_label.configure(text=f"聊天室 — {self.nickname}")
        self.connected = True

        self._add_system_message("🟢 已连接到聊天室")
        if login_result:
            self._display_message(login_result)

        # 把窗口提到最前
        self.root.lift()
        self.root.focus_force()
        self.msg_entry.focus()

    def _display_message(self, raw_msg):
        raw_msg = raw_msg.strip()
        if not raw_msg:
            return
        raw_msg = raw_msg.replace("\r", "")

        if raw_msg.startswith("💬 [私聊]("):
            self._add_private_message(raw_msg)
        elif raw_msg.startswith("📢") or raw_msg.startswith("🔴"):
            self._add_system_message(raw_msg)
            # 从加入/离开消息中提取昵称，维护本地用户列表
            self._update_users_from_join_leave(raw_msg)
        elif any(raw_msg.startswith(p) for p in ("✅", "❌", "🟢")):
            self._add_system_message(raw_msg)
        elif raw_msg.startswith("当前在线"):
            self._add_system_message(raw_msg)
            self._parse_user_list(raw_msg)
        elif "==========" in raw_msg:
            self._add_system_message(raw_msg)
        else:
            self._add_chat_message(raw_msg)

    def _add_system_message(self, text):
        self.msg_text.config(state="normal")
        if self.msg_text.get("end-2c", "end-1c") != "":
            self.msg_text.insert("end", "\n")
        self.msg_text.insert("end", text, ("system",))
        self.msg_text.see("end")
        self.msg_text.config(state="disabled")

        if "当前在线:" in text:
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
        """从 '当前在线: A, B, C' 解析用户列表"""
        if "当前在线:" not in text:
            return
        users_part = text.split("当前在线:", 1)[1].strip()
        self.online_users = [u.strip() for u in users_part.split(",") if u.strip()]
        self._update_user_list_display(self.online_users)

    def _update_users_from_join_leave(self, text):
        """从加入/离开消息维护本地用户列表"""
        # 格式: 📢 {nick} 进入了聊天室  /  🔴 {nick} 离开了聊天室
        for keyword, add in [("进入了聊天室", True), ("离开了聊天室", False)]:
            if keyword in text:
                nick = text.split(keyword)[0].strip()
                # 去掉前面的图标
                nick = nick.lstrip("📢🔴 ").strip()
                if nick:
                    if add:
                        if nick not in self.online_users:
                            self.online_users.append(nick)
                    else:
                        if nick in self.online_users:
                            self.online_users.remove(nick)
                    self._update_user_list_display(self.online_users)
                break

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

        self.title_label.configure(text="聊天室 — 已断开")
        self.status_dot.configure(text_color="#f44336")

        if hasattr(self, 'msg_entry') and self.msg_entry:
            self.msg_entry.configure(state="disabled")
        if hasattr(self, 'send_btn') and self.send_btn:
            self.send_btn.configure(state="disabled")
        if hasattr(self, 'disconnect_btn') and self.disconnect_btn:
            self.disconnect_btn.configure(state="disabled")

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
        self.root.destroy()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = ChatClientUI()
    app.run()
