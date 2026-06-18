@echo off
chcp 65001 >nul 2>&1
title TCP Chat Setup
cd /d "%~dp0"

set ZIP_URL=https://github.com/GarmandoSHAO/TCP-Chat/archive/refs/heads/main.zip
set ZIP_FILE=TCP-Chat.zip
set DOWNLOAD_OK=0

if exist "TCP-Chat.exe" set DOWNLOAD_OK=1
if exist "main.py" set DOWNLOAD_OK=1

if %DOWNLOAD_OK% equ 1 goto :INSTALL

echo ===============================================
echo   TCP Chat - Download ^& Install
echo ===============================================
echo.

:: Method 1: curl.exe
echo [1/3] curl.exe (Windows built-in) ...
where curl.exe >nul 2>&1
if %errorlevel% equ 0 (
    curl.exe -L -# -o "%ZIP_FILE%" "%ZIP_URL%" 2>&1
    if %errorlevel% equ 0 call :CHECK_ZIP
    if %DOWNLOAD_OK% equ 1 goto :EXTRACT
)

:: Method 2: PowerShell
echo [2/3] PowerShell ...
powershell -ExecutionPolicy Bypass -Command "try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; $c = New-Object System.Net.WebClient; $c.DownloadFile('%ZIP_URL%', '%ZIP_FILE%'); Write-Host 'OK' } catch { exit 1 }" 2>&1
if %errorlevel% equ 0 call :CHECK_ZIP
if %DOWNLOAD_OK% equ 1 goto :EXTRACT

:: Method 3: BITS
echo [3/3] BITS ...
powershell -Command "try { Start-BitsTransfer -Source '%ZIP_URL%' -Destination '%ZIP_FILE%' -ErrorAction Stop; Write-Host 'OK' } catch { exit 1 }" 2>&1
if %errorlevel% equ 0 call :CHECK_ZIP
if %DOWNLOAD_OK% equ 1 goto :EXTRACT

:: All failed
echo.
echo ===============================================
echo   Download failed. Please try manually:
echo ===============================================
echo.
echo   1. Download the ZIP:
echo      %ZIP_URL%
echo.
echo   2. Save to this folder as: %ZIP_FILE%
echo.
echo   3. Run this setup again
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
