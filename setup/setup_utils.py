#!/usr/bin/env python3
"""
TCP 聊天室 — 安装辅助工具

提供 VC++ 运行库检测、配置生成、安装验证等功能。
可被 Inno Setup 安装程序调用，也可独立运行。

用法:
    python setup_utils.py check          # 检查系统环境
    python setup_utils.py verify <目录>   # 验证安装完整性
    python setup_utils.py gen-config      # 生成默认 config.json
    python setup_utils.py version         # 打印版本号
"""

import argparse
import json
import os
import platform
import shutil
import sys
import winreg
from pathlib import Path


# ── 常量 ──────────────────────────────────────────────

REQUIRED_FILES = [
    "TCP-Chat.exe",
    "bore.exe",
    "croc.exe",
    "config.json",
]

REQUIRED_FILE_HINTS = {
    "TCP-Chat.exe": "主程序",
    "bore.exe": "隧道穿透工具（内网穿透）",
    "croc.exe": "文件传输工具（点对点传输）",
    "config.json": "配置文件",
}

MIN_PYTHON = (3, 10)
APP_NAME = "TCP 聊天室"
APP_VERSION = "1.0.0"


# ── 核心功能 ──────────────────────────────────────────


def check_vc_redist() -> tuple[bool, str]:
    """检查 VC++ Redistributable for VS 2015-2022 是否安装

    Returns:
        (installed: bool, message: str)
    """
    try:
        # 检测 x64 运行库
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64",
        )
        value, _ = winreg.QueryValueEx(key, "Installed")
        winreg.CloseKey(key)

        if value == 1:
            return True, "✓ VC++ Redistributable (x64) 已安装"

        # 检查 x86
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x86",
        )
        value, _ = winreg.QueryValueEx(key, "Installed")
        winreg.CloseKey(key)

        if value == 1:
            return True, "✓ VC++ Redistributable (x86) 已安装"

        return False, "✗ VC++ Redistributable 未安装"

    except FileNotFoundError:
        # 注册表键不存在 → 未安装
        return False, "✗ VC++ Redistributable 未安装（注册表键不存在）"
    except PermissionError:
        return False, "✗ 无法访问注册表（请以管理员身份运行）"
    except Exception as e:
        return False, f"✗ 检查 VC++ 运行库时出错: {e}"


def check_python_version() -> tuple[bool, str]:
    """检查 Python 版本是否满足要求"""
    current = sys.version_info[:2]
    if current >= MIN_PYTHON:
        return True, f"✓ Python {sys.version.split()[0]}"
    return False, f"✗ 需要 Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+，当前: {sys.version.split()[0]}"


def check_os_version() -> tuple[bool, str]:
    """检查操作系统版本"""
    try:
        version = platform.version()
        release = platform.release()

        # Windows 版本号: 6.1 = Windows 7, 6.2 = 8, 10.0 = 10/11
        major, minor = map(int, version.split(".")[:2])

        if major > 6 or (major == 6 and minor >= 1):
            os_name = f"Windows {release} ({version})"
            return True, f"✓ {os_name}"

        return False, f"✗ 需要 Windows 7+, 当前: Windows {release} ({version})"
    except Exception as e:
        return False, f"✗ 无法检测操作系统版本: {e}"


def verify_installation(install_dir: str) -> dict:
    """验证安装目录的完整性

    Args:
        install_dir: 安装目录路径

    Returns:
        {
            "complete": bool,
            "file_status": list[{"name": str, "exists": bool, "size": int, "hint": str}],
            "total_size_mb": float,
        }
    """
    base = Path(install_dir)
    result = {
        "complete": True,
        "file_status": [],
        "total_size_mb": 0.0,
    }

    for filename in REQUIRED_FILES:
        path = base / filename
        exists = path.exists()
        size = path.stat().st_size if exists else 0
        hint = REQUIRED_FILE_HINTS.get(filename, "")

        result["file_status"].append({
            "name": filename,
            "exists": exists,
            "size_mb": round(size / (1024 * 1024), 2),
            "hint": hint,
        })

        if not exists:
            result["complete"] = False

    result["total_size_mb"] = round(sum(
        f["size_mb"] for f in result["file_status"]
    ), 2)

    return result


