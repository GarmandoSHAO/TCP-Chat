"""
TCP 聊天室 — 安装脚本
克隆仓库 → 安装依赖 → 生成桌面快捷方式
"""
import subprocess
import sys
import os

REPO_URL = "https://github.com/GarmandoSHAO/TCP-Chat.git"
PROJECT_DIR = "TCP-Chat"


def run(cmd, cwd=None):
    print(f"$ {cmd}")
    result = subprocess.run(cmd, shell=True, cwd=cwd)
    if result.returncode != 0:
        print(f"❌ 命令失败: {cmd}")
        sys.exit(1)
    return result


def create_shortcut(target, name):
    """用 PowerShell 在桌面创建快捷方式"""
    desktop = os.path.join(os.environ["USERPROFILE"], "Desktop")
    ps = (
        f'$ws = New-Object -ComObject WScript.Shell; '
        f'$s = $ws.CreateShortcut("{desktop}\\\\{name}.lnk"); '
        f'$s.TargetPath = "{target}"; '
        f'$s.WorkingDirectory = "{os.path.abspath(PROJECT_DIR)}"; '
        f'$s.Save()'
    )
    subprocess.run(["powershell", "-Command", ps], shell=True)
    return os.path.join(desktop, f"{name}.lnk")


def main():
    print("=" * 50)
    print("  TCP 聊天室 — 安装脚本")
    print("=" * 50)

    # 1. 检查 Python
    print("\n[1/5] 检查 Python...")
    if sys.version_info < (3, 10):
        print("❌ 需要 Python 3.10+，请先安装: https://python.org")
        sys.exit(1)
    print(f"   ✅ Python {sys.version_info.major}.{sys.version_info.minor}")

    # 2. 克隆 / 更新仓库
    print(f"\n[2/5] 获取项目 {REPO_URL}...")
    if os.path.exists(PROJECT_DIR):
        print(f"   {PROJECT_DIR} 已存在，执行 git pull...")
        run("git pull", cwd=PROJECT_DIR)
    else:
        run(f"git clone {REPO_URL}")

    project_path = os.path.abspath(PROJECT_DIR)

    # 3. 安装依赖
    print(f"\n[3/5] 安装 Python 依赖...")
    req = os.path.join(project_path, "requirements.txt")
    if os.path.exists(req):
        run(f"{sys.executable} -m pip install -r {req}")
    else:
        run(f"{sys.executable} -m pip install customtkinter")
    print("   ✅ 依赖安装完成")

    # 4. 检查 exe / bore
    print(f"\n[4/5] 检查可执行文件...")
    exe_path = os.path.join(project_path, "TCP-Chat.exe")
    bore_path = os.path.join(project_path, "bore.exe")
    if os.path.exists(exe_path):
        print("   ✅ TCP-Chat.exe 已存在")
        shortcut_target = exe_path
    else:
        print("   ℹ️ TCP-Chat.exe 不存在，将使用 python main.py 启动")
        shortcut_target = sys.executable
        print("     如需打包 exe 请参考 打包说明.md")
    if not os.path.exists(bore_path):
        print("   ℹ️ 外网穿透需下载 bore.exe")
        print("      https://github.com/ekzhang/bore/releases")

    # 5. 创建桌面快捷方式
    print(f"\n[5/5] 生成桌面快捷方式...")
    try:
        shortcut = create_shortcut(shortcut_target, "TCP 聊天室")
        print(f"   ✅ 快捷方式已创建: {shortcut}")
    except Exception as e:
        print(f"   ⚠️ 快捷方式创建失败: {e}")
        print(f"   手动创建: 右键 {shortcut_target} → 发送到桌面")

    print("\n" + "=" * 50)
    print("  ✅ 安装完成！")
    print("=" * 50)
    print(f"\n  项目位置: {project_path}")
    print(f"  运行:     双击桌面「TCP 聊天室」")
    print()


if __name__ == "__main__":
    main()
