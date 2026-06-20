#!/usr/bin/env python3
"""
安装 croc —— 跨平台文件传输工具

自动检测操作系统，下载对应版本，放置到项目根目录。

用法:
    python tools/install_croc.py                              # 安装到项目根目录
    python tools/install_croc.py --dir D:/my-tools            # 安装到指定目录
    python tools/install_croc.py --add-to-path                # 安装并加入 PATH

支持:
    Windows, Linux, macOS
    自动选择最新稳定版
"""

import os
import sys
import platform
import zipfile
import tarfile
import shutil
import stat
import json
import urllib.request
import argparse
import subprocess
from pathlib import Path

# ── 配置 ──────────────────────────────────────────────
CROC_VERSION = "v10.4.4"
GITHUB_REPO = "https://github.com/schollz/croc"

# 各平台对应的文件名
RELEASE_FILES = {
    "windows": {
        "arch": {"amd64": "Windows-64bit", "arm64": "Windows-ARM64"},
        "ext": ".zip",
    },
    "linux": {
        "arch": {
            "amd64": "Linux-64bit",
            "arm64": "Linux-ARM64",
            "armv7l": "Linux-ARM",
            "i386": "Linux-32bit",
        },
        "ext": ".tar.gz",
    },
    "darwin": {
        "arch": {
            "amd64": "macOS-64bit",
            "arm64": "macOS-ARM64",
        },
        "ext": ".tar.gz",
    },
}

BIN_NAMES = {
    "windows": "croc.exe",
    "linux": "croc",
    "darwin": "croc",
}


# ── 工具 ──────────────────────────────────────────────

def detect_platform() -> tuple:
    """检测操作系统和架构，返回 (os_name, arch_name)"""
    system = platform.system().lower()
    machine = platform.machine().lower()

    if system not in RELEASE_FILES:
        print(f"❌ 不支持的操作系统: {system}")
        print(f"   支持: {', '.join(RELEASE_FILES.keys())}")
        sys.exit(1)

    # 统一 arch 命名
    arch_map = {
        "x86_64": "amd64",
        "amd64": "amd64",
        "aarch64": "arm64",
        "arm64": "arm64",
        "armv7l": "armv7l",
        "i386": "i386",
        "i686": "i386",
    }

    arch = arch_map.get(machine)
    if not arch:
        print(f"❌ 不支持的架构: {machine}")
        sys.exit(1)

    available = list(RELEASE_FILES[system]["arch"].keys())
    if arch not in available:
        print(f"❌ 不支持的架构: {system}/{machine}")
        print(f"   支持: {[RELEASE_FILES[system]['arch'][a] for a in available]}")
        sys.exit(1)

    return system, arch


def download_file(url: str, dest: Path) -> None:
    """下载文件，带进度显示"""
    print(f"  下载: {url}")

    def report(block_num, block_size, total_size):
        downloaded = block_num * block_size
        if total_size > 0:
            pct = min(downloaded / total_size * 100, 100)
            speed = downloaded / (1024 * 1024)
            if pct < 100:
                print(f"\r  进度: {pct:.0f}%  ({speed:.0f} MB / {total_size / 1024 / 1024:.0f} MB)", end="", flush=True)
            else:
                print(f"\r  进度: 100%  ({speed:.0f} MB)", flush=True)
        else:
            print(f"\r  已下载: {downloaded / 1024 / 1024:.0f} MB", end="", flush=True)

    # 用 urllib 下载（兼容性好）
    import urllib.request
    urllib.request.urlretrieve(url, str(dest), reporthook=report)
    print()


def extract_archive(archive_path: Path, extract_dir: Path, ext: str, bin_name: str) -> Path:
    """解压并返回二进制文件路径"""
    print(f"  解压: {archive_path.name}")

    if ext == ".zip":
        with zipfile.ZipFile(archive_path, "r") as z:
            z.extractall(extract_dir)
            # 找到解压后的二进制
            for name in z.namelist():
                if name.endswith(bin_name):
                    return extract_dir / name
    elif ext == ".tar.gz":
        with tarfile.open(archive_path, "r:gz") as t:
            t.extractall(extract_dir)
            for member in t.getmembers():
                if member.name.endswith(bin_name):
                    return extract_dir / member.name

    raise FileNotFoundError(f"解压后未找到 {bin_name}")


