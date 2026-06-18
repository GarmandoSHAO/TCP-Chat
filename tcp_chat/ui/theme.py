"""
UI 主题 — 颜色、字体、尺寸常量
"""
from ..config import get

CR = get("corner_radius", 16)

# ---------- 颜色 ----------
SYSTEM_FG = "#667781"
PRIVATE_FG = "#8e24aa"
ERROR_FG = "#d32f2f"
NICKNAME_FG = "#075e54"
TIMESTAMP_FG = "#999999"
HOST_GOLD = "#FFD700"
ONLINE_GREEN = "#4caf50"
WHITE = "#ffffff"
BTN_GRAY = "#555555"
HOVER_GRAY = "#e0e0e0"
HOVER_RED = "#ff4444"
CHAT_TITLE = "#075e54"
STATUS_GREEN = "#76d275"
STATUS_RED = "#f44336"

# ---------- 字体 ----------
FONT_FAMILY = "Segoe UI"
BTN_FONT = (FONT_FAMILY, 14, "bold")
MSG_FONT_SIZE = get("font_scale_base", 12)
