# Запуск API из каталога backend (где лежит пакет app).
Set-Location $PSScriptRoot
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