def main():
    parser = argparse.ArgumentParser(description="安装 croc 文件传输工具")
    parser.add_argument("--dir", default=None,
                        help="安装目录（默认：项目根目录）")
    parser.add_argument("--add-to-path", action="store_true",
                        help="安装后加入系统 PATH（仅 Windows）")
    args = parser.parse_args()

    # ── 检测平台 ──
    print()
    print("=" * 50)
    print("  安装 croc")
    print("=" * 50)
    print(f"  版本: {CROC_VERSION}")
    print()

    system, arch = detect_platform()
    platform_info = RELEASE_FILES[system]
    arch_name = platform_info["arch"][arch]
    ext = platform_info["ext"]
    bin_name = BIN_NAMES[system]

    print(f"  系统: {system} / {arch} → {arch_name}")

    # ── 确定安装目录 ──
    if args.dir:
        install_dir = Path(args.dir).resolve()
    else:
        # 默认：脚本所在目录的父目录（项目根目录）
        install_dir = Path(__file__).resolve().parent.parent

    install_dir.mkdir(parents=True, exist_ok=True)
    dest_bin = install_dir / bin_name

    # ── 检查是否已安装 ──
    if dest_bin.exists():
        try:
            result = subprocess.run(
                [str(dest_bin), "--version"],
                capture_output=True, text=True, timeout=5
            )
            existing_ver = result.stdout.strip()
            if CROC_VERSION[1:] in existing_ver or CROC_VERSION in existing_ver:
                print(f"  ✓ croc 已安装: {dest_bin}")
                print(f"    版本: {existing_ver}")
                print()
                return
            else:
                print(f"  ! 发现旧版本: {existing_ver}，更新中...")
        except Exception:
            print(f"  ! 文件存在但无法运行，重新安装...")

    # ── 下载 ──
    filename = f"croc_{CROC_VERSION}_{arch_name}{ext}"
    url = f"{GITHUB_REPO}/releases/download/{CROC_VERSION}/{filename}"

    # 使用国内镜像加速（如果下载慢可以手动指定）
    proxy_url = os.environ.get("CROC_MIRROR", url)

    tmp_dir = Path(tempfile.mkdtemp())
    archive_path = tmp_dir / filename

    try:
        print(f"  目标: {dest_bin}")
        print()

        download_file(proxy_url, archive_path)

        # ── 解压 ──
        extract_dir = tmp_dir / "extract"
        extract_dir.mkdir()
        extracted_bin = extract_archive(archive_path, extract_dir, ext, bin_name)

        # ── 复制到安装目录 ──
        shutil.copy2(extracted_bin, dest_bin)
        print(f"  ✓ 已安装: {dest_bin}")

        # 设置可执行权限（Linux/macOS）
        if system != "windows":
            dest_bin.chmod(dest_bin.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

        # ── 验证 ──
        result = subprocess.run(
            [str(dest_bin), "--version"],
            capture_output=True, text=True, timeout=5
        )
        version = result.stdout.strip()
        print(f"  版本: {version}")
        print(f"  大小: {dest_bin.stat().st_size / 1024 / 1024:.1f} MB")

        # ── 添加到 PATH ──
        if args.add_to_path and system == "windows":
            _add_to_path_windows(install_dir)
            print("  ✓ 已加入 PATH（重启终端生效）")

        print()
        print(f"  ✓ croc 安装完成！")
        print(f"  用法:")
        print(f"    {dest_bin} send <文件路径>")
        print(f"    {dest_bin} <code-phrase>")
        print()

    except Exception as e:
        print(f"\n  ❌ 安装失败: {e}")
        print(f"\n  手动安装方法:")
        print(f"    1. 访问 {GITHUB_REPO}/releases")
        print(f"    2. 下载 {filename}")
        print(f"    3. 解压后把 {bin_name} 放到 {install_dir}")
        sys.exit(1)
    finally:
        # 清理临时文件
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _add_to_path_windows(dir_path: Path) -> None:
    """Windows 下将目录加入用户 PATH"""
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            "Environment",
            0, winreg.KEY_READ | winreg.KEY_WRITE
        )
        current_path, _ = winreg.QueryValueEx(key, "Path")
        dir_str = str(dir_path)
        if dir_str not in current_path:
            new_path = f"{current_path};{dir_str}"
            winreg.SetValueEx(key, "Path", 0, winreg.REG_EXPAND_SZ, new_path)
            winreg.CloseKey(key)
            # 通知系统环境变量已更改
            import ctypes
            HWND_BROADCAST = 0xFFFF
            WM_SETTINGCHANGE = 0x001A
            ctypes.windll.user32.SendMessageW(HWND_BROADCAST, WM_SETTINGCHANGE, 0, "Environment")
    except Exception as e:
        print(f"  ! 自动加入 PATH 失败: {e}")
        print(f"  请手动将 {dir_path} 加入系统 PATH")


import tempfile


if __name__ == "__main__":
    main()
