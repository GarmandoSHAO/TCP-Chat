@echo off
chcp 65001 >nul 2>&1
title TCP Chat Setup
cd /d "%~dp0"

echo Current folder: %cd%
echo.

if exist "TCP-Chat.exe" goto :ALREADY
if exist "main.py" goto :ALREADY

set ZIP_FILE=TCP-Chat.zip

:: 1. Gitee
del "%ZIP_FILE%" 2>nul
echo [1] Gitee ...
powershell -Command "$p=[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; try { Invoke-WebRequest 'https://gitee.com/garmando/tcp-chat/repository/archive/main.zip' -OutFile '%ZIP_FILE%' -ErrorAction Stop; Write-Host 'OK' } catch { exit 1 }"
if exist "%ZIP_FILE%" goto :EXTRACT

:: 2. GitHub
del "%ZIP_FILE%" 2>nul
echo [2] GitHub ...
powershell -Command "$p=[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; try { Invoke-WebRequest 'https://github.com/GarmandoSHAO/TCP-Chat/archive/refs/heads/main.zip' -OutFile '%ZIP_FILE%' -ErrorAction Stop; Write-Host 'OK' } catch { exit 1 }"
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
if exist "TCP-Chat\TCP-Chat.exe" (
    echo OK - Project ready at:
    echo   %cd%\TCP-Chat
    echo.
    echo Double-click TCP-Chat.exe to run.
) else if exist "TCP-Chat\main.py" (
    echo OK - Project ready at:
    echo   %cd%\TCP-Chat
    echo.
    echo Run: python main.py
) else (
    echo Extraction failed - the downloaded file was not a valid ZIP.
    echo Try downloading manually from GitHub:
    echo   https://github.com/GarmandoSHAO/TCP-Chat/archive/refs/heads/main.zip
)
echo.
pause
