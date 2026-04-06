"""Add commit manage session table

Revision ID: 013
Revises: 012
Create Date: 2026-03-04

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "013"
down_revision: Union[str, None] = "012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "commit_manage_sessions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("commit_id", sa.Integer(), nullable=False),
        sa.Column("editor_user_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("rev", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("lock_expires_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["commit_id"], ["commits.id"]),
        sa.ForeignKeyConstraint(["editor_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_commit_manage_sessions_id", "commit_manage_sessions", ["id"], unique=False)
    op.create_index("ix_commit_manage_sessions_project_id", "commit_manage_sessions", ["project_id"], unique=False)
    op.create_index("ix_commit_manage_sessions_commit_id", "commit_manage_sessions", ["commit_id"], unique=False)
    op.create_index("ix_commit_manage_sessions_editor_user_id", "commit_manage_sessions", ["editor_user_id"], unique=False)
    op.create_index("ix_commit_manage_sessions_status", "commit_manage_sessions", ["status"], unique=False)
    op.create_index(
        "uq_commit_manage_sessions_commit_active",
        "commit_manage_sessions",
        ["commit_id"],
        unique=True,
        postgresql_where=sa.text("status = 'ACTIVE'"),
    )


def downgrade() -> None:
    op.drop_index("uq_commit_manage_sessions_commit_active", table_name="commit_manage_sessions")
    op.drop_index("ix_commit_manage_sessions_status", table_name="commit_manage_sessions")
    op.drop_index("ix_commit_manage_sessions_editor_user_id", table_name="commit_manage_sessions")
    op.drop_index("ix_commit_manage_sessions_commit_id", table_name="commit_manage_sessions")
    op.drop_index("ix_commit_manage_sessions_project_id", table_name="commit_manage_sessions")
    op.drop_index("ix_commit_manage_sessions_id", table_name="commit_manage_sessions")
    op.drop_table("commit_manage_sessions")
