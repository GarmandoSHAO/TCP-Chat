"""
启动页 — 创建房间 / 加入房间
"""
import customtkinter as ctk
from .theme import *
from .icons import (
    ICON_CHAT, ICON_HOME, ICON_SEARCH,
    TEXT_APP_TITLE, TEXT_CREATE_ROOM, TEXT_JOIN_ROOM,
)
from .widgets import make_icon_label, make_title_label, make_primary_button, make_secondary_button

def build_start_view(container, on_create, on_join):
    """启动界面：两个大按钮"""
    frame = ctk.CTkFrame(container, fg_color=WHITE)
    frame.pack(fill="both", expand=True)

    make_icon_label(frame, ICON_CHAT, font_size=48).pack(pady=(50, 0))
    make_title_label(frame, TEXT_APP_TITLE, text_color=CHAT_TITLE).pack(pady=(6, 4))
    ctk.CTkLabel(frame, text="", bg_color=WHITE).pack(pady=(0, 40))

    make_primary_button(
        frame, f"{ICON_HOME}  {TEXT_CREATE_ROOM}", on_create,
    ).pack(pady=5)
    make_secondary_button(
        frame, f"{ICON_SEARCH}  {TEXT_JOIN_ROOM}", on_join,
    ).pack(pady=5)
    return frame
