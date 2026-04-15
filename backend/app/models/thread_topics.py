"""Topic tagging for thread posts (axes slugs)."""

from __future__ import annotations

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ThreadPostTopic(Base):
    __tablename__ = "thread_post_topics"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("thread_posts.id", ondelete="CASCADE"), index=True)
    axis_slug: Mapped[str] = mapped_column(String(80), index=True)

    post = relationship("ThreadPost", foreign_keys=[post_id])


Index("uq_thread_post_topics_post_slug", ThreadPostTopic.post_id, ThreadPostTopic.axis_slug, unique=True)
Index("ix_thread_post_topics_slug_post", ThreadPostTopic.axis_slug, ThreadPostTopic.post_id)

