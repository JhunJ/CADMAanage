
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta
import hashlib
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from geoalchemy2.elements import WKTElement
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
    Entity,
    Project,
    User,
)
from app.models.cad_edit import CadEditOperation, CadEditSession
from app.models.user_cad_shortcut import UserCadShortcut
from app.schemas.cad_edit import (
    CadEditCommitBody,
    CadEditCommitResponse,
    CadEditHeartbeatResponse,
    CadEditOperationApplyResponse,
    CadEditOperationCreate,
    CadEditSessionDetailResponse,
    CadEditSessionStartBody,
    CadEditSessionStartResponse,
    CadEditTempSaveResponse,
    UserCadShortcutBody,
    UserCadShortcutResponse,
)
from app.services.changeset import build_changeset

router = APIRouter(tags=["cad-edit"])

LOCK_TTL_MINUTES = 10

CAD_COMMAND_KEYS = [
    "line",
    "polyline",
    "circle",
    "point",
    "explode",
    "join",
    "move",
    "delete",
    "undo",
    "redo",
]
DEFAULT_SHORTCUT_BINDINGS = {
    "line": "L",
    "polyline": "PL",
    "circle": "C",
    "point": "PO",
    "explode": "X",
    "join": "J",
    "move": "M",
    "delete": "DEL",
    "undo": "CTRL+Z",
    "redo": "CTRL+Y",
}


def _utcnow() -> datetime:
    return datetime.utcnow()


def _as_wkt(geom: Any) -> str | None:
    if geom is None:
        return None
    if hasattr(geom, "wkt"):
        try:
            return geom.wkt
        except Exception:
            pass
    try:
        from geoalchemy2.shape import to_shape

        shp = to_shape(geom)
        if shp is not None and hasattr(shp, "wkt"):
            return shp.wkt
    except Exception:
        pass
    s = str(geom)
    if not s:
        return None
    if s.upper().startswith("SRID="):
        parts = s.split(";", 1)
        return parts[1] if len(parts) == 2 else s
    return s


def _wkt_elem(wkt: str | None) -> WKTElement | None:
    if not wkt:
        return None
    raw = str(wkt).strip()
    if not raw:
        return None
    if raw.upper().startswith("SRID="):
        parts = raw.split(";", 1)
        raw = parts[1] if len(parts) == 2 else raw
    return WKTElement(raw, srid=0)


def _compute_entity_fingerprint(payload: dict[str, Any]) -> str:
    body = "|".join(
        [
            str((payload.get("entity_type") or "").upper()),
            str(payload.get("layer") or ""),
            str(payload.get("color") if payload.get("color") is not None else ""),
            str(payload.get("linetype") or ""),
            str(payload.get("geom_wkt") or ""),
            str(payload.get("props") or ""),
            str(payload.get("block_insert_id") if payload.get("block_insert_id") is not None else ""),
        ]
    )
    return hashlib.sha256(body.encode("utf-8")).hexdigest()[:32]


