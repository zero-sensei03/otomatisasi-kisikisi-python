"""Persist live generation progress.

Revision ID: 7c2e91ab4f60
Revises: 95b3a1c4d8e2
"""
import sqlalchemy as sa
from alembic import op

revision = "7c2e91ab4f60"
down_revision = "95b3a1c4d8e2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "generations",
        sa.Column("progress_json", sa.Text(), nullable=False, server_default="{}"),
    )


def downgrade() -> None:
    op.drop_column("generations", "progress_json")
