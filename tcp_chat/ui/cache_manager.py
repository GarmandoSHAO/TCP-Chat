"""
聊天记录缓存管理 — 每个房间一个 JSON 文件
用于在切换标签页时恢复聊天记录和在线用户列表
"""
import json
import os

from ..config import get_app_root

_CACHE_DIR = None


def _get_dir():
    """获取缓存目录路径（应用根目录/chat_cache）"""
    global _CACHE_DIR
    if _CACHE_DIR is None:
        _CACHE_DIR = os.path.join(get_app_root(), "chat_cache")
    return _CACHE_DIR


def _ensure_dir():
    """确保缓存目录存在"""
    os.makedirs(_get_dir(), exist_ok=True)


def _path_for(room_id):
    """获取房间对应的缓存文件路径"""
    return os.path.join(_get_dir(), f"room_{room_id}.json")


def save(room_id, data):
    """保存房间状态到缓存文件

    Args:
        room_id: 房间号
        data: dict, 包含 messages, online_users, host_id 等
    """
    if not room_id:
        return
    _ensure_dir()
    try:
        with open(_path_for(room_id), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
    except Exception:
        pass


def load(room_id):
    """从缓存文件加载房间状态

    Returns:
        dict | None
    """
    if not room_id:
        return None
    try:
        path = _path_for(room_id)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return None


def delete(room_id):
    """删除房间缓存文件"""
    if not room_id:
        return
    try:
        path = _path_for(room_id)
        if os.path.exists(path):
            os.remove(path)
    except Exception:
        pass


def cleanup():
    """关闭程序时清除整个缓存目录"""
    import shutil
    try:
        d = _get_dir()
        if os.path.exists(d):
            shutil.rmtree(d)
    except Exception:
        pass
