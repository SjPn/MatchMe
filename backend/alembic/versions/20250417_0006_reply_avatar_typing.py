"""reply_to message, user avatar_url

Revision ID: 0006
Revises: 0005
Create Date: 2026-04-17

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)

    ucols = {c["name"] for c in insp.get_columns("users")}
    if "avatar_url" not in ucols:
        op.add_column("users", sa.Column("avatar_url", sa.String(1024), nullable=True))

    mcols = {c["name"] for c in insp.get_columns("messages")}
    if "reply_to_message_id" not in mcols:
        op.add_column("messages", sa.Column("reply_to_message_id", sa.Integer(), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    mcols = {c["name"] for c in insp.get_columns("messages")}
    if "reply_to_message_id" in mcols:
        op.drop_column("messages", "reply_to_message_id")
    ucols = {c["name"] for c in insp.get_columns("users")}
    if "avatar_url" in ucols:
        op.drop_column("users", "avatar_url")
