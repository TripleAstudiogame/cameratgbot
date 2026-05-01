@echo off
title Сброс Пароля (Report Camera)
color 0B
echo.
echo ================================================================
echo   СБРОС ПАРОЛЯ АДМИНИСТРАТОРА НА "Amir"
echo ================================================================
echo.
"%~dp0venv\Scripts\python.exe" "%~dp0reset_password.py"
echo.
pause
