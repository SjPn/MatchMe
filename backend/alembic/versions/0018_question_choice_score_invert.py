"""optional invert for binary/forced_choice scoring (a<->b -> 0/1)

Revision ID: 0018
Revises: 0017
Create Date: 2026-04-21
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0018"
down_revision: Union[str, None] = "0017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    cols = {c["name"] for c in insp.get_columns("questions")}
    if "choice_score_invert" not in cols:
        op.add_column(
            "questions",
            sa.Column(
                "choice_score_invert",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
        )


def downgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    cols = {c["name"] for c in insp.get_columns("questions")}
    if "choice_score_invert" in cols:
        op.drop_column("questions", "choice_score_invert")
