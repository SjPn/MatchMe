"""Блокировки между пользователями: скрытие в ленте, матчах, чатах."""

from __future__ import annotations

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.models.moderation import UserBlock


def related_hidden_user_ids(db: Session, user_id: int) -> set[int]:
    """ID пользователей, с которыми не показываем контент (я заблокировал или меня)."""
    out: set[int] = set()
    rows = db.execute(
        select(UserBlock.blocked_id).where(UserBlock.blocker_id == user_id)
    ).all()
    out.update(int(r[0]) for r in rows)
    rows = db.execute(
        select(UserBlock.blocker_id).where(UserBlock.blocked_id == user_id)
    ).all()
    out.update(int(r[0]) for r in rows)
    return out


def is_hidden_pair(db: Session, a: int, b: int) -> bool:
    if a == b:
        return False
    row = db.scalars(
        select(UserBlock).where(
            or_(
                and_(UserBlock.blocker_id == a, UserBlock.blocked_id == b),
                and_(UserBlock.blocker_id == b, UserBlock.blocked_id == a),
            )
        )
    ).first()
    return row is not None
