from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class GroupRoom(Base):
    __tablename__ = "group_rooms"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    weekly_theme: Mapped[str] = mapped_column(String(500), default="")
    daily_prompt: Mapped[str] = mapped_column(String(500), default="")
    daily_prompt_for: Mapped[date | None] = mapped_column(Date(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    members = relationship(
        "GroupRoomMember",
        back_populates="room",
        cascade="all, delete-orphan",
    )
    messages = relationship(
        "GroupMessage",
        back_populates="room",
        cascade="all, delete-orphan",
    )


class GroupRoomMember(Base):
    __tablename__ = "group_room_members"
    __table_args__ = (UniqueConstraint("room_id", "user_id", name="uq_group_room_member_user"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    room_id: Mapped[int] = mapped_column(ForeignKey("group_rooms.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    left_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    muted: Mapped[bool] = mapped_column(Boolean, default=False)

    room = relationship("GroupRoom", back_populates="members")


class GroupMessage(Base):
    __tablename__ = "group_messages"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    room_id: Mapped[int] = mapped_column(ForeignKey("group_rooms.id", ondelete="CASCADE"), index=True)
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    body: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    reply_to_message_id: Mapped[int | None] = mapped_column(
        ForeignKey("group_messages.id", ondelete="SET NULL"), nullable=True, index=True
    )

    room = relationship("GroupRoom", back_populates="messages")
    reply_parent = relationship(
        "GroupMessage",
        remote_side="GroupMessage.id",
        foreign_keys=[reply_to_message_id],
    )


class GroupMessageReport(Base):
    __tablename__ = "group_message_reports"
    __table_args__ = (
        UniqueConstraint("message_id", "reporter_id", name="uq_group_report_once"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    message_id: Mapped[int] = mapped_column(ForeignKey("group_messages.id", ondelete="CASCADE"), index=True)
    reporter_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    reason: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
