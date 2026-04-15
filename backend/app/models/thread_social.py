"""Social actions for threads (likes)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ThreadPostLike(Base):
    __tablename__ = "thread_post_likes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("thread_posts.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, index=True)

    post = relationship("ThreadPost", foreign_keys=[post_id])
    user = relationship("User", foreign_keys=[user_id])


Index("uq_thread_post_likes_post_user", ThreadPostLike.post_id, ThreadPostLike.user_id, unique=True)

