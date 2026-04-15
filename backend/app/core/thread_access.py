"""Reply permissions based on a post's value_policy_json."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.core.matching import compute_user_axis_scores
from app.core.user_blocks import is_hidden_pair
from app.models.question import QuestionAxis
from app.models.thread import ThreadPost


def _policy(post: ThreadPost) -> dict[str, Any]:
    try:
        raw = json.loads(post.value_policy_json or "{}")
    except json.JSONDecodeError:
        return {}
    return raw if isinstance(raw, dict) else {}


def can_user_reply(db: Session, post: ThreadPost, viewer_id: int) -> tuple[bool, str]:
    """(allowed, user_visible_reason)."""
    if post.visibility != "public":
        return False, "Ответы недоступны для этого поста."

    if post.author_id is not None and viewer_id == post.author_id:
        return True, ""

    if post.author_id is not None and is_hidden_pair(db, viewer_id, post.author_id):
        return False, "Пользователь недоступен (блокировка)."

    p = _policy(post)
    mode = str(p.get("mode") or "axes")
    if mode != "axes":
        return False, "Политика доступа поста не поддерживается."

    axes = p.get("axes")
    if not isinstance(axes, list) or not axes:
        return False, "У поста не заданы правила ценностей (оси)."

    min_axes = p.get("min_axes_matched")
    if not isinstance(min_axes, int) or min_axes < 0:
        min_axes = 1

    axes_by_slug = {a.slug: a for a in db.query(QuestionAxis).all()}
    scores = compute_user_axis_scores(db, viewer_id)

    matched = 0
    missing_any = False
    for ax in axes:
        if not isinstance(ax, dict):
            continue
        slug = str(ax.get("slug") or "").strip()
        if not slug:
            continue
        if slug not in axes_by_slug:
            return False, "Пост ссылается на неизвестную ось."
        axis_id = axes_by_slug[slug].id
        if axis_id not in scores:
            missing_any = True
            continue
        try:
            target = float(ax.get("target"))
            max_dist = float(ax.get("max_dist"))
        except (TypeError, ValueError):
            continue
        viewer = float(scores[axis_id])
        if abs(viewer - target) <= max_dist:
            matched += 1

    if matched >= min_axes:
        return True, ""

    if missing_any:
        return (
            False,
            "Ответьте на вопросы теста по теме поста — тогда сможете участвовать в обсуждении.",
        )
    return False, "Ваш профиль ценностей недостаточно близок к теме этого поста."

