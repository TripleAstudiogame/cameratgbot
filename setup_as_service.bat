@echo off
chcp 65001 >nul
title Report Camera — установка как служба Windows (NSSM)
color 0E
echo.
echo ================================================================
echo   Режим СЛУЖБЫ: Python + Git + NSSM + автозапуск + автообновление
echo   Для простого запуска в окне используйте setup_server.bat
echo ================================================================
echo.

net session >nul 2>&1
if %errorLevel% == 0 (
    echo Права администратора подтверждены.
) else (
    powershell -NoProfile -Command "Start-Process -Verb RunAs -FilePath '%~f0'"
    exit /b
)

cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0server_deploy.ps1"
echo.
pause
