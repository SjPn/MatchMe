from __future__ import annotations

from pydantic import BaseModel, Field, field_validator, model_validator


class MePatch(BaseModel):
    display_name: str | None = Field(None, min_length=1, max_length=100)
    avatar_url: str | None = Field(None, max_length=2048)
    about_me: str | None = Field(None, max_length=4000)

    @field_validator("display_name", mode="before")
    @classmethod
    def strip_display(cls, v: object) -> object:
        if v is None or not isinstance(v, str):
            return v
        s = v.strip()
        return s or None

    @field_validator("avatar_url", mode="before")
    @classmethod
    def empty_avatar_to_none(cls, v: object) -> object:
        if v is None:
            return None
        if isinstance(v, str) and not v.strip():
            return None
        return v.strip() if isinstance(v, str) else v

    @field_validator("about_me", mode="before")
    @classmethod
    def strip_about(cls, v: object) -> object:
        if v is None:
            return None
        if not isinstance(v, str):
            return v
        s = v.strip()
        return s or None


class FeedPreferencesBody(BaseModel):
    axis_weights: dict[str, float] = Field(default_factory=dict)
    soft_priority_slugs: list[str] = Field(default_factory=list)
    dealbreaker_slugs: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def clamp_weights(self) -> FeedPreferencesBody:
        w: dict[str, float] = {}
        for k, v in self.axis_weights.items():
            if not isinstance(k, str):
                continue
            try:
                fv = float(v)
            except (TypeError, ValueError):
                continue
            w[k.strip()] = max(0.0, min(3.0, fv))
        self.axis_weights = w
        self.soft_priority_slugs = [str(x).strip() for x in self.soft_priority_slugs if str(x).strip()][
            :8
        ]
        self.dealbreaker_slugs = [str(x).strip() for x in self.dealbreaker_slugs if str(x).strip()][:5]
        return self


class AxisOptionOut(BaseModel):
    slug: str
    name: str


class FeedPreferencesOut(BaseModel):
    axis_weights: dict[str, float]
    soft_priority_slugs: list[str]
    dealbreaker_slugs: list[str] = Field(default_factory=list)
    available_axes: list[AxisOptionOut]


class ProfilePrivacyOut(BaseModel):
    answers_visible_to_others: bool
    others_see_axis_summary_only: bool
    hint: str


class ProfileAxisSummaryOut(BaseModel):
    slug: str
    name: str
    score: float
    left_label: str
    right_label: str
    lean: str


class ProfileSummaryOut(BaseModel):
    """Ответ GET /me/summary — сводка профиля и осей (согласован с экраном /summary)."""

    display_name: str
    onboarding_step: str
    completion_percent: float
    axes: list[ProfileAxisSummaryOut]
    badges: list[str] = Field(default_factory=list)
    mind_lines: list[str] = Field(default_factory=list)
    about_me: str | None = None
    privacy: ProfilePrivacyOut
