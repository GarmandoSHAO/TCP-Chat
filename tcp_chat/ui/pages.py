"""
页面视图 — 启动页、创建房间页、登录页、聊天页
"""
import tkinter as tk
import customtkinter as ctk
from .theme import *
from .widgets import win_btn, make_draggable
from ..config import get, get_local_ip


# ======================== 启动页 ========================

def build_start_view(container, on_create, on_join):
    """启动界面：两个大按钮"""
    frame = ctk.CTkFrame(container, fg_color=WHITE)
    frame.pack(fill="both", expand=True)

    ctk.CTkLabel(frame, text="💬", font=("Segoe UI", 48),
                 bg_color=WHITE).pack(pady=(50, 0))
    ctk.CTkLabel(frame, text="TCP 聊天室",
                 font=("Segoe UI", 24, "bold"),
                 text_color=CHAT_TITLE,
                 bg_color=WHITE).pack(pady=(6, 4))
    ctk.CTkLabel(frame, text="", bg_color=WHITE).pack(pady=(0, 40))

    ctk.CTkButton(frame, text="🏠  创建聊天房间",
                   font=("Segoe UI", 14, "bold"),
                   width=220, height=44, corner_radius=10,
                   fg_color=CHAT_TITLE, hover_color="#054d44",
                   command=on_create).pack(pady=5)
    ctk.CTkButton(frame, text="🔍  加入聊天房间",
                   font=("Segoe UI", 14, "bold"),
                   width=220, height=44, corner_radius=10,
                   fg_color=WHITE, text_color=CHAT_TITLE,
                   hover_color="#e8f5e9", border_width=2,
                   border_color=CHAT_TITLE,
                   command=on_join).pack(pady=5)
    return frame


# ======================== 创建房间配置页 ========================

def build_create_room_view(container, on_create, on_back, on_tunnel=None):
    """创建房间配置页：IP、端口、房间名、昵称 + 外网开放"""
    frame = ctk.CTkFrame(container, fg_color=WHITE)
    frame.pack(fill="both", expand=True)

    local_ip = get_local_ip()
    ctk.CTkLabel(frame, text="🏠", font=("Segoe UI", 36),
                 bg_color=WHITE).pack(pady=(28, 0))
    ctk.CTkLabel(frame, text="创建聊天房间",
                 font=("Segoe UI", 18, "bold"),
                 text_color=CHAT_TITLE,
                 bg_color=WHITE).pack(pady=(4, 16))

    form = ctk.CTkFrame(frame, fg_color=WHITE)
    form.pack(padx=40)

    entries = {}
    fields = [
        ("服务器IP", local_ip, 22),
        ("端口", str(get("default_port", 8888)), 10),
        ("房间名称", get("default_room_name", "聊天室"), 20),
        ("昵称", get("default_nickname", "用户"), 20),
    ]
    for label, default, width in fields:
        row = ctk.CTkFrame(form, fg_color="transparent")
        row.pack(fill="x", pady=4)
        ctk.CTkLabel(row, text=label, width=65, anchor="e",
                     font=("Segoe UI", 11),
                     bg_color=WHITE).pack(side="left", padx=(0, 8))
        entry = ctk.CTkEntry(row, font=("Segoe UI", 12),
                              width=width * 8, height=30, corner_radius=6)
        entry.insert(0, default)
        entry.pack(side="left")
        entries[label] = entry

    # 外网开放选项
    tunnel_var = ctk.BooleanVar(value=False)
    tunnel_check = ctk.CTkCheckBox(frame, text="🌐 对外网开放（需要 bore）",
                                    font=("Segoe UI", 11),
                                    variable=tunnel_var,
                                    fg_color=CHAT_TITLE,
                                    bg_color=WHITE)
    tunnel_check.pack(pady=(4, 0))

    tunnel_status = ctk.CTkLabel(frame, text="", font=("Segoe UI", 9),
                                  text_color=CHAT_TITLE, bg_color=WHITE)
    tunnel_status.pack()

    if on_tunnel:
        tunnel_check.configure(command=lambda: on_tunnel(tunnel_var, tunnel_status))

    ctk.CTkButton(frame, text="🚀  创建",
                   font=("Segoe UI", 13, "bold"),
                   width=200, height=38, corner_radius=8,
                   fg_color=CHAT_TITLE,
                   command=on_create).pack(pady=(12, 4))
    ctk.CTkButton(frame, text="←  返回",
                   font=("Segoe UI", 11),
                   width=200, height=30, corner_radius=8,
                   fg_color=WHITE, text_color="#888888",
                   hover_color="#f0f0f0",
                   command=on_back).pack(pady=2)
    return frame, entries, tunnel_var, tunnel_status


