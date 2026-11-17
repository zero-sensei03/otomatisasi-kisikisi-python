"""Persist generation lineage and AI processing duration.

Revision ID: b1e7a3c9d240
Revises: 7c2e91ab4f60
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "b1e7a3c9d240"
down_revision = "7c2e91ab4f60"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "generations",
        sa.Column("parent_generation_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_generations_parent_generation_id_generations",
        "generations",
        "generations",
        ["parent_generation_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_generations_parent_generation_id",
        "generations",
        ["parent_generation_id"],
    )
    op.add_column("generations", sa.Column("ai_duration_ms", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("generations", "ai_duration_ms")
    op.drop_index("ix_generations_parent_generation_id", table_name="generations")
    op.drop_constraint("fk_generations_parent_generation_id_generations", "generations", type_="foreignkey")
    op.drop_column("generations", "parent_generation_id")
