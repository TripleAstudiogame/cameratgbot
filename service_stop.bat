@echo off
title Остановка Сервера (Report Camera)
color 0E
echo ================================================================
echo   Остановка службы и всех процессов Report Camera
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

echo [1/2] Остановка системной службы ReportCamera (через NSSM)...
powershell -Command "if (Get-Service ReportCamera -ErrorAction SilentlyContinue) { C:\Windows\System32\nssm.exe stop ReportCamera }"

echo [2/2] Принудительное завершение зависших процессов Python...
taskkill /F /IM python.exe /T >nul 2>&1

echo.
echo ================================================================
echo ГОТОВО! Все процессы остановлены. 
echo Теперь вы можете безопасно изменять или удалять файлы.
echo ================================================================
pause
