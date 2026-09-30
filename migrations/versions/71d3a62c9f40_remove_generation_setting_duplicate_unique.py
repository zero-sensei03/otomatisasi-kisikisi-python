"""Remove redundant generation setting key constraint.

Revision ID: 71d3a62c9f40
Revises: 4c0b8a2d7f31
"""
from alembic import op

revision = "71d3a62c9f40"
down_revision = "4c0b8a2d7f31"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        "generation_settings_key_key",
        "generation_settings",
        type_="unique",
    )


def downgrade() -> None:
    op.create_unique_constraint(
        "generation_settings_key_key",
        "generation_settings",
        ["key"],
    )
