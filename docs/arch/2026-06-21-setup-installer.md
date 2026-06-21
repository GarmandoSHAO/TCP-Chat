# TCP 聊天室 — 安装程序方案

## 方案概述

为 TCP 聊天室制作 **Windows 一键安装包**（Inno Setup），将 `TCP-Chat.exe`、`bore.exe`、`croc.exe` 和 `config.json` 打包成一个 `setup.exe`。用户双击即可安装到 `Program Files`，自动创建桌面快捷方式和开始菜单，并自动检查 VC++ 运行库。

---

## 架构图

```
┌─────────────────────────────────────────────────────────────┐
│                    build_installer.bat                       │
│              (一键构建脚本 — 开发者使用)                      │
└──────────────────────┬──────────────────────────────────────┘
                       │ 调用
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                    installer.iss                             │
│              (Inno Setup 脚本 — 编译入口)                    │
│                                                             │
│  ├─ [Setup]     ─ 安装参数（路径、版本、卸载）                │
│  ├─ [Files]     ─ 打包文件清单                               │
│  ├─ [Icons]     ─ 快捷方式配置                               │
│  ├─ [Run]       ─ 安装后操作                                 │
│  ├─ [Code]      ─ Pascal 脚本（VC++ 检测、升级）             │
│  └─ [UninstallRun] ─ 卸载时清理                              │
└──────────────────────┬──────────────────────────────────────┘
                       │ 编译输出
                       ▼
┌─────────────────────────────────────────────────────────────┐
│               TCP-Chat-Setup-1.0.0.exe                       │
│                                                             │
│   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│   │ TCP-Chat.exe │  │  bore.exe   │  │  croc.exe   │         │
│   │  (31 MB)     │  │  (2.0 MB)   │  │  (8.4 MB)   │         │
│   └─────────────┘  └─────────────┘  └─────────────┘         │
│   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│   │ config.json  │  │ README.md   │  │ setup_utils │         │
│   │  (默认配置)  │  │  (文档)     │  │  (Python)   │         │
│   └─────────────┘  └─────────────┘  └─────────────┘         │
└─────────────────────────────────────────────────────────────┘
                       │ 用户双击安装
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              安装流程 (运行时)                                │
│                                                             │
│  1. 检查 Windows 版本 (7+)          ──── 不满足 → 退出      │
│  2. 检查 VC++ Redistributable       ──── 缺失 → 提示安装    │
│  3. 选择安装目录 (默认 Program Files)                        │
│  4. 解压文件到目标目录                                      │
│  5. 仅首次安装时创建 config.json    ──── 已有则保留用户配置  │
│  6. 创建快捷方式                    桌面 + 开始菜单          │
│  7. 安装后可选「运行 TCP 聊天室」                           │
│                                                             │
│  安装完成目录结构:                                           │
│  C:\Program Files\TCP-Chat\                                  │
│  ├── TCP-Chat.exe                                           │
│  ├── bore.exe                                               │
│  ├── croc.exe                                               │
│  ├── config.json                                            │
│  └── unins000.exe                    (Inno Setup 自动生成)   │
└─────────────────────────────────────────────────────────────┘
```

---

## 模块划分与职责

| 模块 | 文件 | 职责 |
|------|------|------|
| **安装脚本** | `setup/installer.iss` | Inno Setup 编译脚本，定义打包内容、安装路径、快捷方式、卸载逻辑 |
| **安装工具** | `setup/setup_utils.py` | Python 辅助工具：检查 VC++ 运行库、生成默认 config、验证安装完整性 |
| **构建脚本** | `setup/build_installer.bat` | 开发者一键构建脚本：运行 PyInstaller → 复制依赖 → 编译 Inno Setup |
| **版本信息** | `setup/version_info.txt` | 安装包版本号、文件说明、版权信息 |

### 外部依赖（打包进安装包）

