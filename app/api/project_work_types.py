"""API for project-level user-defined work types (공종)"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Project, ProjectWorkType
from app.schemas.project_work_type import ProjectWorkTypeCreate, ProjectWorkTypeResponse

router = APIRouter(tags=["project_work_types"])


@router.get("/projects/{project_id}/work-types")
def list_work_types(project_id: int, db: Session = Depends(get_db)):
    """프로젝트별 공종 목록 (사용자 추가 항목만)"""
    proj = db.query(Project).filter(Project.id == project_id).first()
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")

    items = (
        db.query(ProjectWorkType)
        .filter(ProjectWorkType.project_id == project_id)
        .order_by(ProjectWorkType.sort_order, ProjectWorkType.id)
        .all()
    )
    return {"labels": [it.label for it in items]}


@router.post("/projects/{project_id}/work-types", response_model=ProjectWorkTypeResponse)
def add_work_type(
    project_id: int,
    body: ProjectWorkTypeCreate,
    db: Session = Depends(get_db),
):
    """공종 사용자 추가"""
    proj = db.query(Project).filter(Project.id == project_id).first()
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")

    label = (body.label or "").strip()
    if not label:
        raise HTTPException(status_code=400, detail="label is required")

    existing = (
        db.query(ProjectWorkType)
        .filter(
            ProjectWorkType.project_id == project_id,
            ProjectWorkType.label == label,
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail=f"'{label}' already exists")

    max_order = (
        db.query(ProjectWorkType.sort_order)
        .filter(ProjectWorkType.project_id == project_id)
        .order_by(ProjectWorkType.sort_order.desc())
        .limit(1)
        .scalar() or 0
    )

    item = ProjectWorkType(
        project_id=project_id,
        label=label,
        sort_order=max_order + 1,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/projects/{project_id}/work-types/{label:path}")
def delete_work_type(
    project_id: int,
    label: str,
    db: Session = Depends(get_db),
):
    """공종 삭제"""
    proj = db.query(Project).filter(Project.id == project_id).first()
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")

    item = (
        db.query(ProjectWorkType)
        .filter(
            ProjectWorkType.project_id == project_id,
            ProjectWorkType.label == label,
        )
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Work type not found")

    db.delete(item)
    db.commit()
    return {"status": "deleted", "label": label}
