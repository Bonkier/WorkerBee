@echo off
title WorkerBee Build
cd /d "%~dp0all data"

echo Building WorkerBee...
python -m PyInstaller WorkerBee.spec --clean --noconfirm

if %errorlevel% neq 0 (
    echo Build failed.
    pause
    exit /b 1
)

:: Assemble release folder
echo.
echo Assembling release...
set RELEASE=%~dp0release
rmdir /s /q "%RELEASE%" 2>nul
mkdir "%RELEASE%"
mkdir "%RELEASE%\drivers"

xcopy /e /q "dist\WorkerBee" "%RELEASE%\" >nul
copy "%~dp0setup.bat" "%RELEASE%\" >nul
copy "C:\Users\Abhi\Downloads\Interception\Interception\command line installer\install-interception.exe" "%RELEASE%\drivers\" >nul

echo.
echo Done! Release folder: %RELEASE%
echo Users only need to:
echo   1. Run setup.bat (once, installs driver + requires restart)
echo   2. Run WorkerBee.exe
pause
