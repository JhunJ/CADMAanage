import logging
import time
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import (
    BlockAttr,
    BlockDef,
    BlockInsert,
    Changeset,
    ChangesetItem,
    Commit,
    CommitAnnotation,
    CommitManageSession,
    Entity,
    File,
    Project,
    User,
)
from app.schemas.commit import (
    CommitListResponse,
    CommitManageSessionEndResponse,
    CommitManageSessionHeartbeatResponse,
    CommitManageSessionStartBody,
    CommitManageSessionStartResponse,
    CommitManageSessionStateResponse,
    CommitManageSessionUserBody,
    CommitResponse,
    CommitUpdate,
)
from app.services.storage import delete_file as storage_delete_file

router = APIRouter(tags=["commits"])
logger = logging.getLogger(__name__)
MANAGE_SESSION_TTL_MINUTES = 10


def _utcnow() -> datetime:
    return datetime.utcnow()


def _serialize_manage_session(session: CommitManageSession) -> dict[str, Any]:
    return {
        "id": session.id,
        "project_id": session.project_id,
        "commit_id": session.commit_id,
        "editor_user_id": session.editor_user_id,
        "status": session.status,
        "rev": session.rev,
        "lock_expires_at": session.lock_expires_at,
        "created_at": session.created_at,
        "updated_at": session.updated_at,
    }


def _lock_info_for_session(db: Session, session: CommitManageSession) -> dict[str, Any]:
    info: dict[str, Any] = {
        "session_id": session.id,
        "project_id": session.project_id,
        "commit_id": session.commit_id,
        "editor_user_id": session.editor_user_id,
        "status": session.status,
        "lock_expires_at": session.lock_expires_at,
    }
    user = db.query(User).filter(User.id == session.editor_user_id).first()
    if user:
        info["editor_name"] = user.name
    return info


def _expire_manage_session_if_needed(db: Session, session: CommitManageSession, now: datetime) -> bool:
    if session.status == "ACTIVE" and session.lock_expires_at < now:
        session.status = "EXPIRED"
        session.updated_at = now
        db.flush()
        return True
    return False


