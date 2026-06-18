@echo off
chcp 65001 >nul
title TCP 聊天室 — 安装程序
cd /d "%~dp0"

echo ===============================================
echo   TCP 聊天室 — 安装程序
echo   无需任何环境，Windows 10+ 可直接运行
echo ===============================================
echo.

:: 1. 下载项目压缩包
set ZIP_FILE=TCP-Chat.zip
set URL=https://github.com/GarmandoSHAO/TCP-Chat/archive/refs/heads/main.zip

echo [1/3] 正在下载项目... (约 35MB)
curl -L -# -o "%ZIP_FILE%" "%URL%" 2>&1
if %errorlevel% neq 0 (
    echo ❌ 下载失败，请检查网络连接
    pause
    exit /b
)
echo ✅ 下载完成

:: 2. 解压
echo.
echo [2/3] 正在解压...
if not exist "%ZIP_FILE%" (
    echo ❌ 压缩包不存在
    pause
    exit /b
)
tar -xf "%ZIP_FILE%" 2>nul
if exist TCP-Chat-main (
    if exist TCP-Chat (
        rmdir /s /q TCP-Chat
    )
    move TCP-Chat-main TCP-Chat >nul
)
del "%ZIP_FILE%" 2>nul
echo ✅ 解压完成

:: 3. 创建桌面快捷方式
echo.
echo [3/3] 生成桌面快捷方式...
set EXE_PATH=%cd%\TCP-Chat\TCP-Chat.exe
if not exist "%EXE_PATH%" (
    echo ⚠️ 未找到 TCP-Chat.exe，请手动运行 main.py（需安装 Python）
    echo    python TCP-Chat\main.py
) else (
    powershell -Command ^
        $ws = New-Object -ComObject WScript.Shell; ^
        $s = $ws.CreateShortcut([Environment]::GetFolderPath('Desktop') + '\TCP 聊天室.lnk'); ^
        $s.TargetPath = '%EXE_PATH%'; ^
        $s.WorkingDirectory = '%cd%\TCP-Chat'; ^
        $s.Save() >nul
    echo ✅ 桌面快捷方式已创建
)

echo.
echo ===============================================
echo   ✅ 安装完成！
echo ===============================================
echo.
echo   双击桌面「TCP 聊天室」即可运行
echo.
pause
