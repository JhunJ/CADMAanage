from sqlalchemy import Column, Integer, String, ForeignKey
from app.db.base import Base


class ProjectWorkType(Base):
    """프로젝트별 사용자 추가 공종"""

    __tablename__ = "project_work_types"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)
    label = Column(String(64), nullable=False)
    sort_order = Column(Integer, nullable=False, default=0)
