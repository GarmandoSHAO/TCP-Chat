@echo off
chcp 65001 >nul
title TCP 聊天室 — 安装
cd /d "%~dp0"

echo ================================================
echo   TCP 聊天室 — 安装
echo ================================================
echo.

:: 检查 Python
echo [1/4] 检查 Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ 未找到 Python，请先安装: https://python.org
    pause
    exit /b 1
)
python -c "import sys; exit(0 if sys.version_info >= (3,10) else 1)" >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ 需要 Python 3.10+
    pause
    exit /b 1
)
echo    ✅ Python 正常

:: 安装依赖
echo.
echo [2/4] 安装依赖...
pip install -r requirements.txt >nul 2>&1
if %errorlevel% neq 0 (
    pip install customtkinter >nul 2>&1
)
echo    ✅ 依赖安装完成

:: 检查 bore
echo.
echo [3/4] 检查 bore...
if exist bore.exe (
    echo    ✅ bore.exe 已存在
) else (
    echo    ℹ️ 外网穿透需要 bore.exe
    echo       下载地址: https://github.com/ekzhang/bore/releases
)

:: 完成
echo.
echo ================================================
echo   ✅ 安装完成！
echo ================================================
echo.
echo   运行: python main.py
echo.
pause
