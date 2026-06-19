"""
聊天页 — 顶栏 + 消息区 + 用户面板 + 输入区
"""
import tkinter as tk
import customtkinter as ctk
from .theme import *

def build_chat_view(container, on_send, on_disconnect):
    """聊天主界面：顶栏、消息区、用户面板、输入区"""
    frame = ctk.CTkFrame(container, fg_color="transparent")
    frame.pack(fill="both", expand=True)

    # ---- 顶栏 ----
    top_bar = ctk.CTkFrame(frame, height=38, corner_radius=0, fg_color=WHITE)
    top_bar.pack(fill="x", side="top")
    top_bar.pack_propagate(False)

    status_dot = ctk.CTkLabel(top_bar, text="●", font=("Segoe UI", 14),
                               text_color=STATUS_GREEN, bg_color=WHITE)
    status_dot.pack(side="left", padx=(10, 2))

    title_label = ctk.CTkLabel(top_bar, text="聊天室 — 连接中...",
                                font=("Segoe UI", 12, "bold"),
                                text_color=CHAT_TITLE,
                                fg_color="white",
                                corner_radius=6,
                                cursor="hand2")
    title_label.pack(side="left", padx=6)
    title_label.bind("<Enter>", lambda e: title_label.configure(
        fg_color="#e8f5e9"))
    title_label.bind("<Leave>", lambda e: title_label.configure(
        fg_color="white"))

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

    ctk.CTkLabel(user_frame, text="🟢 在线用户",
                 font=("Segoe UI", 12, "bold"),
                 text_color=CHAT_TITLE, bg_color=WHITE).pack(
                     anchor="w", padx=14, pady=(16, 2))
    user_count = ctk.CTkLabel(user_frame, text="0 人在线",
                               font=("Segoe UI", 10),
                               text_color="#999999", bg_color=WHITE)
    user_count.pack(anchor="w", padx=14)

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