def _clone_commit_to_draft(db: Session, base: Commit, editor_user_id: int) -> Commit:
    settings = dict(base.settings or {})
    cad_edit_meta = dict(settings.get("cad_edit") or {})
    cad_edit_meta["base_commit_id"] = base.id
    cad_edit_meta["draft"] = True
    settings["cad_edit"] = cad_edit_meta
    settings["created_via"] = "cad_edit"

    draft = Commit(
        project_id=base.project_id,
        file_id=base.file_id,
        parent_commit_id=base.id,
        version_label=(base.version_label or "") + "-DRAFT",
        branch_name=base.branch_name,
        assignee_name=base.assignee_name,
        assignee_department=base.assignee_department,
        change_notes=base.change_notes,
        status="DRAFT",
        created_by=editor_user_id,
        settings=settings,
        class_pre=base.class_pre,
        class_major=base.class_major,
        class_mid=base.class_mid,
        class_minor=base.class_minor,
        class_work_type=base.class_work_type,
    )
    db.add(draft)
    db.flush()

    def_map: dict[int, int] = {}
    old_defs = db.query(BlockDef).filter(BlockDef.commit_id == base.id).all()
    for d in old_defs:
        cloned = BlockDef(
            commit_id=draft.id,
            name=d.name,
            base_point=_wkt_elem(_as_wkt(d.base_point)),
            props=deepcopy(d.props) if d.props else None,
        )
        db.add(cloned)
        db.flush()
        def_map[d.id] = cloned.id

    insert_map: dict[int, int] = {}
    old_inserts = db.query(BlockInsert).filter(BlockInsert.commit_id == base.id).all()
    for ins in old_inserts:
        cloned = BlockInsert(
            commit_id=draft.id,
            block_def_id=def_map.get(ins.block_def_id) if ins.block_def_id is not None else None,
            block_name=ins.block_name,
            layer=ins.layer,
            color=ins.color,
            insert_point=_wkt_elem(_as_wkt(ins.insert_point)),
            rotation=ins.rotation,
            scale_x=ins.scale_x,
            scale_y=ins.scale_y,
            scale_z=ins.scale_z,
            transform=deepcopy(ins.transform) if ins.transform else None,
            props=deepcopy(ins.props) if ins.props else None,
            fingerprint=ins.fingerprint,
        )
        db.add(cloned)
        db.flush()
        insert_map[ins.id] = cloned.id

    old_attrs = (
        db.query(BlockAttr)
        .join(BlockInsert, BlockInsert.id == BlockAttr.insert_id)
        .filter(BlockInsert.commit_id == base.id)
        .all()
    )
    for a in old_attrs:
        new_insert_id = insert_map.get(a.insert_id)
        if new_insert_id is None:
            continue
        db.add(
            BlockAttr(
                insert_id=new_insert_id,
                tag=a.tag,
                value=a.value,
                props=deepcopy(a.props) if a.props else None,
            )
        )

    old_entities = db.query(Entity).filter(Entity.commit_id == base.id).all()
    for e in old_entities:
        db.add(
            Entity(
                commit_id=draft.id,
                entity_type=e.entity_type,
                layer=e.layer,
                color=e.color,
                linetype=e.linetype,
                geom=_wkt_elem(_as_wkt(e.geom)),
                centroid=_wkt_elem(_as_wkt(e.centroid)),
                bbox=_wkt_elem(_as_wkt(e.bbox)),
                props=deepcopy(e.props) if e.props else None,
                fingerprint=e.fingerprint,
                block_insert_id=insert_map.get(e.block_insert_id) if e.block_insert_id is not None else None,
            )
        )

    return draft


def _serialize_session(session: CadEditSession) -> dict[str, Any]:
    return {
        "id": session.id,
        "project_id": session.project_id,
        "base_commit_id": session.base_commit_id,
        "draft_commit_id": session.draft_commit_id,
        "editor_user_id": session.editor_user_id,
        "status": session.status,
        "cursor": session.cursor,
        "rev": session.rev,
        "lock_expires_at": session.lock_expires_at,
        "last_checkpoint_at": session.last_checkpoint_at,
        "created_at": session.created_at,
        "updated_at": session.updated_at,
    }


def _serialize_operation(op: CadEditOperation) -> dict[str, Any]:
    return {
        "id": op.id,
        "session_id": op.session_id,
        "op_index": op.op_index,
        "command": op.command,
        "ui_meta": op.ui_meta,
        "created_at": op.created_at,
    }


def _expire_active_sessions_for_base(db: Session, base_commit_id: int) -> None:
    now = _utcnow()
    rows = (
        db.query(CadEditSession)
        .filter(
            CadEditSession.base_commit_id == base_commit_id,
            CadEditSession.status == "ACTIVE",
            CadEditSession.lock_expires_at < now,
        )
        .all()
    )
    for row in rows:
        row.status = "EXPIRED"
        row.updated_at = now
    if rows:
        db.flush()


