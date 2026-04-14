"""likert scale hints json

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-14

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    cols = {c["name"] for c in insp.get_columns("questions")}
    if "likert_hints_json" not in cols:
        op.add_column("questions", sa.Column("likert_hints_json", sa.Text(), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    cols = {c["name"] for c in insp.get_columns("questions")}
    if "likert_hints_json" in cols:
        op.drop_column("questions", "likert_hints_json")
