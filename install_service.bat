@echo off
title Установка Report Camera как Windows Service
echo.
echo ================================================================
echo   Report Camera — Установка службы Windows
echo ================================================================
echo.

REM Проверяем наличие NSSM
where nssm >nul 2>nul
if %errorlevel% neq 0 (
    echo [ОШИБКА] NSSM не найден!
    echo.
    echo Скачайте NSSM с https://nssm.cc/download
    echo Распакуйте nssm.exe в C:\Windows или в PATH
    echo.
    pause
    exit /b 1
)

set SERVICE_NAME=ReportCamera
set APP_DIR=%~dp0
set PYTHON_PATH=%APP_DIR%venv\Scripts\python.exe
set UVICORN_PATH=%APP_DIR%venv\Scripts\uvicorn.exe

echo Остановка существующей службы (если есть)...
nssm stop %SERVICE_NAME% >nul 2>nul
nssm remove %SERVICE_NAME% confirm >nul 2>nul

echo Установка новой службы...
nssm install %SERVICE_NAME% "%UVICORN_PATH%"
nssm set %SERVICE_NAME% AppParameters "app:app --host 0.0.0.0 --port 6565 --workers 1"
nssm set %SERVICE_NAME% AppDirectory "%APP_DIR%"

REM Логирование stdout/stderr
nssm set %SERVICE_NAME% AppStdout "%APP_DIR%service_stdout.log"
nssm set %SERVICE_NAME% AppStderr "%APP_DIR%service_stderr.log"
nssm set %SERVICE_NAME% AppStdoutCreationDisposition 4
nssm set %SERVICE_NAME% AppStderrCreationDisposition 4
nssm set %SERVICE_NAME% AppRotateFiles 1
nssm set %SERVICE_NAME% AppRotateBytes 5242880

REM Автозапуск и автоперезапуск
nssm set %SERVICE_NAME% Start SERVICE_AUTO_START
nssm set %SERVICE_NAME% AppRestartDelay 5000
nssm set %SERVICE_NAME% Description "Report Camera NVR SaaS — мониторинг камер и уведомления в Telegram"

REM Зависимость от сети
nssm set %SERVICE_NAME% DependOnService Tcpip Dhcp

echo.
echo ================================================================
echo   Служба "%SERVICE_NAME%" установлена!
echo.
echo   Запуск:    nssm start %SERVICE_NAME%
echo   Остановка: nssm stop %SERVICE_NAME%
echo   Статус:    nssm status %SERVICE_NAME%
echo   Удаление:  nssm remove %SERVICE_NAME% confirm
echo.
echo   Порт: 6565
echo   URL:  http://localhost:6565
echo ================================================================
echo.

REM Запуск службы
echo Запуск службы...
nssm start %SERVICE_NAME%

echo.
echo Готово! Служба запущена.
pause
