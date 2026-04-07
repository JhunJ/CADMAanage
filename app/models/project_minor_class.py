from sqlalchemy import Column, Integer, String, ForeignKey
from app.db.base import Base


class ProjectMinorClass(Base):
    """프로젝트별 사용자 추가 소분류 (지하1층, 1층, 피트층 등 기본값 외)"""

    __tablename__ = "project_minor_classes"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)
    label = Column(String(64), nullable=False)
    sort_order = Column(Integer, nullable=False, default=0)
