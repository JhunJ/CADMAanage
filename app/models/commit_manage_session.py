from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String

from app.db.base import Base


class CommitManageSession(Base):
    __tablename__ = "commit_manage_sessions"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)
    commit_id = Column(Integer, ForeignKey("commits.id"), nullable=False, index=True)
    editor_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    status = Column(String(32), nullable=False, default="ACTIVE", index=True)
    rev = Column(Integer, nullable=False, default=0)
    lock_expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
