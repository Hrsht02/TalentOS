"""Add assessment attempt persistence.

Revision ID: 0002_assessment_attempts
Revises: 0001_initial_schema
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002_assessment_attempts"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "assessment_attempts",
        sa.Column("assessment_invite_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("assessment_invites.id", ondelete="CASCADE"), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="IN_PROGRESS"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("max_score", sa.Float(), nullable=True),
        sa.Column("answers", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("result_summary", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("attempt_number >= 1", name="ck_assessment_attempt_positive"),
        sa.UniqueConstraint("assessment_invite_id", "attempt_number", name="uq_assessment_attempt_number"),
    )
    op.create_index("ix_assessment_attempts_assessment_invite_id", "assessment_attempts", ["assessment_invite_id"])


def downgrade() -> None:
    op.drop_index("ix_assessment_attempts_assessment_invite_id", table_name="assessment_attempts")
    op.drop_table("assessment_attempts")
