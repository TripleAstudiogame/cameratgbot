@echo off
title Установка зависимостей MailToTelegram
echo Создание виртуального окружения...
python -m venv venv
if %errorlevel% neq 0 (
    echo Ошибка при создании виртуального окружения. Проверьте, установлен ли Python.
    pause
    exit /b %errorlevel%
)

echo Активация окружения и установка библиотек...
call venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt

echo.
echo ========================================================
echo ✅ Установка успешно завершена!
echo Теперь вы можете настроить файл .env и запустить бота.
echo ========================================================
pause
