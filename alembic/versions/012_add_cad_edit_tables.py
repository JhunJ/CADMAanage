"""Add CAD edit session/operation and user shortcut tables

Revision ID: 012
Revises: 011
Create Date: 2026-03-04

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision: str = "012"
down_revision: Union[str, None] = "011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "cad_edit_sessions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("base_commit_id", sa.Integer(), nullable=False),
        sa.Column("draft_commit_id", sa.Integer(), nullable=True),
        sa.Column("editor_user_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("cursor", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rev", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("lock_expires_at", sa.DateTime(), nullable=False),
        sa.Column("last_checkpoint_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["base_commit_id"], ["commits.id"]),
        sa.ForeignKeyConstraint(["draft_commit_id"], ["commits.id"]),
        sa.ForeignKeyConstraint(["editor_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_cad_edit_sessions_id", "cad_edit_sessions", ["id"], unique=False)
    op.create_index("ix_cad_edit_sessions_project_id", "cad_edit_sessions", ["project_id"], unique=False)
    op.create_index("ix_cad_edit_sessions_base_commit_id", "cad_edit_sessions", ["base_commit_id"], unique=False)
    op.create_index("ix_cad_edit_sessions_draft_commit_id", "cad_edit_sessions", ["draft_commit_id"], unique=False)
    op.create_index("ix_cad_edit_sessions_editor_user_id", "cad_edit_sessions", ["editor_user_id"], unique=False)
    op.create_index("ix_cad_edit_sessions_status", "cad_edit_sessions", ["status"], unique=False)
    op.create_index(
        "uq_cad_edit_sessions_base_active",
        "cad_edit_sessions",
        ["base_commit_id"],
        unique=True,
        postgresql_where=sa.text("status = 'ACTIVE'"),
    )

    op.create_table(
        "cad_edit_operations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("op_index", sa.Integer(), nullable=False),
        sa.Column("command", sa.String(length=64), nullable=False),
        sa.Column("forward_patch", JSONB, nullable=False),
        sa.Column("inverse_patch", JSONB, nullable=False),
        sa.Column("ui_meta", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["session_id"], ["cad_edit_sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", "op_index", name="uq_cad_edit_operations_session_op_index"),
    )
    op.create_index("ix_cad_edit_operations_id", "cad_edit_operations", ["id"], unique=False)
    op.create_index("ix_cad_edit_operations_session_id", "cad_edit_operations", ["session_id"], unique=False)

    op.create_table(
        "user_cad_shortcuts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("bindings", JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_user_cad_shortcuts_id", "user_cad_shortcuts", ["id"], unique=False)
    op.create_index("ix_user_cad_shortcuts_user_id", "user_cad_shortcuts", ["user_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_user_cad_shortcuts_user_id", table_name="user_cad_shortcuts")
    op.drop_index("ix_user_cad_shortcuts_id", table_name="user_cad_shortcuts")
    op.drop_table("user_cad_shortcuts")

    op.drop_index("ix_cad_edit_operations_session_id", table_name="cad_edit_operations")
    op.drop_index("ix_cad_edit_operations_id", table_name="cad_edit_operations")
    op.drop_table("cad_edit_operations")

    op.drop_index("uq_cad_edit_sessions_base_active", table_name="cad_edit_sessions")
    op.drop_index("ix_cad_edit_sessions_status", table_name="cad_edit_sessions")
    op.drop_index("ix_cad_edit_sessions_editor_user_id", table_name="cad_edit_sessions")
    op.drop_index("ix_cad_edit_sessions_draft_commit_id", table_name="cad_edit_sessions")
    op.drop_index("ix_cad_edit_sessions_base_commit_id", table_name="cad_edit_sessions")
    op.drop_index("ix_cad_edit_sessions_project_id", table_name="cad_edit_sessions")
    op.drop_index("ix_cad_edit_sessions_id", table_name="cad_edit_sessions")
    op.drop_table("cad_edit_sessions")
