import json
import logging
import time
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import Float, String, and_, bindparam, cast, func, or_, text
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import BlockDef, BlockInsert, Commit, Entity
from app.schemas.entity import (
    AttributeKeysResponse,
    AttrDeleteKeyBody,
    AttrRenameBody,
    EntityListResponse,
    EntityResponse,
    EntityUserAttrsUpdate,
)

router = APIRouter(tags=["entities"])
logger = logging.getLogger(__name__)

# 대량 커밋 시 뷰어가 멈추지 않도록 기본 limit. 0이면 제한 없음.
DEFAULT_ENTITY_LIMIT = 100_000


@router.get("/commits/{commit_id}/entities", response_model=EntityListResponse)
def list_entities(
    commit_id: int,
    layer: str | None = Query(None),
    color: int | None = Query(None),
    color_in: str | None = Query(None, description="쉼표 구분 color 목록 (다중 색상)"),
    entity_type: str | None = Query(None),
    entity_type_in: str | None = Query(None, description="쉼표 구분 entity_type 목록 (다중 타입)"),
    block_insert_id: int | None = Query(None, description="블록 배치 ID로 필터 (해당 배치에서 유래한 엔티티만)"),
    length_min: float | None = Query(None),
    length_max: float | None = Query(None),
    area_min: float | None = Query(None),
    area_max: float | None = Query(None),
    text_height_min: float | None = Query(None, description="TEXT/MTEXT 글자 높이 최소 (props.height 또는 char_height)"),
    text_height_max: float | None = Query(None, description="TEXT/MTEXT 글자 높이 최대"),
    user_attrs: str | None = Query(None, description="공통속성 필터 JSON 예: {\"키1\":\"값1\"}"),
    limit: int | None = Query(None, description="최대 엔티티 개수. 미지정=10만, 0=제한없음"),
    db: Session = Depends(get_db),
):
    t0 = time.perf_counter()
    commit = db.query(Commit).filter(Commit.id == commit_id).first()
    if not commit:
        raise HTTPException(status_code=404, detail="Commit not found")

    q = db.query(Entity).filter(Entity.commit_id == commit_id)
    if layer is not None:
        q = q.filter(Entity.layer == layer)
    colors_list: list[int] = []
    if color_in:
        for token in color_in.split(","):
            token = token.strip()
            if not token:
                continue
            try:
                parsed = int(token)
            except ValueError:
                continue
            if parsed not in colors_list:
                colors_list.append(parsed)
    elif color is not None:
        colors_list = [color]
    if colors_list:
        layer_colors_map = (commit.settings or {}).get("layer_colors") or {}
        color_set = set(colors_list)
        layers_with_color = []
        for k, v in layer_colors_map.items():
            try:
                if int(v) in color_set:
                    layers_with_color.append(k)
            except (TypeError, ValueError):
                continue
        by_layer = or_(
            Entity.color.is_(None),
            Entity.color == 0,
            Entity.color == 256,
        )
        color_clause = Entity.color.in_(colors_list)
        if layers_with_color:
            q = q.filter(
                or_(
                    color_clause,
                    and_(by_layer, Entity.layer.in_(layers_with_color)),
                )
            )
        else:
            q = q.filter(color_clause)
    if entity_type_in:
        types_list = [t.strip() for t in entity_type_in.split(",") if t.strip()]
        if types_list:
            q = q.filter(Entity.entity_type.in_(types_list))
    elif entity_type is not None:
        q = q.filter(Entity.entity_type == entity_type)
    if block_insert_id is not None:
        q = q.filter(Entity.block_insert_id == block_insert_id)
    if length_min is not None:
        q = q.filter(func.ST_Length(Entity.geom) >= length_min)
    if length_max is not None:
        q = q.filter(func.ST_Length(Entity.geom) <= length_max)
    if area_min is not None:
        q = q.filter(func.ST_Area(Entity.geom) >= area_min)
    if area_max is not None:
        q = q.filter(func.ST_Area(Entity.geom) <= area_max)
    if text_height_min is not None or text_height_max is not None:
        text_height_expr = func.coalesce(
            cast(Entity.props["height"].astext, Float()),
            cast(Entity.props["char_height"].astext, Float()),
        )
        if text_height_min is not None:
            q = q.filter(text_height_expr >= text_height_min)
        if text_height_max is not None:
            q = q.filter(text_height_expr <= text_height_max)
    if user_attrs:
        try:
            parsed = json.loads(user_attrs)
            if isinstance(parsed, dict) and len(parsed) > 0:
                q = q.filter(
                    text("(entities.props->'user_attrs') @> CAST(:ua AS jsonb)").bindparams(
                        bindparam("ua", json.dumps(parsed), type_=String())
                    )
                )
        except (json.JSONDecodeError, TypeError):
            pass

    # 도면 렌더 순서는 삽입 순서(=id 증가) 기준으로 고정한다.
    q = q.order_by(Entity.id.asc())

    max_limit = limit if limit is not None else DEFAULT_ENTITY_LIMIT
    if max_limit is not None and max_limit > 0:
        q = q.limit(max_limit)

    entities = q.all()
    elapsed = time.perf_counter() - t0
    logger.info("list_entities commit_id=%s count=%s elapsed=%.2fs", commit_id, len(entities), elapsed)

    # 블록 배치 ID -> 블록명 (Rhino 로드 시 BLOCK_NAME/BLOCK_VARIANT 속성용)
    # BlockInsert.block_name이 비어 있으면 BlockDef.name(실제 블록 정의명, 예: A$C9AD06D4)으로 fallback
    block_insert_ids = [e.block_insert_id for e in entities if getattr(e, "block_insert_id", None) is not None]
    block_name_by_insert_id = {}
    if block_insert_ids:
        rows = (
            db.query(BlockInsert.id, BlockInsert.block_name, BlockInsert.block_def_id)
            .filter(BlockInsert.id.in_(block_insert_ids))
            .all()
        )
        def_ids = [r.block_def_id for r in rows if r.block_def_id is not None]
        def_name_by_id = {}
        if def_ids:
            defs = db.query(BlockDef.id, BlockDef.name).filter(BlockDef.id.in_(def_ids)).all()
            def_name_by_id = {d.id: (d.name or "") for d in defs}
        for row in rows:
            name = (row.block_name or "").strip()
            if not name and row.block_def_id is not None:
                name = def_name_by_id.get(row.block_def_id, "") or ""
            block_name_by_insert_id[row.id] = name

    # 블록별 1-based 순번 (block_insert_id 있으면 항상 부여, block_name 없으면 insert_id로 fallback)
    block_index_counter: dict[str, int] = {}
    entity_responses = []
    for e in entities:
        resp = EntityResponse.model_validate(e)
        if e.block_insert_id is not None:
            block_name = block_name_by_insert_id.get(e.block_insert_id, "") or ""
            key = block_name if block_name else "블록_{0}".format(e.block_insert_id)
            block_index_counter[key] = block_index_counter.get(key, 0) + 1
            block_index = block_index_counter[key]
            display_name = block_name if block_name else "블록"
            resp = resp.model_copy(
                update={
                    "block_name": display_name,
                    "block_variant": e.block_insert_id,
                    "block_index": block_index,
                }
            )
        entity_responses.append(resp)

    layer_colors = commit.settings.get("layer_colors") if commit.settings else None
    return EntityListResponse(entities=entity_responses, layer_colors=layer_colors)


