from pydantic import BaseModel, Field


class GroupJoinOut(BaseModel):
    status: str
    room_id: int | None = None
    message: str | None = None
    eligible_peers: int | None = None
    min_members: int | None = None
    reason: str | None = None


class GroupMemberOut(BaseModel):
    user_id: int
    display_name: str


class GroupRoomDetailOut(BaseModel):
    id: int
    title: str
    slug: str
    weekly_theme: str
    daily_prompt: str
    members: list[GroupMemberOut]
    shared_traits: list[str] = Field(default_factory=list)
    community_rules: list[str]
    privacy_notice: str
    platonic_mission: str = ""
    cohort_size_note: str = ""
    you_muted: bool


class GroupReportIn(BaseModel):
    reason: str = Field(min_length=1, max_length=500)


class GroupMuteIn(BaseModel):
    muted: bool
