@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"

echo Downloading from Gitee...
powershell -Command "$p=[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; Invoke-WebRequest 'https://gitee.com/garmando/tcp-chat/repository/archive/main.zip' -OutFile 'TCP-Chat.zip' -ErrorAction Stop"

if exist "TCP-Chat.zip" (
    echo Saved: %cd%\TCP-Chat.zip
) else (
    echo Failed
)
pause
