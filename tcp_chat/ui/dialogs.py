"""
通用弹窗组件 —— 确认框、信息展示框、IP 信息弹窗

提取自 app.py 的 _confirm_disconnect 和 _show_ip 方法。
"""
from typing import Callable
import customtkinter as ctk
from .theme import CHAT_TITLE, WHITE
from .icons import ICON_SUCCESS, ICON_EXIT_ROOM
from .icon_manager import set_window_icon


def show_confirm(
    parent: ctk.CTk,
    title: str,
    message: str,
    on_confirm: Callable[[], None],
    *,
    confirm_text: str = "确定",
    cancel_text: str = "取消",
    width: int = 300,
    height: int = 140,
) -> ctk.CTkToplevel:
    """通用确认弹窗。

    Args:
        parent: 父窗口
        title: 弹窗标题
        message: 确认提示文本
        on_confirm: 点击确定后的回调
        confirm_text: 确认按钮文本
        cancel_text: 取消按钮文本
        width: 弹窗宽度
        height: 弹窗高度

    Returns:
        CTkToplevel: 模态弹窗实例
    """
    x = parent.winfo_x() + 120
    y = parent.winfo_y() + 100

    win = ctk.CTkToplevel(parent, fg_color=WHITE)
    win.title(title)
    win.geometry(f"{width}x{height}+{x}+{y}")
    win.resizable(False, False)
    win.attributes("-topmost", True)
    win.grab_set()
    set_window_icon(win)

    ctk.CTkLabel(
        win, text=message,
        font=("Segoe UI", 14), text_color="#333333",
    ).pack(pady=(24, 8))

    btn_frame = ctk.CTkFrame(win, fg_color="transparent")
    btn_frame.pack(pady=(8, 0))

    ctk.CTkButton(
        btn_frame, text=confirm_text, font=("Segoe UI", 12, "bold"),
        width=80, height=32, corner_radius=6,
        fg_color=CHAT_TITLE, hover_color="#054d44",
        command=lambda: (win.destroy(), on_confirm()),
    ).pack(side="left", padx=(0, 12))

    ctk.CTkButton(
        btn_frame, text=cancel_text, font=("Segoe UI", 12),
        width=80, height=32, corner_radius=6,
        fg_color="#e0e0e0", text_color="#333333",
        hover_color="#d0d0d0", command=win.destroy,
    ).pack(side="left")

    return win


def show_info_popup(
    parent: ctk.CTk,
    title: str,
    rows: list[tuple[str, str]],
    *,
    width: int = 280,
    base_height: int = 160,
    row_height: int = 48,
) -> None:
    """通用信息弹窗，每行带复制按钮。

    Args:
        parent: 父窗口
        title: 弹窗标题
        rows: [(label, value), ...] 要展示的标签-值对
        width: 弹窗宽度
        base_height: 基础高度（无行时）
        row_height: 每行增加的高度
    """
    h = base_height + len(rows) * row_height
    x = parent.winfo_x() + 60
    y = parent.winfo_y() + 80

    win = ctk.CTkToplevel(parent, fg_color=WHITE)
    win.title(title)
    win.geometry(f"{width}x{h}+{x}+{y}")
    win.resizable(False, False)
    win.attributes("-topmost", True)
    set_window_icon(win)

    frame = ctk.CTkFrame(win, fg_color=WHITE, corner_radius=0)
    frame.pack(expand=True)

    hint = ctk.CTkLabel(
        frame, text="", font=("Segoe UI", 10), text_color="#2e7d32",
    )
    hint.pack(pady=(4, 2))

    def _copy(text: str) -> None:
        win.clipboard_clear()
        win.clipboard_append(text)
        hint.configure(text=f"{ICON_SUCCESS} 复制成功")
        win.after(1500, lambda: hint.configure(text=""))

    for label, value in rows:
        row = ctk.CTkFrame(frame, fg_color="transparent")
        row.pack(fill="x", pady=4)
        ctk.CTkLabel(
            row, text=label, font=("Segoe UI", 12), text_color="#333333",
        ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            row, text=value, font=("Segoe UI", 12), width=0, height=28,
            corner_radius=5, fg_color="#e0e0e0", text_color="#333333",
            hover_color="#d0d0d0", command=lambda v=value: _copy(v),
        ).pack(side="left")

    ctk.CTkButton(
        frame, text="关闭", font=("Segoe UI", 11), width=70, height=28,
        corner_radius=5, fg_color=CHAT_TITLE, command=win.destroy,
    ).pack()


def show_disconnect_confirm(
    parent: ctk.CTk,
    on_disconnect: Callable[[], None],
) -> None:
    """退出房间确认弹窗（对 show_confirm 的语义封装）。"""
    show_confirm(
        parent,
        title=f"{ICON_EXIT_ROOM} 退出房间",
        message="确定离开房间吗？",
        on_confirm=on_disconnect,
        confirm_text="确定",
        cancel_text="取消",
    )