@router.get("/commits/{commit_id}/entities/attribute_keys", response_model=AttributeKeysResponse)
def get_attribute_keys(commit_id: int, db: Session = Depends(get_db)):
    """커밋의 공통속성 키 목록과 엔티티에서 사용 중인 모든 키 목록."""
    commit = db.query(Commit).filter(Commit.id == commit_id).first()
    if not commit:
        raise HTTPException(status_code=404, detail="Commit not found")
    settings = commit.settings or {}
    common = list(settings.get("common_attr_keys") or [])
    individual = list(settings.get("individual_attr_keys") or [])
    entities = db.query(Entity).filter(Entity.commit_id == commit_id).all()
    used_set = set()
    for e in entities:
        ua = (e.props or {}).get("user_attrs") or {}
        if isinstance(ua, dict):
            used_set.update(ua.keys())
    return AttributeKeysResponse(common=common, individual=individual, used_keys=sorted(used_set))


@router.post("/commits/{commit_id}/entities/attributes/rename")
def rename_attribute_key(
    commit_id: int,
    body: AttrRenameBody,
    db: Session = Depends(get_db),
):
    """해당 커밋의 모든 엔티티에서 user_attrs의 old_key를 new_key로 변경."""
    commit = db.query(Commit).filter(Commit.id == commit_id).first()
    if not commit:
        raise HTTPException(status_code=404, detail="Commit not found")
    old_key = (body.old_key or "").strip()
    new_key = (body.new_key or "").strip()
    if not old_key or not new_key:
        raise HTTPException(status_code=400, detail="old_key and new_key required")
    if old_key == new_key:
        return {"status": "ok", "updated": 0}
    entities = db.query(Entity).filter(Entity.commit_id == commit_id).all()
    updated = 0
    for entity in entities:
        props = dict(entity.props) if entity.props else {}
        ua = dict(props.get("user_attrs") or {})
        if old_key in ua:
            ua[new_key] = ua.pop(old_key)
            props["user_attrs"] = ua
            entity.props = props
            updated += 1
    settings = dict(commit.settings or {})
    common = list(settings.get("common_attr_keys") or [])
    individual = list(settings.get("individual_attr_keys") or [])
    if old_key in common:
        common = [new_key if k == old_key else k for k in common]
        settings["common_attr_keys"] = common
    if old_key in individual:
        individual = [new_key if k == old_key else k for k in individual]
        settings["individual_attr_keys"] = individual
    commit.settings = settings
    db.commit()
    return {"status": "ok", "updated": updated}


