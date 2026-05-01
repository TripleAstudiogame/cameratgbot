@echo off
title 1-Click Server Installer (Report Camera)
color 0B
echo.
echo ================================================================
echo   Запуск автоматической установки сервера (Report Camera)
echo ================================================================
echo.

:: Проверка прав Администратора
net session >nul 2>&1
if %errorLevel% == 0 (
    echo Права администратора подтверждены.
) else (
    echo Запрос прав Администратора...
    powershell -Command "Start-Process -Verb RunAs -FilePath '%0' -ArgumentList 'am_admin'"
    exit /b
)

:: Переходим в папку со скриптом
cd /d "%~dp0"

echo Запуск основного установщика (PowerShell)...
powershell.exe -ExecutionPolicy Bypass -NoProfile -File "server_deploy.ps1"

echo.
pause
