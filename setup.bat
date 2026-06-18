@echo off
chcp 65001 >nul 2>&1
title TCP Chat - Setup
cd /d "%~dp0"

echo ===============================================
echo   TCP Chat - Setup
echo ===============================================
echo.

:: Check if running from a proper project folder
if not exist "main.py" if not exist "TCP-Chat.exe" (
    echo ERROR: Please run this from the TCP-Chat project folder.
    echo.
    echo   Option 1: Download the project ZIP from:
    echo   https://github.com/GarmandoSHAO/TCP-Chat/archive/refs/heads/main.zip
    echo.
    echo   Option 2: git clone https://github.com/GarmandoSHAO/TCP-Chat.git
    echo.
    pause
    exit /b
)

echo [1/2] Creating desktop shortcut...
set TARGET=%cd%
if exist "TCP-Chat.exe" (
    set EXE=%TARGET%\TCP-Chat.exe
) else (
    set EXE=%TARGET%\main.py
)

powershell -Command ^
    $ws = New-Object -ComObject WScript.Shell; ^
    $s = $ws.CreateShortcut([Environment]::GetFolderPath('Desktop') + '\TCP Chat.lnk'); ^
    $s.TargetPath = '%EXE%'; ^
    $s.WorkingDirectory = '%TARGET%'; ^
    $s.Save() >nul

if %errorlevel% equ 0 (
    echo   Desktop shortcut created: TCP Chat
) else (
    echo   Warning: could not create shortcut
)
echo.

echo [2/2] Done!
echo.
echo   You can now launch from the desktop shortcut.
echo.
echo   To share this app with others, just zip this whole folder
echo   and send it to them. They unzip and double-click TCP-Chat.exe
echo.
pause
