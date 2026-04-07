"""Initial schema + PostGIS

Revision ID: 001
Revises:
Create Date: 2025-02-12

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from geoalchemy2 import Geometry

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_id", "users", ["id"], unique=False)
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "projects",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_projects_code", "projects", ["code"], unique=True)
    op.create_index("ix_projects_id", "projects", ["id"], unique=False)

    op.create_table(
        "files",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("original_filename", sa.String(512), nullable=False),
        sa.Column("storage_path", sa.String(1024), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=True),
        sa.Column("file_size", sa.BigInteger(), nullable=True),
        sa.Column("uploaded_by", sa.Integer(), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["uploaded_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_files_id", "files", ["id"], unique=False)
    op.create_index("ix_files_sha256", "files", ["sha256"], unique=False)

    op.create_table(
        "commits",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("file_id", sa.Integer(), nullable=False),
        sa.Column("parent_commit_id", sa.Integer(), nullable=True),
        sa.Column("version_label", sa.String(255), nullable=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("settings", sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["file_id"], ["files.id"]),
        sa.ForeignKeyConstraint(["parent_commit_id"], ["commits.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_commits_id", "commits", ["id"], unique=False)
    op.create_index("ix_commits_status", "commits", ["status"], unique=False)

    op.create_table(
        "entities",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("commit_id", sa.Integer(), nullable=False),
        sa.Column("entity_type", sa.String(64), nullable=False),
        sa.Column("layer", sa.String(255), nullable=True),
        sa.Column("color", sa.Integer(), nullable=True),
        sa.Column("linetype", sa.String(255), nullable=True),
        sa.Column("geom", Geometry(geometry_type="GEOMETRY", srid=0), nullable=True),
        sa.Column("centroid", Geometry(geometry_type="POINT", srid=0), nullable=True),
        sa.Column("bbox", Geometry(geometry_type="POLYGON", srid=0), nullable=True),
        sa.Column("props", sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("fingerprint", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["commit_id"], ["commits.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_entities_id", "entities", ["id"], unique=False)
    op.create_index("ix_entities_commit_id", "entities", ["commit_id"], unique=False)
    op.create_index("ix_entities_entity_type", "entities", ["entity_type"], unique=False)
    op.create_index("ix_entities_layer", "entities", ["layer"], unique=False)
    op.create_index("ix_entities_color", "entities", ["color"], unique=False)
    op.create_index("ix_entities_fingerprint", "entities", ["fingerprint"], unique=False)
    op.execute("CREATE INDEX ix_entities_geom ON entities USING GIST (geom)")
    op.execute("CREATE INDEX ix_entities_centroid ON entities USING GIST (centroid)")
    op.execute("CREATE INDEX ix_entities_bbox ON entities USING GIST (bbox)")

    op.create_table(
        "block_defs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("commit_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("base_point", Geometry(geometry_type="POINT", srid=0), nullable=True),
        sa.Column("props", sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(["commit_id"], ["commits.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("commit_id", "name", name="uq_block_defs_commit_name"),
    )
    op.create_index("ix_block_defs_id", "block_defs", ["id"], unique=False)
    op.create_index("ix_block_defs_name", "block_defs", ["name"], unique=False)

    op.create_table(
        "block_inserts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("commit_id", sa.Integer(), nullable=False),
        sa.Column("block_def_id", sa.Integer(), nullable=True),
        sa.Column("block_name", sa.String(255), nullable=False),
        sa.Column("layer", sa.String(255), nullable=True),
        sa.Column("color", sa.Integer(), nullable=True),
        sa.Column("insert_point", Geometry(geometry_type="POINT", srid=0), nullable=True),
        sa.Column("rotation", sa.Float(), nullable=True),
        sa.Column("scale_x", sa.Float(), nullable=True),
        sa.Column("scale_y", sa.Float(), nullable=True),
        sa.Column("scale_z", sa.Float(), nullable=True),
        sa.Column("transform", sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("props", sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("fingerprint", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["block_def_id"], ["block_defs.id"]),
        sa.ForeignKeyConstraint(["commit_id"], ["commits.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_block_inserts_id", "block_inserts", ["id"], unique=False)
    op.create_index("ix_block_inserts_block_name", "block_inserts", ["block_name"], unique=False)
    op.create_index("ix_block_inserts_layer", "block_inserts", ["layer"], unique=False)
    op.create_index("ix_block_inserts_fingerprint", "block_inserts", ["fingerprint"], unique=False)
    op.execute("CREATE INDEX ix_block_inserts_insert_point ON block_inserts USING GIST (insert_point)")

    op.create_table(
        "block_attrs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("insert_id", sa.Integer(), nullable=False),
        sa.Column("tag", sa.String(255), nullable=False),
        sa.Column("value", sa.String(1024), nullable=True),
        sa.Column("props", sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(["insert_id"], ["block_inserts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_block_attrs_id", "block_attrs", ["id"], unique=False)

    op.create_table(
        "changesets",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("from_commit_id", sa.Integer(), nullable=False),
        sa.Column("to_commit_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["from_commit_id"], ["commits.id"]),
        sa.ForeignKeyConstraint(["to_commit_id"], ["commits.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_changesets_id", "changesets", ["id"], unique=False)

    op.create_table(
        "changeset_items",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("changeset_id", sa.Integer(), nullable=False),
        sa.Column("change_type", sa.String(32), nullable=False),
        sa.Column("old_fingerprint", sa.String(128), nullable=True),
        sa.Column("new_fingerprint", sa.String(128), nullable=True),
        sa.Column("old_entity_id", sa.Integer(), nullable=True),
        sa.Column("new_entity_id", sa.Integer(), nullable=True),
        sa.Column("diff", sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(["changeset_id"], ["changesets.id"]),
        sa.ForeignKeyConstraint(["new_entity_id"], ["entities.id"]),
        sa.ForeignKeyConstraint(["old_entity_id"], ["entities.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_changeset_items_id", "changeset_items", ["id"], unique=False)
    op.create_index("ix_changeset_items_change_type", "changeset_items", ["change_type"], unique=False)


def downgrade() -> None:
    op.drop_table("changeset_items")
    op.drop_table("changesets")
    op.drop_table("block_attrs")
    op.drop_table("block_inserts")
    op.drop_table("block_defs")
    op.drop_table("entities")
    op.drop_table("commits")
    op.drop_table("files")
    op.drop_table("projects")
    op.drop_table("users")
    op.execute("DROP EXTENSION IF EXISTS postgis")
