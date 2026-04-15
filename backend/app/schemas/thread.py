from __future__ import annotations

from pydantic import BaseModel, Field


class ThreadAxisPolicy(BaseModel):
    slug: str
    target: float = Field(ge=0.0, le=1.0)
    max_dist: float = Field(ge=0.0, le=1.0)
    weight: float = Field(default=1.0, ge=0.0, le=10.0)


class ThreadValuePolicy(BaseModel):
    """
    MVP policy: viewer can reply if their axis scores are close to the targets.
    Targets are usually the author's axis scores at publish time.
    """

    mode: str = Field(default="axes")
    axes: list[ThreadAxisPolicy] = Field(default_factory=list)
    min_axes_matched: int = Field(default=1, ge=0, le=32)


class ThreadPostCreate(BaseModel):
    body: str = Field(min_length=1, max_length=8000)
    theme_axis_slugs: list[str] = Field(default_factory=list, max_length=8)
    # How strict should the thread be for replies.
    axis_max_dist: float = Field(default=0.22, ge=0.0, le=1.0)


class ThreadPostReplyCreate(BaseModel):
    body: str = Field(min_length=1, max_length=4000)


class ThreadPostQuoteCreate(BaseModel):
    body: str = Field(min_length=1, max_length=4000)


class ThreadMediaOut(BaseModel):
    id: int
    url: str
    mime: str


class ThreadAuthorOut(BaseModel):
    id: int | None
    display_name: str | None


class ThreadPostOut(BaseModel):
    id: int
    author: ThreadAuthorOut
    parent_id: int | None
    root_id: int
    kind: str = "post"
    quote_post_id: int | None = None
    quote_preview: "ThreadPostOut | None" = None
    body: str
    created_at: str
    is_system: bool
    visibility: str
    media: list[ThreadMediaOut] = Field(default_factory=list)
    reply_count: int = 0
    like_count: int = 0
    liked_by_me: bool = False
    repost_count: int = 0
    quote_count: int = 0
    topic_axis_slugs: list[str] = Field(default_factory=list)


class CursorPage(BaseModel):
    items: list[ThreadPostOut]
    next_cursor: str | None = None


class ThreadPostDetailOut(BaseModel):
    post: ThreadPostOut
    parents: list[ThreadPostOut] = Field(default_factory=list)
    replies: list[ThreadPostOut] = Field(default_factory=list)
    next_replies_cursor: str | None = None


class CanReplyOut(BaseModel):
    can_reply: bool
    reason: str = ""


ThreadPostOut.model_rebuild()

