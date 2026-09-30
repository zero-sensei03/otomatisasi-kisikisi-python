"""create authentication

Revision ID: b608305cce9a
Revises: 8c7654ee0c5f
Create Date: 2026-09-30 11:29:50.612431

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b608305cce9a"
down_revision: Union[str, Sequence[str], None] = "8c7654ee0c5f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
