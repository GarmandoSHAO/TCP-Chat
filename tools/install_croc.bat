@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

echo.
echo ================================================
echo         Install croc - File Transfer Tool
echo ================================================
echo.

set "SCRIPT_DIR=%~dp0"
set "PROJECT_DIR=%SCRIPT_DIR%.."
set "CROC_VER=v10.4.4"
set "CROC_ZIP=croc_%CROC_VER%_Windows-64bit.zip"
set "CROC_URL=https://github.com/schollz/croc/releases/download/%CROC_VER%/%CROC_ZIP%"

if exist "%PROJECT_DIR%\croc.exe" (
    echo [OK] croc.exe already installed
    goto :usage
)

echo Target: %PROJECT_DIR%\croc.exe
echo.

:: use mirror if set
if not "%CROC_MIRROR%"=="" set "CROC_URL=%CROC_MIRROR%"
echo Downloading from: %CROC_URL%
echo.

:: PowerShell download
powershell -Command "& {
    $ProgressPreference = 'SilentlyContinue'
    $url = '%CROC_URL%'
    $out = Join-Path $env:TEMP '%CROC_ZIP%'
    Write-Host 'Downloading...'
    try {
        Invoke-WebRequest -Uri $url -OutFile $out -UseBasicParsing -TimeoutSec 120
        Write-Host '[OK] Downloaded'
    } catch {
        Write-Host '[FAIL] ' $_.Exception.Message
        exit 1
    }

    $extract = Join-Path $env:TEMP 'croc_extract'
    if (Test-Path $extract) { Remove-Item $extract -Recurse -Force }
    Expand-Archive -Path $out -DestinationPath $extract -Force

    $exe = Get-ChildItem -Path $extract -Recurse -Filter 'croc.exe' | Select-Object -First 1
    if (-not $exe) { Write-Host '[FAIL] croc.exe not found in archive'; exit 1 }

    Copy-Item $exe.FullName '%PROJECT_DIR%\croc.exe' -Force
    Write-Host '[OK] Installed to %PROJECT_DIR%\croc.exe'

    Remove-Item $out -Force -ErrorAction SilentlyContinue
    Remove-Item $extract -Recurse -Force -ErrorAction SilentlyContinue
}" 2>&1

if %errorlevel% neq 0 (
    echo.
    echo [FAIL] Installation failed.
    echo Manual install: download %CROC_URL%
    echo and extract croc.exe to %PROJECT_DIR%
    pause
    exit /b 1
)

:: verify
echo.
"%PROJECT_DIR%\croc.exe" --version >nul 2>&1
if %errorlevel% equ 0 (
    for /f "tokens=*" %%i in ('"%PROJECT_DIR%\croc.exe" --version 2^>nul') do set CROC_VER_OUT=%%i
    echo [OK] Installation complete!
    echo Version: !CROC_VER_OUT!
    echo Location: %PROJECT_DIR%\croc.exe
) else (
    echo [FAIL] Verification failed
    pause
    exit /b 1
)

:usage
echo.
echo ==================== Usage ====================
echo.
echo Send file:
echo   cd %PROJECT_DIR%
echo   croc.exe send ^<file-path^>
echo.
echo Receive file (run on the other machine):
echo   cd %PROJECT_DIR%
echo   croc.exe ^<code-phrase^>
echo.
echo If download is slow, set mirror first:
echo   set CROC_MIRROR=https://ghproxy.com/https://github.com/schollz/croc/releases/download/v10.4.4/croc_v10.4.4_Windows-64bit.zip
echo   install_croc.bat
echo.
echo ================================================
echo.
pause