# ======================== 登录页 ========================

def build_login_view(container, fields_config, on_connect):
    """登录界面：服务器地址、端口、昵称 + 连接按钮"""
    frame = ctk.CTkFrame(container, fg_color=WHITE)
    frame.pack(fill="both", expand=True)

    body = ctk.CTkFrame(frame, fg_color=WHITE)
    body.pack(fill="both", expand=True)

    ctk.CTkFrame(body, fg_color=WHITE, height=60).pack(fill="x", side="top")

    center = ctk.CTkFrame(body, fg_color=WHITE)
    center.pack(expand=True)

    ctk.CTkLabel(center, text="💬", font=("Segoe UI", 40),
                 bg_color=WHITE).pack()
    ctk.CTkLabel(center, text="TCP 聊天室", font=("Segoe UI", 22, "bold"),
                 text_color="#1a1a1a", bg_color=WHITE).pack(pady=(8, 2))
    ctk.CTkLabel(center, text="连接到聊天服务器",
                 font=("Segoe UI", 11),
                 text_color="#888888", bg_color=WHITE).pack(pady=(0, 20))

    form = ctk.CTkFrame(center, fg_color=WHITE)
    form.pack(padx=40, pady=(0, 16))

    entries = {}
    for label, default, width in fields_config:
        row = ctk.CTkFrame(form, fg_color="transparent")
        row.pack(fill="x", pady=5)
        ctk.CTkLabel(row, text=label, width=75, anchor="e",
                     font=("Segoe UI", 11),
                     text_color=("#555555", "#cccccc")).pack(side="left", padx=(0, 10))
        entry_frame = ctk.CTkFrame(row, fg_color=("#e8e8e8", "#333333"),
                                   corner_radius=CR, height=32)
        entry_frame.pack(side="left", fill="x", expand=True)
        entry_frame.pack_propagate(False)
        entry = tk.Entry(entry_frame, font=("Segoe UI", 12),
                         bd=0, highlightthickness=0,
                         bg="#e8e8e8", fg="#000000",
                         insertbackground="#000000", relief="flat")
        entry.insert(0, default)
        entry.pack(fill="both", expand=True, padx=8, pady=2)
        entries[label] = entry
        entry.bind("<Return>", lambda e: on_connect())

    # 按钮行
    btn_row = ctk.CTkFrame(center, fg_color=WHITE)
    btn_row.pack(pady=(6, 12))

    scan_btn = ctk.CTkButton(btn_row, text="🔍 扫描局域网",
                              font=("Segoe UI", 11), width=130, height=34,
                              corner_radius=CR,
                              fg_color=("#e8e8e8", "#333333"),
                              text_color=("#333333", "#ffffff"),
                              hover_color=("#d0d0d0", "#444444"))
    scan_btn.pack(side="left", padx=(0, 10))

    connect_btn = ctk.CTkButton(btn_row, text="🚀 连接",
                                 font=("Segoe UI", 12, "bold"),
                                 width=120, height=34,
                                 corner_radius=CR)
    connect_btn.pack(side="left")

    status = ctk.CTkLabel(center, text="", font=("Segoe UI", 10),
                          text_color=ERROR_FG)
    status.pack(pady=(0, 20))

    return frame, entries, scan_btn, connect_btn, status


# ======================== 聊天页 ========================

