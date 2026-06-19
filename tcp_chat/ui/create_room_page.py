"""
创建房间配置页 — IP、端口、房间名、昵称
"""
import customtkinter as ctk
from .theme import *
from ..config import get, get_local_ip

def build_create_room_view(container, on_create, on_back):
    """创建房间配置页：IP、端口、房间名、昵称"""
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
        ("局域网IP:端口", f"{local_ip}:{get('default_port', 8888)}", 24),
        ("外网IP", "正在建造隧道...", 24, True),
        ("房间名称", get("default_room_name", "聊天室"), 20),
        ("昵称", get("default_nickname", "用户"), 20),
    ]
    for item in fields:
        label, default, width = item[0], item[1], item[2]
        placeholder = item[3] if len(item) > 3 else False
        row = ctk.CTkFrame(form, fg_color="transparent")
        row.pack(fill="x", pady=4)
        ctk.CTkLabel(row, text=label, width=65, anchor="e",
                     font=("Segoe UI", 11),
                     bg_color=WHITE).pack(side="left", padx=(0, 8))
        entry = ctk.CTkEntry(row, font=("Segoe UI", 12),
                              width=width * 8, height=30, corner_radius=6)
        entry.insert(0, default)
        if placeholder:
            entry.configure(text_color="#aaaaaa")
        entry.pack(side="left")
        entries[label] = entry

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
    return frame, entries
