"""message attachments + optional incremental fetch

Revision ID: 0005
Revises: 0004
Create Date: 2026-04-16

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    cols = {c["name"] for c in insp.get_columns("messages")}
    if "attachment_original_name" not in cols:
        op.add_column("messages", sa.Column("attachment_original_name", sa.String(512), nullable=True))
    if "attachment_mime" not in cols:
        op.add_column("messages", sa.Column("attachment_mime", sa.String(128), nullable=True))
    if "attachment_storage_key" not in cols:
        op.add_column("messages", sa.Column("attachment_storage_key", sa.String(512), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    cols = {c["name"] for c in insp.get_columns("messages")}
    if "attachment_storage_key" in cols:
        op.drop_column("messages", "attachment_storage_key")
    if "attachment_mime" in cols:
        op.drop_column("messages", "attachment_mime")
    if "attachment_original_name" in cols:
        op.drop_column("messages", "attachment_original_name")
