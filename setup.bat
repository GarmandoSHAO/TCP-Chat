@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"

echo Downloading from Gitee...
powershell -Command "$p=[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; Invoke-WebRequest 'https://gitee.com/garmando/tcp-chat/repository/archive/main.zip' -OutFile 'TCP-Chat.zip' -ErrorAction Stop"

if not exist "TCP-Chat.zip" (
    echo Failed
    pause
    exit /b
)

echo Extracting...
tar -xf "TCP-Chat.zip" 2>&1
for /d %%D in (*) do if exist "%%D\main.py" move "%%D" "TCP-Chat" >nul 2>&1
if not exist "TCP-Chat" for /d %%D in (*) do if exist "%%D\tcp_chat" move "%%D" "TCP-Chat" >nul 2>&1

if exist "TCP-Chat\main.py" (
    del "TCP-Chat.zip" 2>nul
    echo OK - %cd%\TCP-Chat
) else (
    echo Extraction failed - ZIP saved at %cd%\TCP-Chat.zip
)
pause
