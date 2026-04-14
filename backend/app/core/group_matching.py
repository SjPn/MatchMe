"""Подбор когорты для групповых комнат: среднее и макс. расхождение по осям."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.group_icebreakers import pick_daily_prompt, pick_weekly_theme
from app.core.matching import compute_user_axis_scores_batch
from app.models.group_room import GroupMessage, GroupRoom, GroupRoomMember
from app.models.question import QuestionAxis
from app.models.user import User


def axis_divergence_stats_from_scores(
    scores_a: dict[int, float],
    scores_b: dict[int, float],
    axes: list[QuestionAxis],
) -> tuple[float, float, int]:
    """Среднее и максимальное |Δ| по осям, где у обоих есть счёт; число осей."""
    diffs: list[float] = []
    for ax in axes:
        if ax.id not in scores_a or ax.id not in scores_b:
            continue
        diffs.append(abs(scores_a[ax.id] - scores_b[ax.id]))
    if not diffs:
        return 1.0, 1.0, 0
    return sum(diffs) / len(diffs), max(diffs), len(diffs)


def axis_divergence_stats(
    db: Session, user_a: int, user_b: int
) -> tuple[float, float, int]:
    axes = db.query(QuestionAxis).all()
    scores = compute_user_axis_scores_batch(db, [user_a, user_b])
    return axis_divergence_stats_from_scores(scores[user_a], scores[user_b], axes)


def users_compatible_for_cohort_from_scores(
    scores_a: dict[int, float],
    scores_b: dict[int, float],
    axes: list[QuestionAxis],
) -> bool:
    mean_d, max_d, n = axis_divergence_stats_from_scores(scores_a, scores_b, axes)
    if n < 1:
        return False
    return mean_d <= settings.group_cohort_mean_divergence_max and max_d <= settings.group_cohort_axis_divergence_max


def users_compatible_for_cohort(db: Session, a: int, b: int) -> bool:
    axes = db.query(QuestionAxis).all()
    scores = compute_user_axis_scores_batch(db, [a, b])
    return users_compatible_for_cohort_from_scores(scores[a], scores[b], axes)


def _eligible_user_ids(db: Session, user_id: int) -> list[int]:
    rows = db.scalars(
        select(User.id).where(
            User.id != user_id,
            User.onboarding_step == "test_completed",
        )
    ).all()
    return sorted([int(x) for x in rows])


def find_eligible_peers(db: Session, user_id: int) -> list[int]:
    eligible_ids = _eligible_user_ids(db, user_id)
    if not eligible_ids:
        return []
    axes = db.query(QuestionAxis).all()
    scores_by_uid = compute_user_axis_scores_batch(db, [user_id] + eligible_ids)
    sa = scores_by_uid[user_id]
    return [
        uid
        for uid in eligible_ids
        if users_compatible_for_cohort_from_scores(sa, scores_by_uid[uid], axes)
    ]


def _active_member_count(db: Session, room_id: int) -> int:
    return (
        db.query(func.count(GroupRoomMember.id))
        .filter(GroupRoomMember.room_id == room_id, GroupRoomMember.left_at.is_(None))
        .scalar()
        or 0
    )


def _active_member_ids(db: Session, room_id: int) -> list[int]:
    rows = db.scalars(
        select(GroupRoomMember.user_id).where(
            GroupRoomMember.room_id == room_id,
            GroupRoomMember.left_at.is_(None),
        )
    ).all()
    return [int(x) for x in rows]


def _user_can_join_room(
    db: Session,
    user_id: int,
    room_id: int,
    scores_by_uid: dict[int, dict[int, float]],
    axes: list[QuestionAxis],
) -> bool:
    mids = _active_member_ids(db, room_id)
    if len(mids) >= settings.group_max_members:
        return False
    if user_id in mids:
        return False
    sa = scores_by_uid[user_id]
    for m in mids:
        if not users_compatible_for_cohort_from_scores(sa, scores_by_uid[m], axes):
            return False
    return True


def _create_room_with_members(db: Session, user_ids: list[int]) -> GroupRoom:
    slug = f"cohort-{uuid.uuid4().hex[:10]}"
    title = f"Схожие взгляды · {len(user_ids)}"
    now = datetime.now(timezone.utc)
    today = now.date()
    room = GroupRoom(
        title=title,
        slug=slug,
        weekly_theme=pick_weekly_theme(),
        daily_prompt=pick_daily_prompt(),
        daily_prompt_for=today,
        created_at=now,
    )
    db.add(room)
    db.flush()
    for uid in user_ids:
        db.add(
            GroupRoomMember(
                room_id=room.id,
                user_id=uid,
                joined_at=now,
                left_at=None,
                muted=False,
            )
        )
    db.commit()
    db.refresh(room)
    return room


def assign_user_to_group(db: Session, user_id: int) -> tuple[GroupRoom | None, dict]:
    """
    Вернуть комнату и статус: already_member | joined | created | waiting.
    """
    user = db.get(User, user_id)
    if user is None:
        return None, {"status": "error", "detail": "user missing"}
    if user.onboarding_step != "test_completed":
        return None, {
            "status": "waiting",
            "reason": "onboarding_incomplete",
            "message": "Сначала завершите тест — так мы сможем подобрать когорту по осям.",
        }

    existing = db.scalars(
        select(GroupRoomMember)
        .where(GroupRoomMember.user_id == user_id, GroupRoomMember.left_at.is_(None))
        .limit(1)
    ).first()
    if existing:
        room = db.get(GroupRoom, existing.room_id)
        return room, {"status": "already_member", "room_id": room.id if room else None}

    eligible_ids = _eligible_user_ids(db, user_id)
    active_member_ids = [
        int(x)
        for x in db.scalars(
            select(GroupRoomMember.user_id)
            .where(GroupRoomMember.left_at.is_(None))
            .distinct()
        ).all()
    ]
    all_ids = list(dict.fromkeys([user_id] + eligible_ids + active_member_ids))
    all_axes = db.query(QuestionAxis).all()
    scores_by_uid = compute_user_axis_scores_batch(db, all_ids)

    sa = scores_by_uid[user_id]
    peers = [
        uid
        for uid in eligible_ids
        if users_compatible_for_cohort_from_scores(sa, scores_by_uid[uid], all_axes)
    ]

    # Присоединиться к существующей комнате с местом
    rooms = db.scalars(select(GroupRoom)).all()
    for room in sorted(rooms, key=lambda r: r.id):
        if not _user_can_join_room(db, user_id, room.id, scores_by_uid, all_axes):
            continue
        now = datetime.now(timezone.utc)
        db.add(
            GroupRoomMember(
                room_id=room.id,
                user_id=user_id,
                joined_at=now,
                left_at=None,
                muted=False,
            )
        )
        db.commit()
        db.refresh(room)
        return room, {"status": "joined"}

    # Собрать новую когорту (клика по совместимости), до лимита участников
    cluster = [user_id]
    for pid in peers:
        if len(cluster) >= settings.group_max_members:
            break
        sp = scores_by_uid[pid]
        if all(
            users_compatible_for_cohort_from_scores(sp, scores_by_uid[q], all_axes)
            for q in cluster
        ):
            cluster.append(pid)

    if len(cluster) < settings.group_min_members:
        return None, {
            "status": "waiting",
            "reason": "not_enough_peers",
            "message": (
                f"Пока мало людей с похожими ответами по осям "
                f"(нужно минимум {settings.group_min_members} человек в комнате). "
                "Загляните позже или зовите друзей пройти тест."
            ),
            "eligible_peers": len(peers),
            "min_members": settings.group_min_members,
        }

    room = _create_room_with_members(db, cluster)
    return room, {"status": "created", "members_added": len(cluster)}


def refresh_daily_prompt_if_needed(db: Session, room: GroupRoom) -> None:
    today = datetime.now(timezone.utc).date()
    if room.daily_prompt_for == today:
        return
    room.daily_prompt = pick_daily_prompt()
    room.daily_prompt_for = today
    db.add(room)
    db.commit()
    db.refresh(room)


def last_message_time(db: Session, room_id: int) -> datetime | None:
    t = db.scalar(
        select(func.max(GroupMessage.created_at)).where(GroupMessage.room_id == room_id)
    )
    return t


def inbox_group_rows(db: Session, user_id: int) -> list[dict]:
    """Элементы для объединённого списка «Диалоги»."""
    rows = db.execute(
        select(GroupRoom, GroupRoomMember)
        .join(GroupRoomMember, GroupRoom.id == GroupRoomMember.room_id)
        .where(GroupRoomMember.user_id == user_id, GroupRoomMember.left_at.is_(None))
    ).all()
    out: list[dict] = []
    for room, _m in rows:
        last_t = last_message_time(db, room.id) or room.created_at
        n = _active_member_count(db, room.id)
        out.append(
            {
                "kind": "group",
                "group_room_id": room.id,
                "title": room.title,
                "member_count": n,
                "last_activity_at": last_t.isoformat() if last_t else None,
            }
        )
    return out
