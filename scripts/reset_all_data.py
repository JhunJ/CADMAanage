"""
DB 전체 초기화 스크립트.
- 모든 테이블 데이터 삭제 (users, projects, commits, files, entities, blocks, changesets, annotations, project_minor_classes, project_work_types)
- 물리 파일(data/uploads) 삭제

실행: python -m scripts.reset_all_data
"""
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from app.db.session import SessionLocal
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


def main():
    db = SessionLocal()
    try:
        # 1. 삭제 전 파일 storage_path 수집 (물리 삭제용)
        files = db.query(File).all()
        storage_paths = [f.storage_path for f in files if f.storage_path]

        # 2. FK 의존성 순서대로 DB 레코드 삭제
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

        # 3. 물리 파일 삭제
        for path in storage_paths:
            try:
                delete_file(path)
                print(f"삭제됨: {path}")
            except Exception as e:
                print(f"파일 삭제 실패 {path}: {e}")

        print("DB 전체 초기화 완료.")
    except Exception as e:
        db.rollback()
        print(f"오류: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
