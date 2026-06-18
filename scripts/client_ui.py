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
import sys, os
import re
# 确保能找到同目录模块（server.py）
_scripts_dir = os.path.dirname(os.path.abspath(__file__))
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

# ========== 配置 ==========
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8888
DISCOVERY_PORT = 9999

ctk.set_appearance_mode("light")
ctk.set_default_color_theme("green")


class ChatClientUI:
    """聊天室 GUI 客户端（CustomTkinter）"""

    # ---------- 全局统一圆角 ----------
    CR = 16  # 所有圆角统一尺寸

    # ---------- 颜色 ----------
    SYSTEM_FG = "#667781"
    PRIVATE_FG = "#8e24aa"
    ERROR_FG = "#d32f2f"
    NICKNAME_FG = "#075e54"
    TIMESTAMP_FG = "#999999"

    def __init__(self, auto_connect=None, launcher=None):
        self.root = ctk.CTk()
        self.root.title("TCP 聊天室")
        self.root.geometry("420x480")
        self.root.resizable(False, False)  # 登录界面固定大小

        # ---- 启动器引用 ----
        self._launcher = launcher

        # ---- 网络状态 ----
        self.sock = None
        self.nickname = ""
        self.connected = False
        self.msg_queue = queue.Queue()
        self.stop_threads = False
        self.online_users = []  # 本地维护的用户列表

        # ---- 字体缩放 ----
        self._scale = 1.0
        self._resize_timer = None
        self._base_width = 880  # 默认窗口宽度

        # ---- 服务端引用 ----
        self._server_thread = None
        self._is_host = False

        # ---- 构建界面 ----
        if auto_connect:
            host, port, nick = auto_connect
            self.nickname = nick
            self.root.after(200, lambda: self._auto_connect(host, port, nick))
        else:
            self._build_start_view()

        # ---- 任务栏图标 ----
        self._set_window_icon()

        # ---- 轮询 ----
        self.root.after(100, self._process_queue)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        # ---- 窗口拖动缩放 ----
        self.root.bind("<Configure>", self._on_window_resize)

    def _set_window_icon(self):
        """设置窗口图标（任务栏显示用）"""
        try:
            import tkinter as tk
            img = tk.PhotoImage(width=16, height=16)
            colors = [
                "#075e54", "#075e54", "#075e54",
                "#ffffff", "#ffffff", "#ffffff",
            ]
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

    # ======================== 窗口缩放 ========================

    def _on_window_resize(self, event):
        """窗口大小变化时防抖处理"""
        if event.widget != self.root:
            return
        # 仅在聊天界面启用缩放
        if not getattr(self, 'chat_frame', None):
            return
        if self._resize_timer:
            self.root.after_cancel(self._resize_timer)
        self._resize_timer = self.root.after(150, self._apply_font_scaling)

    def _apply_font_scaling(self):
        """根据窗口宽度等比缩放字体"""
        if not getattr(self, 'msg_text', None):
            return
        w = self.root.winfo_width()
        scale = max(0.7, min(2.0, w / self._base_width))
        if abs(scale - self._scale) < 0.05:
            return  # 变化太小忽略
        self._scale = scale

        # 消息区域字体（所有标签都随窗口缩放）
        msg_size = max(10, int(12 * scale))
        self.msg_text.configure(font=("Segoe UI", msg_size))
        self.msg_text.tag_configure("normal", font=("Segoe UI", msg_size))
        self.msg_text.tag_configure("nickname_tag", font=("Segoe UI", msg_size, "bold"))
        self.msg_text.tag_configure("system", font=("Segoe UI", max(8, int(10 * scale)), "italic"))
        self.msg_text.tag_configure("timestamp", font=("Segoe UI", max(7, int(9 * scale))))
        self.msg_text.tag_configure("private", font=("Segoe UI", msg_size))
        self.msg_text.tag_configure("error", font=("Segoe UI", msg_size, "bold"))

        # 输入框字体
        if getattr(self, 'msg_entry', None):
            input_size = max(10, int(12 * scale))
            self.msg_entry.configure(font=("Segoe UI", input_size))

        # 用户列表（重建时用最新 scale）
        self._update_user_list_display(self.online_users)

    # ======================== 启动界面 ========================

    def _build_start_view(self):
        """启动界面：两个大按钮，无输入项"""
        self.start_frame = ctk.CTkFrame(self.root, fg_color="white")
        self.start_frame.pack(fill="both", expand=True)

        ctk.CTkLabel(self.start_frame, text="💬", font=("Segoe UI", 48),
                     bg_color="white").pack(pady=(50, 0))
        ctk.CTkLabel(self.start_frame, text="TCP 聊天室",
                     font=("Segoe UI", 24, "bold"),
                     text_color="#075e54",
                     bg_color="white").pack(pady=(6, 4))
        ctk.CTkLabel(self.start_frame, text="", font=("Segoe UI", 11),
                     bg_color="white").pack(pady=(0, 40))

        ctk.CTkButton(self.start_frame, text="🏠  创建聊天房间",
                       font=("Segoe UI", 14, "bold"),
                       width=220, height=44, corner_radius=10,
                       fg_color="#075e54", hover_color="#054d44",
                       command=self._go_create_config).pack(pady=5)
        ctk.CTkButton(self.start_frame, text="🔍  加入聊天房间",
                       font=("Segoe UI", 14, "bold"),
                       width=220, height=44, corner_radius=10,
                       fg_color="white", text_color="#075e54",
                       hover_color="#e8f5e9", border_width=2,
                       border_color="#075e54",
                       command=self._on_join_room).pack(pady=5)

    def _go_create_config(self):
        """切换到创建房间配置页"""
        self.start_frame.pack_forget()
        self._build_create_room_view()

    def _build_create_room_view(self):
        """创建房间配置页：IP、端口、房间名、昵称"""
        self.create_frame = ctk.CTkFrame(self.root, fg_color="white")
        self.create_frame.pack(fill="both", expand=True)

        # 获取本机局域网 IP
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
        except:
            local_ip = "127.0.0.1"

        ctk.CTkLabel(self.create_frame, text="🏠", font=("Segoe UI", 36),
                     bg_color="white").pack(pady=(28, 0))
        ctk.CTkLabel(self.create_frame, text="创建聊天房间",
                     font=("Segoe UI", 18, "bold"),
                     text_color="#075e54",
                     bg_color="white").pack(pady=(4, 16))

        form = ctk.CTkFrame(self.create_frame, fg_color="white")
        form.pack(padx=40)

        fields = [
            ("服务器IP", local_ip, 22),
            ("端口", "8888", 10),
            ("房间名称", "聊天室", 20),
            ("昵称", "用户", 20),
        ]
        self.create_entries = {}
        for label, default, width in fields:
            row = ctk.CTkFrame(form, fg_color="transparent")
            row.pack(fill="x", pady=4)
            ctk.CTkLabel(row, text=label, width=65, anchor="e",
                         font=("Segoe UI", 11),
                         bg_color="white").pack(side="left", padx=(0, 8))
            entry = ctk.CTkEntry(row, font=("Segoe UI", 12),
                                  width=width * 8, height=30, corner_radius=6)
            entry.insert(0, default)
            entry.pack(side="left")
            self.create_entries[label] = entry

        ctk.CTkButton(self.create_frame, text="🚀  创建",
                       font=("Segoe UI", 13, "bold"),
                       width=200, height=38, corner_radius=8,
                       fg_color="#075e54",
                       command=self._on_create_room).pack(pady=(16, 4))
        ctk.CTkButton(self.create_frame, text="←  返回",
                       font=("Segoe UI", 11),
                       width=200, height=30, corner_radius=8,
                       fg_color="white", text_color="#888888",
                       hover_color="#f0f0f0",
                       command=self._back_to_start).pack(pady=2)

    def _back_to_start(self):
        """返回启动页"""
        if hasattr(self, 'create_frame'):
            self.create_frame.pack_forget()
        self._build_start_view()

    def _on_create_room(self):
        """创建房间：从配置页取值 → 启动服务端 → 自动连接"""
        nick = self.create_entries["昵称"].get().strip() or "用户"
        port_str = self.create_entries["端口"].get().strip()
        try:
            port = int(port_str)
        except ValueError:
            port = 8888
        self.nickname = nick
        self._is_host = True

        import server as srv
        srv.PORT = port
        self._server_thread = threading.Thread(
            target=srv.start_server, daemon=True)
        self._server_thread.start()

        self.create_frame.pack_forget()
        self._show_loading("🚀 正在启动房间...")
        self.root.after(500, lambda: self._auto_connect("127.0.0.1", port, nick))

    def _on_join_room(self):
        """加入房间：切换到登录界面"""
        self.start_frame.pack_forget()
        self._build_login_view()

    def _show_loading(self, text="⏳ 请稍候..."):
        """显示加载提示（切换界面时的过渡）"""
        self.loading_frame = ctk.CTkFrame(self.root, fg_color="white")
        self.loading_frame.pack(fill="both", expand=True)
        ctk.CTkLabel(self.loading_frame, text=text,
                     font=("Segoe UI", 14),
                     text_color="#888888",
                     bg_color="white").pack(expand=True)

    # ======================== 登录界面 ========================

    def _build_login_view(self):
        """登录界面（纯 pack 布局，无 place，避免 z-order 问题）"""
        self.login_frame = ctk.CTkFrame(self.root, fg_color="white")
        self.login_frame.pack(fill="both", expand=True)

        # 顶栏（仅用于视觉分隔）
        top_row = ctk.CTkFrame(self.login_frame, fg_color="white", height=4)
        top_row.pack(fill="x", side="top")
        top_row.pack_propagate(False)

        # 内容容器（纯 pack，替代原来的 place）
        body = ctk.CTkFrame(self.login_frame, fg_color="white")
        body.pack(fill="both", expand=True)

        # 在 body 里垂直居中
        spacer_top = ctk.CTkFrame(body, fg_color="white", height=60)
        spacer_top.pack(fill="x", side="top")

        center = ctk.CTkFrame(body, fg_color="white")
        center.pack(expand=True)

        # 图标 + 标题
        ctk.CTkLabel(center, text="💬", font=("Segoe UI", 40),
                     bg_color="white").pack(pady=(0, 0))
        ctk.CTkLabel(center, text="TCP 聊天室", font=("Segoe UI", 22, "bold"),
                     text_color="#1a1a1a", bg_color="white").pack(pady=(8, 2))
        ctk.CTkLabel(center, text="连接到聊天服务器",
                     font=("Segoe UI", 11),
                     text_color="#888888", bg_color="white").pack(pady=(0, 20))

        # 表单
        form = ctk.CTkFrame(center, fg_color="white")
        form.pack(padx=40, pady=(0, 16))

        fields = [
            ("服务器地址", DEFAULT_HOST, 20),
            ("端口", str(DEFAULT_PORT), 8),
            ("昵称", "", 20),
        ]
        self.login_entries = {}

        for label, default, width in fields:
            row = ctk.CTkFrame(form, fg_color="transparent")
            row.pack(fill="x", pady=5)

            ctk.CTkLabel(row, text=label, width=75, anchor="e",
                         font=("Segoe UI", 11),
                         text_color=("#555555", "#cccccc")).pack(side="left", padx=(0, 10))

            entry_frame = ctk.CTkFrame(row, fg_color=("#e8e8e8", "#333333"),
                                       corner_radius=self.CR, height=32)
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
            entry.bind("<Return>", lambda e: self._do_connect())

        # 按钮
        btn_row = ctk.CTkFrame(center, fg_color="white")
        btn_row.pack(pady=(6, 12))

        self.scan_btn = ctk.CTkButton(btn_row, text="🔍 扫描局域网",
                                      font=("Segoe UI", 11), width=130, height=34,
                                      corner_radius=self.CR,
                                      fg_color=("#e8e8e8", "#333333"),
                                      text_color=("#333333", "#ffffff"),
                                      hover_color=("#d0d0d0", "#444444"),
                                      command=self._scan_network)
        self.scan_btn.pack(side="left", padx=(0, 10))

        self.connect_btn = ctk.CTkButton(btn_row, text="🚀 连接",
                                         font=("Segoe UI", 12, "bold"),
                                         width=120, height=34,
                                         corner_radius=self.CR,
                                         command=self._do_connect)
        self.connect_btn.pack(side="left")

        # 状态
        self.login_status = ctk.CTkLabel(center, text="", font=("Segoe UI", 10),
                                         text_color=self.ERROR_FG)
        self.login_status.pack(pady=(0, 20))

        self.root.update_idletasks()
        self.root.after(100, lambda: self.login_entries["昵称"].focus_set())

    # ======================== 聊天界面 ========================

    def _build_chat_view(self):
        """聊天主界面"""
        self.chat_frame = ctk.CTkFrame(self.root, fg_color="transparent")
        self.chat_frame.pack(fill="both", expand=True)

        # ---- 顶栏：断开 | 状态 | 标题 | ─ □ ✕ ----
        top_bar = ctk.CTkFrame(self.chat_frame, height=38, corner_radius=0,
                               fg_color="white")
        top_bar.pack(fill="x", side="top")
        top_bar.pack_propagate(False)

        self.disconnect_btn = ctk.CTkButton(top_bar, text="✕ 断开",
                                             font=("Segoe UI", 10),
                                             width=62, height=26,
                                             corner_radius=6,
                                             fg_color="white",
                                             text_color="#888888",
                                             hover_color="#ffcdd2",
                                             command=self._disconnect)
        self.disconnect_btn.pack(side="left", padx=(4, 0))

        self.status_dot = ctk.CTkLabel(top_bar, text="●",
                                        font=("Segoe UI", 14),
                                        text_color="#76d275",
                                        bg_color="white")
        self.status_dot.pack(side="left", padx=(10, 2))

        self.title_label = ctk.CTkLabel(top_bar,
                                         text="聊天室 — 连接中...",
                                         font=("Segoe UI", 12, "bold"),
                                         text_color="#075e54",
                                         bg_color="white")
        self.title_label.pack(side="left", padx=4)

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
                                font=("Segoe UI", 12),
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
                                    font=("Segoe UI", 12, "bold"))
        self.msg_text.tag_configure("normal", foreground="#000000",
                                    font=("Segoe UI", 12))

        # 滚动条（自动隐藏：内容少于一屏时隐藏 + 停止滚动后慢慢淡去）
        scrollbar = ctk.CTkScrollbar(msg_frame, command=self.msg_text.yview,
                                     orientation="vertical",
                                     corner_radius=self.CR)
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
                                       height=38, corner_radius=self.CR,
                                       placeholder_text="输入消息...")
        self.msg_entry.pack(side="left", fill="both", expand=True, padx=(0, 8))
        self.msg_entry.bind("<Return>", self._on_return)

        self.send_btn = ctk.CTkButton(input_bar, text="发送",
                                       font=("Segoe UI", 12, "bold"),
                                       width=80, height=38,
                                       corner_radius=self.CR,
                                       command=self._send_message)
        self.send_btn.pack(side="left")

        # ---- 命令菜单（输入 / 后弹出）----
        self._build_command_menu()

    def _build_command_menu(self):
        """输入 / 后弹出指令菜单"""
        self.cmd_defs = [
            ("/help", "显示帮助"),
            ("/list", "查看在线用户"),
            ("/to <昵称> <消息>", "私聊某人"),
            ("/quit", "退出聊天室"),
            ("/exit", "退出聊天室"),
        ]

        # 弹出窗口
        self.cmd_popup = ctk.CTkToplevel(self.root)
        self.cmd_popup.overrideredirect(True)
        self.cmd_popup.attributes("-topmost", True)
        self.cmd_popup.withdraw()

        popup_frame = ctk.CTkFrame(self.cmd_popup, corner_radius=self.CR,
                                   fg_color="white", border_width=1,
                                   border_color="#d0d0d0")
        popup_frame.pack(fill="both", expand=True)

        self.cmd_listbox = tk.Listbox(popup_frame,
                                       font=("Segoe UI", 11),
                                       bd=0, highlightthickness=0,
                                       bg="#ffffff", fg="#333333",
                                       activestyle="none",
                                       exportselection=False,
                                       width=30, height=5)
        self.cmd_listbox.pack(fill="both", expand=True, padx=4, pady=4)
        self._cmd_selected = -1

        # 绑定事件
        self.msg_entry.bind("<KeyRelease>", self._on_cmd_key)
        self.msg_entry.bind("<Up>", self._on_cmd_up)
        self.msg_entry.bind("<Down>", self._on_cmd_down)
        self.msg_entry.bind("<Escape>", lambda e: self._cmd_hide())

        # 点击 Listbox 选择
        self.cmd_listbox.bind("<Button-1>", self._on_cmd_click)
        self.cmd_listbox.bind("<Double-Button-1>", self._on_cmd_confirm)

        # 焦点离开时隐藏
        self.msg_entry.bind("<FocusOut>", lambda e: self.root.after(100, self._cmd_hide))

    def _cmd_show(self):
        """显示命令菜单"""
        if self.cmd_listbox.size() == 0:
            return
        # 定位到输入框上方
        x = self.msg_entry.winfo_rootx()
        y = self.msg_entry.winfo_rooty() - self.cmd_popup.winfo_reqheight() - 6
        self.cmd_popup.geometry(f"+{x}+{y}")
        self.cmd_popup.deiconify()
        self._cmd_selected = -1
        self.cmd_listbox.selection_clear(0, tk.END)

    def _cmd_hide(self):
        """隐藏命令菜单"""
        self.cmd_popup.withdraw()

    def _on_cmd_key(self, event):
        """按键时更新命令列表"""
        # Ignore navigation keys
        if event.keysym in ("Up", "Down", "Left", "Right", "Return", "Escape"):
            return
        self.root.after_idle(self._cmd_filter)

    def _cmd_filter(self):
        """根据输入过滤并显示/隐藏菜单"""
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
        """上键移动选中"""
        if not self.cmd_popup.winfo_viewable():
            return
        size = self.cmd_listbox.size()
        if size == 0:
            return
        if self._cmd_selected > 0:
            self._cmd_selected -= 1
        else:
            self._cmd_selected = size - 1
        self.cmd_listbox.selection_clear(0, tk.END)
        self.cmd_listbox.selection_set(self._cmd_selected)
        self.cmd_listbox.activate(self._cmd_selected)
        return "break"

    def _on_cmd_down(self, event):
        """下键移动选中"""
        if not self.cmd_popup.winfo_viewable():
            return
        size = self.cmd_listbox.size()
        if size == 0:
            return
        if self._cmd_selected < size - 1:
            self._cmd_selected += 1
        else:
            self._cmd_selected = 0
        self.cmd_listbox.selection_clear(0, tk.END)
        self.cmd_listbox.selection_set(self._cmd_selected)
        self.cmd_listbox.activate(self._cmd_selected)
        return "break"

    def _on_cmd_click(self, event):
        """点击选中"""
        idx = self.cmd_listbox.nearest(event.y)
        if idx >= 0:
            self._cmd_selected = idx
            self.cmd_listbox.selection_clear(0, tk.END)
            self.cmd_listbox.selection_set(idx)

    def _on_cmd_confirm(self, event):
        """双击确认"""
        self._cmd_insert_selected()

    def _cmd_insert_selected(self):
        """将选中指令插入输入框"""
        if self._cmd_selected < 0 or self._cmd_selected >= self.cmd_listbox.size():
            return
        display = self.cmd_listbox.get(self._cmd_selected)
        cmd = display.split()[0]  # 取第一个空格前的部分作为命令
        self.msg_entry.delete(0, "end")
        self.msg_entry.insert(0, cmd + " ")
        self.msg_entry.icursor(tk.END)
        self._cmd_hide()
        self.msg_entry.focus_set()

    def _on_return(self, event):
        """回车：菜单打开时选命令，否则发送消息"""
        if hasattr(self, 'cmd_popup') and self.cmd_popup.winfo_viewable():
            if self._cmd_selected >= 0:
                self._cmd_insert_selected()
                return "break"
        return self._send_message() or "break"

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
        """重建用户列表（users 为 (昵称, id) 元组列表）"""
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

            is_host = (uid == getattr(self, '_host_id', None))
            dot_color = "#FFD700" if is_host else "#4caf50"
            ctk.CTkLabel(row, text="●", font=("Segoe UI", dot_size),
                         text_color=dot_color).pack(side="left", padx=(0, 5))
            ctk.CTkLabel(row, text=nick, font=("Segoe UI", name_size),
                         anchor="w").pack(side="left", fill="x", expand=True)
            if is_host:
                ctk.CTkLabel(row, text="👑", font=("Segoe UI", dot_size),
                             bg_color="transparent").pack(side="left", padx=(2, 0))

        self.user_count_label.configure(text=f"{len(users)} 人在线")

    # ======================== 连接逻辑 ========================

    def _auto_connect(self, host, port, nickname, retry=3):
        """自动连接（带重试，给服务端时间启动）"""
        import socket as _sk
        for attempt in range(retry):
            try:
                s = _sk.socket(_sk.AF_INET, _sk.SOCK_STREAM)
                s.settimeout(1)
                s.connect((host, port))
                s.close()
                break  # 连接成功
            except:
                if attempt < retry - 1:
                    time.sleep(0.5)
                else:
                    self._connect_thread(host, port, nickname)
                    return
        self._connect_thread(host, port, nickname)

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
            nick = "匿名"

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
                # 扫描到房间立即结束，不等满5秒
                if rooms:
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
        self.root.unbind("<Return>")

        # 展开窗口到聊天大小
        self.root.geometry("880x640")
        self.root.minsize(700, 500)
        self.root.resizable(True, True)

        # 隐藏之前的界面（登录/启动/加载）
        for name in ('login_frame', 'start_frame', 'loading_frame'):
            f = getattr(self, name, None)
            if f:
                try:
                    f.pack_forget()
                except Exception:
                    pass
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
            # 显示时去掉 |id，只显示昵称
            display_msg = raw_msg
            if "|" in display_msg and "离开了" in display_msg or "进入了" in display_msg:
                import re
                display_msg = re.sub(r'\|(\d+)', '', display_msg)
            self._add_system_message(display_msg)
            self._update_users_from_join_leave(raw_msg)  # 原始带 id 的用于解析
        elif any(raw_msg.startswith(p) for p in ("✅", "❌", "🟢")):
            self._add_system_message(raw_msg)
        elif raw_msg.startswith("当前在线"):
            # 显示时去掉 |id；先解析（用原始数据），再显示（用去掉 id 的）
            self._parse_user_list(raw_msg)
            display_online = re.sub(r'\|(\d+)', '', raw_msg) if "|" in raw_msg else raw_msg
            self._add_system_message(display_online, skip_parse=True)
        elif "==========" in raw_msg:
            self._add_system_message(raw_msg)
        else:
            self._add_chat_message(raw_msg)

    def _add_system_message(self, text, skip_parse=False):
        # 显示前去掉 |id
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
        """从 '当前在线: 👑A|id, B|id' 解析"""
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
                except:
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

    def _update_users_from_join_leave(self, text):
        """从加入/离开消息维护本地用户列表（用 id 追踪）"""
        for keyword, add in [("进入了聊天室", True), ("离开了聊天室", False)]:
            if keyword not in text:
                continue
            raw = text.split(keyword)[0].strip()
            # 去掉图标
            raw = raw.lstrip("📢🔴 ").strip()
            if not raw or "|" not in raw:
                break
            parts = raw.rsplit("|", 1)
            nick = parts[0].strip()
            try:
                uid = int(parts[1])
            except:
                break
            if add:
                # 加入：添加 (nick, id) 对
                self.online_users.append((nick, uid))
            else:
                # 离开：按 id 删除
                self.online_users = [(n, i) for n, i in self.online_users if i != uid]
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
    import sys
    # 支持命令行自动连接: python client_ui.py <host> <port> <nickname>
    if len(sys.argv) >= 4:
        app = ChatClientUI(
            auto_connect=(sys.argv[1], int(sys.argv[2]), sys.argv[3]))
    else:
        app = ChatClientUI()
    app.run()
