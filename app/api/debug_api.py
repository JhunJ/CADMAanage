"""
디버깅용 API: 커밋 파일 재파싱 결과 + DB 상태 비교.
블록/엔티티 누락 원인 파악용.
"""
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.session import get_db
from app.models import Commit, File, Entity, BlockInsert, BlockDef
from app.services.storage import get_full_path
from app.services.oda_converter import dwg_to_dxf, dwg_to_dxf_with_info
from app.services.dxf_for_commit import get_dxf_bytes_for_commit
from app.services.dxf_parser import parse_dxf, parse_dxf_stats, debug_layer_colors_extraction

router = APIRouter(tags=["debug"])

# DXF 섹션 검사 시 사용할 최대 바이트 (ASCII DXF에서 SECTION 이름은 앞쪽에 몰려있지 않을 수 있음)
_DXF_PREVIEW_SCAN_BYTES = 500_000


def _dxf_section_names(dxf_bytes: bytes, max_bytes: int = 2_000_000) -> list[str]:
    """ASCII DXF에서 SECTION 이름만 순서대로 추출 (  0\\nSECTION\\n  2\\nNAME). Binary DXF면 빈 리스트."""
    if dxf_bytes[:22] == b"AutoCAD Binary DXF\r\n\x1a\x00":
        return []
    scan = min(len(dxf_bytes), max_bytes)
    text = dxf_bytes[:scan].decode("utf-8", errors="replace")
    if "SECTION" not in text:
        text = dxf_bytes[:scan].decode("cp949", errors="replace")
    names = []
    lines = text.replace("\r", "\n").split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.strip() == "0":
            if i + 1 < len(lines) and lines[i + 1].strip() == "SECTION":
                if i + 3 < len(lines) and lines[i + 2].strip() == "2":
                    names.append(lines[i + 3].strip())
                i += 4
                continue
        i += 1
    return names


