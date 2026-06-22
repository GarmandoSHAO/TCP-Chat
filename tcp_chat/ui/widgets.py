"""
共享 UI 组件 — 窗口按钮、拖拽工具、UI 工厂函数
"""
from typing import Callable
import customtkinter as ctk
from .theme import BTN_FONT, WHITE, BTN_GRAY, HOVER_GRAY, CHAT_TITLE


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


# =============================================================================
# UI 工厂函数 —— 统一标签和按钮样式
# =============================================================================
def make_icon_label(
    parent: ctk.CTkFrame, icon: str,
    font_size: int = 40, **kwargs,
) -> ctk.CTkLabel:
    """创建图标标签（大号 emoji）。"""
    return ctk.CTkLabel(
        parent, text=icon, font=("Segoe UI", font_size),
        bg_color=WHITE, **kwargs,
    )


def make_title_label(
    parent: ctk.CTkFrame, text: str,
    font_size: int = 22, **kwargs,
) -> ctk.CTkLabel:
    """创建标题标签（深色加粗，默认 #1a1a1a）。"""
    defaults: dict = {"text_color": "#1a1a1a", "bg_color": WHITE}
    defaults.update(kwargs)
    return ctk.CTkLabel(
        parent, text=text,
        font=("Segoe UI", font_size, "bold"), **defaults,
    )


def make_subtitle_label(
    parent: ctk.CTkFrame, text: str, **kwargs,
) -> ctk.CTkLabel:
    """创建副标题标签（灰色小字，默认 #888888）。"""
    defaults: dict = {"text_color": "#888888", "bg_color": WHITE}
    defaults.update(kwargs)
    return ctk.CTkLabel(
        parent, text=text, font=("Segoe UI", 11), **defaults,
    )


def make_primary_button(
    parent: ctk.CTkFrame, text: str,
    command: Callable[[], None],
    width: int = 220, height: int = 44,
    **kwargs,
) -> ctk.CTkButton:
    """创建主色调按钮（CHAT_TITLE 背景）。"""
    return ctk.CTkButton(
        parent, text=text, font=("Segoe UI", 14, "bold"),
        width=width, height=height, corner_radius=10,
        fg_color=CHAT_TITLE, hover_color="#054d44",
        command=command, **kwargs,
    )


def make_secondary_button(
    parent: ctk.CTkFrame, text: str,
    command: Callable[[], None],
    width: int = 220, height: int = 44,
    **kwargs,
) -> ctk.CTkButton:
    """创建次要按钮（白色背景 + 边框风格）。"""
    return ctk.CTkButton(
        parent, text=text, font=("Segoe UI", 14, "bold"),
        width=width, height=height, corner_radius=10,
        fg_color=WHITE, text_color=CHAT_TITLE,
        hover_color="#e8f5e9", border_width=2,
        border_color=CHAT_TITLE, command=command, **kwargs,
    )
