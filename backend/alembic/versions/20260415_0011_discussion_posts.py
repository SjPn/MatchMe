"""discussion_posts and discussion_comments

Revision ID: 0011
Revises: 0010
Create Date: 2026-04-15

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)

    if not insp.has_table("discussion_posts"):
        op.create_table(
            "discussion_posts",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("author_id", sa.Integer(), nullable=True),
            sa.Column("title", sa.String(length=220), nullable=False),
            sa.Column("body", sa.Text(), nullable=False),
            sa.Column("theme_axis_slugs_json", sa.Text(), nullable=False),
            sa.Column("image_storage_key", sa.String(length=512), nullable=True),
            sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.ForeignKeyConstraint(["author_id"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )

    if not insp.has_table("discussion_comments"):
        op.create_table(
            "discussion_comments",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("post_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("body", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["post_id"], ["discussion_posts.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )

    insp = sa.inspect(conn)
    if not insp.has_table("discussion_comments"):
        return
    idx_names = {ix["name"] for ix in insp.get_indexes("discussion_comments")}
    if "ix_discussion_comments_post_id" not in idx_names:
        op.create_index("ix_discussion_comments_post_id", "discussion_comments", ["post_id"])
    if "ix_discussion_comments_user_id" not in idx_names:
        op.create_index("ix_discussion_comments_user_id", "discussion_comments", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_discussion_comments_user_id", table_name="discussion_comments")
    op.drop_index("ix_discussion_comments_post_id", table_name="discussion_comments")
    op.drop_table("discussion_comments")
    op.drop_table("discussion_posts")
