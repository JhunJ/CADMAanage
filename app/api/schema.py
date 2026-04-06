"""
스키마 정보 및 샘플 데이터 API. 쿼리 탭에서 테이블 구조 참고용.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Commit, Entity
from app.models.block import BlockDef, BlockInsert

router = APIRouter(tags=["schema"])

SCHEMA_TABLES = ("entities", "block_defs", "block_inserts")
TABLE_MODELS = {
    "entities": (Entity, "commit_id"),
    "block_defs": (BlockDef, "commit_id"),
    "block_inserts": (BlockInsert, "commit_id"),
}


def _serialize_value(v):
    if v is None:
        return None
    if hasattr(v, "wkt"):
        return v.wkt
    try:
        from geoalchemy2.shape import to_shape
        return to_shape(v).wkt
    except Exception:
        pass
    if hasattr(v, "isoformat"):
        return v.isoformat()
    return str(v)


@router.get("/schema")
def get_schema():
    """테이블 목록 및 컬럼 정보."""
    tables = []
    for tname in SCHEMA_TABLES:
        if tname not in TABLE_MODELS:
            continue
        model, _ = TABLE_MODELS[tname]
        cols = []
        for c in model.__table__.columns:
            cols.append({"name": c.name, "type": str(c.type)})
        tables.append({"name": tname, "columns": cols})
    return {"tables": tables}


@router.get("/commits/{commit_id}/schema/{table_name}/sample")
def get_table_sample(
    commit_id: int,
    table_name: str,
    limit: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """지정 테이블의 샘플 행 (commit_id 필터 적용)."""
    if table_name not in TABLE_MODELS:
        raise HTTPException(status_code=404, detail="Unknown table")
    commit = db.query(Commit).filter(Commit.id == commit_id).first()
    if not commit:
        raise HTTPException(status_code=404, detail="Commit not found")
    model, key_col = TABLE_MODELS[table_name]
    q = db.query(model).filter(getattr(model, key_col) == commit_id).limit(limit)
    rows = q.all()
    out = []
    for row in rows:
        out.append({c.name: _serialize_value(getattr(row, c.name)) for c in model.__table__.columns})
    return {"table": table_name, "rows": out}
