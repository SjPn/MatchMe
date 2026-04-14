from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.config import database_engine_kind
from app.core.axis_language import mind_profile_lines, snippet_around_match
from app.core.feed_preferences import parse_feed_preferences_json, validate_prefs_against_db
from app.core.matching import (
    axis_pair_rows_from_scores,
    compare_users_from_axis_rows,
    compare_users_weighted_from_axis_rows,
    compute_user_axis_scores_batch,
)
from app.core.user_blocks import related_hidden_user_ids
from app.database import get_db
from app.models.question import QuestionAxis
from app.models.user import User
from app.schemas.match import FeedCardOut, FeedMetaOut, InsightItem, KeywordHitOut

router = APIRouter(prefix="/feed", tags=["feed"])


@router.get("/meta", response_model=FeedMetaOut)
def feed_meta(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> FeedMetaOut:
    """Сколько «других» пользователей видит API. Если `other_users_total=0`, сид/логин не в ту БД или в таблице только вы."""
    hidden = related_hidden_user_ids(db, user.id)
    other_ids = db.scalars(select(User.id).where(User.id != user.id)).all()
    not_blocked = sum(1 for oid in other_ids if oid not in hidden)
    return FeedMetaOut(
        api_database=database_engine_kind(),
        other_users_total=len(other_ids),
        visible_not_blocked=not_blocked,
    )


def _search_tokens(q: str) -> list[str]:
    return [t for t in q.lower().split() if len(t) >= 2]


def _about_me_matches(about_me: str | None, tokens: list[str]) -> bool:
    if not tokens:
        return True
    text = (about_me or "").lower()
    return all(t in text for t in tokens)


@router.get("", response_model=list[FeedCardOut])
def feed(
    limit: int = Query(default=20, ge=1, le=50),
    q: str | None = Query(None, max_length=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[FeedCardOut]:
    hidden = related_hidden_user_ids(db, user.id)
    others = db.scalars(select(User).where(User.id != user.id)).all()

    raw_w, raw_s, raw_d = parse_feed_preferences_json(user.feed_preferences_json)
    weights, soft_slugs, deal_slugs = validate_prefs_against_db(db, raw_w, raw_s, raw_d)
    weighted_mode = bool(weights) or bool(soft_slugs) or bool(deal_slugs)

    all_axes = db.query(QuestionAxis).all()
    axes_by_id = {a.id: a for a in all_axes}

    search_q = (q or "").strip()
    tokens = _search_tokens(search_q)

    visible = [u for u in others if u.id not in hidden]
    if tokens:
        visible = [u for u in visible if _about_me_matches(u.about_me, tokens)]

    batch_ids = [user.id] + [u.id for u in visible]
    scores_by_uid = compute_user_axis_scores_batch(db, batch_ids)
    scores_self = scores_by_uid[user.id]

    cards: list[FeedCardOut] = []
    for u in visible:
        db_hit = False
        rows = axis_pair_rows_from_scores(scores_self, scores_by_uid[u.id], all_axes)
        if weighted_mode:
            w_pct, base_pct, agree, diff, notes, _, _, _, db_hit = compare_users_weighted_from_axis_rows(
                rows, weights, soft_slugs, deal_slugs
            )
            pct = w_pct
            base = base_pct
            used_w = True
        else:
            pct, agree, diff, _, _, _ = compare_users_from_axis_rows(rows)
            base = pct
            used_w = False
            notes = []

        other_scores = scores_by_uid[u.id]
        t_lines = mind_profile_lines(other_scores, axes_by_id, limit=4)

        kw: KeywordHitOut | None = None
        if tokens and (u.about_me or "").strip():
            snip = snippet_around_match(u.about_me or "", tokens[0])
            if snip:
                kw = KeywordHitOut(field="about_me", snippet=snip, matched_terms=tokens)

        cards.append(
            FeedCardOut(
                user_id=u.id,
                display_name=u.display_name,
                avatar_url=u.avatar_url,
                about_me=u.about_me,
                match_percent=pct,
                base_match_percent=base,
                weighted_used=used_w,
                soft_penalty_notes=notes,
                agreements=[InsightItem(**a) for a in agree[:3]],
                differences=[InsightItem(**d) for d in diff[:1]],
                keyword_hit=kw,
                their_mind_lines=t_lines,
                dealbreaker_hit=db_hit,
            )
        )

    cards.sort(key=lambda c: c.match_percent, reverse=True)
    return cards[:limit]
