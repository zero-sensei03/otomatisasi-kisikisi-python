"""create authentication

Revision ID: 8c7654ee0c5f
Revises:
Create Date: 2026-09-30 11:27:09.326221

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "8c7654ee0c5f"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
