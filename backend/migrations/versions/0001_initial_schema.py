"""Initial TalentOS schema

Revision ID: 0001_initial_schema
Revises:
"""
from alembic import op
from app.db.base import Base
from app import models  # noqa: F401

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    # Keep this initial revision stable as later revisions add tables. The assessment
    # attempt table is introduced by 0002 and must not be created twice on a fresh DB.
    tables = [table for table in Base.metadata.sorted_tables if table.name != "assessment_attempts"]
    Base.metadata.create_all(bind=op.get_bind(), tables=tables, checkfirst=True)


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind(), checkfirst=True)
