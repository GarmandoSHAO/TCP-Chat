@echo off
chcp 65001 >nul 2>&1
title TCP Chat Setup
cd /d "%~dp0"

if exist "TCP-Chat.exe" goto :ALREADY
if exist "main.py" goto :ALREADY

echo Downloading TCP Chat...
echo.

set ZIP_FILE=TCP-Chat.zip

:: 1. Gitee (China)
del "%ZIP_FILE%" 2>nul
echo [1] Gitee ...
powershell -Command "$p=[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; (New-Object System.Net.WebClient).DownloadFile('https://gitee.com/garmando/tcp-chat/repository/archive/main.zip','%ZIP_FILE%')"
if exist "%ZIP_FILE%" goto :EXTRACT

:: 2. GitHub
del "%ZIP_FILE%" 2>nul
echo [2] GitHub ...
powershell -Command "$p=[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; (New-Object System.Net.WebClient).DownloadFile('https://github.com/GarmandoSHAO/TCP-Chat/archive/refs/heads/main.zip','%ZIP_FILE%')"
if exist "%ZIP_FILE%" goto :EXTRACT

echo Download failed.
pause
exit /b

:EXTRACT
echo Extracting...
if exist "TCP-Chat" rmdir /s /q "TCP-Chat" 2>nul
tar -xf "%ZIP_FILE%" 2>nul
del "%ZIP_FILE%" 2>nul
for /d %%D in (*) do if exist "%%D\main.py" move "%%D" "TCP-Chat" >nul 2>&1
if not exist "TCP-Chat" for /d %%D in (*) do if exist "%%D\tcp_chat" move "%%D" "TCP-Chat" >nul 2>&1

:ALREADY
echo.
echo Done! See TCP-Chat folder.
echo.
pause
