from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from app.db.base import Base


class Commit(Base):
    __tablename__ = "commits"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    file_id = Column(Integer, ForeignKey("files.id"), nullable=False)
    parent_commit_id = Column(Integer, ForeignKey("commits.id"), nullable=True)
    version_label = Column(String(255), nullable=True)
    branch_name = Column(String(64), nullable=True)
    assignee_name = Column(String(255), nullable=True)
    assignee_department = Column(String(255), nullable=True)
    change_notes = Column(Text, nullable=True)
    status = Column(String(32), nullable=False, default="PENDING", index=True)  # PENDING, READY, FAILED
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    settings = Column(JSONB, nullable=True)
    error_message = Column(Text, nullable=True)
    progress_message = Column(String(255), nullable=True)  # 처리 중 단계 메시지 (실시간 갱신)
    class_pre = Column(String(32), nullable=True)  # 추가분류: 구조, 건축
    class_major = Column(String(64), nullable=True)  # 대분류: 지하주차장, 아파트, 부대시설, 단위세대
    class_mid = Column(String(32), nullable=True)  # 중분류: 평면, 단면, 일람
    class_minor = Column(String(64), nullable=True)  # 소분류: 선택사항 (사용자 추가 가능)
    class_work_type = Column(String(64), nullable=True)  # 공종: 선택사항 (사용자 추가 가능)

    file_ref = relationship("File", foreign_keys=[file_id], lazy="joined")

    @property
    def original_filename(self) -> str | None:
        return self.file_ref.original_filename if self.file_ref else None
