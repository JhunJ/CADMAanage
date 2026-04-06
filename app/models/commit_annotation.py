from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from app.db.base import Base


class CommitAnnotation(Base):
    __tablename__ = "commit_annotations"

    id = Column(Integer, primary_key=True, index=True)
    commit_id = Column(Integer, ForeignKey("commits.id", ondelete="CASCADE"), nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    title = Column(String(128), nullable=True)
    content = Column(Text, nullable=True)
    category = Column(String(32), nullable=True)
    strokes = Column(JSONB, nullable=False)
    entity_id = Column(Integer, ForeignKey("entities.id", ondelete="SET NULL"), nullable=True)
    position_x = Column(Float, nullable=True)
    position_y = Column(Float, nullable=True)
    image_paths = Column(JSONB, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
