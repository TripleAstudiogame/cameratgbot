@echo off
title Полное Удаление Системы (Report Camera)
color 0C
echo ================================================================
echo   ПОЛНОЕ УДАЛЕНИЕ СЛУЖБЫ И АВТООБНОВЛЕНИЙ ИЗ WINDOWS
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

echo ВНИМАНИЕ: Вы уверены, что хотите полностью удалить службу ReportCamera
echo и автоматическое обновление из системы? 
echo (Сами файлы проекта и база данных удалены НЕ БУДУТ)
echo.
pause

echo.
echo [1/4] Остановка службы...
powershell -Command "if (Get-Service ReportCamera -ErrorAction SilentlyContinue) { C:\Windows\System32\nssm.exe stop ReportCamera }"

echo [2/4] Завершение процессов Python...
taskkill /F /IM python.exe /T >nul 2>&1

echo [3/4] Удаление службы Windows (ReportCamera)...
powershell -Command "if (Get-Service ReportCamera -ErrorAction SilentlyContinue) { C:\Windows\System32\nssm.exe remove ReportCamera confirm }"

echo [4/4] Удаление задачи Автообновления...
schtasks /Delete /TN "ReportCamera_AutoUpdater" /F >nul 2>&1

echo.
echo ================================================================
echo УДАЛЕНИЕ УСПЕШНО ЗАВЕРШЕНО!
echo Система полностью "отвязана" от Windows.
echo Теперь вы можете вручную удалить папку с файлами проекта, 
echo и Windows больше не будет выдавать ошибку "Файл используется".
echo ================================================================
pause
