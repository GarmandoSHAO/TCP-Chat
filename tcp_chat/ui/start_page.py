"""
启动页 — 创建房间 / 加入房间
"""
import customtkinter as ctk
from .theme import *

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
