"""migrate discussion posts/comments into threads

Revision ID: 0016
Revises: 0015
Create Date: 2026-04-15
"""

from __future__ import annotations

import json
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.orm import Session

revision: str = "0016"
down_revision: Union[str, None] = "0015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _parse_slugs(raw: str) -> list[str]:
    try:
        data = json.loads(raw or "[]")
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    out: list[str] = []
    for x in data:
        if isinstance(x, str) and x.strip():
            s = x.strip()
            if s not in out:
                out.append(s)
    return out


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    if not insp.has_table("discussion_posts"):
        return
    if not insp.has_table("thread_posts") or not insp.has_table("thread_post_topics"):
        return

    # ORM helpers (we reuse existing scoring code to preserve "тематика поста" gating)
    from app.core.matching import compute_user_axis_scores
    from app.config import settings
    from app.models.question import QuestionAxis

    db = Session(bind=conn)
    try:
        axes = db.query(QuestionAxis).all()
        by_slug = {a.slug: a.id for a in axes}

        discussion_posts = db.execute(
            sa.text(
                "SELECT id, author_id, title, body, theme_axis_slugs_json, image_storage_key, is_system, created_at "
                "FROM discussion_posts ORDER BY id ASC"
            )
        ).all()

        # Map old discussion post id -> new thread post id
        post_map: dict[int, int] = {}

        for row in discussion_posts:
            dp_id = int(row.id)
            author_id = int(row.author_id) if row.author_id is not None else None
            title = (row.title or "").strip()
            body = (row.body or "").strip()
            slugs = _parse_slugs(row.theme_axis_slugs_json or "[]")
            slugs = [s for s in slugs if s in by_slug]
            is_system = bool(row.is_system)
            created_at = row.created_at

            merged_body = (title + "\n\n" + body).strip() if title else body
            if not merged_body:
                merged_body = "(пустой пост)"

            # Build value policy for replies.
            policy = {"mode": "axes", "axes": [], "min_axes_matched": 1}
            if slugs:
                if is_system or author_id is None:
                    max_dist = float(settings.discussion_system_axis_max_dist_from_center)
                    for slug in slugs:
                        policy["axes"].append({"slug": slug, "target": 0.5, "max_dist": max_dist, "weight": 1.0})
                else:
                    scores = compute_user_axis_scores(db, author_id)
                    # Conservative default for migrated content.
                    max_dist = 0.22
                    for slug in slugs:
                        axis_id = by_slug[slug]
                        if axis_id in scores:
                            policy["axes"].append(
                                {"slug": slug, "target": float(scores[axis_id]), "max_dist": max_dist, "weight": 1.0}
                            )
                policy["min_axes_matched"] = len(policy["axes"]) if policy["axes"] else 1

            # Insert root thread post.
            r = db.execute(
                sa.text(
                    "INSERT INTO thread_posts "
                    "(author_id, parent_id, root_id, kind, quote_post_id, body, value_policy_json, is_system, visibility, created_at) "
                    "VALUES (:author_id, NULL, 0, 'post', NULL, :body, :vp, :is_system, 'public', :created_at) "
                    "RETURNING id"
                ),
                {
                    "author_id": author_id,
                    "body": merged_body,
                    "vp": json.dumps(policy, ensure_ascii=False),
                    "is_system": is_system,
                    "created_at": created_at,
                },
            ).scalar_one()
            new_id = int(r)
            db.execute(sa.text("UPDATE thread_posts SET root_id = :id WHERE id = :id"), {"id": new_id})
            post_map[dp_id] = new_id

            # Topics
            for slug in slugs:
                db.execute(
                    sa.text(
                        "INSERT INTO thread_post_topics (post_id, axis_slug) VALUES (:pid, :slug) "
                        "ON CONFLICT DO NOTHING"
                    ),
                    {"pid": new_id, "slug": slug},
                )

        db.commit()

        if not insp.has_table("discussion_comments"):
            return

        # Map old discussion comment id -> new thread post id (reply node)
        comment_map: dict[int, int] = {}

        comments = db.execute(
            sa.text(
                "SELECT id, post_id, user_id, body, reply_to_comment_id, created_at "
                "FROM discussion_comments ORDER BY id ASC"
            )
        ).all()

        # First pass: create all comment posts (parent will be set after, for reply_to)
        for row in comments:
            dc_id = int(row.id)
            dp_id = int(row.post_id)
            root_id = post_map.get(dp_id)
            if root_id is None:
                continue
            user_id = int(row.user_id)
            body = (row.body or "").strip() or "(пустой комментарий)"
            created_at = row.created_at

            # Inherit value policy from root post.
            vp = db.execute(sa.text("SELECT value_policy_json FROM thread_posts WHERE id = :id"), {"id": root_id}).scalar()
            vp = vp or "{}"

            new_comment_id = db.execute(
                sa.text(
                    "INSERT INTO thread_posts "
                    "(author_id, parent_id, root_id, kind, quote_post_id, body, value_policy_json, is_system, visibility, created_at) "
                    "VALUES (:author_id, :parent_id, :root_id, 'post', NULL, :body, :vp, false, 'public', :created_at) "
                    "RETURNING id"
                ),
                {
                    "author_id": user_id,
                    "parent_id": root_id,  # temporary, may be adjusted
                    "root_id": root_id,
                    "body": body,
                    "vp": vp,
                    "created_at": created_at,
                },
            ).scalar_one()
            comment_map[dc_id] = int(new_comment_id)

        db.commit()

        # Second pass: set nested parent for reply_to_comment_id
        for row in comments:
            dc_id = int(row.id)
            reply_to = row.reply_to_comment_id
            if reply_to is None:
                continue
            child_id = comment_map.get(dc_id)
            parent_comment_id = comment_map.get(int(reply_to))
            if child_id and parent_comment_id:
                db.execute(
                    sa.text("UPDATE thread_posts SET parent_id = :pid WHERE id = :id"),
                    {"pid": parent_comment_id, "id": child_id},
                )

        db.commit()
    finally:
        db.close()


def downgrade() -> None:
    # Data migration is not reversed automatically.
    pass

