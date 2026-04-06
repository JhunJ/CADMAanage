from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Commit, Entity, Project
from app.schemas.entity import AttrDeleteKeyBody, AttrRenameBody
from app.schemas.project import (
    ProjectAttributeKeysResponse,
    ProjectCreate,
    ProjectResponse,
    ProjectUpdate,
)

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=list[ProjectResponse])
def list_projects(db: Session = Depends(get_db)):
    """프로젝트 목록 (업로드 페이지 등에서 사용)."""
    return db.query(Project).order_by(Project.id).all()


@router.post("", response_model=ProjectResponse)
def create_project(body: ProjectCreate, db: Session = Depends(get_db)):
    existing = db.query(Project).filter(Project.code == body.code).first()
    if existing:
        raise HTTPException(status_code=400, detail="Project code already exists")
    project = Project(name=body.name, code=body.code, created_by=body.created_by)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(project_id: int, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.patch("/{project_id}", response_model=ProjectResponse)
def update_project(project_id: int, body: ProjectUpdate, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if body.name is not None:
        project.name = body.name
    if body.code is not None:
        existing = db.query(Project).filter(Project.code == body.code, Project.id != project_id).first()
        if existing:
            raise HTTPException(status_code=400, detail="Project code already exists")
        project.code = body.code
    if body.created_by is not None:
        project.created_by = body.created_by
    if body.settings is not None:
        project.settings = {**(project.settings or {}), **body.settings}
    db.commit()
    db.refresh(project)
    return project


@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: int, db: Session = Depends(get_db)):
    """프로젝트 삭제. 연관 커밋·엔티티 등은 DB FK 정책에 따라 처리."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    db.delete(project)
    db.commit()
    return None


@router.get("/{project_id}/attribute_keys", response_model=ProjectAttributeKeysResponse)
def get_project_attribute_keys(project_id: int, db: Session = Depends(get_db)):
    """프로젝트 단위 공통/개별 속성 키 목록."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    settings = project.settings or {}
    common = list(settings.get("common_attr_keys") or [])
    individual = list(settings.get("individual_attr_keys") or [])
    return ProjectAttributeKeysResponse(common=common, individual=individual)


@router.post("/{project_id}/entities/attributes/rename")
def rename_project_attribute_key(
    project_id: int,
    body: AttrRenameBody,
    db: Session = Depends(get_db),
):
    """해당 프로젝트의 모든 커밋·엔티티에서 user_attrs 키 이름 변경."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    old_key = (body.old_key or "").strip()
    new_key = (body.new_key or "").strip()
    if not old_key or not new_key:
        raise HTTPException(status_code=400, detail="old_key and new_key required")
    if old_key == new_key:
        return {"status": "ok", "updated": 0}
    commits = db.query(Commit).filter(Commit.project_id == project_id).all()
    updated = 0
    for commit in commits:
        entities = db.query(Entity).filter(Entity.commit_id == commit.id).all()
        for entity in entities:
            props = dict(entity.props) if entity.props else {}
            ua = dict(props.get("user_attrs") or {})
            if old_key in ua:
                ua[new_key] = ua.pop(old_key)
                props["user_attrs"] = ua
                entity.props = props
                updated += 1
    settings = dict(project.settings or {})
    common = list(settings.get("common_attr_keys") or [])
    individual = list(settings.get("individual_attr_keys") or [])
    if old_key in common:
        common = [new_key if k == old_key else k for k in common]
        settings["common_attr_keys"] = common
    if old_key in individual:
        individual = [new_key if k == old_key else k for k in individual]
        settings["individual_attr_keys"] = individual
    project.settings = settings
    db.commit()
    return {"status": "ok", "updated": updated}


@router.post("/{project_id}/entities/attributes/delete_key")
def delete_project_attribute_key(
    project_id: int,
    body: AttrDeleteKeyBody,
    db: Session = Depends(get_db),
):
    """해당 프로젝트의 모든 커밋·엔티티에서 user_attrs 해당 키 제거."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    key = (body.key or "").strip()
    if not key:
        raise HTTPException(status_code=400, detail="key required")
    commits = db.query(Commit).filter(Commit.project_id == project_id).all()
    updated = 0
    for commit in commits:
        entities = db.query(Entity).filter(Entity.commit_id == commit.id).all()
        for entity in entities:
            props = dict(entity.props) if entity.props else {}
            ua = dict(props.get("user_attrs") or {})
            if key in ua:
                del ua[key]
                props["user_attrs"] = ua
                entity.props = props
                updated += 1
    settings = dict(project.settings or {})
    common = list(settings.get("common_attr_keys") or [])
    individual = list(settings.get("individual_attr_keys") or [])
    if key in common:
        settings["common_attr_keys"] = [k for k in common if k != key]
    if key in individual:
        settings["individual_attr_keys"] = [k for k in individual if k != key]
    project.settings = settings
    db.commit()
    return {"status": "ok", "updated": updated}
