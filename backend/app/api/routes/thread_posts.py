"""Threads-like timeline and posts (unified root + replies)."""

from __future__ import annotations

import base64
import json
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.thread_access import can_user_reply
from app.database import get_db
from app.models.question import QuestionAxis
from app.models.thread import ThreadMedia, ThreadPost
from app.models.thread_social import ThreadPostLike
from app.models.thread_topics import ThreadPostTopic
from app.models.user import User
from app.schemas.thread import (
    CanReplyOut,
    CursorPage,
    ThreadAuthorOut,
    ThreadMediaOut,
    ThreadPostCreate,
    ThreadPostQuoteCreate,
    ThreadPostDetailOut,
    ThreadPostOut,
    ThreadPostReplyCreate,
)

router = APIRouter(tags=["threads"])


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _encode_cursor(dt: datetime, post_id: int) -> str:
    payload = {"t": dt.isoformat(), "id": int(post_id)}
    raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _decode_cursor(cur: str) -> tuple[datetime, int]:
    try:
        pad = "=" * ((4 - (len(cur) % 4)) % 4)
        raw = base64.urlsafe_b64decode((cur + pad).encode("ascii"))
        data: Any = json.loads(raw.decode("utf-8"))
        t = datetime.fromisoformat(str(data.get("t")))
        pid = int(data.get("id"))
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
        return t, pid
    except Exception as e:
        raise HTTPException(status_code=400, detail="Некорректный cursor") from e


def _media_out(m: ThreadMedia) -> ThreadMediaOut:
    # MVP: media download endpoints are not implemented yet; keep a stable URL shape for future.
    return ThreadMediaOut(id=m.id, url=f"/thread-media/{m.id}", mime=m.mime)


def _author_out(u: User | None) -> ThreadAuthorOut:
    return ThreadAuthorOut(id=u.id if u else None, display_name=(u.display_name if u else None))


def _post_out_fast(
    p: ThreadPost,
    *,
    viewer_id: int | None,
    counts: dict[int, dict[str, int]],
    liked_by_me: set[int],
    topics: dict[int, list[str]],
    users_by_id: dict[int, User],
    media_by_post_id: dict[int, list[ThreadMedia]],
    quote_preview_by_id: dict[int, ThreadPostOut | None],
) -> ThreadPostOut:
    au = users_by_id.get(int(p.author_id)) if p.author_id else None
    c = counts.get(p.id, {})
    media = media_by_post_id.get(p.id, [])
    return ThreadPostOut(
        id=p.id,
        author=_author_out(au),
        parent_id=p.parent_id,
        root_id=p.root_id,
        kind=getattr(p, "kind", "post"),
        quote_post_id=p.quote_post_id,
        quote_preview=quote_preview_by_id.get(p.id),
        body=p.body,
        created_at=p.created_at.isoformat(),
        is_system=p.is_system,
        visibility=p.visibility,
        media=[_media_out(m) for m in media],
        reply_count=int(c.get("replies", 0)),
        like_count=int(c.get("likes", 0)),
        liked_by_me=bool(viewer_id is not None and p.id in liked_by_me),
        repost_count=int(c.get("reposts", 0)),
        quote_count=int(c.get("quotes", 0)),
        topic_axis_slugs=list(topics.get(p.id, [])),
    )


