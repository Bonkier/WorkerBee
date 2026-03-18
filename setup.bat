@echo off
title WorkerBee Setup

:: Re-launch as admin if not already
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Requesting administrator privileges...
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

echo ============================================
echo  WorkerBee - First Time Setup
echo ============================================
echo.
echo This will install the Interception keyboard/mouse driver.
echo This is a one-time setup. You won't need to run this again.
echo.
pause

:: Install Interception driver
echo Installing Interception driver...
"%~dp0drivers\install-interception.exe" /install
if %errorlevel% neq 0 (
    echo.
    echo ERROR: Driver installation failed.
    echo Please try running setup.bat again as Administrator.
    pause
    exit /b 1
)

echo.
echo ============================================
echo  Setup complete!
echo  Please RESTART your computer, then run
echo  WorkerBee.exe to start the application.
echo ============================================
echo.
pause
