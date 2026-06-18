"""
共享 UI 组件 — 窗口按钮、拖拽工具
"""
import tkinter as tk
import customtkinter as ctk
from .theme import CR, BTN_FONT, WHITE, BTN_GRAY, HOVER_GRAY, HOVER_RED


def win_btn(parent, text, cmd, hover=HOVER_GRAY):
    """统一窗口按钮（CTkButton，圆角悬停）"""
    btn = ctk.CTkButton(parent, text=text, width=40, height=30,
                        font=BTN_FONT, corner_radius=8,
                        fg_color=WHITE, text_color=BTN_GRAY,
                        hover_color=hover, command=cmd)
    btn.pack(side="right", padx=(0, 1))
    return btn


def make_draggable(widget, drag_data):
    """让控件可拖动窗口"""
    widget.bind("<Button-1>", lambda e: _drag_start(e, drag_data, widget))
    widget.bind("<B1-Motion>", lambda e: _drag_move(e, drag_data, widget))


def _drag_start(event, drag_data, _widget):
    drag_data["x"] = event.x_root - event.widget.winfo_toplevel().winfo_x()
    drag_data["y"] = event.y_root - event.widget.winfo_toplevel().winfo_y()


def _drag_move(event, drag_data, _widget):
    x = event.x_root - drag_data["x"]
    y = event.y_root - drag_data["y"]
    event.widget.winfo_toplevel().geometry(f"+{x}+{y}")
