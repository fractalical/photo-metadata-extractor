@echo off
title Photo Metadata Extractor

echo.
echo  +======================================+
echo  ^|    Photo Metadata Extractor          ^|
echo  +======================================+
echo.

docker info >nul 2>&1
if errorlevel 1 (
    echo ERROR: Docker is not running.
    echo Please start Docker Desktop and try again.
    pause
    exit /b 1
)

:: Defaults
set PORT=8080
set NUM_COLORS=5
set SKIP_EXISTING=true

:: Read settings from .env if present
if exist ".env" (
    for /f "usebackq tokens=1,* delims==" %%A in (".env") do (
        if "%%A"=="PORT"          set PORT=%%B
        if "%%A"=="NUM_COLORS"    set NUM_COLORS=%%B
        if "%%A"=="SKIP_EXISTING" set SKIP_EXISTING=%%B
        if "%%A"=="BROWSE_ROOT"   set BROWSE_ROOT=%%B
    )
)

:: Auto-detect BROWSE_ROOT from user profile parent (e.g. C:\Users)
if "%BROWSE_ROOT%"=="" (
    for %%I in ("%USERPROFILE%\..") do set BROWSE_ROOT=%%~fI
)

set IMAGE=ghcr.io/fractalical/photo-metadata-extractor:latest

echo   UI: http://localhost:%PORT%
echo.
echo Removing old container if exists...
docker rm -f photo-metadata-extractor-web >nul 2>&1
echo.
echo Pulling image (first run downloads ~500 MB, subsequent runs are instant)...
docker pull %IMAGE%
echo.

:: Run container in detached mode
docker run -d --rm ^
    --name photo-metadata-extractor-web ^
    -p %PORT%:8080 ^
    -v "%BROWSE_ROOT%:/data:rw" ^
    -v "pme-model-cache:/app/models" ^
    -e PME_ROOT_DIR=/data ^
    -e PME_EXECUTION_PROVIDER=CPUExecutionProvider ^
    -e PME_NUM_COLORS=%NUM_COLORS% ^
    -e PME_SKIP_EXISTING=%SKIP_EXISTING% ^
    -e BROWSE_ROOT=%BROWSE_ROOT% ^
    %IMAGE% >nul 2>&1

echo Started! UI: http://localhost:%PORT%
echo.
echo Press Q to stop the container and exit.
echo.

:waitloop
choice /c QC /n /t 1 /d C >nul 2>&1
if errorlevel 2 goto waitloop
:: Q pressed
echo.
echo Stopping container...
docker stop photo-metadata-extractor-web >nul 2>&1
echo Done.
pause