def _require_manage_session(
    db: Session,
    session_id: int,
    commit_id: int | None = None,
    editor_user_id: int | None = None,
) -> CommitManageSession:
    session = db.query(CommitManageSession).filter(CommitManageSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Manage session not found")
    if commit_id is not None and session.commit_id != commit_id:
        raise HTTPException(status_code=400, detail="Manage session does not match commit")
    if editor_user_id is not None and session.editor_user_id != editor_user_id:
        raise HTTPException(status_code=403, detail="Session owner mismatch")

    now = _utcnow()
    if _expire_manage_session_if_needed(db, session, now):
        db.commit()
        raise HTTPException(status_code=409, detail="Manage session expired")

    if session.status != "ACTIVE":
        raise HTTPException(status_code=409, detail=f"Manage session not active: {session.status}")
    return session


def _apply_commit_update_fields(commit: Commit, body: CommitUpdate) -> None:
    if body.version_label is not None:
        commit.version_label = body.version_label.strip() or None
    if body.branch_name is not None:
        commit.branch_name = body.branch_name.strip() or None
    if body.assignee_name is not None:
        commit.assignee_name = body.assignee_name.strip() or None
    if body.assignee_department is not None:
        commit.assignee_department = body.assignee_department.strip() or None
    if body.change_notes is not None:
        commit.change_notes = body.change_notes.strip() or None
    if body.class_pre is not None:
        commit.class_pre = body.class_pre.strip() or None
    if body.class_major is not None:
        commit.class_major = body.class_major.strip() or None
    if body.class_mid is not None:
        commit.class_mid = body.class_mid.strip() or None
    if body.class_minor is not None:
        commit.class_minor = body.class_minor.strip() or None
    if body.class_work_type is not None:
        commit.class_work_type = body.class_work_type.strip() or None
    if body.settings is not None:
        commit.settings = {**(commit.settings or {}), **body.settings}


def _delete_commit_with_dependencies(db: Session, commit: Commit) -> str | None:
    commit_id = commit.id

    related_changesets = db.query(Changeset).filter(
        (Changeset.from_commit_id == commit_id) | (Changeset.to_commit_id == commit_id)
    ).all()
    related_changeset_ids = [cs.id for cs in related_changesets]
    if related_changeset_ids:
        db.query(ChangesetItem).filter(ChangesetItem.changeset_id.in_(related_changeset_ids)).delete(
            synchronize_session=False
        )
    db.query(Changeset).filter(
        (Changeset.from_commit_id == commit_id) | (Changeset.to_commit_id == commit_id)
    ).delete(synchronize_session=False)

    block_inserts = db.query(BlockInsert).filter(BlockInsert.commit_id == commit_id).all()
    block_insert_ids = [bi.id for bi in block_inserts]
    if block_insert_ids:
        db.query(BlockAttr).filter(BlockAttr.insert_id.in_(block_insert_ids)).delete(synchronize_session=False)
    db.query(Entity).filter(Entity.commit_id == commit_id).delete(synchronize_session=False)
    db.query(BlockInsert).filter(BlockInsert.commit_id == commit_id).delete(synchronize_session=False)
    db.query(BlockDef).filter(BlockDef.commit_id == commit_id).delete(synchronize_session=False)
    db.query(CommitAnnotation).filter(CommitAnnotation.commit_id == commit_id).delete(synchronize_session=False)
    db.query(CommitManageSession).filter(CommitManageSession.commit_id == commit_id).delete(synchronize_session=False)

    file_id = commit.file_id
    file = db.query(File).filter(File.id == file_id).first()
    storage_path = file.storage_path if file else None

    db.delete(commit)
    db.flush()
    db.query(File).filter(File.id == file_id).delete(synchronize_session=False)
    return storage_path


@router.get("/projects/{project_id}/commits", response_model=CommitListResponse)
def list_commits(
    project_id: int,
    class_pre: str | None = None,
    class_major: str | None = None,
    class_mid: str | None = None,
    class_minor: str | None = None,
    db: Session = Depends(get_db),
):
    proj = db.query(Project).filter(Project.id == project_id).first()
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    q = db.query(Commit).filter(Commit.project_id == project_id)
    q = q.filter(Commit.status != "DRAFT")
    if class_pre:
        q = q.filter(Commit.class_pre == class_pre)
    if class_major:
        q = q.filter(Commit.class_major == class_major)
    if class_mid:
        q = q.filter(Commit.class_mid == class_mid)
    if class_minor:
        q = q.filter(Commit.class_minor == class_minor)
    commits = q.order_by(Commit.created_at.desc()).all()
    return CommitListResponse(commits=commits)


@router.get("/commits/{commit_id}", response_model=CommitResponse)
def get_commit(commit_id: int, db: Session = Depends(get_db)):
    t0 = time.perf_counter()
    commit = db.query(Commit).filter(Commit.id == commit_id).first()
    elapsed = time.perf_counter() - t0
    if elapsed > 0.5:
        logger.warning("get_commit commit_id=%s slow: %.2fs", commit_id, elapsed)
    if not commit:
        raise HTTPException(status_code=404, detail="Commit not found")
    return commit


@router.post("/commits/{commit_id}/manage-sessions/start", response_model=CommitManageSessionStartResponse)
def start_commit_manage_session(
    commit_id: int,
    body: CommitManageSessionStartBody,
    db: Session = Depends(get_db),
):
    commit = db.query(Commit).filter(Commit.id == commit_id).first()
    if not commit:
        raise HTTPException(status_code=404, detail="Commit not found")

    user = db.query(User).filter(User.id == body.editor_user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Editor user not found")

    now = _utcnow()
    active = (
        db.query(CommitManageSession)
        .filter(CommitManageSession.commit_id == commit_id, CommitManageSession.status == "ACTIVE")
        .first()
    )
    if active and _expire_manage_session_if_needed(db, active, now):
        db.commit()
        active = None

    if active:
        lock_info = _lock_info_for_session(db, active)
        if active.editor_user_id != body.editor_user_id:
            raise HTTPException(status_code=409, detail={"message": "Commit is locked", "lock_info": lock_info})
        active.lock_expires_at = now + timedelta(minutes=MANAGE_SESSION_TTL_MINUTES)
        active.updated_at = now
        db.commit()
        db.refresh(active)
        return CommitManageSessionStartResponse(session=_serialize_manage_session(active), resumed=True, lock_info=lock_info)

    session = CommitManageSession(
        project_id=commit.project_id,
        commit_id=commit.id,
        editor_user_id=body.editor_user_id,
        status="ACTIVE",
        rev=0,
        lock_expires_at=now + timedelta(minutes=MANAGE_SESSION_TTL_MINUTES),
        created_at=now,
        updated_at=now,
    )
    db.add(session)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        fresh = (
            db.query(CommitManageSession)
            .filter(CommitManageSession.commit_id == commit_id, CommitManageSession.status == "ACTIVE")
            .first()
        )
        if fresh:
            raise HTTPException(
                status_code=409,
                detail={"message": "Commit is locked", "lock_info": _lock_info_for_session(db, fresh)},
            )
        raise
    db.refresh(session)
    return CommitManageSessionStartResponse(session=_serialize_manage_session(session), resumed=False, lock_info=None)


@router.get("/commits/{commit_id}/manage-sessions/active", response_model=CommitManageSessionStateResponse)
def get_active_commit_manage_session(commit_id: int, db: Session = Depends(get_db)):
    commit = db.query(Commit).filter(Commit.id == commit_id).first()
    if not commit:
        raise HTTPException(status_code=404, detail="Commit not found")

    session = (
        db.query(CommitManageSession)
        .filter(CommitManageSession.commit_id == commit_id, CommitManageSession.status == "ACTIVE")
        .first()
    )
    if not session:
        return CommitManageSessionStateResponse(session=None)

    now = _utcnow()
    if _expire_manage_session_if_needed(db, session, now):
        db.commit()
        return CommitManageSessionStateResponse(session=None)

    return CommitManageSessionStateResponse(session=_serialize_manage_session(session))


@router.post("/manage-sessions/{session_id}/heartbeat", response_model=CommitManageSessionHeartbeatResponse)
def heartbeat_commit_manage_session(
    session_id: int,
    body: CommitManageSessionUserBody,
    db: Session = Depends(get_db),
):
    session = _require_manage_session(db, session_id, editor_user_id=body.editor_user_id)
    now = _utcnow()
    session.lock_expires_at = now + timedelta(minutes=MANAGE_SESSION_TTL_MINUTES)
    session.updated_at = now
    db.commit()
    db.refresh(session)
    return CommitManageSessionHeartbeatResponse(lock_expires_at=session.lock_expires_at)


@router.post("/manage-sessions/{session_id}/end", response_model=CommitManageSessionEndResponse)
def end_commit_manage_session(
    session_id: int,
    body: CommitManageSessionUserBody,
    db: Session = Depends(get_db),
):
    session = db.query(CommitManageSession).filter(CommitManageSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Manage session not found")

    if session.editor_user_id != body.editor_user_id:
        raise HTTPException(status_code=403, detail="Session owner mismatch")

    if session.status != "ACTIVE":
        return CommitManageSessionEndResponse(status=session.status)

    now = _utcnow()
    if _expire_manage_session_if_needed(db, session, now):
        db.commit()
        return CommitManageSessionEndResponse(status=session.status)

    session.status = "ENDED"
    session.lock_expires_at = now
    session.updated_at = now
    session.rev += 1
    db.commit()
    return CommitManageSessionEndResponse(status=session.status)


@router.patch("/manage-sessions/{session_id}/commit", response_model=CommitResponse)
def update_commit_via_manage_session(
    session_id: int,
    body: CommitUpdate,
    editor_user_id: int,
    db: Session = Depends(get_db),
):
    session = _require_manage_session(db, session_id, editor_user_id=editor_user_id)
    commit = db.query(Commit).filter(Commit.id == session.commit_id).first()
    if not commit:
        raise HTTPException(status_code=404, detail="Commit not found")

    _apply_commit_update_fields(commit, body)
    now = _utcnow()
    session.rev += 1
    session.updated_at = now
    session.lock_expires_at = now + timedelta(minutes=MANAGE_SESSION_TTL_MINUTES)
    db.commit()
    db.refresh(commit)
    return commit


@router.delete("/manage-sessions/{session_id}/commit")
def delete_commit_via_manage_session(
    session_id: int,
    editor_user_id: int,
    db: Session = Depends(get_db),
):
    session = _require_manage_session(db, session_id, editor_user_id=editor_user_id)
    commit = db.query(Commit).filter(Commit.id == session.commit_id).first()
    if not commit:
        raise HTTPException(status_code=404, detail="Commit not found")

    commit_id = commit.id
    storage_path = _delete_commit_with_dependencies(db, commit)
    db.commit()

    if storage_path:
        storage_delete_file(storage_path)
    return {"status": "deleted", "id": commit_id}


@router.patch("/commits/{commit_id}", response_model=CommitResponse)
def update_commit(
    commit_id: int,
    body: CommitUpdate,
    manage_session_id: int | None = None,
    editor_user_id: int | None = None,
    db: Session = Depends(get_db),
):
    commit = db.query(Commit).filter(Commit.id == commit_id).first()
    if not commit:
        raise HTTPException(status_code=404, detail="Commit not found")

    session = None
    if manage_session_id is not None:
        session = _require_manage_session(
            db,
            manage_session_id,
            commit_id=commit_id,
            editor_user_id=editor_user_id,
        )

    _apply_commit_update_fields(commit, body)

    if session:
        now = _utcnow()
        session.rev += 1
        session.updated_at = now
        session.lock_expires_at = now + timedelta(minutes=MANAGE_SESSION_TTL_MINUTES)

    db.commit()
    db.refresh(commit)
    return commit


@router.delete("/commits/{commit_id}")
def delete_commit(
    commit_id: int,
    manage_session_id: int | None = None,
    editor_user_id: int | None = None,
    db: Session = Depends(get_db),
):
    commit = db.query(Commit).filter(Commit.id == commit_id).first()
    if not commit:
        raise HTTPException(status_code=404, detail="Commit not found")

    if manage_session_id is not None:
        _require_manage_session(
            db,
            manage_session_id,
            commit_id=commit_id,
            editor_user_id=editor_user_id,
        )

    storage_path = _delete_commit_with_dependencies(db, commit)
    db.commit()

    if storage_path:
        storage_delete_file(storage_path)
    return {"status": "deleted", "id": commit_id}
