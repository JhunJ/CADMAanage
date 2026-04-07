"""Add commit_annotations table

Revision ID: 004
Revises: 003
Create Date: 2025-02-23

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "commit_annotations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("commit_id", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(128), nullable=True),
        sa.Column("strokes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["commit_id"], ["commits.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_commit_annotations_id", "commit_annotations", ["id"], unique=False)
    op.create_index("ix_commit_annotations_commit_id", "commit_annotations", ["commit_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_commit_annotations_commit_id", table_name="commit_annotations")
    op.drop_index("ix_commit_annotations_id", table_name="commit_annotations")
    op.drop_table("commit_annotations")
