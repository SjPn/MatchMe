from pydantic import BaseModel, Field


class AxisBrief(BaseModel):
    slug: str
    name: str


class QuestionOut(BaseModel):
    id: int
    pack: str
    qtype: str
    text: str
    order_index: int
    option_a: str | None
    option_b: str | None
    likert_min: int
    likert_max: int
    likert_left_label: str | None = None
    likert_right_label: str | None = None
    likert_bipolar_invert: bool = False
    likert_scale_hints: list[str] | None = None
    axes: list[AxisBrief]

    model_config = {"from_attributes": True}


class AnswerItemIn(BaseModel):
    question_id: int
    value_numeric: float | None = None
    value_choice: str | None = Field(default=None, max_length=32)
    confidence: float | None = None


class AnswerBatchIn(BaseModel):
    answers: list[AnswerItemIn]
