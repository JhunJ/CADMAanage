"""API for project-level user-defined minor classification (소분류)"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Project, ProjectMinorClass
from app.schemas.project_minor_class import ProjectMinorClassCreate, ProjectMinorClassResponse

# 기본 소분류 목록 (지하 n층, 기초 n, 1층~n층, 피트층, 옥상 n층, 옥탑층)
DEFAULT_MINOR_CLASSES = [
    *[f"지하{i}층" for i in range(1, 6)],
    *[f"기초{i}" for i in range(1, 4)],
    *[f"{i}층" for i in range(1, 16)],
    "피트층",
    *[f"옥상{i}층" for i in range(1, 4)],
    "옥탑층",
]

router = APIRouter(tags=["project_minor_classes"])


@router.get("/projects/{project_id}/minor-classes")
def list_minor_classes(project_id: int, db: Session = Depends(get_db)):
    """프로젝트별 소분류 목록 (기본값 + 사용자 추가 항목)"""
    proj = db.query(Project).filter(Project.id == project_id).first()
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")

    default_set = set(DEFAULT_MINOR_CLASSES)
    result = list(DEFAULT_MINOR_CLASSES)

    custom = (
        db.query(ProjectMinorClass)
        .filter(ProjectMinorClass.project_id == project_id)
        .order_by(ProjectMinorClass.sort_order, ProjectMinorClass.id)
        .all()
    )
    for c in custom:
        if c.label not in default_set and c.label not in result:
            result.append(c.label)

    return {"labels": result}


@router.post("/projects/{project_id}/minor-classes", response_model=ProjectMinorClassResponse)
def add_minor_class(
    project_id: int,
    body: ProjectMinorClassCreate,
    db: Session = Depends(get_db),
):
    """소분류 사용자 추가"""
    proj = db.query(Project).filter(Project.id == project_id).first()
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")

    label = (body.label or "").strip()
    if not label:
        raise HTTPException(status_code=400, detail="label is required")

    existing = (
        db.query(ProjectMinorClass)
        .filter(
            ProjectMinorClass.project_id == project_id,
            ProjectMinorClass.label == label,
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail=f"'{label}' already exists")

    max_order = (
        db.query(ProjectMinorClass.sort_order)
        .filter(ProjectMinorClass.project_id == project_id)
        .order_by(ProjectMinorClass.sort_order.desc())
        .limit(1)
        .scalar() or 0
    )

    item = ProjectMinorClass(
        project_id=project_id,
        label=label,
        sort_order=max_order + 1,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/projects/{project_id}/minor-classes/{label:path}")
def delete_minor_class(
    project_id: int,
    label: str,
    db: Session = Depends(get_db),
):
    """소분류 삭제 (사용자 추가 항목만 삭제 가능)"""
    proj = db.query(Project).filter(Project.id == project_id).first()
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")

    item = (
        db.query(ProjectMinorClass)
        .filter(
            ProjectMinorClass.project_id == project_id,
            ProjectMinorClass.label == label,
        )
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Minor class not found or cannot delete default")

    db.delete(item)
    db.commit()
    return {"status": "deleted", "label": label}
