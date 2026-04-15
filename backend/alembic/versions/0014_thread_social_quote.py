"""thread social + quote/repost fields

Revision ID: 0014
Revises: 0013
Create Date: 2026-04-15
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0014"
down_revision: Union[str, None] = "0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)

    if insp.has_table("thread_posts"):
        cols = {c["name"] for c in insp.get_columns("thread_posts")}
        if "kind" not in cols:
            op.add_column(
                "thread_posts",
                sa.Column("kind", sa.String(length=16), nullable=False, server_default=sa.text("'post'")),
            )
        if "quote_post_id" not in cols:
            op.add_column(
                "thread_posts",
                sa.Column("quote_post_id", sa.Integer(), nullable=True),
            )
            op.create_foreign_key(
                "fk_thread_posts_quote_post",
                "thread_posts",
                "thread_posts",
                ["quote_post_id"],
                ["id"],
                ondelete="SET NULL",
            )
            op.create_index("ix_thread_posts_quote_post_id", "thread_posts", ["quote_post_id"])

    if not insp.has_table("thread_post_likes"):
        op.create_table(
            "thread_post_likes",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
            sa.Column("post_id", sa.Integer(), sa.ForeignKey("thread_posts.id", ondelete="CASCADE"), nullable=False),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        )
        op.create_index("ix_thread_post_likes_post_id", "thread_post_likes", ["post_id"])
        op.create_index("ix_thread_post_likes_user_id", "thread_post_likes", ["user_id"])
        op.create_index(
            "uq_thread_post_likes_post_user",
            "thread_post_likes",
            ["post_id", "user_id"],
            unique=True,
        )


def downgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)

    if insp.has_table("thread_post_likes"):
        op.drop_index("uq_thread_post_likes_post_user", table_name="thread_post_likes")
        op.drop_index("ix_thread_post_likes_user_id", table_name="thread_post_likes")
        op.drop_index("ix_thread_post_likes_post_id", table_name="thread_post_likes")
        op.drop_table("thread_post_likes")

    if insp.has_table("thread_posts"):
        cols = {c["name"] for c in insp.get_columns("thread_posts")}
        if "quote_post_id" in cols:
            try:
                op.drop_constraint("fk_thread_posts_quote_post", "thread_posts", type_="foreignkey")
            except Exception:
                pass
            try:
                op.drop_index("ix_thread_posts_quote_post_id", table_name="thread_posts")
            except Exception:
                pass
            op.drop_column("thread_posts", "quote_post_id")
        if "kind" in cols:
            op.drop_column("thread_posts", "kind")

