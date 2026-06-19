"""
登录页 — 地址输入、扫描、连接
"""
import tkinter as tk
import customtkinter as ctk
from .theme import *

def build_login_view(container, fields_config, on_connect):
    """登录界面：地址:端口 + 昵称 + 连接按钮"""
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
