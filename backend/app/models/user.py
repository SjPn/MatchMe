from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    hashed_password: Mapped[str | None] = mapped_column(String(255), nullable=True)
    display_name: Mapped[str] = mapped_column(String(100))
    avatar_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    about_me: Mapped[str | None] = mapped_column(Text, nullable=True)
    feed_preferences_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    identity_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    auth_provider: Mapped[str] = mapped_column(String(32), default="email")
    onboarding_step: Mapped[str] = mapped_column(String(64), default="registered")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    answers = relationship("Answer", back_populates="user", cascade="all, delete-orphan")
    likes_sent = relationship("Like", foreign_keys="Like.from_user_id", back_populates="from_user")
    likes_received = relationship("Like", foreign_keys="Like.to_user_id", back_populates="to_user")

    @property
    def identity_verified(self) -> bool:
        return self.identity_verified_at is not None
