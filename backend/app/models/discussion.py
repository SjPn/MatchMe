"""Тематические посты и комментарии (лента обсуждений по осям ценностей)."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class DiscussionPost(Base):
    __tablename__ = "discussion_posts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    author_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    title: Mapped[str] = mapped_column(String(220))
    body: Mapped[str] = mapped_column(Text)
    # JSON-массив slug осей (из question_axes), задающих тему
    theme_axis_slugs_json: Mapped[str] = mapped_column(Text, default="[]")
    image_storage_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    author = relationship("User", foreign_keys=[author_id])
    comments = relationship(
        "DiscussionComment",
        back_populates="post",
        cascade="all, delete-orphan",
    )


class DiscussionComment(Base):
    __tablename__ = "discussion_comments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("discussion_posts.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    body: Mapped[str] = mapped_column(Text)
    reply_to_comment_id: Mapped[int | None] = mapped_column(
        ForeignKey("discussion_comments.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    post = relationship("DiscussionPost", back_populates="comments")
    user = relationship("User", foreign_keys=[user_id])
