from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Commit, CommitAnnotation
from app.schemas.annotation import AnnotationCreate, AnnotationUpdate, AnnotationResponse
from app.services.storage import get_full_path, save_annotation_image

router = APIRouter(tags=["annotations"])


def _get_commit(commit_id: int, db: Session) -> Commit:
    commit = db.query(Commit).filter(Commit.id == commit_id).first()
    if not commit:
        raise HTTPException(status_code=404, detail="Commit not found")
    return commit


@router.get("/commits/{commit_id}/annotations", response_model=list[AnnotationResponse])
def list_annotations(commit_id: int, db: Session = Depends(get_db)):
    _get_commit(commit_id, db)
    items = db.query(CommitAnnotation).filter(CommitAnnotation.commit_id == commit_id).order_by(CommitAnnotation.created_at.desc()).all()
    return items


@router.post("/commits/{commit_id}/annotations", response_model=AnnotationResponse)
def create_annotation(commit_id: int, body: AnnotationCreate, db: Session = Depends(get_db)):
    commit = _get_commit(commit_id, db)
    ann = CommitAnnotation(
        commit_id=commit_id,
        title=(body.title or "").strip() or None,
        content=(body.content or "").strip() or None,
        category=(body.category or "").strip() or None,
        strokes=body.strokes,
        created_by=body.created_by,
        entity_id=body.entity_id,
        position_x=body.position_x,
        position_y=body.position_y,
    )
    db.add(ann)
    db.commit()
    db.refresh(ann)
    return ann


@router.patch("/commits/{commit_id}/annotations/{annotation_id}", response_model=AnnotationResponse)
def update_annotation(commit_id: int, annotation_id: int, body: AnnotationUpdate, db: Session = Depends(get_db)):
    _get_commit(commit_id, db)
    ann = db.query(CommitAnnotation).filter(
        CommitAnnotation.id == annotation_id,
        CommitAnnotation.commit_id == commit_id,
    ).first()
    if not ann:
        raise HTTPException(status_code=404, detail="Annotation not found")
    if body.title is not None:
        ann.title = (body.title or "").strip() or None
    if body.content is not None:
        ann.content = (body.content or "").strip() or None
    if body.category is not None:
        ann.category = (body.category or "").strip() or None
    if body.strokes is not None:
        ann.strokes = body.strokes
    if body.entity_id is not None:
        ann.entity_id = body.entity_id
    if body.position_x is not None:
        ann.position_x = body.position_x
    if body.position_y is not None:
        ann.position_y = body.position_y
    db.commit()
    db.refresh(ann)
    return ann


@router.post("/commits/{commit_id}/annotations/{annotation_id}/images", response_model=AnnotationResponse)
def add_annotation_images(
    commit_id: int,
    annotation_id: int,
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    commit = _get_commit(commit_id, db)
    ann = db.query(CommitAnnotation).filter(
        CommitAnnotation.id == annotation_id,
        CommitAnnotation.commit_id == commit_id,
    ).first()
    if not ann:
        raise HTTPException(status_code=404, detail="Annotation not found")

    paths = list(ann.image_paths or [])
    for f in files:
        if not f.filename or not f.content_type:
            continue
        if not f.content_type.startswith("image/"):
            continue
        try:
            rel = save_annotation_image(commit.project_id, annotation_id, f.filename, f.file)
            paths.append(rel)
        except Exception:
            pass
    ann.image_paths = paths
    db.commit()
    db.refresh(ann)
    return ann


@router.get("/annotations/images/{path:path}")
def serve_annotation_image(path: str):
    """주석 이미지 정적 서빙. path는 projects/1/annotations/2/xxx.png 형태."""
    from fastapi.responses import FileResponse
    if ".." in path or path.startswith("/"):
        raise HTTPException(status_code=400, detail="Invalid path")
    full = get_full_path(path)
    try:
        full = full.resolve()
    except Exception:
        raise HTTPException(status_code=404, detail="Image not found")
    if not full.exists() or not full.is_file():
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(full, media_type="image/png")


@router.delete("/commits/{commit_id}/annotations/{annotation_id}")
def delete_annotation(commit_id: int, annotation_id: int, db: Session = Depends(get_db)):
    _get_commit(commit_id, db)
    ann = db.query(CommitAnnotation).filter(
        CommitAnnotation.id == annotation_id,
        CommitAnnotation.commit_id == commit_id,
    ).first()
    if not ann:
        raise HTTPException(status_code=404, detail="Annotation not found")
    db.delete(ann)
    db.commit()
    return {"ok": True}
