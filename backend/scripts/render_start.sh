#!/usr/bin/env bash
# Старт API на Render: миграции → сид онбординга → uvicorn.
# Вынесено в файл, чтобы в Dashboard не ломали кавычки у $PORT (типичная ошибка: ...$PORT".' → порт "10000.").
set -euo pipefail
cd "$(dirname "$0")/.." || exit 1
export PYTHONPATH=.
alembic upgrade head
python seed.py
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT}"
