"""
GET /commits/{commit_id}/export/dxf - 필터된 엔티티를 DXF로 내보내기.
엔티티만 출력 (폭발된 선/폴리라인 등). 블록 구조는 제외하여 안정성 확보.
"""
import re
from io import StringIO
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session
import ezdxf
from ezdxf.layouts import Modelspace

from app.db.session import get_db
from app.models import Commit, Entity

router = APIRouter(tags=["export"])

# 한글 DXF 내보내기용 텍스트 스타일 (맑은 고딕)
KOREAN_STYLE_NAME = "Korean"
KOREAN_FONT_FILE = "malgun.ttf"


def _geom_to_wkt(geom) -> str | None:
    """DB Geometry -> WKT. GeoAlchemy2가 WKB로 반환해도 Shapely로 WKT 변환."""
    if geom is None:
        return None
    wkt = None
    if hasattr(geom, "wkt"):
        wkt = geom.wkt
    if not wkt:
        try:
            from geoalchemy2.shape import to_shape
            wkt = to_shape(geom).wkt
        except Exception:
            pass
    if not wkt:
        s = str(geom)
        if s and "EMPTY" not in s.upper() and (s.startswith("LINESTRING") or s.startswith("POINT") or s.startswith("MULTI") or s.startswith("POLYGON")):
            wkt = s
    if not wkt:
        return None
    # PostGIS/GeoAlchemy 일부 반환 형식: "SRID=0;LINESTRING(...)" -> 접두어 제거
    if ";" in wkt and re.match(r"^SRID=\d+;", wkt, re.I):
        wkt = re.sub(r"^SRID=\d+;\s*", "", wkt, flags=re.I)
    return wkt


@router.get("/commits/{commit_id}/export/dxf")
def export_commit_dxf(
    commit_id: int,
    layer: str | None = Query(None),
    entity_type: str | None = Query(None),
    db: Session = Depends(get_db),
):
    """필터된 엔티티를 DXF로 내보내기. LINE/LWPOLYLINE/POLYLINE/CIRCLE/ARC/POINT 등 (폭발된 기하만)."""
    commit = db.query(Commit).filter(Commit.id == commit_id).first()
    if not commit:
        raise HTTPException(status_code=404, detail="Commit not found")

    q = db.query(Entity).filter(Entity.commit_id == commit_id)
    if layer is not None:
        q = q.filter(Entity.layer == layer)
    if entity_type is not None:
        q = q.filter(Entity.entity_type == entity_type)
    entities = q.all()

    doc = ezdxf.new("R2010")
    msp = doc.modelspace()

    # 레이어별 색상 보존 (ByLayer 엔티티가 CAD에서 올바른 색으로 표시되도록)
    layer_colors = (commit.settings or {}).get("layer_colors") or {}
    layers_needed = {(e.layer or "0").strip() or "0" for e in entities}
    for lay_name in layers_needed:
        if lay_name not in doc.layers:
            aci = layer_colors.get(lay_name, 7)
            doc.layers.add(lay_name, color=aci)

    # 한글 표시용 텍스트 스타일 추가 (TEXT/MTEXT에서 사용)
    if KOREAN_STYLE_NAME not in doc.styles:
        doc.styles.new(KOREAN_STYLE_NAME, dxfattribs={"font": KOREAN_FONT_FILE})

    for e in entities:
        wkt = _geom_to_wkt(e.geom)
        if not wkt or "EMPTY" in wkt.upper():
            continue
        lay = (e.layer or "0").strip() or "0"
        # 원본이 ByLayer면 256 유지, ByBlock(0)이면 0, 그 외에는 표시색(color)
        props_dict = e.props or {}
        color_bylayer = props_dict.get("color_bylayer")
        color_raw = props_dict.get("color_raw")
        if color_bylayer is True:
            col = 256  # ByLayer
        elif color_raw == 0:
            col = 0  # ByBlock
        elif color_raw == 256:
            col = 256  # ByLayer (color_bylayer 누락 대비)
        else:
            col = int(e.color) if e.color is not None else 256
        et = (e.entity_type or "LINE").strip().upper() or "LINE"
        try:
            _add_entity_from_wkt(msp, et, wkt, lay, col, e.props or {}, text_style=KOREAN_STYLE_NAME)
        except Exception:
            pass

    buf = StringIO()
    doc.write(buf)
    dxf_text = buf.getvalue()

    # 다운로드 파일명: 버전라벨_원본파일명.dxf
    stem = Path(commit.original_filename or "export").stem
    stem_safe = re.sub(r'[^\w\-_.가-힣]', "_", stem)[:200]
    if commit.version_label:
        version_safe = re.sub(r'[^\w\-_.가-힣]', "_", commit.version_label.strip())[:64]
        download_name = f"{version_safe}_{stem_safe}.dxf"
    else:
        download_name = f"{stem_safe}.dxf"

    fallback = f"commit_{commit_id}.dxf"
    return Response(
        content=dxf_text.encode("utf-8"),
        media_type="application/dxf",
        headers={"Content-Disposition": f'attachment; filename="{fallback}"; filename*=UTF-8\'\'{quote(download_name)}'},
    )


