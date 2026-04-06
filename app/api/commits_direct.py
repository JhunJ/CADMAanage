"""
직접 커밋 API: DXF 파일 없이 JSON(entities)만 받아 Commit 생성 및 즉시 DB 적재.
Rhino CadManageSave(직접 모드)에서 사용.
"""
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Commit, File, Project
from app.schemas.commit import CommitResponse, DirectCommitCreate
from app.workers.commit_processor import _persist_entities, _persist_blocks
from app.services.changeset import build_changeset

router = APIRouter(tags=["commits-direct"])
logger = logging.getLogger(__name__)


@router.post("/projects/{project_id}/commits/direct", response_model=CommitResponse)
def create_commit_direct(
    project_id: int,
    body: DirectCommitCreate,
    db: Session = Depends(get_db),
):
    """Rhino 등에서 문서를 엔티티 JSON으로 보내면 파일/파싱 없이 즉시 Commit 생성 및 DB 적재."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if not body.entities:
        raise HTTPException(status_code=400, detail="entities must not be empty")

    # Placeholder File (Commit.file_id NOT NULL)
    f = File(
        project_id=project_id,
        original_filename="rhino_direct",
        storage_path="direct/rhino",
        sha256=None,
        file_size=0,
        uploaded_by=body.created_by,
    )
    db.add(f)
    db.flush()

    settings = dict(body.settings or {})
    layer_colors = settings.get("layer_colors")
    if layer_colors is not None:
        settings["layer_colors"] = layer_colors

    commit = Commit(
        project_id=project_id,
        file_id=f.id,
        parent_commit_id=body.parent_commit_id,
        version_label=(body.version_label or "").strip() or None,
        branch_name=(body.branch_name or "").strip() or None,
        assignee_name=(body.assignee_name or "").strip() or None,
        assignee_department=(body.assignee_department or "").strip() or None,
        change_notes=(body.change_notes or "").strip() or None,
        class_pre=(body.class_pre or "").strip() or None,
        class_major=(body.class_major or "").strip() or None,
        class_mid=(body.class_mid or "").strip() or None,
        class_minor=(body.class_minor or "").strip() or None,
        class_work_type=(body.class_work_type or "").strip() or None,
        status="READY",
        created_by=body.created_by,
        settings=settings or None,
    )
    db.add(commit)
    db.commit()
    db.refresh(commit)

    temp_key_to_insert_id = None
    if body.block_defs or body.block_inserts:
        try:
            temp_key_to_insert_id = _persist_blocks(
                db, commit.id,
                body.block_defs or [],
                body.block_inserts or [],
                body.block_attrs or [],
            )
        except Exception as e:
            logger.exception("Direct commit _persist_blocks failed: %s", e)
            db.rollback()
            commit = db.query(Commit).filter(Commit.id == commit.id).first()
            if commit:
                commit.status = "FAILED"
                commit.error_message = str(e)
                db.commit()
                db.refresh(commit)
            raise HTTPException(status_code=500, detail=f"Block persist failed: {e}")

    # Keep alias keys (e.g. "_temp_insert_key") for block->entity mapping.
    entities_as_dicts = [e.model_dump(by_alias=True) for e in body.entities]
    try:
        _persist_entities(db, commit.id, entities_as_dicts, temp_key_to_insert_id)
    except Exception as e:
        logger.exception("Direct commit persist_entities failed: %s", e)
        db.rollback()
        commit = db.query(Commit).filter(Commit.id == commit.id).first()
        if commit:
            commit.status = "FAILED"
            commit.error_message = str(e)
            db.commit()
            db.refresh(commit)
        raise HTTPException(status_code=500, detail=f"Entity persist failed: {e}")

    if body.parent_commit_id:
        try:
            build_changeset(db, body.parent_commit_id, commit.id)
        except Exception as e:
            logger.warning("Changeset build failed (non-fatal): %s", e)
            db.rollback()
            commit = db.query(Commit).filter(Commit.id == commit.id).first()

    return commit
