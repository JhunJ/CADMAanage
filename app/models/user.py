from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime
from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False, unique=True, index=True)
    role = Column(String(64), nullable=True)  # 역할(소속/부서)
    created_at = Column(DateTime, default=datetime.utcnow)
