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

:: Read PORT from .env if present, default to 8080
set PORT=8080
for /f "usebackq tokens=1,* delims==" %%A in (".env") do (
    if "%%A"=="PORT" set PORT=%%B
)

:: Auto-detect BROWSE_ROOT from user profile parent (e.g. C:\Users)
for %%I in ("%USERPROFILE%\..") do set BROWSE_ROOT=%%~fI

echo   UI: http://localhost:%PORT%
echo.
echo Starting... (first run may take 2-5 minutes to build)
echo Press Ctrl+C to stop.
echo.

docker compose up --build --remove-orphans
pause
