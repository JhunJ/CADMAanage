"""Distinct assignee_department from commits (no new table)."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Commit

router = APIRouter(tags=["departments"])


@router.get("/departments")
def list_departments(db: Session = Depends(get_db)):
    """기존 커밋에서 사용된 소속(assignee_department) distinct 목록."""
    rows = (
        db.query(Commit.assignee_department)
        .filter(Commit.assignee_department.isnot(None), Commit.assignee_department != "")
        .distinct()
        .order_by(Commit.assignee_department)
        .all()
    )
    return [r[0] for r in rows]
