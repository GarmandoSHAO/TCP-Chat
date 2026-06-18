"""
隧道穿透 — 将本地端口暴露到公网（bore / ngrok）
"""
import subprocess
import threading
import time
import re
import sys
import os


def find_bore():
    """查找 bore 可执行文件"""
    # 优先找项目目录下的 bore.exe
    local = os.path.join(os.path.dirname(os.path.dirname(__file__)), "bore.exe")
    if os.path.exists(local):
        return local
    # 找 PATH 里的 bore
    for path in os.environ.get("PATH", "").split(os.pathsep):
        p = os.path.join(path, "bore")
        if os.path.exists(p):
            return p
        p_exe = os.path.join(path, "bore.exe")
        if os.path.exists(p_exe):
            return p_exe
    return None


def find_ngrok():
    """查找 ngrok 可执行文件"""
    local = os.path.join(os.path.dirname(os.path.dirname(__file__)), "ngrok.exe")
    if os.path.exists(local):
        return local
    for path in os.environ.get("PATH", "").split(os.pathsep):
        p = os.path.join(path, "ngrok")
        if os.path.exists(p):
            return p
        p_exe = os.path.join(path, "ngrok.exe")
        if os.path.exists(p_exe):
            return p_exe
    return None


class BoreTunnel:
    """bore 隧道（https://github.com/ekzhang/bore）"""

    def __init__(self, local_port=8888, relay="bore.pub"):
        self.local_port = local_port
        self.relay = relay
        self.process = None
        self.public_port = None
        self._output = []
        self._done = False
        self._result = None

    def start(self):
        """启动 bore 隧道（带超时）"""
        bore_path = find_bore()
        if not bore_path:
            return False, "未找到 bore，请下载后放到项目目录\nhttps://github.com/ekzhang/bore/releases"

        self.process = subprocess.Popen(
            [bore_path, "local", str(self.local_port), "--to", self.relay],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, creationflags=subprocess.CREATE_NO_WINDOW)

        # 用线程读取输出（避免 readline 阻塞导致超时失效）
        def _reader():
            while not self._done:
                line = self.process.stdout.readline()
                if not line:
                    break
                self._output.append(line)
                m = re.search(r"listening at (.+?):(\d+)", line)
                if m:
                    self.public_port = int(m.group(2))
                    self._result = (True, f"{m.group(1)}:{self.public_port}")
                    return
                # 也试 remote_port 格式
                m = re.search(r"remote_port=(\d+)", line)
                if m:
                    self.public_port = int(m.group(1))
                    self._result = (True, f"bore.pub:{self.public_port}")
                    return
                if "error" in line.lower() or "refused" in line.lower():
                    self._result = (False, line.strip())
                    return

        t = threading.Thread(target=_reader, daemon=True)
        t.start()

        # 等待结果（带超时）
        t.join(timeout=10)
        self._done = True

        if self._result:
            return self._result
        return False, "bore 连接失败（请检查网络或防火墙是否阻止了 bore.pub）"

    def stop(self):
        self._done = True
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(3)
            except Exception:
                pass
            self.process = None

    @property
    def public_addr(self):
        if self.public_port:
            return f"bore.pub:{self.public_port}"
        return None


class NgrokTunnel:
    """ngrok 隧道（https://ngrok.com）"""

    def __init__(self, local_port=8888):
        self.local_port = local_port
        self.process = None
        self.public_addr = None
        self._output = []

    def start(self):
        ngrok_path = find_ngrok()
        if not ngrok_path:
            return False, "未找到 ngrok，请下载后放到项目目录\nhttps://ngrok.com/download"

        self.process = subprocess.Popen(
            [ngrok_path, "tcp", str(self.local_port), "--log=stdout"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, creationflags=subprocess.CREATE_NO_WINDOW)

        start = time.time()
        while time.time() - start < 10:
            line = self.process.stdout.readline()
            if not line:
                break
            self._output.append(line)
            # ngrok 输出 JSON 格式，包含 public_url
            if '"url"' in line and 'tcp://' in line:
                m = re.search(r'tcp://([^:]+:\d+)', line)
                if m:
                    self.public_addr = m.group(1)
                    return True, self.public_addr
        return False, "ngrok 启动失败\n" + "\n".join(self._output[-5:])

    def stop(self):
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(3)
            except Exception:
                pass
            self.process = None


def auto_tunnel(local_port=8888):
    """自动选择可用隧道（优先 bore）"""
    if find_bore():
        return BoreTunnel(local_port)
    if find_ngrok():
        return NgrokTunnel(local_port)
    return None
