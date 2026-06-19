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
9. [其他实用技巧](#9-其他实用技巧)
10. [智能体工作流程](#10-智能体工作流程)

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

```python
def handle_client(conn):
    breakpoint()  # 程序执行到这里会进入 pdb
    data = conn.recv(1024)
```

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
    print(f"连接到 {args.host}:{args.port}...")

if __name__ == "__main__":
    main()
```

### 3.3 FastAPI 模板（适用 WebSocket 场景）

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
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.connect((host, port))
    s.sendall(data)

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
    raise
else:
    print("数据接收成功")
finally:
    conn.close()
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
```

### 4.5 类型注解

```python
from typing import Optional, Callable

def send_message(sock: socket.socket, data: bytes) -> int:
    return sock.send(data)

def recv_exact(sock: socket.socket, size: int) -> Optional[bytes]:
    buf = b""
    while len(buf) < size:
        chunk = sock.recv(size - len(buf))
        if not chunk:
            return None
        buf += chunk
    return buf
```

### 4.6 枚举替代魔数

```python
from enum import IntEnum

class MessageType(IntEnum):
    TEXT = 1
    FILE = 2
    HEARTBEAT = 3
    DISCONNECT = 4
```

---

## 5. 网络编程要点

### 5.1 基础 TCP Socket 服务端

```python
import socket
import threading

def handle_client(conn: socket.socket, addr):
    try:
        while True:
            data = conn.recv(1024)
            if not data:
                break
            print(f"[{addr}] {data.decode()}")
            conn.sendall(b"ACK: " + data)
    except ConnectionResetError:
        print(f"[{addr}] 连接重置")
    finally:
        conn.close()

def start_server(host="127.0.0.1", port=8888):
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((host, port))
    server.listen(5)
    try:
        while True:
            conn, addr = server.accept()
            t = threading.Thread(target=handle_client, args=(conn, addr))
            t.daemon = True
            t.start()
    except KeyboardInterrupt:
        print("服务器关闭")
    finally:
        server.close()
```

### 5.2 粘包处理

```python
import struct

def send_msg(sock: socket.socket, data: bytes):
    length = struct.pack("!I", len(data))
    sock.sendall(length + data)

def recv_msg(sock: socket.socket) -> Optional[bytes]:
    header = recv_exact(sock, 4)
    if header is None:
        return None
    length = struct.unpack("!I", header)[0]
    return recv_exact(sock, length)
```

### 5.3 asyncio 异步版本

```python
import asyncio

async def handle_client(reader, writer):
    addr = writer.get_extra_info("peername")
    try:
        while True:
            data = await reader.read(1024)
            if not data:
                break
            writer.write(b"ACK: " + data)
            await writer.drain()
    finally:
        writer.close()
        await writer.wait_closed()

async def main():
    server = await asyncio.start_server(handle_client, "127.0.0.1", 8888)
    async with server:
        await server.serve_forever()

asyncio.run(main())
```

### 5.4 Socket 选项速查

| 选项 | 作用 |
|------|------|
| `SO_REUSEADDR` | 允许快速重启，避免 Address already in use |
| `TCP_NODELAY` | 禁用 Nagle 算法，降低延迟 |
| `SO_KEEPALIVE` | 心跳保活检测断线 |
| `settimeout(5.0)` | 设置 I/O 超时 |
| `setblocking(False)` | 切换非阻塞模式 |

### 5.5 安全注意事项

- 不要用 `eval()` 或 `exec()` 处理用户输入
- socket 接收要设置超时，避免死等
- 用户数据要限长，防内存溢出
- 生产环境用 `ssl.wrap_socket()` 加密传输

---

## 6. 类型注解

### 6.1 基础类型

```python
from typing import List, Dict, Tuple, Set, Optional, Any, Union
names: List[str] = ["Alice", "Bob"]
scores: Dict[str, int] = {"Alice": 100}
maybe: Optional[str] = None
```

### 6.2 Python 3.10+ 新语法

```python
maybe: str | None = None
id_or_name: int | str = 123
```

### 6.3 Protocol（鸭子类型检查）

```python
from typing import Protocol

class MessageHandler(Protocol):
    def handle(self, data: bytes) -> bytes: ...
    def on_close(self) -> None: ...

def run_handler(h: MessageHandler):
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
    with socket.socket() as s:
        s.connect(("127.0.0.1", 8888))
        s.sendall(b"hello")
        response = s.recv(1024)
        assert b"ACK" in response

@pytest.mark.asyncio
async def test_async_connect():
    reader, writer = await asyncio.open_connection("127.0.0.1", 8888)
    writer.write(b"test")
    data = await reader.read(1024)
    assert data
    writer.close()
```

### 7.2 mock 测试

```python
from unittest.mock import Mock

def test_handle_client():
    mock_conn = Mock()
    mock_conn.recv.side_effect = [b"hello", b""]
    handle_client(mock_conn, ("127.0.0.1", 12345))
    assert mock_conn.sendall.called
    assert mock_conn.close.called
```

---

## 8. 依赖管理

```bash
pip freeze > requirements.txt
```

**pyproject.toml：**
```toml
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

### 9.1 bytes 和 str 的区分

```python
# TCP 传出用 bytes
conn.sendall(data.encode("utf-8"))     # str → bytes
data.decode("utf-8")                   # bytes → str

def safe_decode(data: bytes) -> str:
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("utf-8", errors="replace")
```

### 9.2 并发模型选择

| 模型 | 适用场景 | 优点 | 缺点 |
|------|----------|------|------|
| 多线程 threading | 少量长连接 | 简单直观 | GIL、线程开销 |
| select / poll / epoll | 大量短连接 | 单线程高效 | 编码复杂 |
| asyncio | 高并发 I/O | 现代 Python | 学习曲线 |
| multiprocessing | CPU密集型 | 避开 GIL | IPC 复杂 |

---

## 10. 智能体工作流程（Agent Workflow）

本工作流定义了 AI 在 TCP-Chat 项目中与主人协作开发的完整规范。每次对话开始，AI 应遵循此流程。

### 10.1 核心原则

1. **先问再改** — 除非主人明确说"直接改"，否则改文件前先确认
2. **小步提交** — 每个逻辑改动用独立的 commit，不要一锅端
3. **改前看现状** — 改代码前先 `git status` 和 `git diff` 了解当前状态
4. **别丢代码** — 任何修改前确认没有未提交的重要代码
5. **改完就验证** — 改完后自动跑 `flake8` 或 `pytest` 检查有无破坏
6. **按 CLAUDE.md 行事** — 本文件中的 Python 知识、编码规范、惯例都要遵守

### 10.2 完整开发循环

```
主人提出需求
    ↓
① 理解意图 — 确认主人要什么
    ↓
② 看现状 — git status + git diff + 读相关文件
    ↓
③ 制定方案 — 简单描述怎么改
    ↓
④ 确认 — 问主人"这样改可以吗？"
    ↓
⑤ 执行修改 — 改代码（小步进行）
    ↓
⑥ 验证 — flake8 / pytest / 手动测
    ↓
⑦ 提交 — git add + git commit（附清晰信息）
    ↓
⑧ 推送 — git push（主人确认后）
    ↓
回到①
```

### 10.3 对话模式速查

| 主人说的话 | 智能体应该怎么做 |
|------------|----------------|
| "帮我加个功能" | 按完整循环 ①→⑧ 执行 |
| "帮我修个 bug" | 先复现问题，找到根因，再修 |
| "看看这段代码" | 审阅代码，指出问题，给建议 |
| "直接改" | 跳过④确认步，直接改 |
| "帮我提交一下" | `git add .` + `git commit`，信息要写清楚改了啥 |
| "帮我推上去" | 先确认有没有未提交修改，再 `git push` |
| "回滚" | 找到对应 commit，`git revert` 或 `git reset` |
| "审查一下" | 跑 flake8 + pylint + pytest，报告问题 |
| "怎么这么慢" | 检查性能瓶颈，建议优化方案，确认后再改 |
| "先别动，看看再说" | 只读不写，纯分析和建议 |

### 10.4 Commit Message 规范

```
<类型>: <简短描述>

<详细说明（可选）>
```

**类型：**
- `feat` — 新功能
- `fix` — 修 bug
- `refactor` — 重构
- `style` — 格式修改（不影响逻辑）
- `docs` — 文档
- `test` — 测试
- `chore` — 杂项（依赖、配置等）

**示例：**
```
feat: 添加消息长度前缀解决粘包问题

改用 4 字节大端长度前缀 + 消息体的格式，
确保收发双方不会因为 TCP 粘包而出错。
```

### 10.5 情境响应指南

**情境 A：主人刚打开对话，还没说干什么**
1. 先看 `git status` 看当前工作区状态
2. 如果有未提交的修改，主动汇报
3. 等待主人指令

**情境 B：主人说"帮我写个 X"**
1. 读相关文件了解现有代码结构
2. 写之前确认方案
3. 小步实现，每步可验证
4. 实现完运行测试确认没问题

**情境 C：主人发来一段报错信息**
1. 分析报错原因
2. 给出修复方案
3. 确认后修复
4. 验证修复有效

**情境 D：主人说"帮我审查代码"**
1. 跑 `flake8 scripts/` 检查格式问题
2. 如果有测试，跑 `pytest` 检查功能
3. 人工审阅逻辑、安全、性能问题
4. 按严重程度输出问题列表

**情境 E：主人说"怎么部署"**
1. 确认运行环境（Python 版本、OS）
2. 列出依赖和安装步骤
3. 给出启动命令和参数说明
4. 说明端口、防火墙等网络配置

### 10.6 工具使用规范

| 操作 | 用什么 |
|------|--------|
| 读文件 | 用 `Read` 工具，先看目录结构再看具体文件 |
| 搜索代码 | 用 `Grep` 搜函数名、类名、关键词 |
| 改代码 | 用 `Edit` / `Write` 工具，先备份再改 |
| 运行命令 | 用 `Bash` 工具，安全命令直接跑，危险命令先问 |
| 调试 | 用 `breakpoint()` + `pdb`，或 `debugpy` 远程附加 |
| 项目探索 | 先 `Glob` 看目录结构，再深入读关键文件 |

### 10.7 权限与安全

- 改文件前确认文件路径和内容是否正确
- 执行 `git push` 前先 `git diff` 确认改了什么
- 不执行 `rm -rf`、`format` 等破坏性命令
- 不改 `.git` 目录下的文件
- 不改 `node_modules`、`__pycache__` 等生成的目录

---

*本文件由小龙虾整理，整合了 OpenClaw 工作区 skills 中的 Python 知识以及智能体协作工作流程。更新于 2026-06-19。*
