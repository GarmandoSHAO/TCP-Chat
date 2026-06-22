"""
Text 标签配置 —— 消息区的 tag 样式定义与应用

统一 chat_page.py 和 app.py 中重复的 tag 配置和字体缩放逻辑。
"""
import tkinter as tk
from .theme import (
    SYSTEM_FG, PRIVATE_FG, ERROR_FG, NICKNAME_FG,
    TIMESTAMP_FG, MSG_FONT_SIZE,
)

# =============================================================================
# 标签配置表（唯一数据源）
# =============================================================================
TAG_DEFS: list[tuple[str, str, tuple]] = [
    ("system", SYSTEM_FG, ("Segoe UI", 9, "italic")),
    ("private", PRIVATE_FG, ("Segoe UI", 10)),
    ("error", ERROR_FG, ("Segoe UI", 10, "bold")),
    ("timestamp", TIMESTAMP_FG, ("Segoe UI", 8)),
    ("nickname_tag", NICKNAME_FG, ("Segoe UI", MSG_FONT_SIZE, "bold")),
    ("normal", "#000000", ("Segoe UI", MSG_FONT_SIZE)),
]

# =============================================================================
# 字体缩放覆盖映射  (tag_name → (font_size_multiplier, style))
# =============================================================================
_SCALE_OVERRIDES: dict[str, tuple[int, int, str | None]] = {
    # tag_name → (base_size, min_size, style)
    "normal": (MSG_FONT_SIZE, 10, None),
    "nickname_tag": (MSG_FONT_SIZE, 10, "bold"),
    "system": (10, 8, "italic"),
    "timestamp": (9, 7, None),
}


def apply_tags(text_widget: tk.Text, font_size: int = MSG_FONT_SIZE) -> None:
    """给 Text widget 一次性应用所有标准 tag 配置。"""
    for name, fg, (_family, _size, *style) in TAG_DEFS:
        actual_size = (
            font_size if name in ("normal", "nickname_tag")
            else max(8, int(font_size * 0.83))
        )
        font_args: list = [_family, actual_size]
        font_args.extend(style)
        text_widget.tag_configure(name, foreground=fg, font=tuple(font_args))


def scale_tags(
    text_widget: tk.Text,
    scale: float,
    base_size: int = MSG_FONT_SIZE,
) -> None:
    """按缩放比例重新配置所有 tag 字体。

    调用时机：窗口大小变化后，由 _apply_font_scaling 或 _switch_tab 触发。
    """
    for tag_name, (tag_base, min_size, style_name) in _SCALE_OVERRIDES.items():
        size = max(min_size, int(tag_base * scale))
        font_args: list = ["Segoe UI", size]
        if style_name:
            font_args.append(style_name)
        text_widget.tag_configure(tag_name, font=tuple(font_args))