def generate_default_config(target_path: str | None = None) -> str:
    """生成默认 config.json

    Args:
        target_path: 目标路径（默认当前目录）

    Returns:
        配置文件绝对路径
    """
    config = {
        "_comment": "TCP 聊天室配置文件（留空或删除则使用默认值）",
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

    if target_path:
        dest = Path(target_path)
        if dest.is_dir():
            dest = dest / "config.json"
    else:
        dest = Path.cwd() / "config.json"

    # 不覆盖已有文件
    if dest.exists():
        print(f"  ! 配置文件已存在: {dest}")
        return str(dest)

    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

    print(f"  ✓ 已生成配置文件: {dest}")
    return str(dest)


def get_current_version() -> str:
    """从 pyproject.toml 读取版本号"""
    # 向上查找 pyproject.toml
    for parent in [Path(__file__).resolve().parent.parent]:
        pyproject = parent / "pyproject.toml"
        if pyproject.exists():
            import re
            text = pyproject.read_text(encoding="utf-8")
            m = re.search(r'version\s*=\s*"([^"]+)"', text)
            if m:
                return m.group(1)
    return APP_VERSION


# ── 命令行入口 ─────────────────────────────────────────


def cmd_check(args):
    """检查系统环境"""
    print()
    print("=" * 50)
    print(f"  {APP_NAME} — 系统环境检查")
    print("=" * 50)
    print()

    checks = [
        ("操作系统", check_os_version()),
        ("Python 版本", check_python_version()),
        ("VC++ 运行库", check_vc_redist()),
    ]

    all_pass = True
    for name, (ok, msg) in checks:
        status = "✓" if ok else "✗"
        print(f"  [{status}] {name:<12s} {msg}")
        if not ok:
            all_pass = False

    print()
    if all_pass:
        print("  ✓ 所有检查通过！可以安装 TCP 聊天室。")
    else:
        print("  ! 部分检查未通过，请修复后重试。")
    print()

    return 0 if all_pass else 1


def cmd_verify(args):
    """验证安装完整性"""
    install_dir = args.dir or os.getcwd()
    print()
    print("=" * 50)
    print(f"  验证安装目录: {install_dir}")
    print("=" * 50)
    print()

    result = verify_installation(install_dir)

    max_name_len = max(len(f["name"]) for f in result["file_status"])

    for f in result["file_status"]:
        icon = "✓" if f["exists"] else "✗"
        size_str = f"{f['size_mb']:.1f} MB" if f["exists"] else "---"
        print(f"  [{icon}] {f['name']:<{max_name_len + 2}s} {size_str:>8s}  {f['hint']}")

    print()
    print(f"  总大小: {result['total_size_mb']:.1f} MB")

    if result["complete"]:
        print("  ✓ 安装完整，所有文件已就绪！")
    else:
        print("  ✗ 安装不完整，缺少必要文件！")
    print()

    return 0 if result["complete"] else 1


def cmd_gen_config(args):
    """生成配置文件"""
    generate_default_config(args.dir)
    return 0


def cmd_version(args):
    """打印版本号"""
    print(get_current_version())
    return 0


def cmd_cleanup(args):
    """清理安装目录（卸载时调用）"""
    target = Path(args.dir) if args.dir else Path.cwd()
    print(f"清理: {target}")

    dirs_to_clean = ["logs", "download", "__pycache__"]
    for d in dirs_to_clean:
        path = target / d
        if path.exists():
            shutil.rmtree(path, ignore_errors=True)
            print(f"  已删除: {d}")
    return 0


# ── 主入口 ─────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description=f"{APP_NAME} — 安装辅助工具",
    )
    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # check
    subparsers.add_parser("check", help="检查系统环境")

    # verify
    p_verify = subparsers.add_parser("verify", help="验证安装完整性")
    p_verify.add_argument("dir", nargs="?", default=None, help="安装目录（默认当前目录）")

    # gen-config
    p_gen = subparsers.add_parser("gen-config", help="生成默认 config.json")
    p_gen.add_argument("--dir", default=None, help="输出目录（默认当前目录）")

    # version
    subparsers.add_parser("version", help="打印版本号")

    # cleanup
    p_clean = subparsers.add_parser("cleanup", help="清理安装目录（卸载时调用）")
    p_clean.add_argument("--dir", default=None, help="目标目录")

    args = parser.parse_args()

    if args.command == "check":
        return cmd_check(args)
    elif args.command == "verify":
        return cmd_verify(args)
    elif args.command == "gen-config":
        return cmd_gen_config(args)
    elif args.command == "version":
        return cmd_version(args)
    elif args.command == "cleanup":
        return cmd_cleanup(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
