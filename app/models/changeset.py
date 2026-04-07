from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from app.db.base import Base


class Changeset(Base):
    __tablename__ = "changesets"

    id = Column(Integer, primary_key=True, index=True)
    from_commit_id = Column(Integer, ForeignKey("commits.id"), nullable=False)
    to_commit_id = Column(Integer, ForeignKey("commits.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class ChangesetItem(Base):
    __tablename__ = "changeset_items"

    id = Column(Integer, primary_key=True, index=True)
    changeset_id = Column(Integer, ForeignKey("changesets.id"), nullable=False)
    change_type = Column(String(32), nullable=False, index=True)  # ADDED, DELETED, MODIFIED
    old_fingerprint = Column(String(128), nullable=True)
    new_fingerprint = Column(String(128), nullable=True)
    old_entity_id = Column(Integer, ForeignKey("entities.id"), nullable=True)
    new_entity_id = Column(Integer, ForeignKey("entities.id"), nullable=True)
    diff = Column(JSONB, nullable=True)
