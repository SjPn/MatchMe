from pydantic import BaseModel, Field


class UserPublicOut(BaseModel):
    id: int
    display_name: str
    avatar_url: str | None = None
    about_me: str | None = None
    identity_verified: bool = False
    conversation_id: int | None = Field(
        default=None,
        description="Личный чат 1:1 с текущим зрителем, если уже есть взаимный матч.",
    )
    answers_hidden_from_others: bool = Field(
        default=True,
        description="Сырые ответы на вопросы не передаются в API; видна только сводка по осям.",
    )

    model_config = {"from_attributes": True}

