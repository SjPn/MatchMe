"""thread post topics (axes slugs)

Revision ID: 0015
Revises: 0014
Create Date: 2026-04-15
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0015"
down_revision: Union[str, None] = "0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    if insp.has_table("thread_post_topics"):
        return

    op.create_table(
        "thread_post_topics",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("post_id", sa.Integer(), sa.ForeignKey("thread_posts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("axis_slug", sa.String(length=80), nullable=False),
    )
    op.create_index("ix_thread_post_topics_post_id", "thread_post_topics", ["post_id"])
    op.create_index("ix_thread_post_topics_axis_slug", "thread_post_topics", ["axis_slug"])
    op.create_index(
        "uq_thread_post_topics_post_slug",
        "thread_post_topics",
        ["post_id", "axis_slug"],
        unique=True,
    )
    op.create_index(
        "ix_thread_post_topics_slug_post",
        "thread_post_topics",
        ["axis_slug", "post_id"],
        unique=False,
    )


def downgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    if not insp.has_table("thread_post_topics"):
        return
    op.drop_index("ix_thread_post_topics_slug_post", table_name="thread_post_topics")
    op.drop_index("uq_thread_post_topics_post_slug", table_name="thread_post_topics")
    op.drop_index("ix_thread_post_topics_axis_slug", table_name="thread_post_topics")
    op.drop_index("ix_thread_post_topics_post_id", table_name="thread_post_topics")
    op.drop_table("thread_post_topics")

