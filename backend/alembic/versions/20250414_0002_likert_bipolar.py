"""likert bipolar labels

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-14

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 0001 создаёт схему через create_all() по текущим моделям — колонки уже могут быть.
    # batch_alter_table на SQLite давал CircularDependencyError; ADD COLUMN — только если нет колонки.
    conn = op.get_bind()
    insp = sa.inspect(conn)
    cols = {c["name"] for c in insp.get_columns("questions")}

    if "likert_left_label" not in cols:
        op.add_column("questions", sa.Column("likert_left_label", sa.Text(), nullable=True))
    if "likert_right_label" not in cols:
        op.add_column("questions", sa.Column("likert_right_label", sa.Text(), nullable=True))
    if "likert_bipolar_invert" not in cols:
        op.add_column(
            "questions",
            sa.Column(
                "likert_bipolar_invert",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
        )


def downgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    cols = {c["name"] for c in insp.get_columns("questions")}
    if "likert_bipolar_invert" in cols:
        op.drop_column("questions", "likert_bipolar_invert")
    if "likert_right_label" in cols:
        op.drop_column("questions", "likert_right_label")
    if "likert_left_label" in cols:
        op.drop_column("questions", "likert_left_label")
