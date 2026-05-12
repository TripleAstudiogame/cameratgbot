@echo off
chcp 65001 >nul
title Report Camera — автоматическая установка
color 0B

echo.
echo ================================================================
echo   Report Camera — установка и запуск (Windows Server / ПК)
echo   После установки сервер откроется в отдельном окне.
echo ================================================================
echo.

net session >nul 2>&1
if %errorLevel% == 0 (
    echo Права администратора: да.
) else (
    echo Запрос прав администратора...
    powershell -NoProfile -Command "Start-Process -Verb RunAs -FilePath '%~f0'"
    exit /b
)

cd /d "%~dp0"

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup_autonomous.ps1"
if errorlevel 1 (
    echo.
    echo Установка прервалась с ошибкой. Сообщение выше.
    pause
    exit /b 1
)

echo.
echo Окно с сервером должно было открыться отдельно.
echo На рабочем столе ярлык «Report Camera» для следующих запусков.
echo.
pause
