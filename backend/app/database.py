from collections.abc import Generator

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from app.config import settings


def _is_sqlite(url: str) -> bool:
    return url.strip().lower().startswith("sqlite")


def create_db_engine(url: str):
    """Один вход для Alembic и приложения. SQLite — локальная разработка; в проде — PostgreSQL."""
    kwargs: dict = {}
    if _is_sqlite(url):
        kwargs["connect_args"] = {"check_same_thread": False}
        kwargs["pool_pre_ping"] = False
    else:
        # Neon / managed Postgres: короткий recycle, ограниченный пул (лимиты соединений)
        kwargs["pool_pre_ping"] = True
        kwargs["pool_recycle"] = 300
        kwargs["pool_size"] = 5
        kwargs["max_overflow"] = 5

    engine = create_engine(url, **kwargs)
    sqlite_mode = _is_sqlite(url)

    @event.listens_for(engine, "connect")
    def _sqlite_pragma(dbapi_conn, _connection_record):
        if not sqlite_mode:
            return
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return engine


engine = create_db_engine(settings.database_url)


def ensure_sqlite_questions_likert_hints_column() -> None:
    """Если забыли alembic: добавляем колонку в существующий SQLite без пересоздания БД."""
    if not _is_sqlite(settings.database_url):
        return
    insp = inspect(engine)
    if not insp.has_table("questions"):
        return
    with engine.begin() as conn:
        rows = conn.execute(text("PRAGMA table_info(questions)")).fetchall()
        names = {row[1] for row in rows}
        if "likert_hints_json" in names:
            return
        conn.execute(text("ALTER TABLE questions ADD COLUMN likert_hints_json TEXT"))


ensure_sqlite_questions_likert_hints_column()


def ensure_sqlite_message_attachment_columns() -> None:
    if not _is_sqlite(settings.database_url):
        return
    insp = inspect(engine)
    if not insp.has_table("messages"):
        return
    with engine.begin() as conn:
        rows = conn.execute(text("PRAGMA table_info(messages)")).fetchall()
        names = {row[1] for row in rows}
        if "attachment_original_name" not in names:
            conn.execute(text("ALTER TABLE messages ADD COLUMN attachment_original_name VARCHAR(512)"))
        if "attachment_mime" not in names:
            conn.execute(text("ALTER TABLE messages ADD COLUMN attachment_mime VARCHAR(128)"))
        if "attachment_storage_key" not in names:
            conn.execute(text("ALTER TABLE messages ADD COLUMN attachment_storage_key VARCHAR(512)"))


ensure_sqlite_message_attachment_columns()


def ensure_sqlite_user_avatar_and_message_reply() -> None:
    if not _is_sqlite(settings.database_url):
        return
    insp = inspect(engine)
    with engine.begin() as conn:
        if insp.has_table("users"):
            rows = conn.execute(text("PRAGMA table_info(users)")).fetchall()
            names = {row[1] for row in rows}
            if "avatar_url" not in names:
                conn.execute(text("ALTER TABLE users ADD COLUMN avatar_url VARCHAR(1024)"))
        if insp.has_table("messages"):
            rows = conn.execute(text("PRAGMA table_info(messages)")).fetchall()
            names = {row[1] for row in rows}
            if "reply_to_message_id" not in names:
                conn.execute(text("ALTER TABLE messages ADD COLUMN reply_to_message_id INTEGER"))


ensure_sqlite_user_avatar_and_message_reply()


def ensure_sqlite_user_about_and_feed_prefs() -> None:
    if not _is_sqlite(settings.database_url):
        return
    insp = inspect(engine)
    if not insp.has_table("users"):
        return
    with engine.begin() as conn:
        rows = conn.execute(text("PRAGMA table_info(users)")).fetchall()
        names = {row[1] for row in rows}
        if "about_me" not in names:
            conn.execute(text("ALTER TABLE users ADD COLUMN about_me TEXT"))
        if "feed_preferences_json" not in names:
            conn.execute(text("ALTER TABLE users ADD COLUMN feed_preferences_json TEXT"))


ensure_sqlite_user_about_and_feed_prefs()


def ensure_sqlite_identity_verified_column() -> None:
    if not _is_sqlite(settings.database_url):
        return
    insp = inspect(engine)
    if not insp.has_table("users"):
        return
    with engine.begin() as conn:
        rows = conn.execute(text("PRAGMA table_info(users)")).fetchall()
        names = {row[1] for row in rows}
        if "identity_verified_at" not in names:
            conn.execute(
                text("ALTER TABLE users ADD COLUMN identity_verified_at DATETIME")
            )


ensure_sqlite_identity_verified_column()


def ensure_sqlite_schema_compat() -> None:
    """Подтянуть схему SQLite под модели (без полного цикла alembic). Вызывать при старте API."""
    ensure_sqlite_questions_likert_hints_column()
    ensure_sqlite_message_attachment_columns()
    ensure_sqlite_user_avatar_and_message_reply()
    ensure_sqlite_user_about_and_feed_prefs()
    ensure_sqlite_identity_verified_column()
    ensure_discussion_tables()
    ensure_discussion_reply_column()
    ensure_sqlite_group_tables()
    ensure_sqlite_moderation_tables()


def ensure_discussion_reply_column() -> None:
    if not _is_sqlite(settings.database_url):
        return
    insp = inspect(engine)
    if not insp.has_table("discussion_comments"):
        return
    with engine.begin() as conn:
        rows = conn.execute(text("PRAGMA table_info(discussion_comments)")).fetchall()
        names = {row[1] for row in rows}
        if "reply_to_comment_id" not in names:
            conn.execute(
                text("ALTER TABLE discussion_comments ADD COLUMN reply_to_comment_id INTEGER")
            )


def ensure_discussion_tables() -> None:
    if not _is_sqlite(settings.database_url):
        return
    insp = inspect(engine)
    if insp.has_table("discussion_posts"):
        ensure_discussion_reply_column()
        return
    from app.models.discussion import DiscussionComment, DiscussionPost

    DiscussionPost.__table__.create(bind=engine, checkfirst=True)
    DiscussionComment.__table__.create(bind=engine, checkfirst=True)


def ensure_sqlite_moderation_tables() -> None:
    if not _is_sqlite(settings.database_url):
        return
    insp = inspect(engine)
    if insp.has_table("user_blocks"):
        return
    from app.models.moderation import UserBlock, UserReport

    UserBlock.__table__.create(bind=engine, checkfirst=True)
    UserReport.__table__.create(bind=engine, checkfirst=True)


def ensure_sqlite_group_tables() -> None:
    if not _is_sqlite(settings.database_url):
        return
    insp = inspect(engine)
    if insp.has_table("group_rooms"):
        return
    from app.models.group_room import GroupMessage, GroupMessageReport, GroupRoom, GroupRoomMember

    for tbl in (
        GroupRoom.__table__,
        GroupRoomMember.__table__,
        GroupMessage.__table__,
        GroupMessageReport.__table__,
    ):
        tbl.create(bind=engine, checkfirst=True)


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        # При Ctrl+C / отмене задачи rollback в close() может кинуть KeyboardInterrupt / CancelledError —
        # не даём этому засорять stderr и «Exception ignored» в генераторе.
        try:
            db.close()
        except BaseException:
            pass
