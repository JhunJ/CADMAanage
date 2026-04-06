"""Add projects.settings (JSONB) for project-level config

Revision ID: 011
Revises: 010
Create Date: 2025-02-25

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "011"
down_revision: Union[str, None] = "010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("projects", sa.Column("settings", JSONB, nullable=True))


def downgrade() -> None:
    op.drop_column("projects", "settings")
