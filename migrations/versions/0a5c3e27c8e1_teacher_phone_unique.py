"""Require a unique teacher phone for inbound webhook lookup.

Revision ID: 0a5c3e27c8e1
Revises: 6f038f5234c9
"""
from alembic import op

revision = "0a5c3e27c8e1"
down_revision = "6f038f5234c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint("uq_teacher_phone", "teacher", ["phone"])


def downgrade() -> None:
    op.drop_constraint("uq_teacher_phone", "teacher", type_="unique")
