@echo off
chcp 65001 >nul 2>&1
title TCP Chat Setup
cd /d "%~dp0"

set ZIP_URL=https://github.com/GarmandoSHAO/TCP-Chat/archive/refs/heads/main.zip
set ZIP_FILE=TCP-Chat.zip

:: If we're already in the project folder, skip download
if exist "TCP-Chat.exe" goto :INSTALL
if exist "main.py" goto :INSTALL
if exist "tcp_chat" goto :INSTALL

echo ===============================================
echo   TCP Chat - Download ^& Install
echo ===============================================
echo.
echo Downloading from GitHub...
echo.

:: Try multiple download methods
call :DOWNLOAD
if %errorlevel% neq 0 (
    echo.
    echo FAILED: Could not download from GitHub.
    echo Possible causes: network restriction, firewall.
    echo.
    echo Please download manually:
    echo   1. Open: %ZIP_URL%
    echo   2. Save the ZIP to this folder
    echo   3. Run this setup again
    echo.
    pause
    exit /b
)

echo Extracting...
tar -xf "%ZIP_FILE%" 2>nul
if exist "TCP-Chat-main" (
    if exist "TCP-Chat" rmdir /s /q "TCP-Chat" >nul 2>&1
    move "TCP-Chat-main" "TCP-Chat" >nul
)
del "%ZIP_FILE%" 2>nul
cd TCP-Chat

:INSTALL
echo.
echo Creating desktop shortcut...
set TARGET=%cd%
if exist "TCP-Chat.exe" ( set EXE=%TARGET%\TCP-Chat.exe ) else ( set EXE=%TARGET%\main.py )

powershell -Command ^
    $ws = New-Object -ComObject WScript.Shell; ^
    $s = $ws.CreateShortcut([Environment]::GetFolderPath('Desktop') + '\TCP Chat.lnk'); ^
    $s.TargetPath = '%EXE%'; ^
    $s.WorkingDirectory = '%TARGET%'; ^
    $s.Save() >nul

echo.
echo ===============================================
echo   Done!
echo ===============================================
echo.
echo   Shortcut created on desktop: TCP Chat
echo.
pause
exit /b

:DOWNLOAD
echo   Method 1: curl.exe ...
curl.exe -L -s -o "%ZIP_FILE%" "%ZIP_URL%" 2>nul
call :CHECK_FILE "%ZIP_FILE%" && exit /b 0

echo   Method 2: PowerShell ...
powershell -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; $wc = New-Object System.Net.WebClient; try { $wc.DownloadFile('%ZIP_URL%', '%ZIP_FILE%'); Write-Host 'OK' } catch { exit 1 }" >nul 2>&1
call :CHECK_FILE "%ZIP_FILE%" && exit /b 0

echo   Method 3: BITS ...
powershell -Command "Start-BitsTransfer -Source '%ZIP_URL%' -Destination '%ZIP_FILE%'" >nul 2>&1
call :CHECK_FILE "%ZIP_FILE%" && exit /b 0

exit /b 1

:CHECK_FILE
if not exist "%1" exit /b 1
for %%F in ("%1") do if %%~zF LSS 1000 exit /b 1
exit /b 0
