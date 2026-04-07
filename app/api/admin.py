"""관리자용 API (초기화 등)"""

import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db

logger = logging.getLogger(__name__)
from app.models import (
    ChangesetItem,
    Changeset,
    BlockAttr,
    BlockInsert,
    BlockDef,
    Entity,
    CommitAnnotation,
    Commit,
    File,
    ProjectWorkType,
    ProjectMinorClass,
    Project,
    User,
)
from app.services.storage import delete_file

router = APIRouter(tags=["admin"])


@router.post("/admin/reset-all")
def reset_all_data(db: Session = Depends(get_db)):
    """
    DB 전체 초기화. 모든 데이터 삭제 (users, projects, commits, files, entities, blocks 등).
    """
    try:
        files = db.query(File).all()
        storage_paths = [f.storage_path for f in files if f.storage_path]

        db.query(ChangesetItem).delete(synchronize_session=False)
        db.query(Changeset).delete(synchronize_session=False)
        db.query(BlockAttr).delete(synchronize_session=False)
        db.query(BlockInsert).delete(synchronize_session=False)
        db.query(BlockDef).delete(synchronize_session=False)
        db.query(Entity).delete(synchronize_session=False)
        db.query(CommitAnnotation).delete(synchronize_session=False)
        db.query(Commit).delete(synchronize_session=False)
        db.query(File).delete(synchronize_session=False)
        db.query(ProjectWorkType).delete(synchronize_session=False)
        db.query(ProjectMinorClass).delete(synchronize_session=False)
        db.query(Project).delete(synchronize_session=False)
        db.query(User).delete(synchronize_session=False)
        db.commit()

        for path in storage_paths:
            try:
                delete_file(path)
            except Exception as e:
                logger.warning("파일 삭제 실패 %s: %s", path, e)

        logger.info("DB 전체 초기화 완료")
        return {"status": "ok", "message": "DB 전체 초기화 완료"}
    except Exception as e:
        db.rollback()
        logger.exception("초기화 실패: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
