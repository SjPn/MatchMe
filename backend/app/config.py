from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Всегда backend/.env — иначе скрипты из другого cwd (или из корня репо) подхватывали бы не ту БД.
_BACKEND_DIR = Path(__file__).resolve().parent.parent
_ENV_FILE = _BACKEND_DIR / ".env"


_env_kw: dict = {"env_file_encoding": "utf-8", "extra": "ignore"}
if _ENV_FILE.is_file():
    _env_kw["env_file"] = str(_ENV_FILE)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(**_env_kw)

    # Локально: SQLite. Относительный путь приводится к файлу в каталоге backend/ (рядом с app/),
    # чтобы и uvicorn, и seed, и alembic из любой cwd попадали в один и тот же matchme.db.
    # На проде: postgresql+psycopg2://user:pass@host:5432/dbname
    database_url: str = "sqlite:///./matchme.db"

    @field_validator("database_url", mode="after")
    @classmethod
    def normalize_database_url(cls, v: str) -> str:
        v = v.strip()
        low = v.lower()
        # Neon / libpq: postgresql://… без драйвера → SQLAlchemy + psycopg2-binary
        if low.startswith("postgres://"):
            v = "postgresql+psycopg2://" + v[len("postgres://") :]
            low = v.lower()
        elif low.startswith("postgresql://"):
            v = "postgresql+psycopg2://" + v[len("postgresql://") :]
            low = v.lower()
        if not low.startswith("sqlite:///"):
            return v
        path_part = v[len("sqlite:///") :]
        p = Path(path_part)
        if p.is_absolute():
            return v
        backend_dir = Path(__file__).resolve().parent.parent
        resolved = (backend_dir / path_part.lstrip("./")).resolve()
        return f"sqlite:///{resolved.as_posix()}"

    jwt_secret: str = "dev-only-change-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7
    # Любой порт Next (3000, 3300, …); при прямом NEXT_PUBLIC_API_URL на фронте Origin всё равно может быть localhost:3300
    cors_origins: str = (
        "http://localhost:3000,http://127.0.0.1:3000,"
        "http://localhost:3300,http://127.0.0.1:3300"
    )
    # Вложения в чате (локальный путь под backend/)
    max_upload_bytes: int = 10 * 1024 * 1024

    # Групповые чаты: когорта по осям (расхождение в шкале 0–1).
    # При случайных ответах в сидах пороги ~0.20 часто дают пустые комнаты — см. scripts/diagnose_group_cohorts.py
    group_cohort_mean_divergence_max: float = 0.28
    group_cohort_axis_divergence_max: float = 0.42
    group_min_members: int = 3
    group_max_members: int = 12
    group_messages_per_minute: int = 15

    # Лента обсуждений: мин. Match % с автором поста, чтобы комментировать (посты пользователей).
    discussion_min_match_with_author: float = 48.0
    # Посты от системы: макс. |score−0.5| по каждой тематической оси, чтобы комментировать.
    discussion_system_axis_max_dist_from_center: float = 0.45


settings = Settings()


def database_engine_kind() -> str:
    """Что реально подключено у процесса API (для /auth/me и диагностики). Не путать с тем, куда смотрит сид из другого терминала."""
    u = settings.database_url.strip().lower()
    return "sqlite" if u.startswith("sqlite") else "postgresql"
