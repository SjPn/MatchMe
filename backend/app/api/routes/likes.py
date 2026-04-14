from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.user_blocks import is_hidden_pair
from app.database import get_db
from app.models.social import Conversation, Like, Match
from app.models.user import User
from app.schemas.social import LikeIn

router = APIRouter(prefix="/likes", tags=["likes"])


def _ordered_pair(a: int, b: int) -> tuple[int, int]:
    return (a, b) if a < b else (b, a)


@router.post("", status_code=201)
def create_like(
    body: LikeIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    if body.to_user_id == user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid target")
    target = db.get(User, body.to_user_id)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if is_hidden_pair(db, user.id, body.to_user_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Blocked")

    existing = db.scalar(
        select(Like).where(Like.from_user_id == user.id, Like.to_user_id == body.to_user_id)
    )
    if existing is None:
        db.add(Like(from_user_id=user.id, to_user_id=body.to_user_id))
        db.commit()

    reverse = db.scalar(
        select(Like).where(Like.from_user_id == body.to_user_id, Like.to_user_id == user.id)
    )
    mutual = reverse is not None
    match_id: int | None = None
    conversation_id: int | None = None
    if mutual:
        low, high = _ordered_pair(user.id, body.to_user_id)
        match_row = db.scalar(select(Match).where(Match.user_low_id == low, Match.user_high_id == high))
        if match_row is None:
            match_row = Match(user_low_id=low, user_high_id=high)
            db.add(match_row)
            db.flush()
            db.add(Conversation(match_id=match_row.id))
            db.commit()
            db.refresh(match_row)
        match_id = match_row.id
        conv = db.scalar(select(Conversation).where(Conversation.match_id == match_id))
        conversation_id = conv.id if conv else None
    return {"mutual": mutual, "match_id": match_id, "conversation_id": conversation_id}


@router.get("/inbox")
def likes_inbox(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """
    Кто лайкнул меня, но я ещё не лайкнул(а) в ответ (и нет блокировок).
    """
    ids = [int(x) for x in db.scalars(select(Like.from_user_id).where(Like.to_user_id == user.id)).all()]
    out: list[dict] = []
    for from_id in ids:
        if from_id == user.id:
            continue
        if is_hidden_pair(db, user.id, from_id):
            continue
        # уже взаимно или уже лайкнул обратно — не показываем
        back = db.scalar(select(Like).where(Like.from_user_id == user.id, Like.to_user_id == from_id))
        if back is not None:
            continue
        u = db.get(User, from_id)
        out.append(
            {
                "from_user_id": from_id,
                "from_display_name": u.display_name if u else "",
            }
        )
    return out
