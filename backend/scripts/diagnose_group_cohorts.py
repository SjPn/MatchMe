"""
Оценка гипотезы групповых комнат: сколько пользователей с test_completed,
сколько «подходящих пар» по текущим порогам из app.config.settings,
сколько уже создано комнат.

Запуск из backend/:
    python scripts/diagnose_group_cohorts.py
"""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import func, select

from app.config import settings
from app.core.group_matching import users_compatible_for_cohort
from app.database import SessionLocal
from app.models.group_room import GroupRoom
from app.models.user import User


def main() -> None:
    db = SessionLocal()
    try:
        users = db.scalars(
            select(User).where(User.onboarding_step == "test_completed")
        ).all()
        ids = [u.id for u in users]
        n = len(ids)
        print(f"Пользователей с test_completed: {n}")
        print(
            f"Пороги (settings): mean<={settings.group_cohort_mean_divergence_max}, "
            f"max_axis<={settings.group_cohort_axis_divergence_max}, "
            f"min_members={settings.group_min_members}, max={settings.group_max_members}"
        )

        compatible_pairs = 0
        for i, a in enumerate(ids):
            for b in ids[i + 1 :]:
                if users_compatible_for_cohort(db, a, b):
                    compatible_pairs += 1
        print(f"Совместимых пар (по осям): {compatible_pairs} из {n * (n - 1) // 2}")

        rooms = db.scalar(select(func.count(GroupRoom.id))) or 0
        print(f"Комнат group_rooms в БД: {rooms}")

        if n >= 2:
            peers_per_user: list[int] = []
            for uid in ids:
                k = sum(1 for v in ids if v != uid and users_compatible_for_cohort(db, uid, v))
                peers_per_user.append(k)
            peers_per_user.sort()
            mid = peers_per_user[len(peers_per_user) // 2]
            print(
                f"Подходящих собеседников на пользователя: min={peers_per_user[0]}, "
                f"медиана={mid}, max={peers_per_user[-1]}"
            )

        print(
            "\nЕсли compatible_pairs мало или rooms=0 — ослабьте group_cohort_* в .env или "
            "`app/config.py`, либо добавьте пользователей с близкими ответами (не полностью случайный сид)."
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
