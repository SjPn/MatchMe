"""Право комментировать тематический пост по близости ценностей."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.config import settings
from app.core.matching import compare_users, compute_user_axis_scores
from app.core.user_blocks import is_hidden_pair
from app.models.discussion import DiscussionPost
from app.models.question import QuestionAxis


def _theme_slugs(post: DiscussionPost) -> list[str]:
    try:
        raw: Any = json.loads(post.theme_axis_slugs_json or "[]")
    except json.JSONDecodeError:
        return []
    if not isinstance(raw, list):
        return []
    return [str(x).strip() for x in raw if isinstance(x, str) and str(x).strip()]


def can_user_comment_on_post(
    db: Session, post: DiscussionPost, viewer_id: int
) -> tuple[bool, str]:
    """(allowed, user_visible_reason)."""
    if post.author_id is not None and viewer_id == post.author_id:
        return True, ""

    if post.author_id is not None and is_hidden_pair(db, viewer_id, post.author_id):
        return False, "Пользователь недоступен (блокировка)."

    slugs = _theme_slugs(post)
    if not slugs:
        return False, "У поста не задана тема (оси)."

    axes_by_slug = {a.slug: a for a in db.query(QuestionAxis).all()}
    for s in slugs:
        if s not in axes_by_slug:
            return False, "Тема поста ссылается на неизвестную ось."

    if post.author_id is not None:
        pct = compare_users(db, viewer_id, post.author_id)[0]
        if pct >= settings.discussion_min_match_with_author:
            return True, ""
        return (
            False,
            f"Чтобы комментировать, совпадение с автором должно быть не ниже "
            f"{settings.discussion_min_match_with_author:.0f}% (сейчас {pct:.1f}%).",
        )

    scores = compute_user_axis_scores(db, viewer_id)
    max_d = settings.discussion_system_axis_max_dist_from_center
    for slug in slugs:
        ax = axes_by_slug[slug]
        if ax.id not in scores:
            return (
                False,
                "Ответьте на вопросы теста по этой теме — тогда сможете участвовать в обсуждении.",
            )
        d = abs(float(scores[ax.id]) - 0.5)
        if d > max_d:
            return (
                False,
                "Системная тема рассчитана на участников со схожим профилем по этой оси; "
                "ваша позиция пока слишком далека от зоны обсуждения.",
            )
    return True, ""