def build_chat_view(container, on_send, on_disconnect):
    """聊天主界面：顶栏 + 消息区 + 用户面板 + 输入区"""
    frame = ctk.CTkFrame(container, fg_color="transparent")
    frame.pack(fill="both", expand=True)

    # ---- 顶栏 ----
    top_bar = ctk.CTkFrame(frame, height=38, corner_radius=0, fg_color=WHITE)
    top_bar.pack(fill="x", side="top")
    top_bar.pack_propagate(False)

    disconnect_btn = ctk.CTkButton(top_bar, text="✕ 断开",
                                    font=("Segoe UI", 10),
                                    width=62, height=26, corner_radius=6,
                                    fg_color=WHITE, text_color="#888888",
                                    hover_color="#ffcdd2",
                                    command=on_disconnect)
    disconnect_btn.pack(side="left", padx=(4, 0))

    status_dot = ctk.CTkLabel(top_bar, text="●", font=("Segoe UI", 14),
                               text_color=STATUS_GREEN, bg_color=WHITE)
    status_dot.pack(side="left", padx=(10, 2))

    title_label = ctk.CTkLabel(top_bar, text="聊天室 — 连接中...",
                                font=("Segoe UI", 12, "bold"),
                                text_color=CHAT_TITLE, bg_color=WHITE)
    title_label.pack(side="left", padx=4)

    # ---- 主体 ----
    main_area = ctk.CTkFrame(frame, fg_color="transparent")
    main_area.pack(fill="both", expand=True, padx=0, pady=0)

    # === 消息区 ===
    msg_container = ctk.CTkFrame(main_area, fg_color="transparent")
    msg_container.pack(side="left", fill="both", expand=True)

    separator = ctk.CTkFrame(main_area, width=1, fg_color="#d0d0d0",
                             corner_radius=0)
    separator.pack(side="left", fill="y")

    msg_frame = ctk.CTkFrame(msg_container, fg_color=WHITE, corner_radius=0)
    msg_frame.pack(fill="both", expand=True)
    msg_frame.grid_rowconfigure(0, weight=1)
    msg_frame.grid_columnconfigure(0, weight=1)

    msg_text = tk.Text(msg_frame, font=("Segoe UI", MSG_FONT_SIZE),
                       wrap="word", state="disabled",
                       bd=0, padx=14, pady=10, bg="#ffffff",
                       highlightthickness=0)
    msg_text.grid(row=0, column=0, sticky="nsew")

    # 配置标签
    for name, (fg, font) in [
        ("system", (SYSTEM_FG, ("Segoe UI", 9, "italic"))),
        ("private", (PRIVATE_FG, ("Segoe UI", 10))),
        ("error", (ERROR_FG, ("Segoe UI", 10, "bold"))),
        ("timestamp", (TIMESTAMP_FG, ("Segoe UI", 8))),
        ("nickname_tag", (NICKNAME_FG, ("Segoe UI", MSG_FONT_SIZE, "bold"))),
        ("normal", ("#000000", ("Segoe UI", MSG_FONT_SIZE))),
    ]:
        msg_text.tag_configure(name, foreground=fg, font=font)

    # 滚动条
    scrollbar = ctk.CTkScrollbar(msg_frame, command=msg_text.yview,
                                  orientation="vertical", corner_radius=CR)
    scrollbar.grid(row=0, column=1, sticky="ns", padx=(0, 2))

    def _on_scroll(first, last):
        scrollbar.set(first, last)
        if first == "0.0" and last == "1.0":
            scrollbar.grid_remove()
        else:
            scrollbar.grid()
    msg_text.config(yscrollcommand=_on_scroll)
    scrollbar.grid_remove()

    def _on_mw(event):
        msg_text.yview_scroll(int(-1 * event.delta / 120), "units")
        first, last = msg_text.yview()
        if first != "0.0" or last != "1.0":
            scrollbar.grid()
            _auto_hide_scroll()
        return "break"

    _scroll_timer = [None]

    def _auto_hide_scroll():
        if _scroll_timer[0]:
            msg_frame.after_cancel(_scroll_timer[0])
        _scroll_timer[0] = msg_frame.after(1500, scrollbar.grid_remove)

    msg_text.bind("<MouseWheel>", _on_mw)
    msg_frame.bind("<MouseWheel>", _on_mw)

    # === 用户面板 ===
    user_frame = ctk.CTkFrame(main_area, width=190, fg_color=WHITE,
                              corner_radius=0, border_width=0)
    user_frame.pack(side="right", fill="y")
    user_frame.pack_propagate(False)

    # 用户列表标题
    ctk.CTkLabel(user_frame, text="🟢 在线用户",
                 font=("Segoe UI", 12, "bold"),
                 text_color=CHAT_TITLE, bg_color=WHITE).pack(
                     anchor="w", padx=14, pady=(16, 2))
    user_count = ctk.CTkLabel(user_frame, text="0 人在线",
                               font=("Segoe UI", 10),
                               text_color="#999999", bg_color=WHITE)
    user_count.pack(anchor="w", padx=14)

    # Canvas 滚动用户列表
    list_container = ctk.CTkFrame(user_frame, fg_color="transparent")
    list_container.pack(fill="both", expand=True, padx=6, pady=(6, 6))
    list_container.grid_rowconfigure(0, weight=1)
    list_container.grid_columnconfigure(0, weight=1)

    canvas = tk.Canvas(list_container, bd=0, highlightthickness=0, bg="#ffffff")
    canvas.grid(row=0, column=0, sticky="nsew")

    user_list_inner = ctk.CTkFrame(canvas, fg_color="transparent")
    canvas.create_window((0, 0), window=user_list_inner, anchor="nw", tags="inner")

    def _configure_inner(_):
        canvas.configure(scrollregion=canvas.bbox("all"))
        canvas.itemconfig("inner", width=canvas.winfo_width())
    user_list_inner.bind("<Configure>", _configure_inner)
    canvas.bind("<Configure>", _configure_inner)

    user_scroll = ctk.CTkScrollbar(list_container, orientation="vertical",
                                    command=canvas.yview, corner_radius=CR)
    user_scroll.grid(row=0, column=1, sticky="ns")
    user_scroll.grid_remove()
    _user_scroll_timer = [None]

    def _user_scroll_show():
        f, l = canvas.yview()
        if f != "0.0" or l != "1.0":
            user_scroll.grid()

    def _user_scroll_hide():
        if _user_scroll_timer[0]:
            list_container.after_cancel(_user_scroll_timer[0])
        _user_scroll_timer[0] = list_container.after(1500, user_scroll.grid_remove)

    def _on_user_scroll(f, l):
        user_scroll.set(f, l)
        if f == "0.0" and l == "1.0":
            if _user_scroll_timer[0]:
                list_container.after_cancel(_user_scroll_timer[0])
                _user_scroll_timer[0] = None
            user_scroll.grid_remove()

    def _on_user_mw(event):
        canvas.yview_scroll(int(-1 * event.delta / 120), "units")
        _user_scroll_show()
        _user_scroll_hide()
        return "break"

    canvas.configure(yscrollcommand=_on_user_scroll)
    canvas.bind("<MouseWheel>", _on_user_mw)
    list_container.bind("<MouseWheel>", _on_user_mw)

    # ---- 输入区 ----
    input_bar = ctk.CTkFrame(frame, height=56, fg_color="transparent",
                             corner_radius=0)
    input_bar.pack(fill="x", padx=10, pady=(6, 10))
    input_bar.pack_propagate(False)

    msg_entry = ctk.CTkEntry(input_bar, font=("Segoe UI", 12),
                              height=38, corner_radius=CR,
                              placeholder_text="输入消息...")
    msg_entry.pack(side="left", fill="both", expand=True, padx=(0, 8))

    send_btn = ctk.CTkButton(input_bar, text="发送",
                              font=("Segoe UI", 12, "bold"),
                              width=80, height=38,
                              corner_radius=CR, command=on_send)
    send_btn.pack(side="left")

    return {
        "frame": frame,
        "top_bar": top_bar,
        "disconnect_btn": disconnect_btn,
        "status_dot": status_dot,
        "title_label": title_label,
        "msg_text": msg_text,
        "msg_frame": msg_frame,
        "user_list_inner": user_list_inner,
        "user_count": user_count,
        "msg_entry": msg_entry,
        "send_btn": send_btn,
        "canvas": canvas,
    }
