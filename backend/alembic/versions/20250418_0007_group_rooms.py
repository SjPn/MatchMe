"""group rooms, members, messages, reports

Revision ID: 0007
Revises: 0006
Create Date: 2026-04-18

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    if insp.has_table("group_rooms"):
        return

    op.create_table(
        "group_rooms",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("slug", sa.String(64), nullable=False),
        sa.Column("weekly_theme", sa.String(500), nullable=False, server_default=""),
        sa.Column("daily_prompt", sa.String(500), nullable=False, server_default=""),
        sa.Column("daily_prompt_for", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_group_rooms_slug", "group_rooms", ["slug"], unique=True)

    op.create_table(
        "group_room_members",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("room_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("left_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("muted", sa.Boolean(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["room_id"], ["group_rooms.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("room_id", "user_id", name="uq_group_room_member_user"),
    )
    op.create_index("ix_group_room_members_room_id", "group_room_members", ["room_id"])
    op.create_index("ix_group_room_members_user_id", "group_room_members", ["user_id"])

    op.create_table(
        "group_messages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("room_id", sa.Integer(), nullable=False),
        sa.Column("sender_id", sa.Integer(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reply_to_message_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["room_id"], ["group_rooms.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["sender_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reply_to_message_id"], ["group_messages.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_group_messages_room_id", "group_messages", ["room_id"])
    op.create_index("ix_group_messages_sender_id", "group_messages", ["sender_id"])
    op.create_index("ix_group_messages_reply_to", "group_messages", ["reply_to_message_id"])

    op.create_table(
        "group_message_reports",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("message_id", sa.Integer(), nullable=False),
        sa.Column("reporter_id", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["message_id"], ["group_messages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reporter_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("message_id", "reporter_id", name="uq_group_report_once"),
    )
    op.create_index("ix_group_message_reports_message_id", "group_message_reports", ["message_id"])


def downgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    if insp.has_table("group_message_reports"):
        op.drop_table("group_message_reports")
    if insp.has_table("group_messages"):
        op.drop_table("group_messages")
    if insp.has_table("group_room_members"):
        op.drop_table("group_room_members")
    if insp.has_table("group_rooms"):
        op.drop_table("group_rooms")
