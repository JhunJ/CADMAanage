"""Add entities.block_insert_id (FK to block_inserts)

Revision ID: 010
Revises: 009
Create Date: 2025-02-24

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "entities",
        sa.Column("block_insert_id", sa.Integer(), sa.ForeignKey("block_inserts.id"), nullable=True),
    )
    op.create_index("ix_entities_block_insert_id", "entities", ["block_insert_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_entities_block_insert_id", table_name="entities")
    op.drop_column("entities", "block_insert_id")
