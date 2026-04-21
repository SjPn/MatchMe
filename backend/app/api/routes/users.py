from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.user_blocks import is_hidden_pair
from app.database import get_db
from app.models.social import Conversation, Match
from app.models.thread import ThreadPost
from app.models.user import User
from app.schemas.thread import CursorPage
from app.schemas.user import UserPublicOut

router = APIRouter(prefix="/users", tags=["users"])

BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent.parent
VERIFY_ROOT = BACKEND_ROOT / "uploads" / "verify"
AVATAR_ROOT = BACKEND_ROOT / "uploads" / "avatars"
_ALLOWED_VERIFY_EXT = (".jpg", ".jpeg", ".png", ".webp")


def _ordered_pair(a: int, b: int) -> tuple[int, int]:
    return (a, b) if a < b else (b, a)


def _conversation_id_between(db: Session, a: int, b: int) -> int | None:
    low, high = _ordered_pair(a, b)
    match_row = db.scalar(select(Match).where(Match.user_low_id == low, Match.user_high_id == high))
    if match_row is None:
        return None
    conv = db.scalar(select(Conversation).where(Conversation.match_id == match_row.id))
    return conv.id if conv else None


def _verification_photo_path(user_id: int) -> Path | None:
    for ext in _ALLOWED_VERIFY_EXT:
        p = VERIFY_ROOT / f"{user_id}{ext}"
        if p.is_file():
            return p
    return None


@router.get("/{user_id}/avatar")
def user_avatar(user_id: int) -> FileResponse:
    """
    Public avatar endpoint (for <img src> without JWT).
    Uses uploaded avatar if present.
    """
    p: Path | None = None
    for ext in _ALLOWED_VERIFY_EXT:
        cand = AVATAR_ROOT / f"{user_id}{ext}"
        if cand.is_file():
            p = cand
            break
    if p is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No avatar")
    ext = p.suffix.lower()
    media = "image/jpeg"
    if ext == ".png":
        media = "image/png"
    elif ext == ".webp":
        media = "image/webp"
    return FileResponse(p, media_type=media)


@router.get("/{user_id}", response_model=UserPublicOut)
def get_user_public(
    user_id: int,
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
) -> UserPublicOut:
    target = me if user_id == me.id else db.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if user_id != me.id and is_hidden_pair(db, me.id, user_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Blocked")
    avatar_url = target.avatar_url
    conv_id: int | None = None
    if user_id != me.id:
        conv_id = _conversation_id_between(db, me.id, user_id)
    return UserPublicOut(
        id=target.id,
        display_name=target.display_name,
        avatar_url=avatar_url,
        about_me=target.about_me,
        identity_verified=target.identity_verified,
        conversation_id=conv_id,
        answers_hidden_from_others=True,
    )


@router.get("/{user_id}/threads", response_model=CursorPage)
def get_user_threads(
    user_id: int,
    kind: str = Query("posts", pattern="^(posts|replies)$"),
    cursor: str | None = None,
    limit: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
) -> CursorPage:
    # visibility / blocks
    if user_id != me.id and is_hidden_pair(db, me.id, user_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Blocked")

    # Reuse timeline helpers to keep post shape consistent
    from app.api.routes.thread_posts import _build_posts_out, _decode_cursor, _encode_cursor

    target = me if user_id == me.id else db.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    q = db.query(ThreadPost).filter(ThreadPost.author_id == user_id, ThreadPost.visibility == "public")
    if kind == "posts":
        q = q.filter(ThreadPost.parent_id.is_(None))
    else:
        q = q.filter(ThreadPost.parent_id.is_not(None))

    if cursor:
        t, pid = _decode_cursor(cursor)
        q = q.filter((ThreadPost.created_at < t) | ((ThreadPost.created_at == t) & (ThreadPost.id < pid)))

    rows = q.order_by(ThreadPost.created_at.desc(), ThreadPost.id.desc()).limit(limit + 1).all()

    next_cursor: str | None = None
    if len(rows) > limit:
        last = rows[limit - 1]
        next_cursor = _encode_cursor(last.created_at, last.id)
        rows = rows[:limit]

    items = _build_posts_out(db, rows, viewer_id=me.id)
    return CursorPage(items=items, next_cursor=next_cursor)