| 依赖 | 来源 | 作用 | 大小 |
|------|------|------|------|
| `TCP-Chat.exe` | PyInstaller 打包 | 主程序 | ~31 MB |
| `bore.exe` | [ekzhang/bore](https://github.com/ekzhang/bore/releases) | 公网隧道穿透 | ~2.0 MB |
| `croc.exe` | [schollz/croc](https://github.com/schollz/croc/releases) | 点对点文件传输 | ~8.4 MB |
| `config.json` | 项目自带 | 默认配置（首次安装创建） | ~0.5 KB |

---

## 安装流程细节

```
用户双击 setup.exe
       │
       ▼
┌─────────────────────────┐
│  语言/欢迎页             │
└─────────────────────────┘
       │
       ▼
┌─────────────────────────┐
│  检查 VC++ Redistrib.   │◄──── [Code] 中 Pascal 脚本检测注册表
│  ┌── 已安装 → 继续      │      HKLM\SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64
│  └── 未安装 → 弹窗提示  │      检测不到则弹窗引导用户下载
└─────────────────────────┘
       │
       ▼
┌─────────────────────────┐
│  选择安装路径            │──── 默认: {autopf}\TCP-Chat
│  (若检测到旧版本则提示    │     检测 HKCU\SOFTWARE\TCP-Chat\InstallPath
│   升级/覆盖)             │
└─────────────────────────┘
       │
       ▼
┌─────────────────────────┐
│  选择组件                │──── 可选: 桌面快捷方式 / 开始菜单
│  (默认全选)              │
└─────────────────────────┘
       │
       ▼
┌─────────────────────────┐
│  安装中                  │
│  - 复制文件              │
│  - 首次安装则生成 config │──── setup_utils.py 或用 Pascal 直接写
│  - 创建注册表卸载信息    │──── Inno Setup 自动完成
└─────────────────────────┘
       │
       ▼
┌─────────────────────────┐
│  完成页                  │──── 勾选「运行 TCP 聊天室」
│  - 桌面快捷方式          │
│  - 开始菜单              │
└─────────────────────────┘
```

---

## 关键决策与备选方案

### 方案 A（推荐）：Inno Setup Windows 安装包 ★

| 维度 | 说明 |
|------|------|
| 技术栈 | Inno Setup + Pascal Script |
| 安装包大小 | ~42 MB (TCP-Chat 31MB + bore 2MB + croc 8.4MB + overhead) |
| 开发成本 | 低（一个 .iss 文件） |
| 用户门槛 | 最低（双击安装） |
| 维护成本 | 低（改版本号 + 重编译） |
| 风险等级 | **低** |
| 适用场景 | 分发给普通用户 |

**优点：** 专业 Windows 安装体验，卸载干净，支持静默安装 `/VERYSILENT`
**缺点：** 编译需要安装 Inno Setup（开发者需要装一次）

### 方案 B：NSIS (Nullsoft Scriptable Install System)

| 维度 | 说明 |
|------|------|
| 技术栈 | NSIS + 脚本 |
| 风险等级 | **中** |

**优点：** 更小的安装包体积，更快的编译速度
**缺点：** 语法老旧，VC++ 运行时检测需要额外插件，社区不如 Inno Setup 活跃

### 方案 C：纯 Python 安装脚本 + py-to-exe 打包

| 维度 | 说明 |
|------|------|
| 技术栈 | Python + PyInstaller |
| 风险等级 | **中高** |

**优点：** 跨平台，Python 开发者友好
**缺点：** 用户需要先有 Python 环境；Windows 集成（注册表、卸载、快捷方式）需要手写大量代码

---

## 文件改动清单

```
TCP-Chat/
├── docs/arch/
│   └── 2026-06-21-setup-installer.md    (新建) 本文档
├── setup/                                (新建目录)
│   ├── installer.iss                      (新建) Inno Setup 主脚本
│   ├── setup_utils.py                     (新建) 安装辅助工具
│   ├── version_info.txt                   (新建) 版本信息
│   └── build_installer.bat                (新建) 构建脚本
└── .gitignore
    └── (追加) dist/                       (新增忽略)
```

---

## 风险评估

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| 用户缺少 VC++ Redistributable | 中 | 高（程序无法启动） | [Code] 段检测注册表，缺失时弹窗引导下载 |
| bore/croc.exe 被杀毒软件误报 | 中 | 中 | 建议开发者数字签名，或在文档中说明 |
| 安装包体积较大 (~42MB) | 高 | 低 | 这是 PyInstaller 的固有体积，压缩后仍可接受 |
| Inno Setup 版本不兼容 | 低 | 中 | 脚本使用 Inno Setup 6.x 标准语法 |

---

## 设计接口

### setup_utils.py 接口

```python
def check_vc_redist() -> tuple[bool, str]:
    """
    检查 VC++ Redistributable 是否安装
    Returns: (installed: bool, message: str)
    """

def generate_default_config(target_path: str) -> str:
    """
    生成默认 config.json
    Returns: 配置文件路径
    """

def verify_installation(install_dir: str) -> dict:
    """
    验证安装完整性
    Returns: {
        "complete": bool,
        "missing_files": list[str],
        "file_sizes": dict[str, int]
    }
    """

def get_current_version() -> str:
    """
    读取 pyproject.toml 中的版本号
    Returns: 版本号字符串 "1.0.0"
    """
```

### installer.iss Pascal 接口

```pascal
function IsVCRedistInstalled: Boolean;
// 检测 VC++ 运行库是否已安装

function GetPreviousInstallPath: string;
// 读取注册表中上次安装路径

procedure GenerateConfig(Dir: string);
// 首次安装时生成默认 config.json

procedure AddFirewallRule(AppPath: string);
// 添加 Windows 防火墙放行规则（可选）
```
