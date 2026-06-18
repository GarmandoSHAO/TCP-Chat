"""
配置管理 — 加载 config.json，提供默认值
"""
import json
import os
import socket

_CONFIG = None


def _find_config():
    """从项目根目录查找 config.json"""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(root, "config.json")
    if os.path.exists(path):
        return path
    return None


def _defaults():
    """默认配置"""
    return {
        "discovery_port": 9999,
        "default_host": "127.0.0.1",
        "default_port": 8888,
        "default_nickname": "用户",
        "default_room_name": "聊天室",
        "appearance": "light",
        "theme": "green",
        "font_scale_base": 12,
        "window": {
            "login_width": 420,
            "login_height": 480,
            "chat_width": 880,
            "chat_height": 640,
            "chat_min_width": 700,
            "chat_min_height": 500,
        },
        "corner_radius": 16,
    }


def load():
    """加载配置（全局单例）"""
    global _CONFIG
    if _CONFIG is not None:
        return _CONFIG
    cfg = _defaults()
    path = _find_config()
    if path:
        try:
            with open(path, "r", encoding="utf-8") as f:
                user = json.load(f)
            cfg.update(user)
        except (json.JSONDecodeError, OSError):
            pass
    _CONFIG = cfg
    return cfg


def get(key, default=None):
    """获取配置项"""
    cfg = load()
    return cfg.get(key, default)


def get_local_ip():
    """获取本机局域网 IP"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"
