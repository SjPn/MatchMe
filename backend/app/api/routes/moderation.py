from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.user_blocks import is_hidden_pair
from app.database import get_db
from app.models.moderation import UserBlock, UserReport
from app.models.user import User
from app.schemas.moderation import UserReportIn

router = APIRouter(tags=["moderation"])


@router.post("/users/{target_id}/block", status_code=204)
def block_user(
    target_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    if target_id == user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot block yourself")
    target = db.get(User, target_id)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if is_hidden_pair(db, user.id, target_id):
        return Response(status_code=204)
    db.add(
        UserBlock(
            blocker_id=user.id,
            blocked_id=target_id,
            created_at=datetime.now(timezone.utc),
        )
    )
    db.commit()
    return Response(status_code=204)


@router.delete("/users/{target_id}/block", status_code=204)
def unblock_user(
    target_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    row = db.scalars(
        select(UserBlock).where(UserBlock.blocker_id == user.id, UserBlock.blocked_id == target_id)
    ).first()
    if row:
        db.delete(row)
        db.commit()
    return Response(status_code=204)


@router.post("/users/{target_id}/report", status_code=204)
def report_user(
    target_id: int,
    body: UserReportIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    if target_id == user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid target")
    target = db.get(User, target_id)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    existing = db.scalars(
        select(UserReport).where(
            UserReport.reporter_id == user.id, UserReport.reported_id == target_id
        )
    ).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Already reported")
    db.add(
        UserReport(
            reporter_id=user.id,
            reported_id=target_id,
            reason=body.reason.strip()[:500],
            created_at=datetime.now(timezone.utc),
        )
    )
    db.commit()
    return Response(status_code=204)


@router.get("/me/blocked-ids")
def list_blocked_ids(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, list[int]]:
    """Кого я заблокировал (для настроек UI)."""
    rows = db.execute(select(UserBlock.blocked_id).where(UserBlock.blocker_id == user.id)).all()
    return {"blocked_user_ids": [int(r[0]) for r in rows]}
