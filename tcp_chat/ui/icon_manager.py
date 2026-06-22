"""
统一窗口图标管理器

所有窗口（主窗口、初始界面、弹窗）的图标统一通过此模块设置。
源文件为 TCP-Chat.png，程序启动时自动用 Pillow 生成多尺寸 .ico。
修改图标只需替换 TCP-Chat.png，重启后自动生效。
"""
import os
import sys
import logging
from typing import Optional, Union

import customtkinter as ctk
import tkinter as tk

from ..config import get_app_root

# =============================================================================
# 模块级常量
# =============================================================================

logger = logging.getLogger(__name__)

_ICO_SIZES: tuple[int, ...] = (256, 128, 64, 48, 32, 16)
"""生成 ICO 时包含的尺寸列表（从大到小，确保首张为主图），覆盖常见窗口缩放级别。"""

try:
    from PIL import Image
    _HAS_PIL = True
except ImportError:
    _HAS_PIL = False
"""Pillow 可用性标志。不可用时降级使用已有 .ico。"""

_APP_USER_MODEL_ID_SET: bool = False
"""_set_app_user_model_id 是否已执行过（会话级单次）。"""

_ICO_CHECKED: bool = False
"""ensure_ico 是否已执行过完整检测（一次成功 = 会话级缓存）。"""

_ICO_PATH: Optional[str] = None
"""ensure_ico 缓存的结果路径（None 表示无可用图标）。"""


def _set_app_user_model_id(app_id: str = "TCPChat.Room.1") -> None:
    """Windows 7+：设置当前进程的 Application User Model ID。

    这告诉 Windows 任务栏将当前进程归类到指定模型 ID，
    从而使用 .exe 或 .lnk 的图标，而不是 python.exe 的默认图标。
    只需在模块加载时调用一次。
    """
    global _APP_USER_MODEL_ID_SET
    if _APP_USER_MODEL_ID_SET:
        return
    _APP_USER_MODEL_ID_SET = True
    if os.name != "nt":
        return
    try:
        import ctypes
        shell32 = ctypes.windll.shell32
        shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
        logger.debug("_set_app_user_model_id: OK app_id=%s", app_id)
    except Exception:
        logger.debug("_set_app_user_model_id: FAILED", exc_info=True)


# 模块加载时执行一次
_set_app_user_model_id()


# =============================================================================
# 内部辅助
# =============================================================================

def _find_icon_file(ext: str) -> Optional[str]:
    """搜索图标文件：先应用根目录，再回退到 _internal 目录（PyInstaller --onedir）。

    Args:
        ext: 文件扩展名，如 ".ico" 或 ".png"。

    Returns:
        图标文件的绝对路径，或 None。
    """
    # 1. 应用根目录
    path = os.path.join(get_app_root(), f"TCP-Chat{ext}")
    if os.path.exists(path):
        return path
    # 2. _internal 子目录（PyInstaller --onedir 打包数据文件）
    if getattr(sys, "frozen", False):
        internal = os.path.join(os.path.dirname(sys.executable), "_internal", f"TCP-Chat{ext}")
        if os.path.exists(internal):
            return internal
    return None


# =============================================================================
# 公开接口
# =============================================================================

def set_window_icon(window: Union[ctk.CTk, ctk.CTkToplevel, tk.Tk, tk.Toplevel]) -> None:
    """对任意窗口设置 TCP-Chat 图标。

    设置顺序（关键——顺序决定最终效果）：
      1. iconphoto(True, PhotoImage) ← 注册大尺寸 HICON，任务栏优先使用
      2. iconbitmap(ico_path) / wm_iconbitmap(ico_path) ← ICO 多尺寸覆盖，标题栏清晰

    Args:
        window: 需要设置图标的窗口实例。
    """
    ico_path = ensure_ico()

    if not ico_path:
        logger.debug("set_window_icon: 无可用 .ico 文件，跳过")
        return

    # ── Step 1: 加载 PNG 为 PhotoImage，调用 iconphoto ──
    # 这步注册大尺寸 HICON，Windows 任务栏优先使用此图标
    try:
        png_path = _find_icon_file(".png")
        if png_path:
            photo = tk.PhotoImage(file=png_path)
            window.iconphoto(True, photo)
            logger.debug("set_window_icon(%s) iconphoto → OK", type(window).__name__)
    except Exception:
        logger.debug("set_window_icon(%s) iconphoto → FAILED", type(window).__name__)

    # ── Step 2: 用 .ico 的 iconbitmap 覆盖 ──
    # iconbitmap 在后面调用，其 SetClassLong + WM_SETICON 完全覆盖，ICO 多尺寸兼容性更好
    try:
        if isinstance(window, ctk.CTkToplevel):
            # 必须用 wm_iconbitmap（非 iconbitmap），否则 customtkinter
            # 不会设置 _iconbitmap_method_called 标志，200ms 后图标被默认值覆盖
            window.wm_iconbitmap(ico_path)
            logger.debug("set_window_icon(CTkToplevel) wm_iconbitmap → OK")
        else:
            window.iconbitmap(ico_path)
            logger.debug("set_window_icon(%s) iconbitmap → OK", type(window).__name__)
    except Exception:
        logger.debug("set_window_icon(%s) iconbitmap → FAILED", type(window).__name__)


