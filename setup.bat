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

:: Try GitHub first
echo [1/2] GitHub ...
del "%ZIP_FILE%" 2>nul
powershell -Command ^
    $ProgressPreference = 'Continue'; ^
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; ^
    try { ^
        Invoke-WebRequest -Uri 'https://github.com/GarmandoSHAO/TCP-Chat/archive/refs/heads/main.zip' -OutFile '%ZIP_FILE%' -ErrorAction Stop; ^
        exit 0 ^
    } catch { ^
        exit 1 ^
    }
if %errorlevel% equ 0 if exist "%ZIP_FILE%" goto :EXTRACT

:: Fallback: Gitee
echo [2/2] Gitee (fallback) ...
del "%ZIP_FILE%" 2>nul
powershell -Command ^
    $ProgressPreference = 'Continue'; ^
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; ^
    try { ^
        Invoke-WebRequest -Uri 'https://gitee.com/garmando/tcp-chat/repository/archive/main.zip' -OutFile '%ZIP_FILE%' -ErrorAction Stop; ^
        exit 0 ^
    } catch { ^
        exit 1 ^
    }
if %errorlevel% equ 0 if exist "%ZIP_FILE%" goto :EXTRACT

echo.
echo Download failed. Please try:
echo   1. Download: https://github.com/GarmandoSHAO/TCP-Chat/archive/refs/heads/main.zip
echo   2. Save to this folder as %ZIP_FILE%
echo   3. Run setup again
pause
exit /b

:EXTRACT
echo.
echo Extracting...
:: Delete old folder if exists
if exist "TCP-Chat" rmdir /s /q "TCP-Chat" 2>nul
:: Extract zip
tar -xf "%ZIP_FILE%" 2>nul
del "%ZIP_FILE%" 2>nul
:: The zip extracts to TCP-Chat-main (GitHub) or tcp-chat (Gitee)
:: Find the extracted folder and rename to TCP-Chat
for /d %%D in (*) do (
    if exist "%%D\main.py" (
        move "%%D" "TCP-Chat" >nul 2>&1
        goto :EXTRACT_DONE
    )
)
for /d %%D in (*) do (
    if exist "%%D\tcp_chat\__init__.py" (
        move "%%D" "TCP-Chat" >nul 2>&1
        goto :EXTRACT_DONE
    )
)
:EXTRACT_DONE
cd TCP-Chat 2>nul

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
