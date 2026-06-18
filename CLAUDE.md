# TCP-Chat 项目 Python 知识手册

本项目是一个 TCP 聊天应用，以下整理所有 Python 相关知识和最佳实践，供 Claude Code 参考。

---

## 目录

1. [代码质量与 LSP 集成](#1-代码质量与-lsp-集成)
2. [调试技术](#2-调试技术)
3. [项目模板与脚手架](#3-项目模板与脚手架)
4. [Python 最佳实践](#4-python-最佳实践)
5. [网络编程要点](#5-网络编程要点)
6. [类型注解](#6-类型注解)
7. [测试](#7-测试)
8. [依赖管理](#8-依赖管理)

---

## 1. 代码质量与 LSP 集成

### 1.1 代码检查

```bash
# 用 pylsp 检查代码
pip install python-lsp-server
pylsp  # 启动 LSP 服务

# 用 flake8 快速检查
pip install flake8
flake8 scripts/ --max-line-length=100

# 用 pylint 深度检查
pip install pylint
pylint scripts/
```

### 1.2 自动格式化

```bash
pip install black
black scripts/ --line-length=100

# 排序导入
pip install isort
isort scripts/
```

### 1.3 常用诊断规则

| 规则 | 含义 | 修复 |
|------|------|------|
| E302 | 类和函数定义前缺 2 个空行 | 加上空行 |
| E501 | 行超长（默认 79，本项目用 100） | 折行或用括号 |
| F401 | 导入未使用 | 删除或标记 `# noqa` |
| F841 | 变量赋值未使用 | 删除或改 `_` |
| W293 | 空行含空白字符 | 删除行尾空格 |
| E712 | 布尔值比较风格 | `if x is True → if x` |

### 1.4 清理未用导入

```bash
pip install autoflake
autoflake --remove-all-unused-imports --in-place -r scripts/
```

### 1.5 完整检查流程

```bash
isort scripts/
black scripts/ --line-length=100
flake8 scripts/ --max-line-length=100
```

---

## 2. 调试技术

### 2.1 breakpoint() — 最快上手

在代码里插入：
```python
def handle_client(conn):
    breakpoint()  # 程序执行到这里会进入 pdb
    data = conn.recv(1024)
```

运行脚本，会自动进入交互式调试器。

### 2.2 pdb 命令行调试

```bash
python -m pdb scripts/server.py
python -m pdb -c continue scripts/server.py  # 停在未处理异常处
```

**pdb 常用命令：**

| 命令 | 全称 | 作用 |
|------|------|------|
| `n` | next | 执行下一行 |
| `s` | step | 步入函数内部 |
| `r` | return | 执行到函数返回 |
| `c` | continue | 继续执行到下一个断点 |
| `q` | quit | 退出调试器 |
| `w` | where | 查看调用栈 |
| `u` | up | 上移栈帧 |
| `d` | down | 下移栈帧 |
| `p expr` | print | 打印表达式值 |
| `pp expr` | pprint | 漂亮打印 |
| `l` | list | 显示当前行附近代码 |
| `ll` | long list | 显示整个函数源码 |
| `b file.py:42` | break | 在第 42 行设断点 |
| `b func_name` | break | 在函数入口设断点 |
| `cl 1` | clear | 清除编号为 1 的断点 |
| `interact` | interact | 进入完整 Python REPL |
| `display expr` | display | 每次停下时自动显示表达式 |

### 2.3 debugpy — 远程/进程附加调试

```bash
pip install debugpy

# 方式一：启动时监听
python -m debugpy --listen 127.0.0.1:5678 --wait-for-client scripts/server.py

# 方式二：附加到已有进程
python -m debugpy --listen 127.0.0.1:5678 --pid <进程ID>

# 方式三：代码内嵌
import debugpy
debugpy.listen(("127.0.0.1", 5678))
debugpy.wait_for_client()
debugpy.breakpoint()
```

### 2.4 事后回溯调试

```python
import pdb, sys

try:
    run()
except Exception:
    pdb.post_mortem(sys.exc_info()[2])
    raise
```

### 2.5 调试注意事项

- 调试 socket 程序时，建议开两个终端：一个跑 server，一个跑 client
- `PYTHONBREAKPOINT=0` 可以全局禁用 `breakpoint()`
- 调试完毕后记得清理：搜索 `breakpoint()`、`pdb.set_trace`、`debugpy.`
- debugpy 绑定用 `127.0.0.1`，不要暴露到 `0.0.0.0`

---

## 3. 项目模板与脚手架

### 3.1 标准项目结构

```
项目名/
├── src/                     # 源代码入口
│   └── tcp_chat/
│       ├── __init__.py
│       ├── server.py        # 服务端
│       ├── client.py        # 客户端
│       └── protocol.py      # 协议定义
├── tests/                   # 测试目录
│   ├── __init__.py
│   ├── test_server.py
│   └── test_client.py
├── scripts/                 # 工具脚本
├── docs/                    # 文档
├── requirements.txt         # 依赖
├── setup.py 或 pyproject.toml  # 包配置
├── README.md
├── CLAUDE.md                # 本文件
└── .gitignore
```

### 3.2 CLI 工具模板

```python
#!/usr/bin/env python3
import argparse
import sys

def main():
    parser = argparse.ArgumentParser(description="TCP Chat Client")
    parser.add_argument("--host", default="127.0.0.1", help="服务器地址")
    parser.add_argument("--port", type=int, default=8888, help="服务器端口")
    parser.add_argument("-v", "--verbose", action="store_true", help="详细输出")
    args = parser.parse_args()
    # ...
    print(f"连接到 {args.host}:{args.port}...")

if __name__ == "__main__":
    main()
```

### 3.3 FastAPI 模板（适用 HTTP API 场景）

```python
from fastapi import FastAPI, WebSocket
from pydantic import BaseModel

app = FastAPI(title="Chat API", version="1.0.0")

class Message(BaseModel):
    user: str
    content: str

@app.get("/")
async def root():
    return {"message": "Chat Server Running"}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    while True:
        data = await websocket.receive_text()
        await websocket.send_text(f"收到: {data}")
```

---

## 4. Python 最佳实践

### 4.1 命名规范（PEP8）

| 类型 | 规范 | 示例 |
|------|------|------|
| 变量/函数 | `snake_case` | `client_socket`, `send_message()` |
| 类名 | `PascalCase` | `ChatServer`, `MessageHandler` |
| 常量 | `UPPER_CASE` | `MAX_BUFFER_SIZE`, `DEFAULT_PORT` |
| 私有成员 | 前导下划线 | `self._running`, `_handle_data()` |
| 魔术方法 | 双下划线 | `__init__`, `__enter__` |
| 避免冲突 | 后置下划线 | `class_`, `type_` |

### 4.2 上下文管理器（with 语句）

```python
# socket 示例
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.connect((host, port))
    s.sendall(data)

# 自定义上下文管理器
class ManagedSocket:
    def __init__(self):
        self.sock = socket.socket()
    def __enter__(self):
        return self.sock
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.sock.close()
```

### 4.3 异常处理

```python
try:
    data = conn.recv(1024)
except socket.timeout:
    print("接收超时，继续等待...")
except ConnectionResetError:
    print("客户端断开连接")
except Exception as e:
    print(f"未知错误: {e}")
    raise  # 或记录日志后重新抛出
else:
    print("数据接收成功")  # 无异常时执行
finally:
    conn.close()  # 无论如何都会执行
```

### 4.4 日志优先于 print

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

logger.info("服务器启动于 %s:%d", host, port)
logger.debug("收到数据: %r", data)
logger.error("连接异常: %s", exc, exc_info=True)
```

### 4.5 类型注解

```python
from typing import Optional, Callable, Awaitable

def send_message(sock: socket.socket, data: bytes) -> int:
    return sock.send(data)

def recv_exact(sock: socket.socket, size: int) -> Optional[bytes]:
    """接收精确数量的字节，不够则返回 None"""
    buf = b""
    while len(buf) < size:
        chunk = sock.recv(size - len(buf))
        if not chunk:
            return None
        buf += chunk
    return buf

Handler = Callable[[bytes], Optional[bytes]]
async def serve_forever(handler: Handler) -> None:
    ...
```

### 4.6 枚举替代魔数

```python
from enum import IntEnum

class MessageType(IntEnum):
    TEXT = 1
    FILE = 2
    HEARTBEAT = 3
    DISCONNECT = 4

class Packet:
    def __init__(self, msg_type: MessageType, payload: bytes):
        self.msg_type = msg_type
        self.payload = payload
```

---

## 5. 网络编程要点

### 5.1 基础 TCP Socket 服务端

```python
import socket
import threading

def handle_client(conn: socket.socket, addr):
    """处理单个客户端连接"""
    try:
        while True:
            data = conn.recv(1024)
            if not data:
                break  # 客户端断开
            print(f"[{addr}] {data.decode()}")
            conn.sendall(b"ACK: " + data)
    except ConnectionResetError:
        print(f"[{addr}] 连接重置")
    finally:
        conn.close()
        print(f"[{addr}] 连接已关闭")

def start_server(host: str = "127.0.0.1", port: int = 8888):
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((host, port))
    server.listen(5)
    print(f"服务器监听 {host}:{port}")

    try:
        while True:
            conn, addr = server.accept()
            print(f"新连接: {addr}")
            thread = threading.Thread(target=handle_client, args=(conn, addr))
            thread.daemon = True
            thread.start()
    except KeyboardInterrupt:
        print("服务器关闭")
    finally:
        server.close()
```

### 5.2 基础 TCP 客户端

```python
import socket

def start_client(host: str = "127.0.0.1", port: int = 8888):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((host, port))
        s.settimeout(5.0)

        while True:
            msg = input("> ")
            if msg.lower() in ("quit", "exit"):
                break
            s.sendall(msg.encode())
            try:
                response = s.recv(1024)
                print(f"服务器: {response.decode()}")
            except socket.timeout:
                print("响应超时")
```

### 5.3 Socket 选项

| 选项 | 作用 | 用法 |
|------|------|------|
| `SO_REUSEADDR` | 允许重用地址（快速重启） | `s.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)` |
| `TCP_NODELAY` | 禁用 Nagle 算法（低延迟） | `s.setsockopt(IPPROTO_TCP, TCP_NODELAY, 1)` |
| `SO_KEEPALIVE` | 心跳保活 | `s.setsockopt(SOL_SOCKET, SO_KEEPALIVE, 1)` |
| `settimeout()` | 设置 I/O 超时 | `s.settimeout(5.0)` |
| `setblocking()` | 设置阻塞/非阻塞 | `s.setblocking(False)` |

### 5.4 粘包处理

TCP 是流协议，多条消息可能粘在一起：

```python
import struct

def send_msg(sock: socket.socket, data: bytes):
    """发送带长度前缀的消息"""
    length = struct.pack("!I", len(data))  # 4字节大端长度
    sock.sendall(length + data)

def recv_msg(sock: socket.socket) -> Optional[bytes]:
    """接收带长度前缀的消息"""
    header = recv_exact(sock, 4)  # 先读4字节长度
    if header is None:
        return None
    length = struct.unpack("!I", header)[0]
    return recv_exact(sock, length)
```

### 5.5 selectors 多路复用（替代多线程）

```python
import selectors
import socket

sel = selectors.DefaultSelector()

def accept(sock):
    conn, addr = sock.accept()
    conn.setblocking(False)
    sel.register(conn, selectors.EVENT_READ, read)

def read(conn):
    data = conn.recv(1024)
    if data:
        conn.sendall(data)
    else:
        sel.unregister(conn)
        conn.close()

server = socket.socket()
server.bind(("127.0.0.1", 8888))
server.listen(5)
server.setblocking(False)
sel.register(server, selectors.EVENT_READ, accept)

while True:
    for key, _ in sel.select():
        key.data(key.fileobj)
```

### 5.6 asyncio 异步版本

```python
import asyncio

async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    addr = writer.get_extra_info("peername")
    print(f"新连接: {addr}")
    try:
        while True:
            data = await reader.read(1024)
            if not data:
                break
            writer.write(b"ACK: " + data)
            await writer.drain()
    except ConnectionResetError:
        pass
    finally:
        writer.close()
        await writer.wait_closed()

async def main():
    server = await asyncio.start_server(handle_client, "127.0.0.1", 8888)
    async with server:
        await server.serve_forever()

asyncio.run(main())
```

---

## 6. 类型注解

### 6.1 基础类型

```python
from typing import List, Dict, Tuple, Set, Optional, Any, Union

names: List[str] = ["Alice", "Bob"]
scores: Dict[str, int] = {"Alice": 100}
point: Tuple[float, float] = (1.0, 2.0)
maybe: Optional[str] = None  # str | None
anything: Any = 42
id_or_name: Union[int, str] = 123  # int | str (Python 3.10+)
```

### 6.2 Python 3.10+ 新语法

```python
# Python 3.10+
maybe: str | None = None
id_or_name: int | str = 123

# Python 3.12+ 更简洁
type Handler = Callable[[bytes], bytes | None]
```

### 6.3 协议/接口（Protocol）

```python
from typing import Protocol

class MessageHandler(Protocol):
    def handle(self, data: bytes) -> bytes:
        ...
    def on_close(self) -> None:
        ...

def run_handler(h: MessageHandler):
    # 任何实现了 handle 和 on_close 的对象都可以传入
    result = h.handle(b"hello")
```

---

## 7. 测试

### 7.1 pytest 基础

```bash
pip install pytest pytest-asyncio
```

```python
# tests/test_server.py
import socket
import pytest

def test_send_recv():
    """测试基本的发送接收"""
    with socket.socket() as s:
        s.connect(("127.0.0.1", 8888))
        s.sendall(b"hello")
        response = s.recv(1024)
        assert b"ACK" in response

@pytest.mark.asyncio
async def test_async_connect():
    """测试异步连接"""
    reader, writer = await asyncio.open_connection("127.0.0.1", 8888)
    writer.write(b"test")
    data = await reader.read(1024)
    assert data
    writer.close()
```

### 7.2 mock 测试

```python
from unittest.mock import Mock, patch

def test_handle_client():
    mock_conn = Mock()
    mock_conn.recv.side_effect = [b"hello", b""]  # 第二次返回空表示断开

    handle_client(mock_conn, ("127.0.0.1", 12345))
    assert mock_conn.sendall.called
    assert mock_conn.close.called
```

---

## 8. 依赖管理

```bash
# 生成依赖清单
pip freeze > requirements.txt

# 只保留顶层依赖
pip install pip-tools
pip-compile  # 生成 requirements.txt
```

**requirements.txt 典型内容：**
```
# 项目依赖
# 运行时
# （TCP-Chat 是标准库项目，可能无需额外依赖）

# 开发工具
pytest>=8.0
flake8>=7.0
black>=24.0
isort>=5.13
debugpy>=1.8
```

**项目级 pyproject.toml：**
```toml
[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.backends._legacy:_Backend"

[project]
name = "tcp-chat"
version = "1.0.0"
requires-python = ">=3.10"

[tool.black]
line-length = 100

[tool.isort]
profile = "black"
line_length = 100

[tool.pytest.ini_options]
testpaths = ["tests"]
```

---

## 9. 其他实用技巧

### 9.1 编码规范

- 所有源文件用 UTF-8 编码
- 缩进用 4 个空格（不用 Tab）
- 行长不超过 100 字符（本项目的约定）
- 类定义之间空 2 行，方法之间空 1 行

### 9.2 bytes 和 str 的区分

```python
# TCP 传出用 bytes
conn.sendall(data.encode("utf-8"))     # str → bytes
data.decode("utf-8")                   # bytes → str

# 安全做法
def safe_decode(data: bytes) -> str:
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("utf-8", errors="replace")
```

### 9.3 并发模型选择

| 模型 | 适用场景 | 优点 | 缺点 |
|------|----------|------|------|
| 多线程 threading | 少量长连接 | 简单直观 | GIL、线程开销 |
| select / poll / epoll | 大量短连接 | 单线程高效 | 编码复杂 |
| asyncio | 高并发 I/O | 现代 Python 风格 | 学习曲线 |
| multiprocessing | CPU 密集型 | 避开 GIL | IPC 复杂 |

### 9.4 安全注意事项

- 不要用 `eval()` 或 `exec()` 处理用户输入
- socket 接收要设置超时，避免死等
- 用户数据要限长，防内存溢出
- 生产环境用 `ssl.wrap_socket()` 加密传输

---

*本文件由小龙虾整理，整合了 OpenClaw 工作区 skills 中的 Python 知识，包括 lsp-python（代码质量）、python-debugpy（调试）、python-script-generator（项目模板），以及通用的 Python 网络编程最佳实践。*
