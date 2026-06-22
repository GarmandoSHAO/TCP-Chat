"""
可复用 UI 模式 —— 滚动条自动隐藏、消息插入、表单行、用户卡片

提取自 chat_page.py、app.py、login_page.py、create_room_page.py 的重复模式。
"""
import tkinter as tk
from typing import Callable
import customtkinter as ctk
from .theme import HOST_GOLD, ONLINE_GREEN
from .icons import ICON_HOST, ICON_DOT_ONLINE


# =============================================================================
# 滚动条自动隐藏
# =============================================================================
def make_auto_hide_scrollbar(
    container: ctk.CTkFrame,
    text_widget: tk.Text,
    scrollbar: ctk.CTkScrollbar,
    hide_delay_ms: int = 1500,
) -> None:
    """给 Text widget 绑定自动隐藏滚动条逻辑。

    鼠标滚轮时显示滚动条，空闲 hide_delay_ms 后自动隐藏。
    内容可完全显示（first=='0.0' and last=='1.0'）时不显示。
    """
    _scroll_timer: list[int | None] = [None]

    def _on_scroll(first: str, last: str) -> None:
        scrollbar.set(first, last)
        if first == "0.0" and last == "1.0":
            scrollbar.grid_remove()
        else:
            scrollbar.grid()

    def _auto_hide() -> None:
        if _scroll_timer[0] is not None:
            container.after_cancel(_scroll_timer[0])
        _scroll_timer[0] = container.after(hide_delay_ms, scrollbar.grid_remove)

    def _on_mousewheel(event: tk.Event) -> str:
        text_widget.yview_scroll(int(-1 * event.delta / 120), "units")
        first, last = text_widget.yview()
        if first != "0.0" or last != "1.0":
            scrollbar.grid()
            _auto_hide()
        return "break"

    text_widget.config(yscrollcommand=_on_scroll)
    scrollbar.grid_remove()
    text_widget.bind("<MouseWheel>", _on_mousewheel)
    container.bind("<MouseWheel>", _on_mousewheel)


# =============================================================================
# 消息插入辅助
# =============================================================================
def insert_msg(
    text_widget: tk.Text,
    text: str,
    tag: str = "system",
    *,
    ensure_newline: bool = True,
    auto_scroll: bool = True,
) -> None:
    """向 Text widget 安全插入一条消息。

    自动处理 state 切换、换行、滚动，调用方无需关心内部状态。
    """
    text_widget.config(state="normal")
    if ensure_newline and text_widget.get("end-2c", "end-1c") != "":
        text_widget.insert("end", "\n")
    text_widget.insert("end", text, (tag,))
    if auto_scroll:
        text_widget.see("end")
    text_widget.config(state="disabled")


def insert_msg_with_timestamp(
    text_widget: tk.Text,
    timestamp: str,
    content: str,
    tag: str = "normal",
    *,
    nickname: str | None = None,
    is_self: bool = False,
) -> None:
    """插入带时间戳的聊天/私聊消息。

    Args:
        text_widget: 目标 Text 控件
        timestamp: 时间字符串（如 "14:30"）
        content: 消息内容
        tag: 内容使用的 tag
        nickname: 发送者昵称（可选，有则先插入昵称行）
        is_self: 是否为本人发送（昵称后追加 "(我)"）
    """
    text_widget.config(state="normal")
    if text_widget.get("end-2c", "end-1c") != "":
        text_widget.insert("end", "\n")
    text_widget.insert("end", f"  {timestamp}  ", ("timestamp",))
    if nickname:
        suffix = " (我)" if is_self else ""
        text_widget.insert("end", nickname + suffix, ("nickname_tag",))
        text_widget.insert("end", f"\n{content}", (tag,))
    else:
        text_widget.insert("end", content, (tag,))
    text_widget.see("end")
    text_widget.config(state="disabled")


# =============================================================================
# 表单行
# =============================================================================
def make_form_row(
    parent: ctk.CTkFrame,
    label: str,
    default: str,
    label_width: int = 75,
    entry_width_ch: int = 24,
    *,
    readonly: bool = False,
) -> ctk.CTkEntry:
    """创建标准表单行：标签 + Entry，返回 Entry 控件。

    替代 login_page.py 和 create_room_page.py 中的内联循环构建。
    """
    row = ctk.CTkFrame(parent, fg_color="transparent")
    row.pack(fill="x", pady=4)

    ctk.CTkLabel(
        row, text=label, width=label_width, anchor="e",
        font=("Segoe UI", 11),
    ).pack(side="left", padx=(0, 8))

    entry = ctk.CTkEntry(
        row, font=("Segoe UI", 12),
        width=entry_width_ch * 8, height=30, corner_radius=6,
    )
    entry.insert(0, default)
    if readonly:
        entry.configure(text_color="#aaaaaa")
    entry.pack(side="left")
    return entry


# =============================================================================
# 用户卡片
# =============================================================================
def make_user_card(
    parent: ctk.CTkFrame,
    nick: str,
    *,
    is_host: bool = False,
    is_self: bool = False,
    font_size: int = 12,
    on_right_click: Callable[[object, str], None] | None = None,
) -> ctk.CTkFrame:
    """创建单个用户卡片（含悬停变色、右键菜单绑定）。

    Returns:
        CTkFrame: 用户卡片行容器
    """
    # 配色
    if is_host:
        bg = "#fff8e1"
        hover_bg = "#ffecb3"
    elif is_self:
        bg = "#f5f5f5"
        hover_bg = "#e0e0e0"
    else:
        bg = "#f0fdf4"
        hover_bg = "#c8f0d0"

    row = ctk.CTkFrame(parent, fg_color=bg, corner_radius=8, border_width=0)
    row.pack(fill="x", pady=1, padx=4)

    indicator = ICON_HOST if is_host else f"  {ICON_DOT_ONLINE} "
    icolor = HOST_GOLD if is_host else ONLINE_GREEN
    ind_lbl = ctk.CTkLabel(
        row, text=indicator, font=("Segoe UI", font_size + 2),
        text_color=icolor, fg_color=bg,
    )
    ind_lbl.pack(side="left", padx=(6, 2))

    lbl = ctk.CTkLabel(
        row, text=nick, font=("Segoe UI", font_size),
        anchor="w",
        cursor="hand2" if not is_self else "",
    )
    lbl.pack(side="left", fill="x", expand=True)

    if not is_self and on_right_click:
        lbl.bind("<Button-3>", lambda e, n=nick: on_right_click(e, n))

    # 悬停变色
    def _enter(e, r=row, i=ind_lbl, h=hover_bg):
        r.configure(fg_color=h)
        i.configure(fg_color=h)

    def _leave(e, r=row, i=ind_lbl, b=bg):
        r.configure(fg_color=b)
        i.configure(fg_color=b)

    for w in (row, lbl, ind_lbl):
        w.bind("<Enter>", _enter)
        w.bind("<Leave>", _leave)

    return row