def _add_entity_from_wkt(
    msp: Modelspace,
    entity_type: str,
    wkt: str,
    layer: str,
    color: int,
    props: dict,
    text_style: str | None = None,
):
    """WKT -> ezdxf entity. LINE/LWPOLYLINE/POLYLINE/CIRCLE/ARC/POINT/TEXT/MTEXT 지원."""
    if not wkt or "EMPTY" in wkt.upper():
        return
    wkt = wkt.strip()
    if re.match(r"^SRID=\d+;", wkt, re.I):
        wkt = re.sub(r"^SRID=\d+;\s*", "", wkt, flags=re.I)
    # LINESTRING (2점 이상) -> LINE 또는 LWPOLYLINE
    m_lin = re.match(r"LINESTRING\s*Z?\s*\(([^)]+)\)", wkt, re.I)
    if m_lin:
        pts = [[float(x) for x in p.split()] for p in m_lin.group(1).split(",")]
        if not pts:
            return
        pts_2d = [p[:2] for p in pts]
        if entity_type == "LINE" and len(pts_2d) >= 2:
            msp.add_line(pts_2d[0], pts_2d[1], dxfattribs={"layer": layer, "color": color})
        else:
            msp.add_lwpolyline(pts_2d, dxfattribs={"layer": layer, "color": color})
        return
    # MULTILINESTRING ((x y, x y), (x y, x y)) -> 각 링을 LWPOLYLINE로
    if wkt.upper().startswith("MULTILINESTRING"):
        inner = wkt.replace("MULTILINESTRING", "").strip().strip("()")
        for part in re.split(r"\)\s*,\s*\(", inner):
            part = part.strip("()")
            try:
                pts = [[float(x) for x in p.split()] for p in part.split(",")]
                if len(pts) >= 2:
                    msp.add_lwpolyline([p[:2] for p in pts], dxfattribs={"layer": layer, "color": color})
            except (ValueError, TypeError):
                pass
        return
    # POINT / TEXT / MTEXT (all stored as POINT geom)
    m_pt = re.match(r"POINT\s*Z?\s*\(([^)]+)\)", wkt, re.I)
    if m_pt:
        nums = [float(x) for x in m_pt.group(1).split()]
        if len(nums) >= 2:
            insert_pt = tuple(nums[:2])
            if entity_type == "TEXT":
                text = (props.get("text") or "").strip()
                dxf_attribs = {"layer": layer, "color": color, "insert": insert_pt}
                if text_style:
                    dxf_attribs["style"] = text_style
                height = props.get("height")
                if height is not None:
                    dxf_attribs["height"] = float(height)
                msp.add_text(text, dxfattribs=dxf_attribs)
            elif entity_type == "MTEXT":
                text = (props.get("text") or "").strip()
                dxf_attribs = {"layer": layer, "color": color, "insert": insert_pt}
                if text_style:
                    dxf_attribs["style"] = text_style
                msp.add_mtext(text, dxfattribs=dxf_attribs)
            else:
                msp.add_point(insert_pt, dxfattribs={"layer": layer, "color": color})
        return
    # POLYGON: HATCH면 add_hatch, 아니면 외곽선만 LWPOLYLINE로
    m_poly = re.match(r"POLYGON\s*Z?\s*\(\(([^)]+)\)", wkt, re.I)
    if m_poly:
        try:
            pts = [[float(x) for x in p.split()] for p in m_poly.group(1).split(",")]
            if pts:
                pts_2d = [tuple(p[:2]) for p in pts]
                if entity_type == "HATCH":
                    hatch = msp.add_hatch(color=color, dxfattribs={"layer": layer})
                    hatch.paths.add_polyline_path(pts_2d, is_closed=True)
                else:
                    msp.add_lwpolyline(pts_2d, dxfattribs={"layer": layer, "color": color})
        except (ValueError, TypeError):
            pass
