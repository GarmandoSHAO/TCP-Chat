"""
日志系统配置 —— 程序每一步都写入日志文件
"""

import logging
import os
import sys
import time
from logging.handlers import RotatingFileHandler

from .config import get_app_root

_LOG_DIR = os.path.join(get_app_root(), "logs")
os.makedirs(_LOG_DIR, exist_ok=True)

# 只保留最近 5 个日志文件
_log_files = sorted(
    os.path.join(_LOG_DIR, f) for f in os.listdir(_LOG_DIR)
    if f.startswith('chat_') and f.endswith('.log')
)
for _f in _log_files[:-4]:
    try:
        os.remove(_f)
    except OSError:
        pass

_LOG_FILE = os.path.join(_LOG_DIR, f"chat_{time.strftime('%Y%m%d_%H%M%S')}.log")

# 日志格式：[时间] [级别] [模块:行号] 消息
_FORMAT = "%(asctime)s [%(levelname)-5s] [%(name)s:%(lineno)d] %(message)s"
_DATE_FMT = "%H:%M:%S"


class MilliFormatter(logging.Formatter):
    """支持毫秒的日志格式器"""
    def formatTime(self, record, datefmt=None):
        ct = self.converter(record.created)
        if datefmt:
            s = time.strftime(datefmt, ct)
            return f"{s}.{int(record.msecs):03d}"
        return super().formatTime(record, datefmt)


def setup_logging(level=logging.DEBUG, console_level=logging.INFO):
    """
    配置全局日志：
      - 文件: logs/chat_YYYYMMDD_HHMMSS.log (DEBUG 级别，详细)
      - 控制台: INFO 级别（简略）
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    root_logger.handlers.clear()

    # 文件 handler（DEBUG 级别，包含毫秒）
    file_handler = RotatingFileHandler(
        _LOG_FILE, maxBytes=50 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(MilliFormatter(_FORMAT, _DATE_FMT))
    root_logger.addHandler(file_handler)

    # 控制台 handler（INFO 级别）
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(console_level)
    console_handler.setFormatter(MilliFormatter(
        "%(asctime)s [%(levelname)s] %(message)s", "%H:%M:%S"
    ))
    root_logger.addHandler(console_handler)

    tcp_logger = logging.getLogger("tcp_chat")
    tcp_logger.setLevel(logging.DEBUG)

    for logger_name in ("customtkinter", "PIL", "matplotlib"):
        logging.getLogger(logger_name).setLevel(logging.WARNING)

    return _LOG_FILE


def get_log_path() -> str:
    return _LOG_FILE
