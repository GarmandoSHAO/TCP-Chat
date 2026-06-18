@echo off
chcp 65001 >nul 2>&1
title TCP Chat Setup
cd /d "%~dp0"

echo Downloading from Gitee...
echo.

powershell -Command "$p=[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; try { Invoke-WebRequest 'https://gitee.com/garmando/tcp-chat/repository/archive/main.zip' -OutFile 'TCP-Chat.zip' -ErrorAction Stop; Write-Host 'OK' } catch { Write-Host 'FAIL'; exit 1 }"

if not exist "TCP-Chat.zip" (
    echo Download failed.
    pause
    exit /b
)

echo Extracting...
if exist "TCP-Chat" rmdir /s /q "TCP-Chat" 2>nul
tar -xf "TCP-Chat.zip" 2>nul
del "TCP-Chat.zip" 2>nul
for /d %%D in (*) do if exist "%%D\main.py" move "%%D" "TCP-Chat" >nul 2>&1
if not exist "TCP-Chat" for /d %%D in (*) do if exist "%%D\tcp_chat" move "%%D" "TCP-Chat" >nul 2>&1

if exist "TCP-Chat\TCP-Chat.exe" (
    echo Done! Files in: %cd%\TCP-Chat
) else (
    echo Extraction failed.
)
pause