@router.post("/commits/{commit_id}/entities/attributes/delete_key")
def delete_attribute_key(
    commit_id: int,
    body: AttrDeleteKeyBody,
    db: Session = Depends(get_db),
):
    """해당 커밋의 모든 엔티티에서 user_attrs의 해당 키 제거. 공통 목록에서도 제거."""
    commit = db.query(Commit).filter(Commit.id == commit_id).first()
    if not commit:
        raise HTTPException(status_code=404, detail="Commit not found")
    key = (body.key or "").strip()
    if not key:
        raise HTTPException(status_code=400, detail="key required")
    entities = db.query(Entity).filter(Entity.commit_id == commit_id).all()
    updated = 0
    for entity in entities:
        props = dict(entity.props) if entity.props else {}
        ua = dict(props.get("user_attrs") or {})
        if key in ua:
            del ua[key]
            props["user_attrs"] = ua
            entity.props = props
            updated += 1
    settings = dict(commit.settings or {})
    common = list(settings.get("common_attr_keys") or [])
    individual = list(settings.get("individual_attr_keys") or [])
    if key in common:
        settings["common_attr_keys"] = [k for k in common if k != key]
    if key in individual:
        settings["individual_attr_keys"] = [k for k in individual if k != key]
    commit.settings = settings
    db.commit()
    return {"status": "ok", "updated": updated}


@router.patch("/commits/{commit_id}/entities/{entity_id}", response_model=EntityResponse)
def patch_entity(
    commit_id: int,
    entity_id: int,
    body: EntityUserAttrsUpdate,
    db: Session = Depends(get_db),
):
    """엔티티의 user_attrs(공통속성)만 갱신. props 내 user_attrs 키로 저장."""
    commit = db.query(Commit).filter(Commit.id == commit_id).first()
    if not commit:
        raise HTTPException(status_code=404, detail="Commit not found")
    entity = db.query(Entity).filter(Entity.commit_id == commit_id, Entity.id == entity_id).first()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    props = dict(entity.props) if entity.props else {}
    if body.user_attrs is not None:
        props["user_attrs"] = {str(k): str(v) for k, v in body.user_attrs.items()}
    entity.props = props
    db.commit()
    db.refresh(entity)
    return entity
