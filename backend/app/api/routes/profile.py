from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.axis_language import AXIS_POLES, mind_profile_lines
from app.core.feed_preferences import (
    parse_feed_preferences_json,
    serialize_feed_preferences,
    validate_prefs_against_db,
)
from app.core.matching import compute_user_axis_scores
from app.database import get_db
from app.models.answer import Answer
from app.models.question import Question
from app.models.question import QuestionAxis
from app.models.user import User
from app.schemas.auth import UserOut
from app.schemas.profile import (
    AxisOptionOut,
    FeedPreferencesBody,
    FeedPreferencesOut,
    MePatch,
    ProfileAxisSummaryOut,
    ProfilePrivacyOut,
    ProfileSummaryOut,
)

router = APIRouter(prefix="/me", tags=["me"])

VERIFY_ROOT = Path(__file__).resolve().parent.parent.parent.parent / "uploads" / "verify"
_ALLOWED_VERIFY_EXT = frozenset({".jpg", ".jpeg", ".png", ".webp"})
_MAX_VERIFY_BYTES = 5 * 1024 * 1024


def _lean_label(score_0_1: float, left: str, right: str) -> str:
    if score_0_1 <= 0.40:
        return f"скорее {left.lower()}"
    if score_0_1 >= 0.60:
        return f"скорее {right.lower()}"
    return "скорее нейтрально"


@router.get("/summary", response_model=ProfileSummaryOut)
def profile_summary(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ProfileSummaryOut:
    """Оси, завершённость, бейджи, короткая карточка «как я думаю» (контракт с экраном /summary)."""
    scores = compute_user_axis_scores(db, user.id)
    axes = {a.id: a for a in db.query(QuestionAxis).all()}
    axis_rows: list[ProfileAxisSummaryOut] = []
    for i in sorted(scores.keys()):
        if i not in axes:
            continue
        ax = axes[i]
        score = float(scores.get(i, 0.5))
        left, right = AXIS_POLES.get(ax.slug, ("Левый полюс", "Правый полюс"))
        axis_rows.append(
            ProfileAxisSummaryOut(
                slug=ax.slug,
                name=ax.name,
                score=round(score, 2),
                left_label=left,
                right_label=right,
                lean=_lean_label(score, left, right),
            )
        )
    total_q = db.query(Question).filter(Question.pack == "onboarding").count()
    answered = (
        db.query(Answer)
        .join(Question, Answer.question_id == Question.id)
        .filter(Answer.user_id == user.id, Question.pack == "onboarding")
        .count()
    )
    completion = round(100.0 * answered / total_q, 1) if total_q else 0.0

    plus_total = db.query(Question).filter(Question.pack == "onboarding_plus").count()
    plus_answered = (
        db.query(Answer)
        .join(Question, Answer.question_id == Question.id)
        .filter(Answer.user_id == user.id, Question.pack == "onboarding_plus")
        .count()
    )

    badges: list[str] = []
    if completion >= 80.0:
        badges.append("transparent_axes")
    about = (user.about_me or "").strip()
    if len(about) >= 12:
        badges.append("about_me")

    mind_lines = mind_profile_lines(scores, axes, limit=4)

    return ProfileSummaryOut(
        display_name=user.display_name or "",
        onboarding_step=user.onboarding_step or "",
        completion_percent=float(completion),
        onboarding_plus_total=int(plus_total),
        onboarding_plus_answered=int(plus_answered),
        axes=axis_rows,
        badges=badges,
        mind_lines=mind_lines,
        about_me=user.about_me,
        privacy=ProfilePrivacyOut(
            answers_visible_to_others=False,
            others_see_axis_summary_only=True,
            hint=(
                "Конкретные ответы на вопросы видите только вы; другим показывается "
                "сводка по осям и совпадение."
            ),
        ),
    )


@router.get("/feed-preferences", response_model=FeedPreferencesOut)
def get_feed_preferences(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> FeedPreferencesOut:
    raw_w, raw_s, raw_d = parse_feed_preferences_json(user.feed_preferences_json)
    w, s, d = validate_prefs_against_db(db, raw_w, raw_s, raw_d)
    axes = db.query(QuestionAxis).order_by(QuestionAxis.id).all()
    return FeedPreferencesOut(
        axis_weights=w,
        soft_priority_slugs=s,
        dealbreaker_slugs=d,
        available_axes=[AxisOptionOut(slug=a.slug, name=a.name) for a in axes],
    )


@router.put("/feed-preferences", response_model=FeedPreferencesOut)
def put_feed_preferences(
    body: FeedPreferencesBody,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> FeedPreferencesOut:
    w, s, d = validate_prefs_against_db(db, body.axis_weights, body.soft_priority_slugs, body.dealbreaker_slugs)
    user.feed_preferences_json = serialize_feed_preferences(w, s, d)
    db.add(user)
    db.commit()
    db.refresh(user)
    axes = db.query(QuestionAxis).order_by(QuestionAxis.id).all()
    return FeedPreferencesOut(
        axis_weights=w,
        soft_priority_slugs=s,
        dealbreaker_slugs=d,
        available_axes=[AxisOptionOut(slug=a.slug, name=a.name) for a in axes],
    )


@router.post("/verification-photo", response_model=UserOut)
async def upload_verification_photo(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> User:
    """Загрузка селфи для бейджа доверия (MVP: авто-подтверждение после успешной загрузки)."""
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in _ALLOWED_VERIFY_EXT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Разрешены изображения: JPG, PNG, WebP",
        )
    raw = await file.read()
    if len(raw) > _MAX_VERIFY_BYTES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Файл больше 5 МБ")
    VERIFY_ROOT.mkdir(parents=True, exist_ok=True)
    dest = VERIFY_ROOT / f"{user.id}{suffix}"
    dest.write_bytes(raw)
    user.identity_verified_at = datetime.now(timezone.utc)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.patch("/profile", response_model=UserOut)
def patch_profile(
    body: MePatch,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> User:
    patch = body.model_dump(exclude_unset=True)
    if "display_name" in patch and patch["display_name"] is not None:
        user.display_name = patch["display_name"]
    if "avatar_url" in patch:
        user.avatar_url = patch["avatar_url"]
    if "about_me" in patch:
        user.about_me = patch["about_me"]
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
