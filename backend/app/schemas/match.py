from pydantic import BaseModel, Field


class InsightItem(BaseModel):
    axis: str
    slug: str
    detail: str


class SharedTraitOut(BaseModel):
    axis: str
    slug: str
    summary: str
    strength: str = "medium"
    detail: str = ""


class ConversationPromptOut(BaseModel):
    axis: str
    slug: str
    prompt: str
    note: str = ""
    detail: str = ""


class KeywordHitOut(BaseModel):
    field: str
    snippet: str
    matched_terms: list[str] = Field(default_factory=list)


class FeedMetaOut(BaseModel):
    """Диагностика пустой ленты: лента не фильтрует по «похожести», только показывает других пользователей."""

    api_database: str = Field(description="sqlite | postgresql — движок у этого процесса API")
    other_users_total: int = Field(description="Пользователей в БД кроме текущего")
    visible_not_blocked: int = Field(description="Сколько из них не скрыты блокировкой 1:1")


class FeedCardOut(BaseModel):
    user_id: int
    display_name: str
    avatar_url: str | None = None
    about_me: str | None = None
    match_percent: float
    base_match_percent: float
    weighted_used: bool = False
    soft_penalty_notes: list[str] = Field(default_factory=list)
    agreements: list[InsightItem]
    differences: list[InsightItem]
    keyword_hit: KeywordHitOut | None = None
    their_mind_lines: list[str] = Field(default_factory=list)
    dealbreaker_hit: bool = False


class CompareOut(BaseModel):
    match_percent: float
    base_match_percent: float | None = None
    weighted_active: bool = False
    soft_penalty_notes: list[str] = Field(default_factory=list)
    agreements: list[InsightItem]
    differences: list[InsightItem]
    their_mind_lines: list[str] = Field(default_factory=list)
    your_mind_lines: list[str] = Field(default_factory=list)
    match_headline: str = ""
    shared_traits: list[SharedTraitOut] = Field(default_factory=list)
    conversation_prompts: list[ConversationPromptOut] = Field(default_factory=list)
    dealbreaker_hit: bool = False
