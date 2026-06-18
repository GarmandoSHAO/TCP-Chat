@echo off
chcp 65001 >nul 2>&1
title TCP Chat Setup
cd /d "%~dp0"

set ZIP_FILE=TCP-Chat.zip
set DOWNLOAD_OK=0

if exist "TCP-Chat.exe" set DOWNLOAD_OK=1
if exist "main.py" set DOWNLOAD_OK=1

if %DOWNLOAD_OK% equ 1 goto :INSTALL

echo ===============================================
echo   TCP Chat - Download ^& Install
echo ===============================================
echo.

:: Try Gitee first (faster in China)
set ZIP_URL=https://gitee.com/garmando/tcp-chat/repository/archive/main.zip
echo [1] Gitee (China) ...
powershell -Command ^
    $ProgressPreference = 'Continue'; ^
    try { ^
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; ^
        Invoke-WebRequest -Uri '%ZIP_URL%' -OutFile '%ZIP_FILE%' -ErrorAction Stop; ^
        Write-Host 'OK'; ^
        exit 0; ^
    } catch { ^
        exit 1; ^
    }
if %errorlevel% equ 0 call :CHECK_ZIP
if %DOWNLOAD_OK% equ 1 goto :EXTRACT

:: Fallback: GitHub
set ZIP_URL=https://github.com/GarmandoSHAO/TCP-Chat/archive/refs/heads/main.zip
echo [2] GitHub (fallback) ...
powershell -Command ^
    $ProgressPreference = 'Continue'; ^
    try { ^
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; ^
        Invoke-WebRequest -Uri '%ZIP_URL%' -OutFile '%ZIP_FILE%' -ErrorAction Stop; ^
        Write-Host 'OK'; ^
        exit 0; ^
    } catch { ^
        exit 1; ^
    }
if %errorlevel% equ 0 call :CHECK_ZIP
if %DOWNLOAD_OK% equ 1 goto :EXTRACT

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

:CHECK_ZIP
if not exist "%ZIP_FILE%" exit /b 1
for %%F in ("%ZIP_FILE%") do if %%~zF GEQ 500000 set DOWNLOAD_OK=1
exit /b 0

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