def _build_posts_out(
    db: Session,
    posts: list[ThreadPost],
    *,
    viewer_id: int,
    counts: dict[int, dict[str, int]] | None = None,
    liked_by_me: set[int] | None = None,
    topics: dict[int, list[str]] | None = None,
    include_quote_preview: bool = True,
) -> list[ThreadPostOut]:
    if not posts:
        return []

    ids = [p.id for p in posts]
    counts = counts or _collect_counts(db, ids)
    liked_by_me = liked_by_me or _collect_liked_by_me(db, viewer_id, ids)
    topics = topics or _collect_topics(db, ids)

    author_ids = {int(p.author_id) for p in posts if p.author_id}
    users = db.query(User).filter(User.id.in_(sorted(author_ids))).all() if author_ids else []
    users_by_id: dict[int, User] = {int(u.id): u for u in users}

    media_rows = (
        db.query(ThreadMedia)
        .filter(ThreadMedia.post_id.in_(ids))
        .order_by(ThreadMedia.post_id.asc(), ThreadMedia.id.asc())
        .all()
    )
    media_by_post_id: dict[int, list[ThreadMedia]] = {}
    for m in media_rows:
        media_by_post_id.setdefault(int(m.post_id), []).append(m)

    quote_preview_by_id: dict[int, ThreadPostOut | None] = {pid: None for pid in ids}
    if include_quote_preview:
        quote_ids = {int(p.quote_post_id) for p in posts if p.quote_post_id}
        if quote_ids:
            quoted = (
                db.query(ThreadPost)
                .filter(ThreadPost.id.in_(sorted(quote_ids)), ThreadPost.visibility == "public")
                .all()
            )
            quoted_by_id: dict[int, ThreadPost] = {int(q.id): q for q in quoted}

            quoted_author_ids = {int(q.author_id) for q in quoted if q.author_id} - set(users_by_id.keys())
            if quoted_author_ids:
                more_users = db.query(User).filter(User.id.in_(sorted(quoted_author_ids))).all()
                for u in more_users:
                    users_by_id[int(u.id)] = u

            quoted_media_rows = (
                db.query(ThreadMedia)
                .filter(ThreadMedia.post_id.in_(sorted(quote_ids)))
                .order_by(ThreadMedia.post_id.asc(), ThreadMedia.id.asc())
                .all()
            )
            for m in quoted_media_rows:
                media_by_post_id.setdefault(int(m.post_id), []).append(m)

            # We intentionally don't recurse quote-of-quote in previews.
            quoted_counts = _collect_counts(db, list(quote_ids))
            quoted_topics = _collect_topics(db, list(quote_ids))
            quoted_liked = _collect_liked_by_me(db, viewer_id, list(quote_ids))
            empty_quote_preview: dict[int, ThreadPostOut | None] = {}
            for p in posts:
                if not p.quote_post_id:
                    continue
                qp = quoted_by_id.get(int(p.quote_post_id))
                if not qp:
                    continue
                quote_preview_by_id[p.id] = _post_out_fast(
                    qp,
                    viewer_id=viewer_id,
                    counts=quoted_counts,
                    liked_by_me=quoted_liked,
                    topics=quoted_topics,
                    users_by_id=users_by_id,
                    media_by_post_id=media_by_post_id,
                    quote_preview_by_id=empty_quote_preview,
                )

    return [
        _post_out_fast(
            p,
            viewer_id=viewer_id,
            counts=counts,
            liked_by_me=liked_by_me,
            topics=topics,
            users_by_id=users_by_id,
            media_by_post_id=media_by_post_id,
            quote_preview_by_id=quote_preview_by_id,
        )
        for p in posts
    ]


def _collect_counts(db: Session, post_ids: list[int]) -> dict[int, dict[str, int]]:
    if not post_ids:
        return {}
    out: dict[int, dict[str, int]] = {pid: {} for pid in post_ids}

    rows = (
        db.query(ThreadPost.parent_id, func.count(ThreadPost.id))
        .filter(ThreadPost.parent_id.in_(post_ids), ThreadPost.visibility == "public")
        .group_by(ThreadPost.parent_id)
        .all()
    )
    for parent_id, cnt in rows:
        if parent_id in out:
            out[int(parent_id)]["replies"] = int(cnt or 0)

    rows = (
        db.query(ThreadPostLike.post_id, func.count(ThreadPostLike.id))
        .filter(ThreadPostLike.post_id.in_(post_ids))
        .group_by(ThreadPostLike.post_id)
        .all()
    )
    for pid, cnt in rows:
        if pid in out:
            out[int(pid)]["likes"] = int(cnt or 0)

    rows = (
        db.query(ThreadPost.quote_post_id, func.count(ThreadPost.id))
        .filter(
            ThreadPost.quote_post_id.in_(post_ids),
            ThreadPost.visibility == "public",
            ThreadPost.parent_id.is_(None),
            ThreadPost.kind == "repost",
        )
        .group_by(ThreadPost.quote_post_id)
        .all()
    )
    for qid, cnt in rows:
        if qid in out:
            out[int(qid)]["reposts"] = int(cnt or 0)

    rows = (
        db.query(ThreadPost.quote_post_id, func.count(ThreadPost.id))
        .filter(
            ThreadPost.quote_post_id.in_(post_ids),
            ThreadPost.visibility == "public",
            ThreadPost.parent_id.is_(None),
            ThreadPost.kind == "quote",
        )
        .group_by(ThreadPost.quote_post_id)
        .all()
    )
    for qid, cnt in rows:
        if qid in out:
            out[int(qid)]["quotes"] = int(cnt or 0)

    return out


