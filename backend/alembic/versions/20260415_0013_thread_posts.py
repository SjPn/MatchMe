"""thread posts: unified posts + replies

Revision ID: 0013
Revises: 0012
Create Date: 2026-04-15
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    На «чистой» БД ревизия 0001 делает Base.metadata.create_all() по текущим моделям —
    таблицы thread_posts / thread_media могут уже существовать до этой миграции.
    Повторное CREATE приводит к DuplicateTable; пропускаем, если таблицы есть.
    """
    conn = op.get_bind()
    insp = sa.inspect(conn)

    if not insp.has_table("thread_posts"):
        op.create_table(
            "thread_posts",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
            sa.Column("author_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("parent_id", sa.Integer(), sa.ForeignKey("thread_posts.id", ondelete="SET NULL"), nullable=True),
            sa.Column("root_id", sa.Integer(), nullable=False),
            sa.Column("body", sa.Text(), nullable=False),
            sa.Column("value_policy_json", sa.Text(), nullable=False, server_default=sa.text("'{}'")),
            sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("visibility", sa.String(length=24), nullable=False, server_default=sa.text("'public'")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        )
        op.create_index("ix_thread_posts_author_id", "thread_posts", ["author_id"])
        op.create_index("ix_thread_posts_parent_id", "thread_posts", ["parent_id"])
        op.create_index("ix_thread_posts_root_id", "thread_posts", ["root_id"])
        op.create_index("ix_thread_posts_created_at", "thread_posts", ["created_at"])
        op.create_index(
            "ix_thread_posts_root_created",
            "thread_posts",
            ["root_id", "created_at", "id"],
            unique=False,
        )

    if not insp.has_table("thread_media"):
        op.create_table(
            "thread_media",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
            sa.Column("post_id", sa.Integer(), sa.ForeignKey("thread_posts.id", ondelete="CASCADE"), nullable=False),
            sa.Column("storage_key", sa.String(length=512), nullable=False),
            sa.Column("mime", sa.String(length=80), nullable=False, server_default=sa.text("'image/jpeg'")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        )
        op.create_index("ix_thread_media_post_id", "thread_media", ["post_id"])


def downgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)

    if insp.has_table("thread_media"):
        try:
            op.drop_index("ix_thread_media_post_id", table_name="thread_media")
        except Exception:
            pass
        op.drop_table("thread_media")

    if insp.has_table("thread_posts"):
        for ix in (
            "ix_thread_posts_root_created",
            "ix_thread_posts_created_at",
            "ix_thread_posts_root_id",
            "ix_thread_posts_parent_id",
            "ix_thread_posts_author_id",
        ):
            try:
                op.drop_index(ix, table_name="thread_posts")
            except Exception:
                pass
        op.drop_table("thread_posts")