def get_icon_path(ext: str = ".ico") -> str:
    """获取图标文件的绝对路径。

    优先应用根目录，PyInstaller --onedir 打包时回退 _internal/ 子目录。

    Args:
        ext: 文件扩展名，如 ".ico" 或 ".png"。

    Returns:
        图标文件的绝对路径字符串。
    """
    found = _find_icon_file(ext)
    if found:
        return found
    # 回退：即使文件不存在也返回应用根目录路径（用于创建 .ico 等场景）
    return os.path.join(get_app_root(), f"TCP-Chat{ext}")


def ensure_ico() -> Optional[str]:
    """确保 .ico 文件存在且为最新，返回其路径。

    首次调用时执行完整检测和重建；后续调用直接返回缓存结果（会话级）。
    要强制重新检测，须重启程序。

    检测逻辑：
        1. 如果 .ico 不存在或比 .png 旧 → 重建
        2. 重建依赖 Pillow，不可用时降级返回已有 .ico
        3. 两者皆无返回 None

    Returns:
        .ico 文件的绝对路径，或 None（无可用图标）。
    """
    global _ICO_CHECKED, _ICO_PATH

    if _ICO_CHECKED:
        return _ICO_PATH

    ico_path = get_icon_path(".ico")
    png_path = get_icon_path(".png")

    if not os.path.exists(png_path):
        logger.debug("ensure_ico: PNG 不存在 → %s", png_path)
        _ICO_CHECKED = True
        _ICO_PATH = ico_path if os.path.exists(ico_path) else None
        return _ICO_PATH

    if _need_rebuild(png_path, ico_path):
        if _HAS_PIL:
            if _png_to_ico(png_path, ico_path):
                logger.debug("ensure_ico: 重建 .ico 成功 → %s", ico_path)
            else:
                logger.warning("ensure_ico: 重建 .ico 失败")
                _ICO_CHECKED = True
                _ICO_PATH = ico_path if os.path.exists(ico_path) else None
                return _ICO_PATH
        else:
            logger.debug("ensure_ico: Pillow 不可用，使用已有 .ico")
            if os.path.exists(ico_path):
                _ICO_CHECKED = True
                _ICO_PATH = ico_path
                return _ICO_PATH
            logger.warning("ensure_ico: Pillow 不可用且无 .ico，无法设置图标")
            _ICO_CHECKED = True
            _ICO_PATH = None
            return None
    else:
        logger.debug("ensure_ico: .ico 已是最新 → %s", ico_path)

    _ICO_CHECKED = True
    _ICO_PATH = ico_path if os.path.exists(ico_path) else None
    return _ICO_PATH


# =============================================================================
# 内部函数
# =============================================================================

def _need_rebuild(png_path: str, ico_path: str) -> bool:
    """检查 .ico 是否需要重建。

    需要重建的条件：
        - .ico 文件不存在
        - .png 文件的修改时间晚于 .ico 的修改时间

    Args:
        png_path: PNG 源文件路径（调用方保证存在）。
        ico_path: ICO 目标文件路径。

    Returns:
        需要重建返回 True。
    """
    if not os.path.exists(ico_path):
        return True
    png_mtime = os.path.getmtime(png_path)
    ico_mtime = os.path.getmtime(ico_path)
    return png_mtime > ico_mtime


def _png_to_ico(png_path: str, ico_path: str) -> bool:
    """用 Pillow 将 PNG 转为多尺寸 ICO 文件。

    生成的 ICO 包含 _ICO_SIZES 中列出的所有尺寸，
    确保在不同 DPI 和窗口缩放级别下图标清晰。

    Args:
        png_path: 源 PNG 文件路径。
        ico_path: 目标 ICO 文件路径。

    Returns:
        转换成功返回 True，否则 False。
    """
    try:
        with Image.open(png_path) as source:
            sizes = []
            for size in _ICO_SIZES:
                # 使用 LANCZOS 高质量重采样
                resized = source.resize((size, size), Image.Resampling.LANCZOS)
                # 确保是 RGBA 模式，.ico 需要
                if resized.mode != "RGBA":
                    resized = resized.convert("RGBA")
                sizes.append(resized)

            # 写入 .ico 文件（首个尺寸为主图，其余通过 append_images 附加）
            sizes[0].save(
                ico_path,
                format="ICO",
                append_images=sizes[1:],
            )
        return True
    except Exception:
        logger.exception("_png_to_ico 转换失败")
        return False
