"""Persist cognitive level on generated questions and selected generation levels.

Revision ID: 95b3a1c4d8e2
Revises: 71d3a62c9f40
"""
import sqlalchemy as sa
from alembic import op

revision = "95b3a1c4d8e2"
down_revision = "71d3a62c9f40"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "generation_questions",
        sa.Column("cognitive_level", sa.String(length=2), nullable=False, server_default="C1"),
    )
    op.add_column(
        "generations",
        sa.Column(
            "cognitive_levels",
            sa.Text(),
            nullable=False,
            server_default='["C1","C2","C3","C4","C5","C6"]',
        ),
    )
    op.execute(
        """UPDATE generation_questions AS q
           SET cognitive_level = b.cognitive_level
           FROM generation_blueprints AS b
           WHERE b.question_id = q.id"""
    )


def downgrade() -> None:
    op.drop_column("generations", "cognitive_levels")
    op.drop_column("generation_questions", "cognitive_level")
