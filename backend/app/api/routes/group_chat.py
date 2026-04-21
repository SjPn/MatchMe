from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.config import settings
from app.core.group_icebreakers import (
    COMMUNITY_RULES,
    PLATONIC_MISSION,
    PRIVACY_NOTICE,
    cohort_size_note,
)
from app.core.group_matching import assign_user_to_group, refresh_daily_prompt_if_needed
from app.core.group_rate_limit import allow_group_message
from app.core.group_traits import group_shared_traits_for_user
from app.database import get_db
from app.models.group_room import (
    GroupMessage,
    GroupMessageReport,
    GroupRoom,
    GroupRoomMember,
    GroupRoomReadState,
)
from app.models.user import User
from app.schemas.group_chat import GroupJoinOut, GroupMuteIn, GroupReportIn, GroupRoomDetailOut
from app.schemas.social import MessageIn, MessageOut, MessageReplyPreview

router = APIRouter(prefix="/group-rooms", tags=["group-chat"])


def _member(db: Session, room_id: int, user_id: int) -> GroupRoomMember | None:
    return db.scalars(
        select(GroupRoomMember).where(
            GroupRoomMember.room_id == room_id,
            GroupRoomMember.user_id == user_id,
            GroupRoomMember.left_at.is_(None),
        )
    ).first()


def _room_or_404(db: Session, room_id: int) -> GroupRoom:
    room = db.get(GroupRoom, room_id)
    if room is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room not found")
    return room


def _message_to_out(db: Session, room_id: int, m: GroupMessage) -> MessageOut:
    reply_to: MessageReplyPreview | None = None
    if m.reply_to_message_id:
        parent = db.get(GroupMessage, m.reply_to_message_id)
        if parent and parent.room_id == room_id:
            raw = (parent.body or "").strip()
            snippet = raw[:200] if raw else "Сообщение"
            reply_to = MessageReplyPreview(
                id=parent.id, sender_id=parent.sender_id, body_snippet=snippet
            )
    sender = db.get(User, m.sender_id)
    name = sender.display_name if sender else ""
    return MessageOut(
        id=m.id,
        sender_id=m.sender_id,
        body=m.body or "",
        created_at=m.created_at.isoformat(),
        attachment=None,
        reply_to=reply_to,
        sender_display_name=name,
    )


