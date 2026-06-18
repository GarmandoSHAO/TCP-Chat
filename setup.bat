@echo off
chcp 65001 >nul
title TCP 聊天室 — 安装程序
cd /d "%~dp0"

echo ===============================================
echo   TCP 聊天室 — 安装程序
echo ===============================================

:: 1. 检查 Python
echo.
echo [1/4] 检查 Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ 未安装 Python，请先安装 https://python.org
    pause
    exit /b
)
for /f "tokens=2" %%i in ('python --version 2^>^&1') do set pyver=%%i
echo    ✅ Python %pyver%

:: 2. 下载项目
echo.
echo [2/4] 获取项目...
if exist TCP-Chat (
    echo    TCP-Chat 已存在
    cd TCP-Chat
    git pull
    cd ..
) else (
    git clone https://github.com/GarmandoSHAO/TCP-Chat.git
    if %errorlevel% neq 0 (
        echo ❌ 下载失败，请确保已安装 git
        pause
        exit /b
    )
    echo    ✅ 下载完成
)

:: 3. 安装依赖
echo.
echo [3/4] 安装依赖...
cd TCP-Chat
if exist requirements.txt (
    pip install -r requirements.txt
) else (
    pip install customtkinter
)
echo    ✅ 依赖安装完成

:: 4. 创建桌面快捷方式
echo.
echo [4/4] 生成桌面快捷方式...
if exist TCP-Chat.exe (
    set target=%cd%\TCP-Chat.exe
) else (
    set target=python
    set args=main.py
)

powershell -Command ^
    $ws = New-Object -ComObject WScript.Shell; ^
    $s = $ws.CreateShortcut([Environment]::GetFolderPath('Desktop') + '\TCP 聊天室.lnk'); ^
    $s.TargetPath = '%target%'; ^
    $s.Arguments = '%args%'; ^
    $s.WorkingDirectory = '%cd%'; ^
    $s.Save() >nul 2>&1

echo    ✅ 桌面快捷方式已创建

echo.
echo ===============================================
echo   ✅ 安装完成！
echo ===============================================
echo.
echo   双击桌面「TCP 聊天室」即可运行
echo.
pause
