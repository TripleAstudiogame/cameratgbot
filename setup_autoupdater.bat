@echo off
title Настройка автообновлений Report Camera
echo.
echo ================================================================
echo   Report Camera — Установка планировщика автообновлений
echo ================================================================
echo.

if not "%1"=="am_admin" (
    powershell -Command "Start-Process -Verb RunAs -FilePath '%0' -ArgumentList 'am_admin'"
    exit /b
)

set TASK_NAME=ReportCamera_AutoUpdater
set SCRIPT_PATH=C:\Amir\mailru_integrator\MailToTelegram\auto_updater.ps1

echo Удаляем старую задачу (если есть)...
schtasks /Delete /TN "%TASK_NAME%" /F >nul 2>nul

echo Создаем задачу на проверку GitHub каждые 5 минут...
schtasks /Create /TN "%TASK_NAME%" /TR "powershell.exe -ExecutionPolicy Bypass -WindowStyle Hidden -File ""%SCRIPT_PATH%""" /SC MINUTE /MO 5 /RU "SYSTEM" /RL HIGHEST /F

echo.
echo Задача успешно создана! 
echo Теперь сервер будет каждые 5 минут проверять ветку main в GitHub.
echo В случае обновлений служба ReportCamera будет автоматически обновлена.
echo.
pause
