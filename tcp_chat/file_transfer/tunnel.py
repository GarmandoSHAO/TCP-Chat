"""
bore 隧道管理 —— 自动启动、监控和重连

封装 bore.exe 进程的生命周期管理。
支持自动重连（隧道断开后自动重启）。
"""

import os
import subprocess
import threading
import time
import re
import logging
from typing import Optional

from ..config import get_app_root

logger = logging.getLogger(__name__)

# bore 可执行文件搜索路径
BORE_FILENAME = "bore.exe" if os.name == "nt" else "bore"
DEFAULT_BORE_PATH = os.path.join(get_app_root(), BORE_FILENAME)


def find_bore() -> Optional[str]:
    """查找 bore 可执行文件路径"""
    # 1. 项目根目录
    if os.path.exists(DEFAULT_BORE_PATH):
        return os.path.abspath(DEFAULT_BORE_PATH)

    # 2. 系统 PATH
    import shutil
    path = shutil.which(BORE_FILENAME)
    if path:
        return os.path.abspath(path)

    # 3. 当前目录
    if os.path.exists(BORE_FILENAME):
        return os.path.abspath(BORE_FILENAME)

    return None


class BoreTunnel:
    """
    bore 隧道管理器

    使用方式:
        tunnel = BoreTunnel()
        addr = tunnel.start(local_port=9000)
        print(f"Public: {addr}")
        # ... 传输中 ...
        tunnel.stop()
    """

    # bore.pub 默认服务器
    DEFAULT_SERVER = "bore.pub"

    def __init__(self, bore_path: Optional[str] = None, server: str = DEFAULT_SERVER):
        self.bore_path = bore_path or find_bore()
        if not self.bore_path:
            raise FileNotFoundError(
                "bore executable not found. "
                "Download from https://github.com/ekzhang/bore/releases"
            )

        self.server = server
        self._process: Optional[subprocess.Popen] = None
        self._public_addr: Optional[str] = None
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._monitor_thread: Optional[threading.Thread] = None
        self._local_port: Optional[int] = None

    # ── 生命周期 ──────────────────────────────────────

    def start(self, local_port: int, max_retries: int = -1) -> str:
        """
        启动 bore 隧道。

        参数:
            local_port: 本地端口
            max_retries: 重试次数（-1 表示无限重试）

        返回:
            public_addr: 公网地址字符串 "bore.pub:xxxxx"

        抛出:
            RuntimeError: 启动失败（达到重试上限）
        """
        self._local_port = local_port
        self._stop_event.clear()
        retry_delay = 1.0
        attempts = 0

        while not self._stop_event.is_set():
            attempts += 1
            try:
                public_addr = self._start_once(local_port)
                if public_addr:
                    self._public_addr = public_addr
                    logger.info("bore tunnel ready: %s", public_addr)

                    # 启动监控线程（检测进程退出后自动重启）
                    self._start_monitor()

                    return public_addr
            except Exception as e:
                logger.warning("bore start attempt %d failed: %s", attempts, e)

            if max_retries != -1 and attempts >= max_retries:
                raise RuntimeError(
                    f"bore failed after {attempts} attempts"
                )

            logger.info("retrying bore in %.0fs...", retry_delay)
            self._stop_event.wait(retry_delay)
            retry_delay = min(retry_delay * 2, 30.0)

        raise RuntimeError("bore tunnel stopped before becoming ready")

    def stop(self) -> None:
        """停止 bore 隧道"""
        self._stop_event.set()
        self._kill_process()

    def wait(self, timeout: Optional[float] = None) -> None:
        """等待隧道完全停止"""
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=timeout)

    @property
    def public_addr(self) -> Optional[str]:
        """获取公网地址"""
        return self._public_addr

    @property
    def is_alive(self) -> bool:
        """检查隧道进程是否存活"""
        if self._process is None:
            return False
        ret = self._process.poll()
        return ret is None  # None = 仍在运行

    # ── 内部实现 ──────────────────────────────────────

    def _start_once(self, local_port: int) -> Optional[str]:
        """启动一次 bore 进程，返回公网地址或 None"""
        self._kill_process()

        cmd = [
            self.bore_path,
            "local",
            str(local_port),
            "--to", self.server,
        ]

        logger.debug("Running: %s", " ".join(cmd))

        # Windows 上隐藏控制台窗口
        startupinfo = None
        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        self._process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            startupinfo=startupinfo,
        )

        # 从 stdout 解析公网地址
        public_addr = self._parse_public_addr(self._process)
        return public_addr

    def _parse_public_addr(self, process: subprocess.Popen) -> Optional[str]:
        """从 bore stdout 解析公网地址"""
        # bore 输出格式（不同版本有差异）:
        # "listening at bore.pub:12345"
        # "bore.pub:12345"
        # "remote_port=12345"
        patterns = [
            re.compile(r"listening at\s+(\S+)", re.IGNORECASE),
            re.compile(r"(\S+\.pub:\d+)"),
            re.compile(r"remote_port=(\d+)"),
        ]

        output_buffer = ""
        deadline = time.time() + 10.0  # 10 秒超时

        while time.time() < deadline and process.poll() is None:
            try:
                line = process.stdout.readline()
                if line:
                    text = line.decode("utf-8", errors="replace").strip()
                    output_buffer += text + "\n"
                    logger.debug("bore: %s", text)

                    for pattern in patterns:
                        match = pattern.search(text)
                        if match:
                            addr = match.group(1)
                            # 如果只匹配到端口号，拼完整地址
                            if addr.isdigit():
                                addr = f"{self.server}:{addr}"
                            return addr
            except (IOError, OSError):
                break

        # 超时：检查进程是否已退出
        if process.poll() is not None:
            remaining = process.stdout.read()
            if remaining:
                output_buffer += remaining.decode("utf-8", errors="replace")
            logger.error("bore exited early:\n%s", output_buffer)

        return None

    def _start_monitor(self) -> None:
        """启动监控线程，进程退出后自动重启"""
        if self._monitor_thread and self._monitor_thread.is_alive():
            return  # 已有监控线程在运行

        def monitor():
            while not self._stop_event.is_set():
                if self._process is None:
                    break

                # 等待进程退出
                try:
                    self._process.wait()
                except OSError:
                    pass

                if self._stop_event.is_set():
                    break

                logger.warning("bore process died, restarting...")

                # 自动重启
                if self._local_port is not None:
                    try:
                        addr = self._start_once(self._local_port)
                        if addr:
                            self._public_addr = addr
                            logger.info("bore tunnel restored: %s", addr)
                            continue
                    except Exception as e:
                        logger.error("bore restart failed: %s", e)

                # 重启失败，等待后重试
                self._stop_event.wait(5.0)

        self._monitor_thread = threading.Thread(target=monitor, daemon=True)
        self._monitor_thread.start()

    def _kill_process(self) -> None:
        """终止 bore 进程"""
        if self._process is not None:
            try:
                self._process.terminate()
                self._process.wait(timeout=5)
            except Exception:
                try:
                    self._process.kill()
                    self._process.wait(timeout=3)
                except Exception:
                    pass
            finally:
                self._process = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()

    def __repr__(self) -> str:
        status = "alive" if self.is_alive else "stopped"
        addr = self._public_addr or "N/A"
        return f"BoreTunnel({addr}, {status})"
