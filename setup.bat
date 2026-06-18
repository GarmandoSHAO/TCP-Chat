@echo off
chcp 65001 >nul 2>&1
title TCP Chat Setup
cd /d "%~dp0"

if exist "TCP-Chat.exe" goto :INSTALL
if exist "main.py" goto :INSTALL

echo ===============================================
echo   TCP Chat - Download ^& Install
echo ===============================================
echo.

set ZIP_FILE=TCP-Chat.zip

:: 1. Gitee
del "%ZIP_FILE%" 2>nul
echo [1] Gitee ...
powershell -Command "$p=[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; (New-Object System.Net.WebClient).DownloadFile('https://gitee.com/garmando/tcp-chat/repository/archive/main.zip','%ZIP_FILE%')"
if exist "%ZIP_FILE%" goto :EXTRACT

:: 2. GitHub fallback
del "%ZIP_FILE%" 2>nul
echo [2] GitHub ...
powershell -Command "$p=[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; (New-Object System.Net.WebClient).DownloadFile('https://github.com/GarmandoSHAO/TCP-Chat/archive/refs/heads/main.zip','%ZIP_FILE%')"
if exist "%ZIP_FILE%" goto :EXTRACT

echo.
echo Download failed. Manual: %ZIP_URL%
pause
exit /b

:EXTRACT
echo.
echo Extracting...
if exist "TCP-Chat" rmdir /s /q "TCP-Chat" 2>nul
tar -xf "%ZIP_FILE%" 2>nul
del "%ZIP_FILE%" 2>nul
:: Find the extracted folder
for /d %%D in (*) do if exist "%%D\main.py" move "%%D" "TCP-Chat" >nul 2>&1
if not exist "TCP-Chat" for /d %%D in (*) do if exist "%%D\tcp_chat" move "%%D" "TCP-Chat" >nul 2>&1
cd TCP-Chat 2>nul

:INSTALL
echo.
echo Creating desktop shortcut...
set TARGET=%cd%
if exist "TCP-Chat.exe" ( set EXE=%TARGET%\TCP-Chat.exe ) else ( set EXE=%TARGET%\main.py )
powershell -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Desktop')+'\TCP Chat.lnk');$s.TargetPath='%EXE%';$s.WorkingDirectory='%TARGET%';$s.Save()" >nul
echo.
echo Done! Shortcut created: TCP Chat (desktop)
echo.
pause
