from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    display_name: str = Field(min_length=1, max_length=100)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: int
    email: str
    display_name: str
    onboarding_step: str
    avatar_url: str | None = None
    about_me: str | None = None
    identity_verified: bool = False
    # Какой движок БД у этого процесса uvicorn (не приходит из ORM — подставляется в /auth/me)
    server_db_kind: str = "unknown"

    model_config = {"from_attributes": True}


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    sub: str | None = None
