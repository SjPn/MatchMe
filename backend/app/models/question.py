from sqlalchemy import Boolean, Column, Float, ForeignKey, Integer, String, Table, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

question_axis_link = Table(
    "question_axis_link",
    Base.metadata,
    Column("question_id", ForeignKey("questions.id", ondelete="CASCADE"), primary_key=True),
    Column("axis_id", ForeignKey("question_axes.id", ondelete="CASCADE"), primary_key=True),
    Column("weight", Float, nullable=False, default=1.0),
)


class QuestionAxis(Base):
    __tablename__ = "question_axes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    pack: Mapped[str] = mapped_column(String(64), index=True)
    qtype: Mapped[str] = mapped_column(String(32))
    text: Mapped[str] = mapped_column(Text)
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    option_a: Mapped[str | None] = mapped_column(Text, nullable=True)
    option_b: Mapped[str | None] = mapped_column(Text, nullable=True)
    likert_min: Mapped[int] = mapped_column(Integer, default=1)
    likert_max: Mapped[int] = mapped_column(Integer, default=10)
    likert_left_label: Mapped[str | None] = mapped_column(Text, nullable=True)
    likert_right_label: Mapped[str | None] = mapped_column(Text, nullable=True)
    # bipolar: слева min на шкале UI; если True — левый край = likert_max (сильнее «левый» полюс в смысле вопроса)
    likert_bipolar_invert: Mapped[bool] = mapped_column(Boolean, default=False)
    # JSON-массив строк: индекс i = подсказка для value likert_min + i
    likert_hints_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    axes = relationship(
        "QuestionAxis",
        secondary=question_axis_link,
        backref="questions",
    )
