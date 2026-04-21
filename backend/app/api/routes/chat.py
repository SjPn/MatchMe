import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.config import settings
from app.core.group_matching import inbox_group_rows
from app.core.user_blocks import is_hidden_pair
from app.core.typing_store import other_users_typing, ping_typing
from app.database import get_db
from app.models.group_room import GroupMessage, GroupRoomReadState
from app.models.social import Conversation, ConversationReadState, Match, Message
from app.models.user import User
from app.schemas.social import MessageAttachmentOut, MessageIn, MessageOut, MessageReplyPreview

router = APIRouter(prefix="/conversations", tags=["chat"])

BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent.parent
UPLOAD_ROOT = BACKEND_ROOT / "uploads" / "chat"

_ALLOWED_EXT = frozenset(
    {".pdf", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".txt", ".zip", ".doc", ".docx", ".xlsx"}
)


def _conversation_for_user(db: Session, conversation_id: int, user_id: int) -> Conversation | None:
    conv = db.get(Conversation, conversation_id)
    if conv is None:
        return None
    m = conv.match
    if m is None:
        return None
    if user_id not in (m.user_low_id, m.user_high_id):
        return None
    other_id = m.user_high_id if m.user_low_id == user_id else m.user_low_id
    if is_hidden_pair(db, user_id, other_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Blocked")
    return conv


def _validate_reply_target(db: Session, conversation_id: int, reply_to_message_id: int | None) -> None:
    if reply_to_message_id is None:
        return
    parent = db.get(Message, reply_to_message_id)
    if parent is None or parent.conversation_id != conversation_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid reply target")


def _count_unread_direct(db: Session, viewer_id: int, conversation_id: int, last_read_message_id: int) -> int:
    n = db.scalar(
        select(func.count(Message.id)).where(
            Message.conversation_id == conversation_id,
            Message.sender_id != viewer_id,
            Message.id > last_read_message_id,
        )
    )
    return int(n or 0)


def _count_unread_group(db: Session, viewer_id: int, room_id: int, last_read_message_id: int) -> int:
    n = db.scalar(
        select(func.count(GroupMessage.id)).where(
            GroupMessage.room_id == room_id,
            GroupMessage.sender_id != viewer_id,
            GroupMessage.id > last_read_message_id,
        )
    )
    return int(n or 0)


def _attach_unread_to_conversation_list(db: Session, user_id: int, items: list[dict]) -> None:
    """Mutates each row: adds integer unread_count (from others, id > last_read)."""
    direct_rows = [x for x in items if x.get("kind") == "direct"]
    if direct_rows:
        cids = [int(x["conversation_id"]) for x in direct_rows]
        st = db.execute(
            select(ConversationReadState.conversation_id, ConversationReadState.last_read_message_id).where(
                ConversationReadState.user_id == user_id,
                ConversationReadState.conversation_id.in_(cids),
            )
        ).all()
        last_by = {int(c): int(l or 0) for c, l in st}
        for x in direct_rows:
            cid = int(x["conversation_id"])
            x["unread_count"] = _count_unread_direct(db, user_id, cid, last_by.get(cid, 0))

    group_rows = [x for x in items if x.get("kind") == "group"]
    if group_rows:
        rids = [int(x["group_room_id"]) for x in group_rows]
        st = db.execute(
            select(GroupRoomReadState.room_id, GroupRoomReadState.last_read_message_id).where(
                GroupRoomReadState.user_id == user_id,
                GroupRoomReadState.room_id.in_(rids),
            )
        ).all()
        last_by = {int(r): int(l or 0) for r, l in st}
        for x in group_rows:
            rid = int(x["group_room_id"])
            x["unread_count"] = _count_unread_group(db, user_id, rid, last_by.get(rid, 0))

    for x in items:
        x.setdefault("unread_count", 0)


def _message_to_out(db: Session, cid: int, m: Message) -> MessageOut:
    att: MessageAttachmentOut | None = None
    if m.attachment_storage_key:
        att = MessageAttachmentOut(
            original_name=m.attachment_original_name or "file",
            mime=m.attachment_mime or "application/octet-stream",
            url=f"/conversations/{cid}/messages/{m.id}/attachment",
        )
    reply_to: MessageReplyPreview | None = None
    if m.reply_to_message_id:
        parent = db.get(Message, m.reply_to_message_id)
        if parent:
            raw = (parent.body or "").strip()
            if raw:
                snippet = raw[:200]
            elif parent.attachment_original_name:
                snippet = f"📎 {parent.attachment_original_name}"[:200]
            else:
                snippet = "Вложение"
            reply_to = MessageReplyPreview(id=parent.id, sender_id=parent.sender_id, body_snippet=snippet)
    return MessageOut(
        id=m.id,
        sender_id=m.sender_id,
        body=m.body or "",
        created_at=m.created_at.isoformat(),
        attachment=att,
        reply_to=reply_to,
    )


@router.get("")
def list_conversations(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[dict]:
    rows = db.execute(
        select(Conversation, Match)
        .join(Match, Conversation.match_id == Match.id)
        .where(or_(Match.user_low_id == user.id, Match.user_high_id == user.id))
    ).all()
    conv_ids = [conv.id for conv, _ in rows]
    last_map: dict[int, datetime] = {}
    if conv_ids:
        times = db.execute(
            select(Message.conversation_id, func.max(Message.created_at)).where(
                Message.conversation_id.in_(conv_ids)
            ).group_by(Message.conversation_id)
        ).all()
        last_map = {cid: t for cid, t in times if t is not None}

    out = []
    for conv, match in rows:
        other_id = match.user_high_id if match.user_low_id == user.id else match.user_low_id
        if is_hidden_pair(db, user.id, other_id):
            continue
        other = db.get(User, other_id)
        last_msg_at = last_map.get(conv.id)
        last_activity = last_msg_at or match.created_at
        out.append(
            {
                "kind": "direct",
                "conversation_id": conv.id,
                "other_user_id": other_id,
                "other_display_name": other.display_name if other else "",
                "last_activity_at": last_activity.isoformat() if last_activity else None,
            }
        )
    out.extend(inbox_group_rows(db, user.id))
    out.sort(key=lambda x: x.get("last_activity_at") or "", reverse=True)
    _attach_unread_to_conversation_list(db, user.id, out)
    return out


@router.get("/unread-count")
def unread_count(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """
    Total unread messages counter for bottom nav badge.

    MVP approach: per-user last_read_message_id tracked for direct conversations and group rooms.
    """
    # Direct conversations where user participates
    rows = db.execute(
        select(Conversation.id, Match.user_low_id, Match.user_high_id)
        .join(Match, Conversation.match_id == Match.id)
        .where(or_(Match.user_low_id == user.id, Match.user_high_id == user.id))
    ).all()
    conv_ids = [int(r[0]) for r in rows]

    direct_unread = 0
    if conv_ids:
        states = db.execute(
            select(ConversationReadState.conversation_id, ConversationReadState.last_read_message_id).where(
                ConversationReadState.user_id == user.id,
                ConversationReadState.conversation_id.in_(conv_ids),
            )
        ).all()
        last_by_cid = {int(cid): int(last or 0) for cid, last in states}
        for cid in conv_ids:
            last = last_by_cid.get(cid, 0)
            direct_unread += _count_unread_direct(db, user.id, cid, last)

    group_rows = inbox_group_rows(db, user.id)
    room_ids = [int(x["group_room_id"]) for x in group_rows]
    group_unread = 0
    if room_ids:
        states = db.execute(
            select(GroupRoomReadState.room_id, GroupRoomReadState.last_read_message_id).where(
                GroupRoomReadState.user_id == user.id,
                GroupRoomReadState.room_id.in_(room_ids),
            )
        ).all()
        last_by_rid = {int(rid): int(last or 0) for rid, last in states}
        for rid in room_ids:
            last = last_by_rid.get(rid, 0)
            group_unread += _count_unread_group(db, user.id, rid, last)

    return {"direct": direct_unread, "group": group_unread, "total": direct_unread + group_unread}


@router.post("/{conversation_id}/read", status_code=204)
def mark_conversation_read(
    conversation_id: int,
    last_message_id: int = Query(..., ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    conv = _conversation_for_user(db, conversation_id, user.id)
    if conv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    st = db.scalar(
        select(ConversationReadState).where(
            ConversationReadState.conversation_id == conversation_id,
            ConversationReadState.user_id == user.id,
        )
    )
    now = datetime.now(timezone.utc)
    if st is None:
        st = ConversationReadState(
            conversation_id=conversation_id,
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


@router.get("/{conversation_id}/peer")
def get_conversation_peer(
    conversation_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    conv = _conversation_for_user(db, conversation_id, user.id)
    if conv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    m = conv.match
    assert m is not None
    other_id = m.user_high_id if m.user_low_id == user.id else m.user_low_id
    other = db.get(User, other_id)
    return {
        "other_user_id": other_id,
        "other_display_name": other.display_name if other else "",
    }


@router.get("/{conversation_id}/messages", response_model=list[MessageOut])
def list_messages(
    conversation_id: int,
    after_id: int | None = Query(None, description="Только сообщения с id > after_id (для опроса)"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[MessageOut]:
    conv = _conversation_for_user(db, conversation_id, user.id)
    if conv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    q = db.query(Message).filter(Message.conversation_id == conversation_id)
    if after_id is not None:
        q = q.filter(Message.id > after_id)
    msgs = q.order_by(Message.created_at.asc()).all()
    return [_message_to_out(db, conversation_id, m) for m in msgs]


@router.post("/{conversation_id}/messages", response_model=MessageOut, status_code=201)
def send_message(
    conversation_id: int,
    body: MessageIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> MessageOut:
    conv = _conversation_for_user(db, conversation_id, user.id)
    if conv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    _validate_reply_target(db, conversation_id, body.reply_to_message_id)
    msg = Message(
        conversation_id=conversation_id,
        sender_id=user.id,
        body=body.body.strip(),
        created_at=datetime.now(timezone.utc),
        reply_to_message_id=body.reply_to_message_id,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return _message_to_out(db, conversation_id, msg)


@router.post("/{conversation_id}/messages/upload", response_model=MessageOut, status_code=201)
async def send_message_with_file(
    conversation_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    file: UploadFile = File(...),
    caption: str = Form(""),
    reply_to_id: int | None = Form(None),
) -> MessageOut:
    conv = _conversation_for_user(db, conversation_id, user.id)
    if conv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    _validate_reply_target(db, conversation_id, reply_to_id)

    raw = await file.read()
    if len(raw) > settings.max_upload_bytes:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="File too large")

    orig_name = file.filename or "file"
    ext = Path(orig_name).suffix.lower()
    if ext not in _ALLOWED_EXT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type. Allowed: {', '.join(sorted(_ALLOWED_EXT))}",
        )

    safe_stem = re.sub(r"[^a-zA-Z0-9._-]+", "_", Path(orig_name).stem)[:80] or "file"
    stored = f"{uuid.uuid4().hex}_{safe_stem}{ext}"
    storage_key = f"{conversation_id}/{stored}"
    dest_dir = UPLOAD_ROOT / str(conversation_id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / stored
    dest_path.write_bytes(raw)

    mime = file.content_type or "application/octet-stream"
    msg = Message(
        conversation_id=conversation_id,
        sender_id=user.id,
        body=caption.strip(),
        created_at=datetime.now(timezone.utc),
        attachment_original_name=orig_name,
        attachment_mime=mime,
        attachment_storage_key=storage_key,
        reply_to_message_id=reply_to_id,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return _message_to_out(db, conversation_id, msg)


@router.get("/{conversation_id}/messages/{message_id}/attachment")
def download_attachment(
    conversation_id: int,
    message_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    conv = _conversation_for_user(db, conversation_id, user.id)
    if conv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    msg = db.get(Message, message_id)
    if msg is None or msg.conversation_id != conversation_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    if not msg.attachment_storage_key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No attachment")
    path = UPLOAD_ROOT / msg.attachment_storage_key
    if not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File missing")
    return FileResponse(
        path,
        media_type=msg.attachment_mime or "application/octet-stream",
        filename=msg.attachment_original_name or "download",
    )


@router.post("/{conversation_id}/typing", status_code=204)
def post_typing(
    conversation_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    conv = _conversation_for_user(db, conversation_id, user.id)
    if conv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    ping_typing(conversation_id, user.id)
    return Response(status_code=204)


@router.get("/{conversation_id}/typing")
def get_typing(
    conversation_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, list[int]]:
    conv = _conversation_for_user(db, conversation_id, user.id)
    if conv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return {"typing_user_ids": other_users_typing(conversation_id, user.id)}
