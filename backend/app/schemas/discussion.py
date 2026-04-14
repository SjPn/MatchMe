from pydantic import BaseModel, Field


class DiscussionPostCreate(BaseModel):
    title: str = Field(min_length=1, max_length=220)
    body: str = Field(min_length=1, max_length=8000)
    theme_axis_slugs: list[str] = Field(min_length=1, max_length=8)


class DiscussionPostOut(BaseModel):
    id: int
    title: str
    body: str
    theme_axis_slugs: list[str]
    theme_axes: list[dict] = Field(default_factory=list)  # {slug, name}
    author_id: int | None
    author_display_name: str | None
    is_system: bool
    image_url: str | None = None
    comment_count: int = 0
    created_at: str


class DiscussionPostListOut(BaseModel):
    id: int
    title: str
    body_preview: str
    theme_axis_slugs: list[str]
    theme_axes: list[dict] = Field(default_factory=list)
    author_id: int | None
    author_display_name: str | None
    is_system: bool
    image_url: str | None = None
    comment_count: int = 0
    created_at: str


class DiscussionCommentCreate(BaseModel):
    body: str = Field(min_length=1, max_length=4000)
    reply_to_comment_id: int | None = None


class CommentReplyPreview(BaseModel):
    id: int
    user_id: int
    display_name: str
    body_snippet: str


class DiscussionCommentOut(BaseModel):
    id: int
    user_id: int
    display_name: str
    body: str
    reply_to_comment_id: int | None = None
    reply_to: CommentReplyPreview | None = None
    created_at: str


class CommentPermissionOut(BaseModel):
    can_comment: bool
    reason: str = ""
