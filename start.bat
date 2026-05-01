@echo off
title Report Camera — NVR SaaS
echo Запуск Report Camera на порту 6565...
call venv\Scripts\activate.bat

python -m uvicorn app:app --host 0.0.0.0 --port 6565 --workers 1
pause
