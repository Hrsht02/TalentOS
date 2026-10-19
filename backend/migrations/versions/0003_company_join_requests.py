"""Add company join requests.

Revision ID: 0003_company_join_requests
Revises: 0002_assessment_attempts
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0003_company_join_requests"
down_revision = "0002_assessment_attempts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "company_join_requests",
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="PENDING"),
        sa.Column("reviewed_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("company_id", "user_id", name="uq_company_join_request_user"),
    )
    op.create_index("ix_company_join_requests_company_id", "company_join_requests", ["company_id"])
    op.create_index("ix_company_join_requests_user_id", "company_join_requests", ["user_id"])
    op.create_index("ix_company_join_requests_status", "company_join_requests", ["status"])


def downgrade() -> None:
    op.drop_index("ix_company_join_requests_status", table_name="company_join_requests")
    op.drop_index("ix_company_join_requests_user_id", table_name="company_join_requests")
    op.drop_index("ix_company_join_requests_company_id", table_name="company_join_requests")
    op.drop_table("company_join_requests")
