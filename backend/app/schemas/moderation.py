from pydantic import BaseModel, Field


class UserReportIn(BaseModel):
    reason: str = Field(min_length=1, max_length=500)