def _require_active_session(db: Session, session_id: int) -> CadEditSession:
    now = _utcnow()
    session = db.query(CadEditSession).filter(CadEditSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.status != "ACTIVE":
        raise HTTPException(status_code=409, detail=f"Session not active: {session.status}")
    if session.lock_expires_at < now:
        session.status = "EXPIRED"
        session.updated_at = now
        db.commit()
        raise HTTPException(status_code=409, detail="Session lock expired")
    return session


def _apply_patch(db: Session, draft_commit_id: int, patch: dict[str, Any]) -> dict[str, int]:
    created_map: dict[str, int] = {}

    delete_ids = []
    for x in (patch.get("entity_deletes") or []):
        try:
            delete_ids.append(int(x))
        except (TypeError, ValueError):
            continue
    if delete_ids:
        (
            db.query(Entity)
            .filter(Entity.commit_id == draft_commit_id, Entity.id.in_(delete_ids))
            .delete(synchronize_session=False)
        )

    for upd in patch.get("entity_updates") or []:
        if not isinstance(upd, dict):
            continue
        entity_id = upd.get("id")
        if entity_id is None:
            continue
        ent = (
            db.query(Entity)
            .filter(Entity.commit_id == draft_commit_id, Entity.id == int(entity_id))
            .first()
        )
        if not ent:
            continue

        touched = False
        if "entity_type" in upd and upd.get("entity_type") is not None:
            ent.entity_type = str(upd.get("entity_type"))
            touched = True
        if "layer" in upd:
            ent.layer = upd.get("layer")
            touched = True
        if "color" in upd:
            ent.color = upd.get("color")
            touched = True
        if "linetype" in upd:
            ent.linetype = upd.get("linetype")
            touched = True
        if "props" in upd:
            ent.props = deepcopy(upd.get("props")) if upd.get("props") is not None else None
            touched = True
        if "block_insert_id" in upd:
            val = upd.get("block_insert_id")
            ent.block_insert_id = int(val) if val is not None else None
            touched = True
        if "geom_wkt" in upd:
            ent.geom = _wkt_elem(upd.get("geom_wkt"))
            touched = True
        if "centroid_wkt" in upd:
            ent.centroid = _wkt_elem(upd.get("centroid_wkt"))
        if "bbox_wkt" in upd:
            ent.bbox = _wkt_elem(upd.get("bbox_wkt"))

        if "fingerprint" in upd and upd.get("fingerprint"):
            ent.fingerprint = str(upd.get("fingerprint"))
        elif touched:
            current = {
                "entity_type": ent.entity_type,
                "layer": ent.layer,
                "color": ent.color,
                "linetype": ent.linetype,
                "geom_wkt": _as_wkt(ent.geom),
                "props": ent.props,
                "block_insert_id": ent.block_insert_id,
            }
            ent.fingerprint = _compute_entity_fingerprint(current)

    for create in patch.get("entity_creates") or []:
        if not isinstance(create, dict):
            continue
        et = (create.get("entity_type") or "").strip().upper()
        geom_wkt = create.get("geom_wkt")
        if not et or not geom_wkt:
            continue
        payload = {
            "entity_type": et,
            "layer": create.get("layer"),
            "color": create.get("color"),
            "linetype": create.get("linetype"),
            "geom_wkt": geom_wkt,
            "props": create.get("props") or {},
            "block_insert_id": create.get("block_insert_id"),
        }
        fp = (create.get("fingerprint") or "").strip() or _compute_entity_fingerprint(payload)
        ent = Entity(
            commit_id=draft_commit_id,
            entity_type=et,
            layer=create.get("layer"),
            color=create.get("color"),
            linetype=create.get("linetype"),
            geom=_wkt_elem(geom_wkt),
            centroid=_wkt_elem(create.get("centroid_wkt")),
            bbox=_wkt_elem(create.get("bbox_wkt")),
            props=deepcopy(create.get("props")) if create.get("props") is not None else None,
            fingerprint=fp,
            block_insert_id=(
                int(create.get("block_insert_id")) if create.get("block_insert_id") is not None else None
            ),
        )
        db.add(ent)
        db.flush()
        temp_id = create.get("temp_id")
        if temp_id is not None:
            created_map[str(temp_id)] = int(ent.id)

    for upd in patch.get("block_insert_updates") or []:
        if not isinstance(upd, dict):
            continue
        ins_id = upd.get("id")
        if ins_id is None:
            continue
        ins = (
            db.query(BlockInsert)
            .filter(BlockInsert.commit_id == draft_commit_id, BlockInsert.id == int(ins_id))
            .first()
        )
        if not ins:
            continue
        if "layer" in upd:
            ins.layer = upd.get("layer")
        if "color" in upd:
            ins.color = upd.get("color")
        if "rotation" in upd:
            ins.rotation = upd.get("rotation")
        if "scale_x" in upd:
            ins.scale_x = upd.get("scale_x")
        if "scale_y" in upd:
            ins.scale_y = upd.get("scale_y")
        if "scale_z" in upd:
            ins.scale_z = upd.get("scale_z")
        if "transform" in upd:
            ins.transform = deepcopy(upd.get("transform")) if upd.get("transform") is not None else None
        if "props" in upd:
            ins.props = deepcopy(upd.get("props")) if upd.get("props") is not None else None

    settings_patch = patch.get("settings_patch")
    if isinstance(settings_patch, dict) and settings_patch:
        draft = db.query(Commit).filter(Commit.id == draft_commit_id).first()
        if draft:
            merged_settings = dict(draft.settings or {})
            for key, value in settings_patch.items():
                if key == "layer_colors" and isinstance(value, dict):
                    layer_colors = dict(merged_settings.get("layer_colors") or {})
                    for layer_name, color_value in value.items():
                        lname = str(layer_name or "").strip()
                        if not lname:
                            continue
                        if color_value is None or str(color_value).strip() == "":
                            layer_colors.pop(lname, None)
                        else:
                            try:
                                layer_colors[lname] = int(color_value)
                            except (TypeError, ValueError):
                                layer_colors[lname] = color_value
                    merged_settings["layer_colors"] = layer_colors
                else:
                    merged_settings[key] = deepcopy(value)
            draft.settings = merged_settings

    return created_map


def _delete_draft_commit_data(db: Session, draft_commit_id: int) -> None:
    related_changesets = (
        db.query(Changeset)
        .filter((Changeset.from_commit_id == draft_commit_id) | (Changeset.to_commit_id == draft_commit_id))
        .all()
    )
    cs_ids = [x.id for x in related_changesets]
    if cs_ids:
        (
            db.query(ChangesetItem)
            .filter(ChangesetItem.changeset_id.in_(cs_ids))
            .delete(synchronize_session=False)
        )
        (
            db.query(Changeset)
            .filter((Changeset.from_commit_id == draft_commit_id) | (Changeset.to_commit_id == draft_commit_id))
            .delete(synchronize_session=False)
        )

    block_inserts = db.query(BlockInsert).filter(BlockInsert.commit_id == draft_commit_id).all()
    block_insert_ids = [b.id for b in block_inserts]
    if block_insert_ids:
        (
            db.query(BlockAttr)
            .filter(BlockAttr.insert_id.in_(block_insert_ids))
            .delete(synchronize_session=False)
        )

    db.query(Entity).filter(Entity.commit_id == draft_commit_id).delete(synchronize_session=False)
    db.query(BlockInsert).filter(BlockInsert.commit_id == draft_commit_id).delete(synchronize_session=False)
    db.query(BlockDef).filter(BlockDef.commit_id == draft_commit_id).delete(synchronize_session=False)
    db.query(CommitAnnotation).filter(CommitAnnotation.commit_id == draft_commit_id).delete(synchronize_session=False)
    db.query(Commit).filter(Commit.id == draft_commit_id).delete(synchronize_session=False)


def _normalize_bindings(bindings: dict[str, str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for cmd, key in (bindings or {}).items():
        c = str(cmd).strip().lower()
        if c not in CAD_COMMAND_KEYS:
            continue
        k = str(key).strip().upper()
        if not k:
            continue
        out[c] = k
    seen: dict[str, str] = {}
    for cmd, key in out.items():
        prev = seen.get(key)
        if prev is not None and prev != cmd:
            raise HTTPException(status_code=400, detail=f"Duplicate shortcut key: {key}")
        seen[key] = cmd
    return out


def _resolve_temp_ids_in_patch(patch: dict[str, Any], created_map: dict[str, int]) -> dict[str, Any]:
    out = deepcopy(patch or {})
    deletes = out.get("entity_deletes") or []
    resolved = []
    for d in deletes:
        if isinstance(d, str) and d in created_map:
            resolved.append(created_map[d])
        else:
            resolved.append(d)
    out["entity_deletes"] = resolved
    return out

@router.post("/cad-edit/sessions/start", response_model=CadEditSessionStartResponse)
def start_cad_edit_session(body: CadEditSessionStartBody, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == body.project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    base_commit = db.query(Commit).filter(Commit.id == body.base_commit_id).first()
    if not base_commit:
        raise HTTPException(status_code=404, detail="Base commit not found")
    if base_commit.project_id != body.project_id:
        raise HTTPException(status_code=400, detail="base_commit_id does not belong to project")
    if base_commit.status != "READY":
        raise HTTPException(status_code=400, detail="Only READY commits can start edit session")

    user = db.query(User).filter(User.id == body.editor_user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Editor user not found")

    _expire_active_sessions_for_base(db, body.base_commit_id)

    existing = (
        db.query(CadEditSession)
        .filter(
            CadEditSession.base_commit_id == body.base_commit_id,
            CadEditSession.status == "ACTIVE",
        )
        .first()
    )
    now = _utcnow()
    if existing:
        lock_info = {
            "base_commit_id": existing.base_commit_id,
            "editor_user_id": existing.editor_user_id,
            "lock_expires_at": existing.lock_expires_at,
        }
        if existing.editor_user_id == body.editor_user_id:
            existing.lock_expires_at = now + timedelta(minutes=LOCK_TTL_MINUTES)
            existing.updated_at = now
            db.commit()
            db.refresh(existing)
            return CadEditSessionStartResponse(
                session_id=existing.id,
                draft_commit_id=existing.draft_commit_id or 0,
                resumed=True,
                lock_info=lock_info,
            )

        lock_user = db.query(User).filter(User.id == existing.editor_user_id).first()
        if lock_user:
            lock_info["editor_name"] = lock_user.name
        raise HTTPException(status_code=409, detail={"message": "Commit is locked", "lock_info": lock_info})

    draft = _clone_commit_to_draft(db, base_commit, body.editor_user_id)

    session = CadEditSession(
        project_id=body.project_id,
        base_commit_id=body.base_commit_id,
        draft_commit_id=draft.id,
        editor_user_id=body.editor_user_id,
        status="ACTIVE",
        cursor=0,
        rev=0,
        lock_expires_at=now + timedelta(minutes=LOCK_TTL_MINUTES),
        created_at=now,
        updated_at=now,
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    return CadEditSessionStartResponse(
        session_id=session.id,
        draft_commit_id=draft.id,
        resumed=False,
        lock_info={
            "base_commit_id": session.base_commit_id,
            "editor_user_id": session.editor_user_id,
            "lock_expires_at": session.lock_expires_at,
        },
    )


@router.get("/cad-edit/sessions/{session_id}", response_model=CadEditSessionDetailResponse)
def get_cad_edit_session(session_id: int, db: Session = Depends(get_db)):
    session = db.query(CadEditSession).filter(CadEditSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    ops = (
        db.query(CadEditOperation)
        .filter(CadEditOperation.session_id == session_id)
        .order_by(CadEditOperation.op_index.asc())
        .all()
    )
    draft = (
        db.query(Commit).filter(Commit.id == session.draft_commit_id).first() if session.draft_commit_id else None
    )
    draft_meta = (
        {
            "id": draft.id,
            "status": draft.status,
            "version_label": draft.version_label,
            "change_notes": draft.change_notes,
            "parent_commit_id": draft.parent_commit_id,
            "created_by": draft.created_by,
            "created_at": draft.created_at,
        }
        if draft
        else None
    )

    return CadEditSessionDetailResponse(
        session=_serialize_session(session),
        cursor=session.cursor,
        operations=[_serialize_operation(x) for x in ops],
        draft_commit_meta=draft_meta,
    )


@router.post("/cad-edit/sessions/{session_id}/heartbeat", response_model=CadEditHeartbeatResponse)
def heartbeat_cad_edit_session(session_id: int, db: Session = Depends(get_db)):
    session = _require_active_session(db, session_id)
    now = _utcnow()
    session.lock_expires_at = now + timedelta(minutes=LOCK_TTL_MINUTES)
    session.updated_at = now
    db.commit()
    db.refresh(session)
    return CadEditHeartbeatResponse(lock_expires_at=session.lock_expires_at)


@router.post("/cad-edit/sessions/{session_id}/operations", response_model=CadEditOperationApplyResponse)
def add_cad_edit_operation(
    session_id: int,
    body: CadEditOperationCreate,
    db: Session = Depends(get_db),
):
    session = _require_active_session(db, session_id)

    total_count = db.query(CadEditOperation).filter(CadEditOperation.session_id == session_id).count()
    if session.cursor < total_count:
        (
            db.query(CadEditOperation)
            .filter(CadEditOperation.session_id == session_id, CadEditOperation.op_index > session.cursor)
            .delete(synchronize_session=False)
        )

    created_map = _apply_patch(db, session.draft_commit_id, body.forward_patch)
    resolved_inverse_patch = _resolve_temp_ids_in_patch(body.inverse_patch, created_map)

    next_index = session.cursor + 1
    op = CadEditOperation(
        session_id=session_id,
        op_index=next_index,
        command=(body.command or "").strip() or "UNKNOWN",
        forward_patch=body.forward_patch,
        inverse_patch=resolved_inverse_patch,
        ui_meta=body.ui_meta,
    )
    db.add(op)

    now = _utcnow()
    session.cursor = next_index
    session.rev += 1
    session.updated_at = now
    session.lock_expires_at = now + timedelta(minutes=LOCK_TTL_MINUTES)

    db.commit()

    return CadEditOperationApplyResponse(cursor=session.cursor, applied=True, created_entity_id_map=created_map)


@router.post("/cad-edit/sessions/{session_id}/undo", response_model=CadEditOperationApplyResponse)
def undo_cad_edit_operation(session_id: int, db: Session = Depends(get_db)):
    session = _require_active_session(db, session_id)
    if session.cursor <= 0:
        return CadEditOperationApplyResponse(cursor=0, applied=False, created_entity_id_map={})

    op = (
        db.query(CadEditOperation)
        .filter(CadEditOperation.session_id == session_id, CadEditOperation.op_index == session.cursor)
        .first()
    )
    if not op:
        return CadEditOperationApplyResponse(cursor=session.cursor, applied=False, created_entity_id_map={})

    _apply_patch(db, session.draft_commit_id, op.inverse_patch or {})

    now = _utcnow()
    session.cursor -= 1
    session.rev += 1
    session.updated_at = now
    session.lock_expires_at = now + timedelta(minutes=LOCK_TTL_MINUTES)
    db.commit()

    return CadEditOperationApplyResponse(cursor=session.cursor, applied=True, created_entity_id_map={})


@router.post("/cad-edit/sessions/{session_id}/redo", response_model=CadEditOperationApplyResponse)
def redo_cad_edit_operation(session_id: int, db: Session = Depends(get_db)):
    session = _require_active_session(db, session_id)

    next_op = (
        db.query(CadEditOperation)
        .filter(CadEditOperation.session_id == session_id, CadEditOperation.op_index == session.cursor + 1)
        .first()
    )
    if not next_op:
        return CadEditOperationApplyResponse(cursor=session.cursor, applied=False, created_entity_id_map={})

    created_map = _apply_patch(db, session.draft_commit_id, next_op.forward_patch or {})

    now = _utcnow()
    session.cursor += 1
    session.rev += 1
    session.updated_at = now
    session.lock_expires_at = now + timedelta(minutes=LOCK_TTL_MINUTES)
    db.commit()

    return CadEditOperationApplyResponse(cursor=session.cursor, applied=True, created_entity_id_map=created_map)


@router.post("/cad-edit/sessions/{session_id}/temp-save", response_model=CadEditTempSaveResponse)
def temp_save_cad_edit_session(session_id: int, db: Session = Depends(get_db)):
    session = _require_active_session(db, session_id)
    now = _utcnow()
    session.last_checkpoint_at = now
    session.rev += 1
    session.updated_at = now
    session.lock_expires_at = now + timedelta(minutes=LOCK_TTL_MINUTES)
    db.commit()
    db.refresh(session)
    return CadEditTempSaveResponse(checkpoint_at=now, rev=session.rev)

@router.post("/cad-edit/sessions/{session_id}/commit", response_model=CadEditCommitResponse)
def commit_cad_edit_session(
    session_id: int,
    body: CadEditCommitBody,
    db: Session = Depends(get_db),
):
    session = _require_active_session(db, session_id)
    notes = (body.change_notes or "").strip()
    if not notes:
        raise HTTPException(status_code=400, detail="change_notes is required")

    draft = db.query(Commit).filter(Commit.id == session.draft_commit_id).first()
    if not draft:
        raise HTTPException(status_code=404, detail="Draft commit not found")
    if draft.status != "DRAFT":
        raise HTTPException(status_code=409, detail=f"Draft commit status is {draft.status}")

    base = db.query(Commit).filter(Commit.id == session.base_commit_id).first()
    if not base:
        raise HTTPException(status_code=404, detail="Base commit not found")

    now = _utcnow()

    draft.parent_commit_id = session.base_commit_id
    draft.change_notes = notes
    draft.version_label = (body.version_label or "").strip() or (
        (base.version_label or f"commit-{base.id}") + "-edit-" + now.strftime("%Y%m%d%H%M")
    )
    draft.class_pre = (body.class_pre or "").strip() or None
    draft.class_major = (body.class_major or "").strip() or None
    draft.class_mid = (body.class_mid or "").strip() or None
    draft.class_minor = (body.class_minor or "").strip() or None
    draft.class_work_type = (body.class_work_type or "").strip() or None
    draft.assignee_name = (body.assignee_name or "").strip() or None
    draft.assignee_department = (body.assignee_department or "").strip() or None
    draft.status = "READY"
    draft.created_by = session.editor_user_id

    settings = dict(draft.settings or {})
    settings["created_via"] = "cad_edit"
    cad_edit_meta = dict(settings.get("cad_edit") or {})
    cad_edit_meta["base_commit_id"] = session.base_commit_id
    cad_edit_meta["session_id"] = session.id
    cad_edit_meta["draft"] = False
    cad_edit_meta["committed_at"] = now.isoformat()
    settings["cad_edit"] = cad_edit_meta
    draft.settings = settings

    build_changeset(db, session.base_commit_id, draft.id)
    db.flush()

    cs = (
        db.query(Changeset)
        .filter(Changeset.from_commit_id == session.base_commit_id, Changeset.to_commit_id == draft.id)
        .first()
    )

    session.status = "COMMITTED"
    session.lock_expires_at = now
    session.last_checkpoint_at = now
    session.updated_at = now
    session.rev += 1

    db.commit()

    return CadEditCommitResponse(commit_id=draft.id, changeset_id=cs.id if cs else None)


@router.post("/cad-edit/sessions/{session_id}/abort")
def abort_cad_edit_session(session_id: int, db: Session = Depends(get_db)):
    session = db.query(CadEditSession).filter(CadEditSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.status != "ACTIVE":
        return {"status": session.status}

    now = _utcnow()
    if session.lock_expires_at < now:
        session.status = "EXPIRED"
        session.updated_at = now
        db.commit()
        return {"status": session.status}

    try:
        draft_id = session.draft_commit_id
        if draft_id is not None:
            # Break FK reference first, then delete draft tree.
            session.draft_commit_id = None
            db.flush()
            _delete_draft_commit_data(db, draft_id)

        session.status = "ABORTED"
        session.lock_expires_at = now
        session.updated_at = now
        session.rev += 1
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Abort failed: {exc}") from exc

    return {"status": session.status}


@router.get("/projects/{project_id}/cad-edit-commits")
def list_cad_edit_commits(project_id: int, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    commits = (
        db.query(Commit)
        .filter(
            Commit.project_id == project_id,
            Commit.status == "READY",
            Commit.settings["created_via"].astext == "cad_edit",
        )
        .order_by(Commit.created_at.desc())
        .all()
    )

    user_ids = [c.created_by for c in commits if c.created_by is not None]
    users = db.query(User).filter(User.id.in_(user_ids)).all() if user_ids else []
    user_name_by_id = {u.id: u.name for u in users}

    out = []
    for c in commits:
        cs = (
            db.query(Changeset)
            .filter(Changeset.from_commit_id == c.parent_commit_id, Changeset.to_commit_id == c.id)
            .first()
        )
        counts = {"ADDED": 0, "DELETED": 0, "MODIFIED": 0, "total": 0}
        if cs:
            items = db.query(ChangesetItem).filter(ChangesetItem.changeset_id == cs.id).all()
            for it in items:
                ct = (it.change_type or "").upper()
                if ct in counts:
                    counts[ct] += 1
                counts["total"] += 1
        out.append(
            {
                "commit_id": c.id,
                "base_commit_id": c.parent_commit_id,
                "created_by": c.created_by,
                "created_by_name": user_name_by_id.get(c.created_by),
                "created_at": c.created_at,
                "change_notes": c.change_notes,
                "counts": counts,
            }
        )
    return out


@router.get("/commits/{commit_id}/cad-edit-objects")
def list_cad_edit_objects(commit_id: int, db: Session = Depends(get_db)):
    commit = db.query(Commit).filter(Commit.id == commit_id).first()
    if not commit:
        raise HTTPException(status_code=404, detail="Commit not found")

    cs = (
        db.query(Changeset)
        .filter(Changeset.from_commit_id == commit.parent_commit_id, Changeset.to_commit_id == commit.id)
        .first()
    )
    if not cs:
        return []

    items = (
        db.query(ChangesetItem)
        .filter(ChangesetItem.changeset_id == cs.id)
        .order_by(ChangesetItem.id.asc())
        .all()
    )

    entity_ids = []
    for it in items:
        if it.old_entity_id is not None:
            entity_ids.append(it.old_entity_id)
        if it.new_entity_id is not None:
            entity_ids.append(it.new_entity_id)
    entity_by_id: dict[int, Entity] = {}
    if entity_ids:
        rows = db.query(Entity).filter(Entity.id.in_(entity_ids)).all()
        entity_by_id = {e.id: e for e in rows}

    out = []
    for it in items:
        diff = it.diff or {}
        snap = None
        ct = (it.change_type or "").upper()
        if ct == "DELETED":
            snap = diff.get("old_snapshot") if isinstance(diff, dict) else None
            src = entity_by_id.get(it.old_entity_id) if it.old_entity_id is not None else None
        else:
            snap = diff.get("new_snapshot") if isinstance(diff, dict) else None
            src = entity_by_id.get(it.new_entity_id) if it.new_entity_id is not None else None
        if not snap:
            snap = {}
        entity_type = snap.get("entity_type") or (src.entity_type if src else None)
        layer = snap.get("layer") or (src.layer if src else None)
        centroid_wkt = snap.get("centroid_wkt") or (_as_wkt(src.centroid) if src else None)
        out.append(
            {
                "change_type": ct,
                "old_entity_id": it.old_entity_id,
                "new_entity_id": it.new_entity_id,
                "entity_type": entity_type,
                "layer": layer,
                "centroid_wkt": centroid_wkt,
            }
        )

    return out

@router.get("/users/{user_id}/cad-shortcuts", response_model=UserCadShortcutResponse)
def get_user_cad_shortcuts(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    row = db.query(UserCadShortcut).filter(UserCadShortcut.user_id == user_id).first()
    merged = dict(DEFAULT_SHORTCUT_BINDINGS)
    updated_at = None
    if row and row.bindings:
        merged.update(_normalize_bindings(row.bindings))
        updated_at = row.updated_at

    return UserCadShortcutResponse(user_id=user_id, bindings=merged, updated_at=updated_at)


@router.put("/users/{user_id}/cad-shortcuts", response_model=UserCadShortcutResponse)
def put_user_cad_shortcuts(user_id: int, body: UserCadShortcutBody, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    normalized = _normalize_bindings(body.bindings)
    now = _utcnow()

    row = db.query(UserCadShortcut).filter(UserCadShortcut.user_id == user_id).first()
    if not row:
        row = UserCadShortcut(
            user_id=user_id,
            bindings=normalized,
            created_at=now,
            updated_at=now,
        )
        db.add(row)
    else:
        row.bindings = normalized
        row.updated_at = now

    db.commit()
    db.refresh(row)

    merged = dict(DEFAULT_SHORTCUT_BINDINGS)
    merged.update(normalized)
    return UserCadShortcutResponse(user_id=user_id, bindings=merged, updated_at=row.updated_at)
