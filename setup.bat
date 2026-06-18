@echo off
chcp 65001 >nul 2>&1
title TCP Chat Setup
cd /d "%~dp0"

set ZIP_URL=https://github.com/GarmandoSHAO/TCP-Chat/archive/refs/heads/main.zip
set ZIP_FILE=TCP-Chat.zip

:: Already installed?
if exist "TCP-Chat.exe" goto :INSTALL
if exist "main.py" goto :INSTALL

echo ===============================================
echo   TCP Chat - Download ^& Install
echo ===============================================
echo.

:: Try each download method
call :DOWNLOAD_CURL
if %errorlevel% equ 0 goto :EXTRACT

call :DOWNLOAD_PS
if %errorlevel% equ 0 goto :EXTRACT

call :DOWNLOAD_BITS
if %errorlevel% equ 0 goto :EXTRACT

echo.
echo Failed to download. Please download manually:
echo   %ZIP_URL%
echo Save the ZIP to this folder and run setup again.
pause
exit /b

:DOWNLOAD_CURL
echo [1/3] curl.exe (Windows built-in) ...
where curl.exe >nul 2>&1 || exit /b 1
curl.exe -L -# -o "%ZIP_FILE%" "%ZIP_URL%" 2>&1
if %errorlevel% neq 0 exit /b 1
call :CHECK_ZIP && echo Done^^! || exit /b 1
exit /b 0

:DOWNLOAD_PS
echo [2/3] PowerShell ...
powershell -Command "
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12;
$wc = New-Object System.Net.WebClient;
$wc.DownloadFile('%ZIP_URL%', '%ZIP_FILE%');
Write-Host 'Done!'" 2>&1
if %errorlevel% neq 0 exit /b 1
call :CHECK_ZIP && exit /b 0 || exit /b 1

:DOWNLOAD_BITS
echo [3/3] BITS (Background Intelligent Transfer) ...
powershell -Command "Start-BitsTransfer -Source '%ZIP_URL%' -Destination '%ZIP_FILE%'" 2>&1
call :CHECK_ZIP && exit /b 0 || exit /b 1

:CHECK_ZIP
if not exist "%ZIP_FILE%" exit /b 1
set "SIZE="
for %%F in ("%ZIP_FILE%") do set SIZE=%%~zF
if "%SIZE%"=="" exit /b 1
if %SIZE% LSS 500000 exit /b 1
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