@router.post("/join", response_model=GroupJoinOut)
def join_group_cohort(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> GroupJoinOut:
    room, meta = assign_user_to_group(db, user.id)
    st = meta.get("status", "waiting")
    if st == "waiting":
        return GroupJoinOut(
            status="waiting",
            message=meta.get("message"),
            eligible_peers=meta.get("eligible_peers"),
            min_members=meta.get("min_members"),
            reason=meta.get("reason"),
        )
    if room is None:
        return GroupJoinOut(status="waiting", message=meta.get("message", "Нет комнаты"))
    return GroupJoinOut(status=st, room_id=room.id, message=meta.get("message"))


@router.get("/{room_id}", response_model=GroupRoomDetailOut)
def get_room(
    room_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> GroupRoomDetailOut:
    room = _room_or_404(db, room_id)
    mem = _member(db, room_id, user.id)
    if mem is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a member")
    refresh_daily_prompt_if_needed(db, room)

    rows = db.execute(
        select(User.id, User.display_name)
        .join(GroupRoomMember, GroupRoomMember.user_id == User.id)
        .where(GroupRoomMember.room_id == room_id, GroupRoomMember.left_at.is_(None))
    ).all()
    members = [{"user_id": int(r[0]), "display_name": r[1]} for r in rows]
    traits = group_shared_traits_for_user(db, room_id, user.id)

    return GroupRoomDetailOut(
        id=room.id,
        title=room.title,
        slug=room.slug,
        weekly_theme=room.weekly_theme,
        daily_prompt=room.daily_prompt,
        members=members,
        shared_traits=traits,
        community_rules=list(COMMUNITY_RULES),
        privacy_notice=PRIVACY_NOTICE,
        platonic_mission=PLATONIC_MISSION,
        cohort_size_note=cohort_size_note(settings.group_min_members, settings.group_max_members),
        you_muted=bool(mem.muted),
    )


@router.post("/{room_id}/read", status_code=204)
def mark_room_read(
    room_id: int,
    last_message_id: int = Query(..., ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    _room_or_404(db, room_id)
    if _member(db, room_id, user.id) is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a member")
    st = db.scalar(
        select(GroupRoomReadState).where(
            GroupRoomReadState.room_id == room_id,
            GroupRoomReadState.user_id == user.id,
        )
    )
    now = datetime.now(timezone.utc)
    if st is None:
        st = GroupRoomReadState(
            room_id=room_id,
            user_id=user.id,
            last_read_message_id=int(last_message_id),
            updated_at=now,
        )
        db.add(st)
    else:
        st.last_read_message_id = max(int(st.last_read_message_id or 0), int(last_message_id))
        st.updated_at = now
        db.add(st)
    db.commit()
    return Response(status_code=204)


@router.get("/{room_id}/messages", response_model=list[MessageOut])
def list_messages(
    room_id: int,
    after_id: int | None = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[MessageOut]:
    _room_or_404(db, room_id)
    if _member(db, room_id, user.id) is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a member")
    q = db.query(GroupMessage).filter(GroupMessage.room_id == room_id)
    if after_id is not None:
        q = q.filter(GroupMessage.id > after_id)
    msgs = q.order_by(GroupMessage.created_at.asc()).all()
    return [_message_to_out(db, room_id, m) for m in msgs]


def _validate_reply(db: Session, room_id: int, reply_id: int | None) -> None:
    if reply_id is None:
        return
    parent = db.get(GroupMessage, reply_id)
    if parent is None or parent.room_id != room_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid reply target")


@router.post("/{room_id}/messages", response_model=MessageOut, status_code=201)
def send_message(
    room_id: int,
    body: MessageIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> MessageOut:
    _room_or_404(db, room_id)
    mem = _member(db, room_id, user.id)
    if mem is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a member")
    if not allow_group_message(user.id, settings.group_messages_per_minute):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Слишком много сообщений. Подождите минуту.",
        )
    _validate_reply(db, room_id, body.reply_to_message_id)
    msg = GroupMessage(
        room_id=room_id,
        sender_id=user.id,
        body=body.body.strip(),
        created_at=datetime.now(timezone.utc),
        reply_to_message_id=body.reply_to_message_id,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return _message_to_out(db, room_id, msg)


@router.post("/{room_id}/messages/{message_id}/report", status_code=204)
def report_message(
    room_id: int,
    message_id: int,
    body: GroupReportIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    if _member(db, room_id, user.id) is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a member")
    msg = db.get(GroupMessage, message_id)
    if msg is None or msg.room_id != room_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
    existing = db.scalars(
        select(GroupMessageReport).where(
            GroupMessageReport.message_id == message_id,
            GroupMessageReport.reporter_id == user.id,
        )
    ).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Already reported")
    db.add(
        GroupMessageReport(
            message_id=message_id,
            reporter_id=user.id,
            reason=body.reason.strip()[:500],
            created_at=datetime.now(timezone.utc),
        )
    )
    db.commit()
    return Response(status_code=204)


@router.post("/{room_id}/leave", status_code=204)
def leave_room(
    room_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    mem = _member(db, room_id, user.id)
    if mem is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not a member")
    mem.left_at = datetime.now(timezone.utc)
    db.add(mem)
    db.commit()
    return Response(status_code=204)


@router.post("/{room_id}/mute", status_code=204)
def mute_room(
    room_id: int,
    body: GroupMuteIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    mem = _member(db, room_id, user.id)
    if mem is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not a member")
    mem.muted = body.muted
    db.add(mem)
    db.commit()
    return Response(status_code=204)
