"""Ensure likert_hints_json exists (repair if 0003 was stamped without DDL).

Revision ID: 0004
Revises: 0003
Create Date: 2026-04-15

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    cols = [c["name"] for c in insp.get_columns("questions")]
    if "likert_hints_json" not in cols:
        op.add_column("questions", sa.Column("likert_hints_json", sa.Text(), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    cols = [c["name"] for c in insp.get_columns("questions")]
    if "likert_hints_json" in cols:
        op.drop_column("questions", "likert_hints_json")
