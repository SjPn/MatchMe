"""initial schema

Revision ID: 0001
Revises:
Create Date: 2025-04-13

"""

from typing import Sequence, Union

from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from app.config import settings
    from app.database import Base, create_db_engine

    eng = create_db_engine(settings.database_url)
    Base.metadata.create_all(bind=eng)


def downgrade() -> None:
    from app.config import settings
    from app.database import Base, create_db_engine

    eng = create_db_engine(settings.database_url)
    Base.metadata.drop_all(bind=eng)
