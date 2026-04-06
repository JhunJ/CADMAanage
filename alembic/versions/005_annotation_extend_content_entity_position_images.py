"""Extend commit_annotations: content, entity_id, position, image_paths

Revision ID: 005
Revises: 004
Create Date: 2025-02-23

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("commit_annotations", sa.Column("content", sa.Text(), nullable=True))
    op.add_column("commit_annotations", sa.Column("entity_id", sa.Integer(), nullable=True))
    op.add_column("commit_annotations", sa.Column("position_x", sa.Float(), nullable=True))
    op.add_column("commit_annotations", sa.Column("position_y", sa.Float(), nullable=True))
    op.add_column("commit_annotations", sa.Column("image_paths", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.create_foreign_key(
        "fk_commit_annotations_entity_id",
        "commit_annotations",
        "entities",
        ["entity_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_commit_annotations_entity_id", "commit_annotations", ["entity_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_commit_annotations_entity_id", table_name="commit_annotations")
    op.drop_constraint("fk_commit_annotations_entity_id", "commit_annotations", type_="foreignkey")
    op.drop_column("commit_annotations", "image_paths")
    op.drop_column("commit_annotations", "position_y")
    op.drop_column("commit_annotations", "position_x")
    op.drop_column("commit_annotations", "entity_id")
    op.drop_column("commit_annotations", "content")
