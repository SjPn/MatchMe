"""reply_to_comment_id on discussion_comments

Revision ID: 0012
Revises: 0011
Create Date: 2026-04-16

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: Union[str, None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    if not insp.has_table("discussion_comments"):
        return
    cols = {c["name"] for c in insp.get_columns("discussion_comments")}
    if "reply_to_comment_id" in cols:
        return
    op.add_column(
        "discussion_comments",
        sa.Column("reply_to_comment_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_discussion_comments_reply",
        "discussion_comments",
        "discussion_comments",
        ["reply_to_comment_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    if not insp.has_table("discussion_comments"):
        return
    cols = {c["name"] for c in insp.get_columns("discussion_comments")}
    if "reply_to_comment_id" not in cols:
        return
    try:
        op.drop_constraint("fk_discussion_comments_reply", "discussion_comments", type_="foreignkey")
    except Exception:
        pass
    op.drop_column("discussion_comments", "reply_to_comment_id")