@router.get("/debug/commits/{commit_id}/parse")
def debug_commit_parse(commit_id: int, db: Session = Depends(get_db)):
    """
    커밋에 연결된 파일을 다시 변환/파싱해서,
    - DXF 내 레이아웃·엔티티 타입별 개수
    - parse_dxf 결과(entities, block_inserts 수)
    - DB에 저장된 entity, block_insert 개수
    를 한꺼번에 반환. 뷰어에 아무것도 안 나올 때 원인 파악용.
    """
    commit = db.query(Commit).filter(Commit.id == commit_id).first()
    if not commit:
        raise HTTPException(status_code=404, detail="Commit not found")
    if commit.status != "READY":
        return {
            "commit_id": commit_id,
            "status": commit.status,
            "message": "커밋이 READY가 아니어서 파일을 재파싱하지 않습니다.",
        }

    file = db.query(File).filter(File.id == commit.file_id).first()
    if not file:
        raise HTTPException(status_code=404, detail="File not found")

    full_path = get_full_path(file.storage_path)
    if not full_path.exists():
        return {
            "commit_id": commit_id,
            "error": "file_not_on_disk",
            "path": str(full_path),
        }

    suffix = full_path.suffix.upper()
    dxf_bytes = None
    if suffix == ".DWG":
        dxf_path = dwg_to_dxf(full_path)
        if dxf_path is None:
            return {"commit_id": commit_id, "error": "DWG 변환 실패 (ODA 없음)"}
        dxf_bytes = dxf_path.read_bytes()
    else:
        dxf_bytes = full_path.read_bytes()

    # 0) DXF 크기·미리보기 (ENTITIES/BLOCKS 섹션은 파일 중후반에 있으므로 충분히 스캔)
    dxf_byte_size = len(dxf_bytes)
    binary_dxf = dxf_bytes[:22] == b"AutoCAD Binary DXF\r\n\x1a\x00"
    dxf_preview = {
        "binary": binary_dxf,
        "size": dxf_byte_size,
        "has_ENTITIES": None,
        "has_BLOCKS": None,
        "snippet": None,
    }
    if not binary_dxf:
        scan_len = min(dxf_byte_size, _DXF_PREVIEW_SCAN_BYTES)
        for enc in ("utf-8", "cp949", "latin-1"):
            try:
                text = dxf_bytes[:scan_len].decode(enc, errors="replace")
                dxf_preview["has_ENTITIES"] = "ENTITIES" in text or "ENTITIES\r\n" in text
                dxf_preview["has_BLOCKS"] = "BLOCKS" in text or "BLOCKS\r\n" in text
                dxf_preview["snippet"] = text[:500].replace("\r", "").strip()
                dxf_preview["scan_bytes"] = scan_len
                dxf_preview["encoding_tried"] = enc
                break
            except Exception:
                continue
    else:
        dxf_preview["snippet"] = "(Binary DXF – section check from stats below)"

    # 1) DXF 내부 통계 (레이아웃별, 타입별 개수) — 파싱 결과로 섹션 존재 여부 보정
    try:
        stats = parse_dxf_stats(dxf_bytes)
        if dxf_preview.get("has_ENTITIES") is False and stats.get("layouts"):
            total_ents = sum(l.get("total", 0) for l in stats.get("layouts", []))
            if total_ents > 0:
                dxf_preview["has_ENTITIES"] = True
                dxf_preview["note"] = "ENTITIES not in first scan; confirmed from layout stats"
        if dxf_preview.get("has_BLOCKS") is False and stats.get("block_def_count", 0) > 0:
            dxf_preview["has_BLOCKS"] = True
            dxf_preview["note"] = dxf_preview.get("note") or "BLOCKS not in first scan; confirmed from block_def_count"
    except Exception as e:
        stats = {"error": str(e)}

    # 2) 우리 파서 결과 + 블록 일치 여부 디버깅
    try:
        entities, block_defs, block_inserts, block_attrs, _ = parse_dxf(dxf_bytes, commit.settings or {})
        def_names = {bd.get("name") for bd in block_defs if bd.get("name")}
        insert_names = {bi.get("block_name") for bi in block_inserts if bi.get("block_name")}
        missing_defs = insert_names - def_names  # INSERT는 있는데 정의 없음
        type_counts = {}
        for e in entities:
            t = e.get("entity_type") or "?"
            type_counts[t] = type_counts.get(t, 0) + 1

        parse_result = {
            "entities_count": len(entities),
            "block_defs_count": len(block_defs),
            "block_inserts_count": len(block_inserts),
            "block_attrs_count": len(block_attrs),
            "entity_type_breakdown": type_counts,
            "block_def_names_sample": sorted(def_names)[:20],
            "block_insert_names_sample": sorted(insert_names)[:20],
            "inserts_without_def": sorted(missing_defs)[:15],
            "inserts_without_def_count": len(missing_defs),
            "first_entity": None,
            "first_block_insert": None,
        }
        if entities:
            e0 = entities[0]
            parse_result["first_entity"] = {
                "entity_type": e0.get("entity_type"),
                "geom_wkt_preview": (e0.get("geom_wkt") or "")[:300],
            }
        if block_inserts:
            bi0 = block_inserts[0]
            parse_result["first_block_insert"] = {
                "block_name": bi0.get("block_name"),
                "insert_point_wkt": (bi0.get("insert_point_wkt") or "")[:200],
            }
        if block_defs:
            bd0 = block_defs[0]
            ent_in_def = (bd0.get("props") or {}).get("entities") or []
            parse_result["first_block_def"] = {
                "name": bd0.get("name"),
                "entities_in_def": len(ent_in_def),
            }
    except Exception as e:
        parse_result = {"error": str(e)}

    # 3) DB 상태 (엔티티·블록 정의·블록 배치)
    db_entity_count = db.query(func.count(Entity.id)).filter(Entity.commit_id == commit_id).scalar() or 0
    db_insert_count = db.query(func.count(BlockInsert.id)).filter(BlockInsert.commit_id == commit_id).scalar() or 0
    db_def_count = db.query(func.count(BlockDef.id)).filter(BlockDef.commit_id == commit_id).scalar() or 0
    first_db_entity = db.query(Entity).filter(Entity.commit_id == commit_id).limit(1).first()
    db_def_names = [r[0] for r in db.query(BlockDef.name).filter(BlockDef.commit_id == commit_id).limit(20).all()]
    db_insert_names_sample = [r[0] for r in db.query(BlockInsert.block_name).filter(BlockInsert.commit_id == commit_id).distinct().limit(20).all()]

    db_state = {
        "entity_count": db_entity_count,
        "block_def_count": db_def_count,
        "block_insert_count": db_insert_count,
        "block_def_names_sample": db_def_names,
        "block_insert_names_sample": db_insert_names_sample,
        "first_entity": None,
    }
    if first_db_entity:
        geom_str = None
        if first_db_entity.geom is not None:
            g = first_db_entity.geom
            if hasattr(g, "wkt"):
                geom_str = g.wkt
            else:
                try:
                    from geoalchemy2.shape import to_shape
                    geom_str = to_shape(g).wkt
                except Exception:
                    geom_str = str(g)
        db_state["first_entity"] = {
            "id": first_db_entity.id,
            "entity_type": first_db_entity.entity_type,
            "geom_preview": (geom_str or "")[:300] if geom_str else None,
        }

    return {
        "commit_id": commit_id,
        "file": {"storage_path": file.storage_path, "suffix": suffix},
        "dxf_byte_size": dxf_byte_size,
        "dxf_preview": dxf_preview,
        "dxf_stats": stats,
        "parse_result": parse_result,
        "db_state": db_state,
    }


