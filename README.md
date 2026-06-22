# TCP 聊天室

基于 TCP Socket 的多客户端聊天室，支持群聊、私聊、在线用户列表、局域网自动发现、文件传输。

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 运行客户端
python -m tcp_chat
# 或
python main.py
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
├── tcp_chat/               # 源代码包
│   ├── __init__.py
│   ├── __main__.py         # python -m tcp_chat 入口
│   ├── server.py           # 服务端
│   ├── client.py           # 客户端网络层
│   ├── config.py           # 配置管理
│   ├── tunnel.py           # 内网穿透
│   ├── log_config.py       # 日志配置
│   ├── ui/                 # GUI 模块
│   │   ├── app.py          # 主窗口控制器
│   │   ├── icon_manager.py # 统一窗口图标管理器
│   │   ├── icons.py        # UI 图标与文本常量
│   │   ├── theme.py        # 主题常量
│   │   ├── chat_page.py    # 聊天界面
│   │   ├── login_page.py   # 登录界面
│   │   ├── start_page.py   # 起始界面
│   │   ├── create_room_page.py  # 创建房间界面
│   │   ├── initial_interface.py # 初始界面窗口
│   │   ├── dialogs.py      # 通用弹窗组件
│   │   ├── widgets.py      # 通用控件
│   │   ├── patterns.py     # UI 模式（滚动条、用户卡片等）
│   │   ├── tags.py         # 消息标签样式
│   │   ├── cache_manager.py # 聊天缓存
│   │   └── file_transfer_ui.py # 文件传输 UI
│   └── file_transfer/      # 文件传输协议
│       ├── __init__.py
│       ├── protocol.py
│       ├── session.py
│       ├── sender.py
│       ├── receiver.py
│       ├── bitmap.py
│       └── tunnel.py
├── test/                   # 测试
├── tools/                  # 工具脚本
├── setup/                  # 打包脚本
├── dist/                   # 打包输出
├── docs/                   # 文档
│   └── arch/               # 架构方案
├── TCP-Chat.png            # 图标源文件
├── TCP-Chat.ico            # 图标（自动生成）
├── requirements.txt        # 依赖
├── pyproject.toml          # 项目配置
└── README.md
```

## 功能

- 多用户群聊 / 私聊 `/to <昵称> <消息>`
- 局域网自动发现（UDP 广播）
- 房主标识（👑 金色标志）
- 消息字体随窗口缩放
- 命令提示（输入 `/` 弹出菜单）
- 文件传输（基于 croc）

## 修改图标

所有窗口的图标统一通过 `tcp_chat/ui/icon_manager.py` 管理：

1. 替换 `TCP-Chat.png` 为你自己的图标
2. 重启程序，`.ico` 文件会自动重建
3. 所有窗口（主窗口、初始界面、弹窗）图标同步更新

无需手动准备 `.ico` 文件，程序启动时通过 Pillow 自动转换。
