from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.session import get_db
from app.models import Commit, BlockDef, BlockInsert, BlockAttr
from app.schemas.block import BlockDefResponse, BlockInsertResponse, BlockInsertUpdate, BlockAttrResponse
from app.services.dxf_for_commit import get_dxf_bytes_for_commit
from app.services.dxf_parser import parse_dxf

router = APIRouter(tags=["blocks"])

# 블록 내부 엔티티 응답 상한 (페이징 대신 일단 상한)
BLOCK_ENTITIES_LIMIT = 2000


@router.get("/commits/{commit_id}/blocks/defs")
def list_block_defs(commit_id: int, db: Session = Depends(get_db)):
    commit = db.query(Commit).filter(Commit.id == commit_id).first()
    if not commit:
        raise HTTPException(status_code=404, detail="Commit not found")
    defs = db.query(BlockDef).filter(BlockDef.commit_id == commit_id).all()
    # 블록별 insert 개수
    insert_counts = (
        db.query(BlockInsert.block_name, func.count(BlockInsert.id).label("cnt"))
        .filter(BlockInsert.commit_id == commit_id)
        .group_by(BlockInsert.block_name)
        .all()
    )
    count_by_name = {name: cnt for name, cnt in insert_counts}
    out = []
    for d in defs:
        item = BlockDefResponse.model_validate(d)
        out.append({
            **item.model_dump(),
            "insert_count": count_by_name.get(d.name, 0),
        })
    return {"defs": out}


@router.get("/commits/{commit_id}/blocks/inserts")
def list_block_inserts(
    commit_id: int,
    name: str | None = Query(None),
    layer: str | None = Query(None),
    db: Session = Depends(get_db),
):
    commit = db.query(Commit).filter(Commit.id == commit_id).first()
    if not commit:
        raise HTTPException(status_code=404, detail="Commit not found")
    q = db.query(BlockInsert).filter(BlockInsert.commit_id == commit_id)
    if name is not None:
        q = q.filter(BlockInsert.block_name == name)
    if layer is not None:
        q = q.filter(BlockInsert.layer == layer)
    inserts = q.all()
    return {"inserts": [BlockInsertResponse.model_validate(i) for i in inserts]}


@router.get("/commits/{commit_id}/blocks/inserts/{insert_id}/attrs")
def list_block_insert_attrs(
    commit_id: int,
    insert_id: int,
    db: Session = Depends(get_db),
):
    """해당 블록 배치(insert)에 속한 BlockAttr 목록 반환."""
    commit = db.query(Commit).filter(Commit.id == commit_id).first()
    if not commit:
        raise HTTPException(status_code=404, detail="Commit not found")
    insert = (
        db.query(BlockInsert)
        .filter(
            BlockInsert.id == insert_id,
            BlockInsert.commit_id == commit_id,
        )
        .first()
    )
    if not insert:
        raise HTTPException(status_code=404, detail="Block insert not found")
    attrs = db.query(BlockAttr).filter(BlockAttr.insert_id == insert_id).all()
    return {"attrs": [BlockAttrResponse.model_validate(a) for a in attrs]}


@router.patch("/commits/{commit_id}/blocks/inserts/{insert_id}")
def update_block_insert(
    commit_id: int,
    insert_id: int,
    body: BlockInsertUpdate,
    db: Session = Depends(get_db),
):
    """블록 배치의 props(예: user_attrs) 병합 갱신."""
    commit = db.query(Commit).filter(Commit.id == commit_id).first()
    if not commit:
        raise HTTPException(status_code=404, detail="Commit not found")
    insert = (
        db.query(BlockInsert)
        .filter(
            BlockInsert.id == insert_id,
            BlockInsert.commit_id == commit_id,
        )
        .first()
    )
    if not insert:
        raise HTTPException(status_code=404, detail="Block insert not found")
    if body.props is not None:
        insert.props = {**(insert.props or {}), **body.props}
    db.commit()
    db.refresh(insert)
    return BlockInsertResponse.model_validate(insert)


@router.get("/commits/{commit_id}/blocks/defs/{block_def_id}/entities")
def list_block_def_entities(
    commit_id: int,
    block_def_id: int,
    limit: int = Query(default=2000, le=5000, ge=1),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    """블록 정의 내부 엔티티 목록. 온디맨드 파싱으로 DXF 재로드 후 해당 블록의 props.entities 반환."""
    commit = db.query(Commit).filter(Commit.id == commit_id).first()
    if not commit:
        raise HTTPException(status_code=404, detail="Commit not found")
    block_def = db.query(BlockDef).filter(
        BlockDef.id == block_def_id,
        BlockDef.commit_id == commit_id,
    ).first()
    if not block_def:
        raise HTTPException(status_code=404, detail="Block definition not found")
    _, _, dxf_bytes = get_dxf_bytes_for_commit(commit_id, db)
    if dxf_bytes is None:
        raise HTTPException(
            status_code=404,
            detail="Commit file not loadable (not READY or file missing)",
        )
    _, block_defs_parsed, _, _, _ = parse_dxf(dxf_bytes, commit.settings or {})
    block_name = block_def.name
    entities_in_def = []
    for bd in block_defs_parsed:
        if bd.get("name") == block_name:
            entities_in_def = (bd.get("props") or {}).get("entities") or []
            break
    total = len(entities_in_def)
    # seq 부여 후 슬라이스
    limited = entities_in_def[offset : offset + limit]
    entities_out = [
        {
            "seq": offset + i,
            "entity_type": e.get("entity_type"),
            "layer": e.get("layer"),
            "color": e.get("color"),
            "geom": e.get("geom_wkt"),
            "props": e.get("props") or {},
        }
        for i, e in enumerate(limited)
    ]
    return {
        "entities": entities_out,
        "total": total,
        "has_more": offset + len(limited) < total,
        "block_name": block_name,
    }
