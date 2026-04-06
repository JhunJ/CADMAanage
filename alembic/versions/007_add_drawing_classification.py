"""Add drawing classification (class_pre, class_major, class_mid, class_minor) and project_minor_classes

Revision ID: 007
Revises: 006
Create Date: 2025-02-23

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("commits", sa.Column("class_pre", sa.String(32), nullable=True))
    op.add_column("commits", sa.Column("class_major", sa.String(64), nullable=True))
    op.add_column("commits", sa.Column("class_mid", sa.String(32), nullable=True))
    op.add_column("commits", sa.Column("class_minor", sa.String(64), nullable=True))

    op.create_table(
        "project_minor_classes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(64), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_project_minor_classes_project_id", "project_minor_classes", ["project_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_project_minor_classes_project_id", table_name="project_minor_classes")
    op.drop_table("project_minor_classes")
    op.drop_column("commits", "class_minor")
    op.drop_column("commits", "class_mid")
    op.drop_column("commits", "class_major")
    op.drop_column("commits", "class_pre")
