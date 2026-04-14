from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.config import settings
from app.database import get_db
from app.models.answer import Answer
from app.models.question import Question
from app.models.user import User
from app.schemas.question import AnswerBatchIn, AnswerItemIn

router = APIRouter(prefix="/answers", tags=["answers"])


def _dialect_insert():
    if settings.database_url.strip().lower().startswith("sqlite"):
        from sqlalchemy.dialects.sqlite import insert

        return insert
    from sqlalchemy.dialects.postgresql import insert

    return insert


@router.post("", status_code=204)
def save_answers(
    body: AnswerBatchIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    # Один question_id в теле — один раз (дубликаты в массиве).
    by_question: dict[int, AnswerItemIn] = {}
    for item in body.answers:
        by_question[item.question_id] = item

    Insert = _dialect_insert()
    now = datetime.now(timezone.utc)

    for item in by_question.values():
        q = db.get(Question, item.question_id)
        if q is None:
            continue
        ins = Insert(Answer).values(
            user_id=user.id,
            question_id=item.question_id,
            value_numeric=item.value_numeric,
            value_choice=item.value_choice,
            confidence=item.confidence,
            answered_at=now,
        )
        ins = ins.on_conflict_do_update(
            index_elements=[Answer.__table__.c.user_id, Answer.__table__.c.question_id],
            set_=dict(
                value_numeric=ins.excluded.value_numeric,
                value_choice=ins.excluded.value_choice,
                confidence=ins.excluded.confidence,
                answered_at=ins.excluded.answered_at,
            ),
        )
        db.execute(ins)

    db.commit()

    total_onboarding = db.query(Question).filter(Question.pack == "onboarding").count()
    answered = (
        db.query(Answer)
        .join(Question, Answer.question_id == Question.id)
        .filter(Answer.user_id == user.id, Question.pack == "onboarding")
        .count()
    )
    if total_onboarding > 0 and answered >= total_onboarding:
        user.onboarding_step = "test_completed"
        db.add(user)
        db.commit()
