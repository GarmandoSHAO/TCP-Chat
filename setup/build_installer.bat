@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

title TCP 聊天室 — 构建安装包

echo.
echo ================================================
echo     TCP 聊天室 — 安装包构建脚本
echo ================================================
echo.

:: ── 检查环境 ──────────────────────────────────────

echo [1/4] 检查环境...
echo.

:: Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [FAIL] 未找到 Python，请安装 Python 3.10+
    pause
    exit /b 1
)
for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PY_VER=%%i
echo   [OK] Python %PY_VER%

:: PyInstaller
python -c "import PyInstaller" >nul 2>&1
if %errorlevel% neq 0 (
    echo [FAIL] 未安装 PyInstaller，正在安装...
    pip install pyinstaller
)
echo   [OK] PyInstaller

:: Inno Setup
set "ISCC="
for %%p in (
    "%ProgramFiles%\Inno Setup 6\ISCC.exe"
    "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
    "%ProgramFiles%\Inno Setup\ISCC.exe"
    "%ProgramFiles(x86)%\Inno Setup\ISCC.exe"
    "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
) do (
    if exist "%%~p" set "ISCC=%%~p"
)
if "%ISCC%"=="" (
    echo   [WARN] 未找到 Inno Setup 6.x
    echo   请从 https://jrsoftware.org/isinfo.php 下载安装
    set NEED_ISCC=1
) else (
    echo   [OK] Inno Setup: %ISCC%
)

:: ── 切换到项目根目录 ────────────────────────────

cd /d "%~dp0.."
set "ROOT=%CD%"
echo   [OK] 项目目录: %ROOT%

:: ── Step 2: PyInstaller --onedir 打包 ─────────────

echo.
echo [2/4] PyInstaller --onedir 打包...
echo.

:: 清理旧产物
if exist "%ROOT%\dist\TCP-Chat" rmdir /s /q "%ROOT%\dist\TCP-Chat"

:: 用 spec 文件打包（--onedir 模式，自动包含 datas）
python -m PyInstaller "%ROOT%\TCP-Chat.spec" --distpath "%ROOT%\dist" --workpath "%ROOT%\build" --noconfirm

if %errorlevel% neq 0 (
    echo [FAIL] PyInstaller 打包失败
    pause
    exit /b 1
)

:: 检查产物
set "BUILD_DIR=%ROOT%\dist\TCP-Chat"
if not exist "%BUILD_DIR%\TCP-Chat.exe" (
    echo [FAIL] dist\TCP-Chat\TCP-Chat.exe 未生成
    pause
    exit /b 1
)
echo   [OK] dist\TCP-Chat\TCP-Chat.exe

:: ── Step 3: 复制外部工具到打包目录 ───────────────

echo.
echo [3/4] 复制外部工具...
echo.

if exist "%ROOT%\bore.exe" (
    copy /y "%ROOT%\bore.exe" "%BUILD_DIR%\bore.exe" >nul
    echo   [OK] bore.exe → dist\TCP-Chat\
) else (
    echo   [WARN] bore.exe 未找到，隧道功能不可用
    echo   请从 https://github.com/ekzhang/bore/releases 下载
)

if exist "%ROOT%\croc.exe" (
    copy /y "%ROOT%\croc.exe" "%BUILD_DIR%\croc.exe" >nul
    echo   [OK] croc.exe → dist\TCP-Chat\
) else (
    echo   [WARN] croc.exe 未找到，文件传输功能不可用
    echo   请运行 python tools/install_croc.py 安装
)

:: 复制 config.json
if exist "%ROOT%\config.json" (
    copy /y "%ROOT%\config.json" "%BUILD_DIR%\config.json" >nul
    echo   [OK] config.json → dist\TCP-Chat\
)

:: 图标文件（TCP-Chat.png / TCP-Chat.ico）已由 PyInstaller datas 自动打包

:: 复制 README
if exist "%ROOT%\README.md" (
    copy /y "%ROOT%\README.md" "%BUILD_DIR%\README.md" >nul
)

:: 复制 setup_utils.py（给安装程序用）
copy /y "%ROOT%\setup\setup_utils.py" "%BUILD_DIR%\setup_utils.py" >nul

echo.
echo   打包目录内容:
dir /b "%BUILD_DIR%"
echo.

:: ── Step 4: 构建 Inno Setup 安装包 ──────────────

echo.
echo [4/4] 构建安装包...
echo.

if "%ISCC%"=="" (
    echo   [SKIP] 未安装 Inno Setup，跳过安装包构建
    echo.
    echo   可用手动方式:
    echo     安装 Inno Setup 6.x 后运行:
    echo       ISCC.exe setup\installer.iss
    echo   或直接分发 dist\TCP-Chat\ 目录
    goto :summary
)

"%ISCC%" "%ROOT%\setup\installer.iss"
if %errorlevel% neq 0 (
    echo [FAIL] 安装包构建失败
    pause
    exit /b 1
)

:: ── 输出结果 ─────────────────────────────────────

:summary
echo.
echo ================================================
echo     构建结果
echo ================================================
echo.

if exist "%ROOT%\dist\*.exe" (
    echo 安装包:
    for %%f in ("%ROOT%\dist\TCP-Chat-Setup-*.exe") do (
        echo   [DIST] %%f
    )
)
echo.
echo 绿色分发目录:
echo   [DIR] %BUILD_DIR%
echo   直接压缩此目录即可绿色分发
echo.

echo ================================================
echo.

pause