@router.get("/debug/commits/{commit_id}/layer-colors")
def debug_commit_layer_colors(commit_id: int, db: Session = Depends(get_db)):
    """
    커밋 DXF의 레이어 색상 추출 디버깅 결과를 반환.
    layer_colors_final, layer_colors_from_doc, layer_colors_from_raw, per_layer 상세.
    """
    _, _, dxf_bytes = get_dxf_bytes_for_commit(commit_id, db)
    if dxf_bytes is None:
        raise HTTPException(status_code=404, detail="Commit not found or file not loadable")
    out = debug_layer_colors_extraction(dxf_bytes)
    out["commit_id"] = commit_id
    return out


def _get_oda_check_output_dir():
    """ODA 검증용 DXF 저장 폴더: data/oda_check_output (프로젝트 내 고정 경로)."""
    from app.services.storage import get_upload_root
    root = get_upload_root().resolve()
    # upload_root 가 data/uploads 이면 data/oda_check_output, 아니면 {upload_root}/oda_check_output
    if root.name == "uploads" and root.parent.name == "data":
        out_dir = root.parent / "oda_check_output"
    else:
        out_dir = root / "oda_check_output"
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


@router.get("/debug/commits/{commit_id}/oda-check")
def debug_commit_oda_check(
    commit_id: int,
    save: bool = False,
    db: Session = Depends(get_db),
):
    """
    DWG 커밋에 대해 변환기(DWG→DXF)가 제대로 변환했는지 검증.
    - save=1 이면 변환된 DXF를 프로젝트 data/oda_check_output/commit_{id}.dxf 에 저장 (직접 열어볼 수 있음).
    - 사용된 변환기(ODA / ezdxf_odafc / dwg2dxf), SECTION 목록, parse_dxf_stats 반환.
    """
    commit = db.query(Commit).filter(Commit.id == commit_id).first()
    if not commit:
        raise HTTPException(status_code=404, detail="Commit not found")

    file = db.query(File).filter(File.id == commit.file_id).first()
    if not file:
        raise HTTPException(status_code=404, detail="File not found")

    full_path = get_full_path(file.storage_path)
    if not full_path.exists():
        return {
            "commit_id": commit_id,
            "error": "file_not_on_disk",
            "path": str(full_path),
        }

    suffix = full_path.suffix.upper()
    if suffix != ".DWG":
        return {
            "commit_id": commit_id,
            "message": "ODA 검증은 DWG 파일만 가능합니다.",
            "file_suffix": suffix,
        }

    dxf_path, converter = dwg_to_dxf_with_info(full_path)
    if dxf_path is None:
        return {
            "commit_id": commit_id,
            "converter_used": None,
            "error": "DWG 변환 실패 (ODA/odafc/dwg2dxf 없음 또는 변환 오류)",
        }

    try:
        dxf_bytes = dxf_path.read_bytes()
    except Exception as e:
        return {
            "commit_id": commit_id,
            "converter_used": converter,
            "dxf_path": str(dxf_path),
            "error": f"변환된 DXF 읽기 실패: {e}",
        }

    saved_to: str | None = None
    if save:
        try:
            out_dir = _get_oda_check_output_dir()
            dest = out_dir / f"commit_{commit_id}.dxf"
            dest.write_bytes(dxf_bytes)
            saved_to = str(dest.resolve())
        except Exception as e:
            saved_to = f"(저장 실패: {e})"

    section_names = _dxf_section_names(dxf_bytes)
    has_blocks = "BLOCKS" in section_names
    has_entities = "ENTITIES" in section_names

    try:
        stats = parse_dxf_stats(dxf_bytes)
    except Exception as e:
        stats = {"error": str(e)}

    block_def_count = stats.get("block_def_count", 0) if isinstance(stats, dict) else 0
    layouts = stats.get("layouts", []) if isinstance(stats, dict) else []
    total_entities_in_layouts = sum(l.get("total", 0) for l in layouts)

    if has_blocks and has_entities and block_def_count > 0:
        verdict = "OK (BLOCKS+ENTITIES+블록정의 있음)"
    elif has_blocks and has_entities:
        verdict = "OK (BLOCKS+ENTITIES 있음, 블록 정의 0개)"
    else:
        verdict = "WARN (BLOCKS 또는 ENTITIES 섹션 없음 – 변환 불완전 가능)"

    res = {
        "commit_id": commit_id,
        "converter_used": converter,
        "dxf_path_temp": str(dxf_path),
        "dxf_size_bytes": len(dxf_bytes),
        "dxf_sections": section_names,
        "has_BLOCKS_section": has_blocks,
        "has_ENTITIES_section": has_entities,
        "conversion_ok": has_blocks and has_entities,
        "parse_dxf_stats": stats,
        "summary": {
            "block_def_count": block_def_count,
            "layout_count": len(layouts),
            "total_entities_in_layouts": total_entities_in_layouts,
            "verdict": verdict,
        },
    }
    if save:
        res["saved_to"] = saved_to
        res["saved_to_note"] = "위 경로의 DXF 파일을 캐드/뷰어로 직접 열어 확인할 수 있습니다."
    return res
