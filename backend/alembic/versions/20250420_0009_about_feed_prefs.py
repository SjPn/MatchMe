"""about_me and feed_preferences_json on users

Revision ID: 0009
Revises: 0008
Create Date: 2026-04-20

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    if not insp.has_table("users"):
        return
    cols = {c["name"] for c in insp.get_columns("users")}
    if "about_me" not in cols:
        op.add_column("users", sa.Column("about_me", sa.Text(), nullable=True))
    if "feed_preferences_json" not in cols:
        op.add_column("users", sa.Column("feed_preferences_json", sa.Text(), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    if not insp.has_table("users"):
        return
    cols = {c["name"] for c in insp.get_columns("users")}
    if "feed_preferences_json" in cols:
        op.drop_column("users", "feed_preferences_json")
    if "about_me" in cols:
        op.drop_column("users", "about_me")
