from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.axis_language import mind_profile_lines
from app.core.feed_preferences import parse_feed_preferences_json, validate_prefs_against_db
from app.core.matching import compare_users, compare_users_weighted, compute_user_axis_scores
from app.core.user_blocks import is_hidden_pair
from app.database import get_db
from app.models.question import QuestionAxis
from app.models.user import User
from app.schemas.match import (
    CompareOut,
    ConversationPromptOut,
    InsightItem,
    SharedTraitOut,
)

router = APIRouter(tags=["compare"])


@router.get("/users/{user_id}/compare", response_model=CompareOut)
def compare(
    user_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CompareOut:
    if user_id == user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot compare with yourself")
    other = db.get(User, user_id)
    if other is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if is_hidden_pair(db, user.id, user_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Blocked")

    axes_by_id = {a.id: a for a in db.query(QuestionAxis).all()}
    raw_w, raw_s, raw_d = parse_feed_preferences_json(user.feed_preferences_json)
    weights, soft_slugs, deal_slugs = validate_prefs_against_db(db, raw_w, raw_s, raw_d)
    weighted_active = bool(weights) or bool(soft_slugs) or bool(deal_slugs)

    viewer_scores = compute_user_axis_scores(db, user.id)
    other_scores = compute_user_axis_scores(db, user_id)
    your_lines = mind_profile_lines(viewer_scores, axes_by_id, limit=4)
    their_lines = mind_profile_lines(other_scores, axes_by_id, limit=4)

    if weighted_active:
        (
            w_pct,
            base_pct,
            agree,
            diff,
            notes,
            headline,
            traits,
            prompts,
            db_hit,
        ) = compare_users_weighted(db, user.id, user_id, weights, soft_slugs, deal_slugs)
        return CompareOut(
            match_percent=w_pct,
            base_match_percent=base_pct,
            weighted_active=True,
            soft_penalty_notes=notes,
            agreements=[InsightItem(**a) for a in agree],
            differences=[InsightItem(**d) for d in diff],
            their_mind_lines=their_lines,
            your_mind_lines=your_lines,
            match_headline=headline,
            shared_traits=[SharedTraitOut(**t) for t in traits],
            conversation_prompts=[ConversationPromptOut(**p) for p in prompts],
            dealbreaker_hit=db_hit,
        )

    pct, agree, diff, headline, traits, prompts = compare_users(db, user.id, user_id)
    return CompareOut(
        match_percent=pct,
        base_match_percent=None,
        weighted_active=False,
        soft_penalty_notes=[],
        agreements=[InsightItem(**a) for a in agree],
        differences=[InsightItem(**d) for d in diff],
        their_mind_lines=their_lines,
        your_mind_lines=your_lines,
        match_headline=headline,
        shared_traits=[SharedTraitOut(**t) for t in traits],
        conversation_prompts=[ConversationPromptOut(**p) for p in prompts],
        dealbreaker_hit=False,
    )
