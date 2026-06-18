# TCP 聊天室

基于 TCP Socket 的多客户端聊天室，支持群聊、私聊、在线用户列表、局域网自动发现。

## 快速开始

```bash
# 运行客户端（启动器）
python -m src.tcp_chat.client_ui
# 或直接运行
python src/tcp_chat/client_ui.py
```

## 使用说明

### 创建房间
1. 点「创建聊天房间」
2. 填写房间配置（IP、端口、房间名、昵称）
3. 服务端自动启动，房主自动进入聊天室

### 加入房间
1. 点「加入聊天房间」
2. 输入服务器 IP 或点「扫描局域网」
3. 输入昵称，连接

## 项目结构

```
TCP-Chat/
├── src/
│   └── tcp_chat/        # 源代码包
│       ├── __init__.py
│       ├── server.py     # 服务端
│       └── client_ui.py  # GUI 客户端
├── tests/                # 测试
├── requirements.txt      # 依赖
├── pyproject.toml        # 项目配置
└── README.md
```

## 功能

- 多用户群聊 / 私聊 `/to <昵称> <消息>`
- 局域网自动发现（UDP 广播）
- 房主标识（👑 金色标志）
- 消息字体随窗口缩放
- 命令提示（输入 `/` 弹出菜单）
