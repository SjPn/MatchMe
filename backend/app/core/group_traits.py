"""Короткие пояснения «почему эта группа» для текущего пользователя."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.matching import compute_user_axis_scores_batch
from app.models.group_room import GroupRoomMember
from app.models.question import QuestionAxis


def group_shared_traits_for_user(
    db: Session,
    room_id: int,
    user_id: int,
    *,
    closeness: float = 0.19,
    limit: int = 5,
) -> list[str]:
    """
    Оси, где позиция пользователя близка к среднему по активным участникам комнаты.
    """
    uids = [
        int(x)
        for x in db.scalars(
            select(GroupRoomMember.user_id).where(
                GroupRoomMember.room_id == room_id,
                GroupRoomMember.left_at.is_(None),
            )
        ).all()
    ]
    if user_id not in uids or len(uids) < 2:
        return []

    axes = db.query(QuestionAxis).order_by(QuestionAxis.id).all()
    # Раньше: на каждую ось × каждого участника вызывали compute_user_axis_scores —
    # сотни запросов к ответам и таймаут/500 на GET /group-rooms/{id}.
    scores_by_uid = compute_user_axis_scores_batch(db, uids)
    centroid: dict[int, float] = {}
    for ax in axes:
        vals: list[float] = []
        for uid in uids:
            sc = scores_by_uid.get(uid) or {}
            if ax.id in sc:
                vals.append(sc[ax.id])
        if len(vals) >= 2:
            centroid[ax.id] = sum(vals) / len(vals)

    me = scores_by_uid.get(user_id) or {}
    traits: list[str] = []
    for ax in axes:
        if len(traits) >= limit:
            break
        if ax.id not in centroid or ax.id not in me:
            continue
        if abs(me[ax.id] - centroid[ax.id]) <= closeness:
            traits.append(f"«{ax.name}»: близко к среднему в этой комнате")
    return traits
