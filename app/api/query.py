"""
읽기 전용 자유 쿼리 API. SELECT만 허용, 내부 참고용.
"""
import re
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import get_db

router = APIRouter(tags=["query"])

ALLOWED_TABLES = {"entities", "block_defs", "block_inserts", "commits"}
MAX_ROWS = 500


class ReadonlyQueryBody(BaseModel):
    sql: str


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


@router.post("/query/readonly")
def run_readonly_query(body: ReadonlyQueryBody, db: Session = Depends(get_db)):
    """SELECT 전용 읽기 쿼리 실행. 테이블 화이트리스트 적용."""
    raw = (body.sql or "").strip()
    if not raw:
        raise HTTPException(status_code=400, detail="sql is required")
    single = raw.split(";")
    single = [s.strip() for s in single if s.strip()]
    if len(single) != 1:
        raise HTTPException(status_code=400, detail="Single SELECT statement only")
    sql = single[0]
    if not sql.upper().startswith("SELECT"):
        raise HTTPException(status_code=400, detail="Only SELECT is allowed")
    from_match = re.search(r"\bFROM\s+(\w+)", sql, re.IGNORECASE)
    if from_match:
        table = from_match.group(1).lower()
        if table not in ALLOWED_TABLES:
            raise HTTPException(status_code=400, detail=f"Table not allowed: {table}")
    try:
        result = db.execute(text(sql))
        rows = result.mappings().fetchmany(MAX_ROWS)
        columns = list(result.keys()) if hasattr(result, "keys") else (list(rows[0].keys()) if rows else [])
    except Exception as e:
        raise HTTPException(status_code=400, detail="Query failed: " + str(e))
    out_rows = []
    for row in rows:
        out_rows.append({k: _serialize_value(row[k]) for k in columns})
    return {"columns": columns, "rows": out_rows}
