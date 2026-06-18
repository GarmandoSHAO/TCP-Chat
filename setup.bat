@echo off
chcp 65001 >nul 2>&1
title TCP Chat Setup
cd /d "%~dp0"

set ZIP_FILE=TCP-Chat.zip

if exist "TCP-Chat.exe" goto :INSTALL
if exist "main.py" goto :INSTALL

echo ===============================================
echo   TCP Chat - Download ^& Install
echo ===============================================
echo.

:: Try Gitee first (faster in China)
echo [1] Gitee (China) ...
set ZIP_URL=https://gitee.com/garmando/tcp-chat/repository/archive/main.zip
powershell -Command ^
    $ProgressPreference = 'Continue'; ^
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; ^
    try { Invoke-WebRequest -Uri '%ZIP_URL%' -OutFile '%ZIP_FILE%' -ErrorAction Stop; Write-Host 'OK' } catch { exit 1 }
if exist "%ZIP_FILE%" for %%F in ("%ZIP_FILE%") do if %%~zF GEQ 500000 goto :EXTRACT

:: Fallback: GitHub
echo.
echo [2] GitHub (fallback) ...
set ZIP_URL=https://github.com/GarmandoSHAO/TCP-Chat/archive/refs/heads/main.zip
powershell -Command ^
    $ProgressPreference = 'Continue'; ^
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; ^
    try { Invoke-WebRequest -Uri '%ZIP_URL%' -OutFile '%ZIP_FILE%' -ErrorAction Stop; Write-Host 'OK' } catch { exit 1 }
if exist "%ZIP_FILE%" for %%F in ("%ZIP_FILE%") do if %%~zF GEQ 500000 goto :EXTRACT

:: All failed
echo.
echo ===============================================
echo   Download failed.
echo ===============================================
echo.
echo   Please download manually:
echo   1. https://gitee.com/garmando/tcp-chat/repository/archive/main.zip
echo   2. Save to this folder as %ZIP_FILE%
echo   3. Run setup again
echo.
pause
exit /b

:EXTRACT
echo.
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
echo   Shortcut created: TCP Chat (desktop)
echo.
pause
