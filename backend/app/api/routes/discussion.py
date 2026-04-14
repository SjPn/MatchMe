"""Тематическая лента обсуждений (по осям ценностей)."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import FileResponse, Response
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.config import settings
from app.core.discussion_access import can_user_comment_on_post
from app.database import get_db
from app.models.discussion import DiscussionComment, DiscussionPost
from app.models.question import QuestionAxis
from app.models.user import User
from app.schemas.discussion import (
    CommentPermissionOut,
    CommentReplyPreview,
    DiscussionCommentCreate,
    DiscussionCommentOut,
    DiscussionPostCreate,
    DiscussionPostListOut,
    DiscussionPostOut,
)

router = APIRouter(prefix="/discussions", tags=["discussions"])

BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent.parent
DISCUSSION_UPLOAD = BACKEND_ROOT / "uploads" / "discussion"
_ALLOWED_IMG = frozenset({".jpg", ".jpeg", ".png", ".webp", ".gif"})


def _require_test_done(user: User) -> None:
    if user.onboarding_step != "test_completed":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Сначала завершите тест и онбординг.",
        )


def _slug_json(slugs: list[str]) -> str:
    return json.dumps(slugs, ensure_ascii=False)


def _parse_slugs(raw: str) -> list[str]:
    try:
        data = json.loads(raw or "[]")
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    return [str(x).strip() for x in data if isinstance(x, str) and str(x).strip()]


def _axes_for_slugs(db: Session, slugs: list[str]) -> list[dict[str, str]]:
    if not slugs:
        return []
    rows = db.query(QuestionAxis).filter(QuestionAxis.slug.in_(slugs)).all()
    by_slug = {a.slug: a for a in rows}
    return [{"slug": s, "name": by_slug[s].name} for s in slugs if s in by_slug]


def _image_url(post_id: int, key: str | None) -> str | None:
    if not key:
        return None
    return f"/discussions/posts/{post_id}/image"


def _if_none_match_matches(header: str | None, etag: str) -> bool:
    if not header:
        return False
    for part in header.split(","):
        if part.strip() == etag:
            return True
    return False


def _discussion_feed_etag(db: Session) -> str:
    mp = db.query(func.max(DiscussionPost.id)).scalar()
    mc = db.query(func.max(DiscussionComment.id)).scalar()
    return f'W/"dm-{int(mp or 0)}-{int(mc or 0)}"'


def _discussion_post_comments_etag(db: Session, post_id: int) -> str:
    mx = (
        db.query(func.max(DiscussionComment.id))
        .filter(DiscussionComment.post_id == post_id)
        .scalar()
    )
    return f'W/"dmc-{post_id}-{int(mx or 0)}"'


def _preview(body: str, n: int = 220) -> str:
    t = (body or "").strip()
    if len(t) <= n:
        return t
    return t[: n - 1] + "…"


def _comments_to_out(
    db: Session,
    rows: list[tuple[DiscussionComment, User]],
) -> list[DiscussionCommentOut]:
    parent_ids = {c.reply_to_comment_id for c, _ in rows if c.reply_to_comment_id}
    parent_map: dict[int, tuple[DiscussionComment, User]] = {}
    if parent_ids:
        prs = (
            db.query(DiscussionComment, User)
            .join(User, DiscussionComment.user_id == User.id)
            .filter(DiscussionComment.id.in_(parent_ids))
            .all()
        )
        for pc, pu in prs:
            parent_map[pc.id] = (pc, pu)
    out: list[DiscussionCommentOut] = []
    for c, u in rows:
        rto: CommentReplyPreview | None = None
        rid = c.reply_to_comment_id
        if rid and rid in parent_map:
            pc, pu = parent_map[rid]
            if pc.post_id == c.post_id:
                rto = CommentReplyPreview(
                    id=pc.id,
                    user_id=pc.user_id,
                    display_name=pu.display_name or "",
                    body_snippet=_preview(pc.body, 120),
                )
            else:
                rid = None
        elif rid:
            rid = None
        out.append(
            DiscussionCommentOut(
                id=c.id,
                user_id=c.user_id,
                display_name=u.display_name or "",
                body=c.body,
                reply_to_comment_id=rid,
                reply_to=rto,
                created_at=c.created_at.isoformat(),
            )
        )
    return out


def _author_label(post: DiscussionPost, db: Session) -> str | None:
    if post.author_id:
        au = db.get(User, post.author_id)
        return au.display_name if au else None
    if post.is_system:
        return "MatchMe"
    return None


def _build_post_out(db: Session, post: DiscussionPost) -> DiscussionPostOut:
    slugs = _parse_slugs(post.theme_axis_slugs_json)
    cc = (
        db.query(func.count(DiscussionComment.id))
        .filter(DiscussionComment.post_id == post.id)
        .scalar()
        or 0
    )
    return DiscussionPostOut(
        id=post.id,
        title=post.title,
        body=post.body,
        theme_axis_slugs=slugs,
        theme_axes=_axes_for_slugs(db, slugs),
        author_id=post.author_id,
        author_display_name=_author_label(post, db),
        is_system=post.is_system,
        image_url=_image_url(post.id, post.image_storage_key),
        comment_count=int(cc),
        created_at=post.created_at.isoformat(),
    )


@router.get("/posts", response_model=list[DiscussionPostListOut])
def list_posts(
    request: Request,
    response: Response,
    limit: int = Query(30, ge=1, le=50),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[DiscussionPostListOut] | Response:
    _ = user
    etag = _discussion_feed_etag(db)
    if _if_none_match_matches(request.headers.get("if-none-match"), etag):
        return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers={"ETag": etag})
    posts = (
        db.query(DiscussionPost)
        .order_by(DiscussionPost.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    out: list[DiscussionPostListOut] = []
    for post in posts:
        slugs = _parse_slugs(post.theme_axis_slugs_json)
        cc = (
            db.query(func.count(DiscussionComment.id))
            .filter(DiscussionComment.post_id == post.id)
            .scalar()
            or 0
        )
        out.append(
            DiscussionPostListOut(
                id=post.id,
                title=post.title,
                body_preview=_preview(post.body),
                theme_axis_slugs=slugs,
                theme_axes=_axes_for_slugs(db, slugs),
                author_id=post.author_id,
                author_display_name=_author_label(post, db),
                is_system=post.is_system,
                image_url=_image_url(post.id, post.image_storage_key),
                comment_count=int(cc),
                created_at=post.created_at.isoformat(),
            )
        )
    response.headers["ETag"] = etag
    return out


@router.get("/posts/{post_id}", response_model=DiscussionPostOut)
def get_post(
    post_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DiscussionPostOut:
    _ = user
    post = db.get(DiscussionPost, post_id)
    if post is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Пост не найден")
    return _build_post_out(db, post)


@router.get("/posts/{post_id}/can-comment", response_model=CommentPermissionOut)
def get_can_comment(
    post_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CommentPermissionOut:
    post = db.get(DiscussionPost, post_id)
    if post is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Пост не найден")
    ok, reason = can_user_comment_on_post(db, post, user.id)
    return CommentPermissionOut(can_comment=ok, reason=reason)


@router.post("/posts", response_model=DiscussionPostOut, status_code=201)
def create_post(
    body: DiscussionPostCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DiscussionPostOut:
    _require_test_done(user)
    axes = db.query(QuestionAxis).all()
    valid = {a.slug for a in axes}
    cleaned = []
    for s in body.theme_axis_slugs:
        s = s.strip()
        if s in valid and s not in cleaned:
            cleaned.append(s)
    if not cleaned:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Укажите хотя бы одну существующую тему (ось из теста).",
        )
    post = DiscussionPost(
        author_id=user.id,
        title=body.title.strip(),
        body=body.body.strip(),
        theme_axis_slugs_json=_slug_json(cleaned),
        is_system=False,
        created_at=datetime.now(timezone.utc),
    )
    db.add(post)
    db.commit()
    db.refresh(post)
    return _build_post_out(db, post)


@router.post("/posts/{post_id}/image", response_model=DiscussionPostOut)
async def upload_post_image(
    post_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DiscussionPostOut:
    _require_test_done(user)
    post = db.get(DiscussionPost, post_id)
    if post is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Пост не найден")
    if post.author_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Только автор может добавить обложку")
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in _ALLOWED_IMG:
        raise HTTPException(status_code=400, detail="Допустимы JPG, PNG, WebP, GIF")
    raw = await file.read()
    if len(raw) > settings.max_upload_bytes:
        raise HTTPException(status_code=400, detail="Файл слишком большой")
    DISCUSSION_UPLOAD.mkdir(parents=True, exist_ok=True)
    key = f"{post_id}_{uuid.uuid4().hex}{suffix}"
    (DISCUSSION_UPLOAD / key).write_bytes(raw)
    post.image_storage_key = key
    db.add(post)
    db.commit()
    db.refresh(post)
    return _build_post_out(db, post)


@router.get("/posts/{post_id}/image")
def get_post_image(
    post_id: int,
    db: Session = Depends(get_db),
) -> FileResponse:
    """Без JWT: иначе <img src> в браузере не отправит токен. Публично по id поста (MVP)."""
    post = db.get(DiscussionPost, post_id)
    if post is None or not post.image_storage_key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Нет изображения")
    key = post.image_storage_key
    if "/" in key or "\\" in key or ".." in key:
        raise HTTPException(status_code=404, detail="Файл не найден")
    base = DISCUSSION_UPLOAD.resolve()
    path = (DISCUSSION_UPLOAD / key).resolve()
    if path.parent != base or not path.is_file():
        raise HTTPException(status_code=404, detail="Файл не найден")
    media = "image/jpeg"
    if key.lower().endswith(".png"):
        media = "image/png"
    elif key.lower().endswith(".webp"):
        media = "image/webp"
    elif key.lower().endswith(".gif"):
        media = "image/gif"
    return FileResponse(path, media_type=media)


@router.get("/posts/{post_id}/comments", response_model=list[DiscussionCommentOut])
def list_comments(
    request: Request,
    response: Response,
    post_id: int,
    after_id: int | None = Query(None, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[DiscussionCommentOut] | Response:
    _ = user
    post = db.get(DiscussionPost, post_id)
    if post is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Пост не найден")
    etag = _discussion_post_comments_etag(db, post_id)
    if _if_none_match_matches(request.headers.get("if-none-match"), etag):
        return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers={"ETag": etag})
    q = (
        db.query(DiscussionComment, User)
        .join(User, DiscussionComment.user_id == User.id)
        .filter(DiscussionComment.post_id == post_id)
    )
    if after_id is not None:
        q = q.filter(DiscussionComment.id > after_id)
    rows = q.order_by(DiscussionComment.created_at.asc()).all()
    response.headers["ETag"] = etag
    return _comments_to_out(db, rows)


@router.post("/posts/{post_id}/comments", response_model=DiscussionCommentOut, status_code=201)
def add_comment(
    post_id: int,
    body: DiscussionCommentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DiscussionCommentOut:
    _require_test_done(user)
    post = db.get(DiscussionPost, post_id)
    if post is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Пост не найден")
    ok, reason = can_user_comment_on_post(db, post, user.id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=reason)
    reply_to_id = body.reply_to_comment_id
    if reply_to_id is not None:
        parent = db.get(DiscussionComment, reply_to_id)
        if parent is None or parent.post_id != post_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ответ возможен только на комментарий к этому посту.",
            )
    c = DiscussionComment(
        post_id=post_id,
        user_id=user.id,
        body=body.body.strip(),
        reply_to_comment_id=reply_to_id,
        created_at=datetime.now(timezone.utc),
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return _comments_to_out(db, [(c, user)])[0]


@router.get("/axes", response_model=list[dict])
def list_axes_for_form(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """Оси для выбора темы поста."""
    _ = user
    axes = db.query(QuestionAxis).order_by(QuestionAxis.id).all()
    return [{"slug": a.slug, "name": a.name} for a in axes]
