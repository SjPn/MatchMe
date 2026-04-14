"""
Симуляция пользователей: регистрация + полный онбординг со случайными ответами.

По умолчанию создаётся 100 «новых» пользователей (или перезаполняются их ответы, если email уже есть).

Запуск из каталога backend:
    python scripts/seed_fixture_users.py
    python scripts/seed_fixture_users.py --count 50

Нужны вопросы в БД: python seed.py

Логины: chaos001@<domain> … chaosNNN@<domain>, пароль одинаковый для всех (см. CHAOS_PASSWORD в коде).
"""

from __future__ import annotations

import argparse
import os
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.database import SessionLocal
from app.models.answer import Answer
from app.models.question import Question
from app.models.user import User

# Домен и префикс email; пароль один для удобства локальной проверки групп / ленты
CHAOS_DOMAIN = "matchme.demo"
CHAOS_EMAIL_PREFIX = "chaos"
CHAOS_PASSWORD = "ChaosDemo2026!"


def _mask_database_url(url: str) -> str:
    if "@" not in url or "://" not in url:
        return url
    try:
        scheme, rest = url.split("://", 1)
        if "@" not in rest:
            return url
        creds, host = rest.rsplit("@", 1)
        return f"{scheme}://***:***@{host}"
    except ValueError:
        return "(скрыто)"


def _ensure_user(db: Session, email: str, display_name: str, password: str) -> User:
    u = db.scalar(select(User).where(User.email == email))
    if u:
        u.hashed_password = hash_password(password)
        u.display_name = display_name
        return u
    u = User(
        email=email.lower().strip(),
        hashed_password=hash_password(password),
        display_name=display_name,
        auth_provider="email",
        onboarding_step="registered",
    )
    db.add(u)
    db.flush()
    return u


def _replace_onboarding_answers(
    db: Session,
    user_id: int,
    questions: list[Question],
    rng: random.Random,
) -> None:
    db.execute(delete(Answer).where(Answer.user_id == user_id))
    db.flush()
    now = datetime.now(timezone.utc)
    for q in questions:
        vn, vc = _chaotic_answer(rng, q)
        db.add(
            Answer(
                user_id=user_id,
                question_id=q.id,
                value_numeric=vn,
                value_choice=vc,
                confidence=None,
                answered_at=now,
            )
        )
    db.flush()


def _chaotic_answer(rng: random.Random, q: Question) -> tuple[float | None, str | None]:
    """Случайный допустимый ответ под тип вопроса."""
    if q.qtype == "likert":
        lo, hi = int(q.likert_min), int(q.likert_max)
        if hi < lo:
            lo, hi = hi, lo
        return float(rng.randint(lo, hi)), None
    if q.qtype in ("binary", "forced_choice"):
        return None, rng.choice(("a", "b"))
    # неизвестный тип — без ответа
    return None, None


def _set_onboarding_completed(db: Session, user: User) -> None:
    user.onboarding_step = "test_completed"
    db.add(user)


def _rng_for_index(i: int) -> random.Random:
    """Отдельный RNG на пользователя: хаотично, но воспроизводимо при том же i и PYTHONHASHSEED."""
    seed = int.from_bytes(os.urandom(8), "big") ^ (i * 0x9E3779B97F4A7C15)
    return random.Random(seed)


def main() -> None:
    ap = argparse.ArgumentParser(description="Симуляция пользователей с хаотичными ответами.")
    ap.add_argument("--count", type=int, default=100, help="Сколько пользователей (по умолчанию 100)")
    ap.add_argument(
        "--domain",
        type=str,
        default=CHAOS_DOMAIN,
        help=f"Домен email (по умолчанию {CHAOS_DOMAIN})",
    )
    args = ap.parse_args()
    count = max(1, min(args.count, 5000))
    domain = args.domain.strip().lower() or CHAOS_DOMAIN

    db = SessionLocal()
    try:
        from app.config import settings

        print(f"Подключение к БД: {_mask_database_url(settings.database_url)}")
        print("(должно совпадать с тем, что использует uvicorn; backend/.env грузится по абсолютному пути.)")

        questions = (
            db.query(Question)
            .filter(Question.pack == "onboarding")
            .order_by(Question.order_index, Question.id)
            .all()
        )
        if not questions:
            print("Нет вопросов pack=onboarding. Сначала: python seed.py")
            sys.exit(1)

        nq = len(questions)
        width = max(3, len(str(count)))
        print(f"Онбординг: {nq} вопросов. Создаю/обновляю {count} пользователей ({CHAOS_EMAIL_PREFIX}001…@{domain}).")

        for i in range(1, count + 1):
            email = f"{CHAOS_EMAIL_PREFIX}{i:0{width}d}@{domain}"
            display = f"Хаос {i:0{width}d}"
            u = _ensure_user(db, email, display, CHAOS_PASSWORD)
            rng = _rng_for_index(i)
            _replace_onboarding_answers(db, u.id, questions, rng)
            _set_onboarding_completed(db, u)
            db.commit()
            if i <= 5 or i == count or i % 25 == 0:
                print(f"  OK {i}/{count} {email}")

        total = db.scalar(select(func.count()).select_from(User)) or 0
        print("\nГотово.")
        print(f"Всего пользователей в этой БД сейчас: {total}")
        print(f"Пароль для всех chaos*: {CHAOS_PASSWORD}")
        print(f"Примеры входа: {CHAOS_EMAIL_PREFIX}001@{domain} … {CHAOS_EMAIL_PREFIX}{count:0{width}d}@{domain}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
