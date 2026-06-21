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

echo [1/5] 检查环境...
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
) do (
    if exist "%%~p" set "ISCC=%%~p"
)
if "%ISCC%"=="" (
    echo   [WARN] 未找到 Inno Setup 6.x
    echo   请从 https://jrsoftware.org/isinfo.php 下载安装
    echo.
    echo   安装后设置 ISCC_PATH 环境变量，或修改本脚本
    echo.
    set NEED_ISCC=1
) else (
    echo   [OK] Inno Setup: %ISCC%
)

:: ── 切换到项目根目录 ────────────────────────────

cd /d "%~dp0.."
set "ROOT=%CD%"
echo   [OK] 项目目录: %ROOT%

:: ── Step 2: PyInstaller 打包 ─────────────────────

echo.
echo [2/5] PyInstaller 打包...
echo.

python -m PyInstaller --onefile --noconsole --name "TCP-Chat" ^
    --hidden-import tcp_chat.server ^
    --hidden-import tcp_chat.tunnel ^
    --hidden-import tcp_chat.config ^
    --hidden-import tcp_chat.client ^
    --distpath "%ROOT%" ^
    "%ROOT%\main.py"

if %errorlevel% neq 0 (
    echo [FAIL] PyInstaller 打包失败
    pause
    exit /b 1
)

:: 检查 exe 是否生成
if not exist "%ROOT%\TCP-Chat.exe" (
    echo [FAIL] TCP-Chat.exe 未生成
    pause
    exit /b 1
)
for %%f in ("%ROOT%\TCP-Chat.exe") do set EXE_SIZE=%%~zf
set /a "EXE_SIZE_MB=EXE_SIZE / 1024 / 1024"
echo   [OK] TCP-Chat.exe (%EXE_SIZE_MB% MB)

:: ── Step 3: 检查外部工具 ─────────────────────────

echo.
echo [3/5] 检查外部工具...
echo.

if not exist "%ROOT%\bore.exe" (
    echo   [WARN] bore.exe 未找到
    echo   请从 https://github.com/ekzhang/bore/releases 下载
    echo   并放置到项目根目录
    echo.
) else (
    for %%f in ("%ROOT%\bore.exe") do set BORE_SIZE=%%~zf
    set /a "BORE_SIZE_KB=BORE_SIZE / 1024"
    echo   [OK] bore.exe (%BORE_SIZE_KB% KB)
)

if not exist "%ROOT%\croc.exe" (
    echo   [WARN] croc.exe 未找到
    echo   请运行 python tools/install_croc.py 安装
    echo   或从 https://github.com/schollz/croc/releases 下载
    echo.
) else (
    for %%f in ("%ROOT%\croc.exe") do set CROC_SIZE=%%~zf
    set /a "CROC_SIZE_MB=CROC_SIZE / 1024 / 1024"
    echo   [OK] croc.exe (%CROC_SIZE_MB% MB)
)

:: ── Step 4: 构建 Inno Setup 安装包 ──────────────

echo.
echo [4/5] 构建安装包...
echo.

if "%ISCC%"=="" (
    echo   [SKIP] 未安装 Inno Setup，跳过安装包构建
    echo.
    echo   可用手动方式:
    echo     安装 Inno Setup 6.x 后运行:
    echo       "%ISCC%" "%ROOT%\setup\installer.iss"
    echo   或直接分发 TCP-Chat.exe + bore.exe + croc.exe + config.json
    goto :summary
)

"%ISCC%" "%ROOT%\setup\installer.iss"
if %errorlevel% neq 0 (
    echo [FAIL] 安装包构建失败
    pause
    exit /b 1
)

:: ── Step 5: 输出结果 ─────────────────────────────

:summary
echo.
echo ================================================
echo     构建结果
echo ================================================
echo.

:: 列出生成的安装包
if exist "%ROOT%\dist\*.exe" (
    echo 安装包:
    for %%f in ("%ROOT%\dist\TCP-Chat-Setup-*.exe") do (
        for %%s in ("%%f") do set /a "PKG_SIZE_MB=%%~zs / 1024 / 1024"
        echo   [DIST] %%f (!PKG_SIZE_MB! MB)
    )
)

echo.
echo 构建产物:
echo   [EXE] %ROOT%\TCP-Chat.exe
if exist "%ROOT%\bore.exe" echo   [BIN] %ROOT%\bore.exe
if exist "%ROOT%\croc.exe" echo   [BIN] %ROOT%\croc.exe
echo   [CFG] %ROOT%\config.json

echo.
echo 分发方式:
echo   1. 完整安装包: dist\TCP-Chat-Setup-*.exe
echo   2. 绿色免安装: 直接打包 TCP-Chat.exe + bore.exe + croc.exe + config.json
echo.
echo ================================================
echo.

pause
