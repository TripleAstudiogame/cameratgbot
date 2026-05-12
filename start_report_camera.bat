@echo off
chcp 65001 >nul
title Report Camera — веб http://localhost:6565
cd /d "%~dp0"

if not exist "venv\Scripts\python.exe" (
    echo [Ошибка] Нет папки venv. Запустите сначала setup_server.bat от имени администратора.
    echo.
    pause
    exit /b 1
)

echo Запуск сервера... Окно не закрывайте — здесь идёт работа программы.
echo Откройте в браузере: http://localhost:6565
echo Остановка: закройте это окно или нажмите Ctrl+C
echo.

"%~dp0venv\Scripts\python.exe" "%~dp0app.py"
set ERR=%ERRORLEVEL%
if not %ERR%==0 (
    echo.
    echo Процесс завершился с кодом %ERR%.
    pause
)
exit /b %ERR%
