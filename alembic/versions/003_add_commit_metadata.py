"""Add assignee, change_notes, branch_name to commits

Revision ID: 003
Revises: 002
Create Date: 2025-02-23

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("commits", sa.Column("assignee_name", sa.String(255), nullable=True))
    op.add_column("commits", sa.Column("assignee_department", sa.String(255), nullable=True))
    op.add_column("commits", sa.Column("change_notes", sa.Text(), nullable=True))
    op.add_column("commits", sa.Column("branch_name", sa.String(64), nullable=True))


def downgrade() -> None:
    op.drop_column("commits", "branch_name")
    op.drop_column("commits", "change_notes")
    op.drop_column("commits", "assignee_department")
    op.drop_column("commits", "assignee_name")
