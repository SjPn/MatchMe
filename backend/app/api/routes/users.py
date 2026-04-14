from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.user_blocks import is_hidden_pair
from app.database import get_db
from app.models.user import User
from app.schemas.user import UserPublicOut

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/{user_id}", response_model=UserPublicOut)
def get_user_public(
    user_id: int,
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
) -> UserPublicOut:
    target = me if user_id == me.id else db.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if user_id != me.id and is_hidden_pair(db, me.id, user_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Blocked")
    return UserPublicOut(
        id=target.id,
        display_name=target.display_name,
        avatar_url=target.avatar_url,
        about_me=target.about_me,
        identity_verified=target.identity_verified,
        answers_hidden_from_others=True,
    )

