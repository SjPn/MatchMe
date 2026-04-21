"""chat unread states (direct + group)

Revision ID: 0017
Revises: 0016
Create Date: 2026-04-21
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0017"
down_revision: Union[str, None] = "0016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)

    if not insp.has_table("conversation_read_states"):
        op.create_table(
            "conversation_read_states",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column(
                "conversation_id",
                sa.Integer(),
                sa.ForeignKey("conversations.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "user_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("last_read_message_id", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.UniqueConstraint("conversation_id", "user_id", name="uq_conversation_read_state_pair"),
        )
        op.create_index(
            "ix_conversation_read_states_conversation_id",
            "conversation_read_states",
            ["conversation_id"],
        )
        op.create_index(
            "ix_conversation_read_states_user_id",
            "conversation_read_states",
            ["user_id"],
        )

    if not insp.has_table("group_room_read_states"):
        op.create_table(
            "group_room_read_states",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column(
                "room_id",
                sa.Integer(),
                sa.ForeignKey("group_rooms.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "user_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("last_read_message_id", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.UniqueConstraint("room_id", "user_id", name="uq_group_room_read_state_pair"),
        )
        op.create_index(
            "ix_group_room_read_states_room_id",
            "group_room_read_states",
            ["room_id"],
        )
        op.create_index(
            "ix_group_room_read_states_user_id",
            "group_room_read_states",
            ["user_id"],
        )


def downgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)

    if insp.has_table("conversation_read_states"):
        op.drop_index("ix_conversation_read_states_user_id", table_name="conversation_read_states")
        op.drop_index("ix_conversation_read_states_conversation_id", table_name="conversation_read_states")
        op.drop_table("conversation_read_states")

    if insp.has_table("group_room_read_states"):
        op.drop_index("ix_group_room_read_states_user_id", table_name="group_room_read_states")
        op.drop_index("ix_group_room_read_states_room_id", table_name="group_room_read_states")
        op.drop_table("group_room_read_states")

