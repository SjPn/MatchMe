"""Threads-like posts (single entity for root + replies) and media attachments."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ThreadPost(Base):
    """
    Single entity for root posts and replies (graph).

    - parent_id: immediate parent (reply target), NULL for root
    - root_id: root post id (self for root), speeds timeline & subtree queries
    """

    __tablename__ = "thread_posts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    author_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )

    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("thread_posts.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # NOTE: root_id can't be a FK with "self" set on insert easily (root points to itself).
    # We keep it as an integer and maintain it in application code.
    root_id: Mapped[int] = mapped_column(Integer, index=True)

    kind: Mapped[str] = mapped_column(String(16), default="post")  # post | repost | quote
    quote_post_id: Mapped[int | None] = mapped_column(
        ForeignKey("thread_posts.id", ondelete="SET NULL"), nullable=True, index=True
    )

    body: Mapped[str] = mapped_column(Text)
    value_policy_json: Mapped[str] = mapped_column(Text, default="{}")

    is_system: Mapped[bool] = mapped_column(Boolean, default=False)
    visibility: Mapped[str] = mapped_column(String(24), default="public")  # public | unlisted | deleted

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, index=True)

    author = relationship("User", foreign_keys=[author_id])
    parent = relationship("ThreadPost", remote_side=[id], foreign_keys=[parent_id])
    quoted_post = relationship("ThreadPost", remote_side=[id], foreign_keys=[quote_post_id])

    media = relationship(
        "ThreadMedia",
        back_populates="post",
        cascade="all, delete-orphan",
    )


Index("ix_thread_posts_root_created", ThreadPost.root_id, ThreadPost.created_at, ThreadPost.id)


class ThreadMedia(Base):
    __tablename__ = "thread_media"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("thread_posts.id", ondelete="CASCADE"), index=True)
    storage_key: Mapped[str] = mapped_column(String(512))
    mime: Mapped[str] = mapped_column(String(80), default="image/jpeg")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    post = relationship("ThreadPost", back_populates="media")
