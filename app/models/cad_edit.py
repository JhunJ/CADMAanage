from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from app.db.base import Base


class CadEditSession(Base):
    __tablename__ = "cad_edit_sessions"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)
    base_commit_id = Column(Integer, ForeignKey("commits.id"), nullable=False, index=True)
    draft_commit_id = Column(Integer, ForeignKey("commits.id"), nullable=True, index=True)
    editor_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    status = Column(String(32), nullable=False, default="ACTIVE", index=True)
    cursor = Column(Integer, nullable=False, default=0)
    rev = Column(Integer, nullable=False, default=0)
    lock_expires_at = Column(DateTime, nullable=False)
    last_checkpoint_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class CadEditOperation(Base):
    __tablename__ = "cad_edit_operations"
    __table_args__ = (
        UniqueConstraint("session_id", "op_index", name="uq_cad_edit_operations_session_op_index"),
    )

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("cad_edit_sessions.id"), nullable=False, index=True)
    op_index = Column(Integer, nullable=False)
    command = Column(String(64), nullable=False)
    forward_patch = Column(JSONB, nullable=False)
    inverse_patch = Column(JSONB, nullable=False)
    ui_meta = Column(JSONB, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
