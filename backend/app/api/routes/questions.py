import json

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.question import Question
from app.models.user import User
from app.schemas.question import AxisBrief, QuestionOut

router = APIRouter(prefix="/questions", tags=["questions"])

_ALLOWED_QUESTION_PACKS = frozenset({"onboarding", "onboarding_plus"})


@router.get("", response_model=list[QuestionOut])
def list_questions(
    response: Response,
    pack: str = Query(default="onboarding"),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[QuestionOut]:
    if pack not in _ALLOWED_QUESTION_PACKS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Неизвестный набор вопросов")
    rows = (
        db.query(Question)
        .filter(Question.pack == pack)
        .order_by(Question.order_index, Question.id)
        .all()
    )
    out: list[QuestionOut] = []
    for q in rows:
        hints: list[str] | None = None
        if q.likert_hints_json:
            try:
                raw = json.loads(q.likert_hints_json)
                if isinstance(raw, list) and all(isinstance(x, str) for x in raw):
                    hints = raw
            except (json.JSONDecodeError, TypeError):
                hints = None
        out.append(
            QuestionOut(
                id=q.id,
                pack=q.pack,
                qtype=q.qtype,
                text=q.text,
                order_index=q.order_index,
                option_a=q.option_a,
                option_b=q.option_b,
                likert_min=q.likert_min,
                likert_max=q.likert_max,
                likert_left_label=q.likert_left_label,
                likert_right_label=q.likert_right_label,
                likert_bipolar_invert=bool(q.likert_bipolar_invert),
                likert_scale_hints=hints,
                axes=[AxisBrief(slug=a.slug, name=a.name) for a in q.axes],
            )
        )
    # Список вопросов не должен кэшироваться CDN/браузером — иначе после сида на проде виден старый набор.
    response.headers["Cache-Control"] = "private, no-store, max-age=0"
    return out
