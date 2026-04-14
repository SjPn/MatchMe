@echo off
REM Запуск API: рабочая папка должна быть backend/ (где лежит пакет app).
cd /d "%~dp0"
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
