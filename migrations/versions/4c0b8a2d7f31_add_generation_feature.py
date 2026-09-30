"""Add structured AI generation feature.

Revision ID: 4c0b8a2d7f31
Revises: e09f1af5e0e7
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "4c0b8a2d7f31"
down_revision = "e09f1af5e0e7"
branch_labels = None
depends_on = None

material_type = postgresql.ENUM("TEXT", "FILE", name="generation_material_type", create_type=False)
status_type = postgresql.ENUM("PENDING", "PROCESSING", "COMPLETED", "FAILED", name="generation_status", create_type=False)
question_type = postgresql.ENUM("MULTIPLE_CHOICE", "SHORT_ANSWER", "ESSAY", name="generation_question_type", create_type=False)


def upgrade():
    bind = op.get_bind()
    material_type.create(bind, checkfirst=True)
    status_type.create(bind, checkfirst=True)
    question_type.create(bind, checkfirst=True)
    uuid = sa.UUID()
    timestamps = [sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False)]
    op.create_table("generation_settings", sa.Column("key", sa.String(100), nullable=False, unique=True), sa.Column("value", sa.String(255), nullable=False), sa.Column("description", sa.Text()), sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False), sa.Column("id", uuid, primary_key=True), *timestamps)
    op.create_index("ix_generation_settings_key", "generation_settings", ["key"], unique=True)
    op.create_table("generations", sa.Column("user_id", uuid, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False), sa.Column("title", sa.String(255), nullable=False), sa.Column("description", sa.Text()), sa.Column("subject", sa.String(150), nullable=False), sa.Column("class_name", sa.String(100), nullable=False), sa.Column("type_materi", material_type, nullable=False), sa.Column("material_text", sa.Text(), nullable=False), sa.Column("material_file_name", sa.String(255)), sa.Column("material_file_path", sa.String(512)), sa.Column("material_file_mime_type", sa.String(150)), sa.Column("status", status_type, server_default="PENDING", nullable=False), sa.Column("error_message", sa.Text()), sa.Column("summary", sa.Text()), sa.Column("total_multiple_choice", sa.Integer(), nullable=False), sa.Column("total_short_answer", sa.Integer(), nullable=False), sa.Column("total_essay", sa.Integer(), nullable=False), sa.Column("total_questions", sa.Integer(), nullable=False), sa.Column("ai_provider", sa.String(50)), sa.Column("ai_model", sa.String(150)), sa.Column("generation_cost", sa.Numeric(12, 4), server_default="0", nullable=False), sa.Column("started_at", sa.DateTime(timezone=True)), sa.Column("completed_at", sa.DateTime(timezone=True)), sa.Column("id", uuid, primary_key=True), *timestamps)
    op.create_index("ix_generations_user_id", "generations", ["user_id"])
    op.create_index("ix_generations_status", "generations", ["status"])
    op.create_table("generation_references", sa.Column("generation_id", uuid, sa.ForeignKey("generations.id", ondelete="CASCADE"), nullable=False), sa.Column("url", sa.Text(), nullable=False), sa.Column("title", sa.String(255)), sa.Column("extracted_content", sa.Text()), sa.Column("extraction_status", sa.String(30), nullable=False), sa.Column("error_message", sa.Text()), sa.Column("id", uuid, primary_key=True), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False))
    op.create_index("ix_generation_references_generation_id", "generation_references", ["generation_id"])
    op.create_table("generation_questions", sa.Column("generation_id", uuid, sa.ForeignKey("generations.id", ondelete="CASCADE"), nullable=False), sa.Column("number", sa.Integer(), nullable=False), sa.Column("type", question_type, nullable=False), sa.Column("question", sa.Text(), nullable=False), sa.Column("answer", sa.Text(), nullable=False), sa.Column("explanation", sa.Text(), nullable=False), sa.Column("id", uuid, primary_key=True), *timestamps, sa.UniqueConstraint("generation_id", "number", name="uq_generation_question_number"))
    op.create_index("ix_generation_questions_generation_id", "generation_questions", ["generation_id"])
    op.create_table("generation_question_options", sa.Column("question_id", uuid, sa.ForeignKey("generation_questions.id", ondelete="CASCADE"), nullable=False), sa.Column("label", sa.String(1), nullable=False), sa.Column("text", sa.Text(), nullable=False), sa.Column("is_correct", sa.Boolean(), nullable=False), sa.Column("id", uuid, primary_key=True))
    op.create_index("ix_generation_question_options_question_id", "generation_question_options", ["question_id"])
    op.create_table("generation_blueprints", sa.Column("generation_id", uuid, sa.ForeignKey("generations.id", ondelete="CASCADE"), nullable=False), sa.Column("question_id", uuid, sa.ForeignKey("generation_questions.id", ondelete="CASCADE"), nullable=False, unique=True), sa.Column("number", sa.Integer(), nullable=False), sa.Column("material_topic", sa.Text(), nullable=False), sa.Column("learning_objective", sa.Text(), nullable=False), sa.Column("indicator", sa.Text(), nullable=False), sa.Column("question_type", question_type, nullable=False), sa.Column("cognitive_level", sa.String(2), nullable=False), sa.Column("difficulty", sa.String(10), nullable=False), sa.Column("id", uuid, primary_key=True), sa.UniqueConstraint("generation_id", "number", name="uq_generation_blueprint_number"))
    op.create_index("ix_generation_blueprints_generation_id", "generation_blueprints", ["generation_id"])
    op.create_table("generation_usage", sa.Column("user_id", uuid, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False), sa.Column("generation_id", uuid, sa.ForeignKey("generations.id", ondelete="CASCADE"), nullable=False, unique=True), sa.Column("free_generation_used", sa.Integer(), nullable=False), sa.Column("cost", sa.Numeric(12, 4), nullable=False), sa.Column("id", uuid, primary_key=True), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False))
    op.create_index("ix_generation_usage_user_id", "generation_usage", ["user_id"])
    settings = sa.table("generation_settings", sa.column("id", uuid), sa.column("key", sa.String), sa.column("value", sa.String), sa.column("description", sa.Text), sa.column("is_active", sa.Boolean))
    values = [("generation.free_limit", "100", "Kuota generation gratis per pengguna."), ("generation.cost_per_generate", "0", "Biaya per generation."), ("generation.enabled", "true", "Aktifkan fitur generation."), ("generation.max_questions_per_generate", "50", "Jumlah maksimum soal per generation."), ("generation.max_material_characters", "30000", "Karakter materi maksimum."), ("generation.max_reference_characters", "5000", "Karakter tiap referensi maksimum.")]
    op.bulk_insert(settings, [dict(id=__import__("uuid").uuid4(), key=k, value=v, description=d, is_active=True) for k, v, d in values])


def downgrade():
    op.drop_index("ix_generation_usage_user_id", table_name="generation_usage")
    op.drop_table("generation_usage")
    op.drop_index("ix_generation_blueprints_generation_id", table_name="generation_blueprints")
    op.drop_table("generation_blueprints")
    op.drop_index("ix_generation_question_options_question_id", table_name="generation_question_options")
    op.drop_table("generation_question_options")
    op.drop_index("ix_generation_questions_generation_id", table_name="generation_questions")
    op.drop_table("generation_questions")
    op.drop_index("ix_generation_references_generation_id", table_name="generation_references")
    op.drop_table("generation_references")
    op.drop_index("ix_generations_status", table_name="generations")
    op.drop_index("ix_generations_user_id", table_name="generations")
    op.drop_table("generations")
    op.drop_index("ix_generation_settings_key", table_name="generation_settings")
    op.drop_table("generation_settings")
    question_type.drop(op.get_bind(), checkfirst=True)
    status_type.drop(op.get_bind(), checkfirst=True)
    material_type.drop(op.get_bind(), checkfirst=True)
