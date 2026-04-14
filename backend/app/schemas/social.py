from pydantic import BaseModel, Field


class LikeIn(BaseModel):
    to_user_id: int = Field(ge=1)


class MessageIn(BaseModel):
    body: str = Field(min_length=1, max_length=4000)
    reply_to_message_id: int | None = Field(None, ge=1)


class MessageAttachmentOut(BaseModel):
    original_name: str
    mime: str
    url: str


class MessageReplyPreview(BaseModel):
    id: int
    sender_id: int
    body_snippet: str


class MessageOut(BaseModel):
    id: int
    sender_id: int
    body: str
    created_at: str
    attachment: MessageAttachmentOut | None = None
    reply_to: MessageReplyPreview | None = None
    sender_display_name: str | None = None

    model_config = {"from_attributes": True}
