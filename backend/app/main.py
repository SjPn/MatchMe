import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect

from app.api.routes import (
    answers,
    auth,
    avatar,
    chat,
    compare,
    feed,
    group_chat,
    likes,
    moderation,
    profile,
    questions,
    thread_posts,
    users,
)
from app.config import settings
from app.database import Base, engine, ensure_sqlite_schema_compat

_log = logging.getLogger("uvicorn.error")


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Локальный SQLite: если забыли alembic — создаём таблицы при старте. На PostgreSQL в проде — только миграции."""
    url = settings.database_url.strip().lower()
    if url.startswith("sqlite"):
        # Тот же файл, что и у запросов: добавляем недостающие колонки (avatar_url и т.д.)
        ensure_sqlite_schema_compat()
        insp = inspect(engine)
        if not insp.has_table("users"):
            Base.metadata.create_all(bind=engine)
            _log.warning(
                "SQLite: созданы отсутствующие таблицы. Запусти один раз: python seed.py"
            )
    yield


app = FastAPI(title="MatchMe API", version="0.1.0", lifespan=lifespan)

origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
if not origins:
    origins = ["http://localhost:3000", "http://127.0.0.1:3000"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(questions.router)
app.include_router(answers.router)
app.include_router(profile.router)
app.include_router(avatar.router)
app.include_router(feed.router)
app.include_router(thread_posts.router)
app.include_router(compare.router)
app.include_router(likes.router)
app.include_router(chat.router)
app.include_router(group_chat.router)
app.include_router(moderation.router)
app.include_router(users.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