def _collect_liked_by_me(db: Session, viewer_id: int, post_ids: list[int]) -> set[int]:
    if not post_ids:
        return set()
    rows = (
        db.query(ThreadPostLike.post_id)
        .filter(ThreadPostLike.user_id == viewer_id, ThreadPostLike.post_id.in_(post_ids))
        .all()
    )
    return {int(r[0]) for r in rows}


def _collect_topics(db: Session, post_ids: list[int]) -> dict[int, list[str]]:
    if not post_ids:
        return {}
    rows = (
        db.query(ThreadPostTopic.post_id, ThreadPostTopic.axis_slug)
        .filter(ThreadPostTopic.post_id.in_(post_ids))
        .order_by(ThreadPostTopic.post_id.asc(), ThreadPostTopic.axis_slug.asc())
        .all()
    )
    out: dict[int, list[str]] = {}
    for pid, slug in rows:
        out.setdefault(int(pid), []).append(str(slug))
    return out


@router.get("/axes", response_model=list[dict])
def list_axes(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[dict]:
    _ = user
    axes = db.query(QuestionAxis).order_by(QuestionAxis.id).all()
    return [{"slug": a.slug, "name": a.name} for a in axes]


def _timeline_etag(db: Session) -> str:
    mx = db.query(func.max(ThreadPost.id)).scalar()
    return f'W/"tl-{int(mx or 0)}"'


def _if_none_match_matches(header: str | None, etag: str) -> bool:
    if not header:
        return False
    for part in header.split(","):
        if part.strip() == etag:
            return True
    return False


@router.get("/timeline", response_model=CursorPage)
def timeline(
    request: Request,
    response: Response,
    cursor: str | None = None,
    topic: str | None = Query(None, min_length=1, max_length=80),
    limit: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CursorPage | Response:
    viewer_id = user.id

    # ETag only for the first page (cursor is None), so we can poll cheaply.
    if cursor is None:
        etag = _timeline_etag(db)
        if _if_none_match_matches(request.headers.get("if-none-match"), etag):
            return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers={"ETag": etag})
        response.headers["ETag"] = etag

    q = db.query(ThreadPost).filter(ThreadPost.parent_id.is_(None), ThreadPost.visibility == "public")
    if topic:
        q = (
            q.join(ThreadPostTopic, ThreadPostTopic.post_id == ThreadPost.id)
            .filter(ThreadPostTopic.axis_slug == topic.strip())
        )
    if cursor:
        t, pid = _decode_cursor(cursor)
        q = q.filter(
            (ThreadPost.created_at < t)
            | ((ThreadPost.created_at == t) & (ThreadPost.id < pid))
        )
    rows = q.order_by(ThreadPost.created_at.desc(), ThreadPost.id.desc()).limit(limit + 1).all()

    next_cursor: str | None = None
    if len(rows) > limit:
        last = rows[limit - 1]
        next_cursor = _encode_cursor(last.created_at, last.id)
        rows = rows[:limit]
    ids = [p.id for p in rows]
    counts = _collect_counts(db, ids)
    liked = _collect_liked_by_me(db, viewer_id, ids)
    topics = _collect_topics(db, ids)
    items = _build_posts_out(db, rows, viewer_id=viewer_id, counts=counts, liked_by_me=liked, topics=topics)
    return CursorPage(items=items, next_cursor=next_cursor)


@router.get("/posts/{post_id}", response_model=ThreadPostDetailOut)
def get_post_detail(
    post_id: int,
    replies_limit: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ThreadPostDetailOut:
    viewer_id = user.id
    p = db.get(ThreadPost, post_id)
    if p is None or p.visibility != "public":
        raise HTTPException(status_code=404, detail="Пост не найден")

    parents_posts: list[ThreadPost] = []
    seen: set[int] = set()
    cur = p
    # Walk parents chain up to 32 to avoid cycles / abuse.
    for _i in range(32):
        if cur.parent_id is None:
            break
        if cur.parent_id in seen:
            break
        seen.add(cur.parent_id)
        par = db.get(ThreadPost, cur.parent_id)
        if par is None or par.visibility != "public":
            break
        parents_posts.append(par)
        cur = par
    parents_posts.reverse()

    # First page of replies (newest first)
    rq = (
        db.query(ThreadPost)
        .filter(ThreadPost.parent_id == p.id, ThreadPost.visibility == "public")
        .order_by(ThreadPost.created_at.desc(), ThreadPost.id.desc())
        .limit(replies_limit + 1)
        .all()
    )
    next_cur: str | None = None
    if len(rq) > replies_limit:
        last = rq[replies_limit - 1]
        next_cur = _encode_cursor(last.created_at, last.id)
        rq = rq[:replies_limit]

    all_posts = [p] + parents_posts + rq
    all_ids = [x.id for x in all_posts]
    counts = _collect_counts(db, all_ids)
    liked = _collect_liked_by_me(db, viewer_id, all_ids)
    topics = _collect_topics(db, all_ids)
    outs = _build_posts_out(db, all_posts, viewer_id=viewer_id, counts=counts, liked_by_me=liked, topics=topics)
    out_by_id = {o.id: o for o in outs}
    return ThreadPostDetailOut(
        post=out_by_id[p.id],
        parents=[out_by_id[x.id] for x in parents_posts],
        replies=[out_by_id[x.id] for x in rq],
        next_replies_cursor=next_cur,
    )


@router.get("/posts/{post_id}/replies", response_model=CursorPage)
def get_replies(
    post_id: int,
    cursor: str | None = None,
    limit: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CursorPage:
    viewer_id = user.id
    p = db.get(ThreadPost, post_id)
    if p is None or p.visibility != "public":
        raise HTTPException(status_code=404, detail="Пост не найден")

    q = (
        db.query(ThreadPost)
        .filter(ThreadPost.parent_id == post_id, ThreadPost.visibility == "public")
    )
    if cursor:
        t, pid = _decode_cursor(cursor)
        q = q.filter((ThreadPost.created_at < t) | ((ThreadPost.created_at == t) & (ThreadPost.id < pid)))
    rows = q.order_by(ThreadPost.created_at.desc(), ThreadPost.id.desc()).limit(limit + 1).all()

    next_cursor: str | None = None
    if len(rows) > limit:
        last = rows[limit - 1]
        next_cursor = _encode_cursor(last.created_at, last.id)
        rows = rows[:limit]
    ids = [x.id for x in rows]
    counts = _collect_counts(db, ids)
    liked = _collect_liked_by_me(db, viewer_id, ids)
    topics = _collect_topics(db, ids)
    return CursorPage(
        items=_build_posts_out(db, rows, viewer_id=viewer_id, counts=counts, liked_by_me=liked, topics=topics),
        next_cursor=next_cursor,
    )


@router.get("/posts/{post_id}/can-reply", response_model=CanReplyOut)
def can_reply(
    post_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CanReplyOut:
    p = db.get(ThreadPost, post_id)
    if p is None or p.visibility != "public":
        raise HTTPException(status_code=404, detail="Пост не найден")
    ok, reason = can_user_reply(db, p, user.id)
    return CanReplyOut(can_reply=ok, reason=reason)


@router.post("/posts", response_model=ThreadPostOut, status_code=201)
def create_root_post(
    body: ThreadPostCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ThreadPostOut:
    text = body.body.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Текст поста обязателен")

    # Build a value policy: axes -> target=author score at publish time.
    slugs = [s.strip() for s in (body.theme_axis_slugs or []) if s and s.strip()]
    axes = db.query(QuestionAxis).all()
    by_slug = {a.slug: a for a in axes}
    cleaned: list[str] = []
    for s in slugs:
        if s in by_slug and s not in cleaned:
            cleaned.append(s)

    # MVP: allow empty axes (open thread), but if axes provided — enforce them.
    policy: dict[str, Any] = {"mode": "axes", "axes": [], "min_axes_matched": 1}
    if cleaned:
        from app.core.matching import compute_user_axis_scores

        scores = compute_user_axis_scores(db, user.id)
        axis_max_dist = float(body.axis_max_dist)
        for slug in cleaned:
            ax = by_slug[slug]
            if ax.id not in scores:
                raise HTTPException(
                    status_code=400,
                    detail="Ответьте на вопросы теста по выбранным темам (осям), чтобы публиковать пост.",
                )
            policy["axes"].append(
                {
                    "slug": slug,
                    "target": float(scores[ax.id]),
                    "max_dist": axis_max_dist,
                    "weight": 1.0,
                }
            )
        policy["min_axes_matched"] = len(policy["axes"])

    p = ThreadPost(
        author_id=user.id,
        parent_id=None,
        root_id=0,  # will be set after insert
        kind="post",
        quote_post_id=None,
        body=text,
        value_policy_json=json.dumps(policy, ensure_ascii=False),
        is_system=False,
        visibility="public",
        created_at=_now(),
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    p.root_id = p.id
    db.add(p)
    db.commit()
    db.refresh(p)

    # Persist topics as normalized rows
    if cleaned:
        for slug in cleaned:
            db.add(ThreadPostTopic(post_id=p.id, axis_slug=slug))
        db.commit()

    counts = _collect_counts(db, [p.id])
    liked = _collect_liked_by_me(db, user.id, [p.id])
    topics = _collect_topics(db, [p.id])
    return _build_posts_out(db, [p], viewer_id=user.id, counts=counts, liked_by_me=liked, topics=topics)[0]


@router.post("/posts/{post_id}/reply", response_model=ThreadPostOut, status_code=201)
def reply_to_post(
    post_id: int,
    body: ThreadPostReplyCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ThreadPostOut:
    parent = db.get(ThreadPost, post_id)
    if parent is None or parent.visibility != "public":
        raise HTTPException(status_code=404, detail="Пост не найден")

    ok, reason = can_user_reply(db, parent, user.id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=reason)

    text = body.body.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Текст ответа обязателен")

    p = ThreadPost(
        author_id=user.id,
        parent_id=parent.id,
        root_id=parent.root_id or parent.id,
        kind="post",
        quote_post_id=None,
        body=text,
        value_policy_json=parent.value_policy_json,  # inherit contract down the thread
        is_system=False,
        visibility="public",
        created_at=_now(),
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    counts = _collect_counts(db, [p.id])
    liked = _collect_liked_by_me(db, user.id, [p.id])
    topics = _collect_topics(db, [p.id])
    return _build_posts_out(db, [p], viewer_id=user.id, counts=counts, liked_by_me=liked, topics=topics)[0]


@router.post("/posts/{post_id}/like", status_code=204)
def like_post(
    post_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    p = db.get(ThreadPost, post_id)
    if p is None or p.visibility != "public":
        raise HTTPException(status_code=404, detail="Пост не найден")
    existing = (
        db.query(ThreadPostLike)
        .filter(ThreadPostLike.post_id == post_id, ThreadPostLike.user_id == user.id)
        .first()
    )
    if existing is None:
        db.add(ThreadPostLike(post_id=post_id, user_id=user.id, created_at=_now()))
        db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/posts/{post_id}/like", status_code=204)
def unlike_post(
    post_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    p = db.get(ThreadPost, post_id)
    if p is None or p.visibility != "public":
        raise HTTPException(status_code=404, detail="Пост не найден")
    q = db.query(ThreadPostLike).filter(ThreadPostLike.post_id == post_id, ThreadPostLike.user_id == user.id)
    if q.first() is not None:
        q.delete()
        db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/posts/{post_id}/repost", response_model=ThreadPostOut, status_code=201)
def repost(
    post_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ThreadPostOut:
    target = db.get(ThreadPost, post_id)
    if target is None or target.visibility != "public":
        raise HTTPException(status_code=404, detail="Пост не найден")
    p = ThreadPost(
        author_id=user.id,
        parent_id=None,
        root_id=0,
        kind="repost",
        quote_post_id=target.id,
        body="",
        value_policy_json="{}",
        is_system=False,
        visibility="public",
        created_at=_now(),
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    p.root_id = p.id
    db.add(p)
    db.commit()
    db.refresh(p)
    counts = _collect_counts(db, [p.id, target.id])
    liked = _collect_liked_by_me(db, user.id, [p.id, target.id])
    topics = _collect_topics(db, [p.id, target.id])
    return _build_posts_out(db, [p], viewer_id=user.id, counts=counts, liked_by_me=liked, topics=topics)[0]


@router.post("/posts/{post_id}/quote", response_model=ThreadPostOut, status_code=201)
def quote(
    post_id: int,
    body: ThreadPostQuoteCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ThreadPostOut:
    target = db.get(ThreadPost, post_id)
    if target is None or target.visibility != "public":
        raise HTTPException(status_code=404, detail="Пост не найден")
    text = body.body.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Текст обязателен")
    p = ThreadPost(
        author_id=user.id,
        parent_id=None,
        root_id=0,
        kind="quote",
        quote_post_id=target.id,
        body=text,
        value_policy_json="{}",
        is_system=False,
        visibility="public",
        created_at=_now(),
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    p.root_id = p.id
    db.add(p)
    db.commit()
    db.refresh(p)
    counts = _collect_counts(db, [p.id, target.id])
    liked = _collect_liked_by_me(db, user.id, [p.id, target.id])
    topics = _collect_topics(db, [p.id, target.id])
    return _build_posts_out(db, [p], viewer_id=user.id, counts=counts, liked_by_me=liked, topics=topics)[0]

