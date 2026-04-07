# -*- coding: utf-8 -*-
"""
CAD Manage - Rhino 8 연동 스크립트
- 라이노 열기: 웹에서 "라이노 열기" 버튼 또는 "라이노 열기.bat" 실행 → 라이노가 뜨면 메뉴에서 [가져오기]로 DB에서 불러오기.
- 가져오기(1): 서버에서 프로젝트·버전 선택 → 현재 문서에 객체로 추가.
- 저장(2): 현재 문서를 DB에 새 버전으로 저장 (먼저 가져오기로 불러온 문서여야 함).
"""
from __future__ import print_function
import os
import sys
import json
import re
import tempfile
import time
import threading
import codecs

try:
    import Rhino
    import scriptcontext
except ImportError:
    print("Rhino 8 환경에서만 실행 가능합니다.")
    sys.exit(1)

try:
    import Rhino.UI
    import Eto.Forms as eto_forms
    import Eto.Drawing as eto_drawing
except ImportError:
    eto_forms = None
    eto_drawing = None

# 연동 정보 저장 경로 (문서별로 저장하면 같은 문서에서 Save 시 재사용)
def _link_file_path():
    doc_path = scriptcontext.doc.Path if scriptcontext.doc and scriptcontext.doc.Path else ""
    if doc_path:
        folder = os.path.dirname(doc_path)
        return os.path.join(folder, "_cadmanage_link.json")
    return os.path.join(tempfile.gettempdir(), "cadmanage_rhino_link.json")


def _load_link():
    path = _link_file_path()
    if not os.path.exists(path):
        return None
    try:
        with codecs.open(path, "r", "utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _save_link(data):
    path = _link_file_path()
    try:
        with codecs.open(path, "w", "utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print("연동 정보 저장 실패:", e)
        return False


def _launch_file_path():
    return os.path.join(tempfile.gettempdir(), "cadmanage_launch.json")


def _extract_first_json_object(s):
    """문자열에서 첫 번째 완전한 JSON 객체 '{' ... '}' 구간만 추출. 뒤의 Extra data 무시."""
    start = s.find("{")
    if start < 0:
        return None
    depth = 0
    for i in range(start, len(s)):
        if s[i] == "{":
            depth += 1
        elif s[i] == "}":
            depth -= 1
            if depth == 0:
                return s[start : i + 1]
    return None


def _read_launch_json(path):
    """launch.json 읽기. BOM/줄바꿈 제거 후 첫 번째 JSON 객체만 파싱 (Extra data 방지)."""
    with codecs.open(path, "r", "utf-8") as f:
        raw = f.read().strip()
    if raw.startswith("\ufeff"):
        raw = raw.lstrip("\ufeff")

    debug_path = _debug_log_path()
    try:
        with codecs.open(debug_path, "a", "utf-8") as log:
            log.write("_read_launch_json: len=%s\n" % (len(raw),))
            log.write("  raw[:100]=%s\n" % (repr(raw[:100]) if len(raw) > 0 else "(empty)",))
            log.write("  raw[-30:]=%s\n" % (repr(raw[-30:]) if len(raw) >= 30 else repr(raw),))
            if len(raw) >= 72:
                log.write("  raw[64:72]=%s (char 66-69)\n" % (repr(raw[64:72]),))
            elif len(raw) > 64:
                log.write("  raw[64:]=%s\n" % (repr(raw[64:]),))
    except Exception:
        pass

    obj_str = _extract_first_json_object(raw)
    if obj_str is not None:
        try:
            return json.loads(obj_str)
        except Exception:
            pass
    try:
        return json.loads(raw)
    except Exception as e:
        try:
            _debug("_read_launch_json failed: len=%s raw[:100]=%s raw[64:72]=%s" % (
                len(raw), repr(raw[:100]), repr(raw[64:72]) if len(raw) >= 72 else repr(raw[64:])))
        except Exception:
            pass
        raise


_listener_started = False


def _background_listener_loop():
    """백그라운드에서 launch.json을 주기적으로 확인. 있으면 UI 스레드에서 열기 실행."""
    launch_path = _launch_file_path()
    while True:
        time.sleep(2.0)
        if not os.path.exists(launch_path):
            continue
        try:
            info = _read_launch_json(launch_path)
            try:
                os.remove(launch_path)
            except Exception:
                pass
            def open_on_ui():
                try:
                    print("CadManage: 웹에서 연동 요청 수신. 객체 불러오는 중...")
                    _do_open_from_info(info)
                except Exception as e:
                    print("CadManage 연동 처리 실패:", e)
            try:
                if hasattr(Rhino.RhinoApp, "InvokeOnUiThread"):
                    Rhino.RhinoApp.InvokeOnUiThread(open_on_ui)
                else:
                    open_on_ui()
            except Exception:
                open_on_ui()
        except Exception as e:
            _debug("리스너에서 launch 파일 처리 예외: {}".format(e))


def _debug_log_path():
    return os.path.join(tempfile.gettempdir(), "cadmanage_rhino_debug.txt")


def _debug(msg):
    """디버깅: 콘솔 출력 + 로그 파일에 기록 (원인 파악용)"""
    print(msg)
    try:
        with codecs.open(_debug_log_path(), "a", "utf-8") as f:
            f.write(msg + "\n")
    except Exception:
        pass


# ACI 0-255 -> (R,G,B) decimal. Source: AutoCAD Color Index (0-7 basic, 8-255 standard palette).
_ACI_RGB = [
    (0, 0, 0), (255, 0, 0), (255, 255, 0), (0, 255, 0), (0, 255, 255), (0, 0, 255), (255, 0, 255), (255, 255, 255),
    (65, 65, 65), (128, 128, 128), (255, 0, 0), (255, 170, 170), (189, 0, 0), (189, 126, 126), (129, 0, 0), (129, 86, 86),
    (104, 0, 0), (104, 69, 69), (79, 0, 0), (79, 53, 53), (255, 63, 0), (255, 191, 170), (189, 46, 0), (189, 141, 126),
    (129, 31, 0), (129, 96, 86), (104, 25, 0), (104, 78, 69), (79, 19, 0), (79, 59, 53), (255, 127, 0), (255, 212, 170),
    (189, 94, 0), (189, 157, 126), (129, 64, 0), (129, 107, 86), (104, 52, 0), (104, 86, 69), (79, 39, 0), (79, 66, 53),
    (255, 191, 0), (255, 234, 170), (189, 141, 0), (189, 173, 126), (129, 96, 0), (129, 118, 86), (104, 78, 0), (104, 95, 69),
    (79, 59, 0), (79, 73, 53), (255, 255, 0), (255, 255, 170), (189, 189, 0), (189, 189, 126), (129, 129, 0), (129, 129, 86),
    (104, 104, 0), (104, 104, 69), (79, 79, 0), (79, 79, 53), (191, 255, 0), (234, 255, 170), (141, 189, 0), (173, 189, 126),
    (96, 129, 0), (118, 129, 86), (78, 104, 0), (95, 104, 69), (59, 79, 0), (73, 79, 53), (127, 255, 0), (212, 255, 170),
    (94, 189, 0), (157, 189, 126), (64, 129, 0), (107, 129, 86), (52, 104, 0), (86, 104, 69), (39, 79, 0), (66, 79, 53),
    (63, 255, 0), (191, 255, 170), (46, 189, 0), (141, 189, 126), (31, 129, 0), (96, 129, 86), (25, 104, 0), (78, 104, 69),
    (19, 79, 0), (59, 79, 53), (0, 255, 0), (170, 255, 170), (0, 189, 0), (126, 189, 126), (0, 129, 0), (86, 129, 86),
    (0, 104, 0), (69, 104, 69), (0, 79, 0), (53, 79, 53), (0, 255, 63), (170, 255, 191), (0, 189, 46), (126, 189, 141),
    (0, 129, 31), (86, 129, 96), (0, 104, 25), (69, 104, 78), (0, 79, 19), (53, 79, 59), (0, 255, 127), (170, 255, 212),
    (0, 189, 94), (126, 189, 157), (0, 129, 64), (86, 129, 107), (0, 104, 52), (69, 104, 86), (0, 79, 39), (53, 79, 66),
    (0, 255, 191), (170, 255, 234), (0, 189, 141), (126, 189, 173), (0, 129, 96), (86, 129, 118), (0, 104, 78), (69, 104, 95),
    (0, 79, 59), (53, 79, 73), (0, 255, 255), (170, 255, 255), (0, 189, 189), (126, 189, 189), (0, 129, 129), (86, 129, 129),
    (0, 104, 104), (69, 104, 104), (0, 79, 79), (53, 79, 79), (0, 191, 255), (170, 234, 255), (0, 141, 189), (126, 173, 189),
    (0, 96, 129), (86, 118, 129), (0, 78, 104), (69, 95, 104), (0, 59, 79), (53, 73, 79), (0, 127, 255), (170, 212, 255),
    (0, 94, 189), (126, 157, 189), (0, 64, 129), (86, 107, 129), (0, 52, 104), (69, 86, 104), (0, 39, 79), (53, 66, 79),
    (0, 63, 255), (170, 191, 255), (0, 46, 189), (126, 141, 189), (0, 31, 129), (86, 96, 129), (0, 25, 104), (69, 78, 104),
    (0, 19, 79), (53, 59, 79), (0, 0, 255), (170, 170, 255), (0, 0, 189), (126, 126, 189), (0, 0, 129), (86, 86, 129),
    (0, 0, 104), (69, 69, 104), (0, 0, 79), (53, 53, 79), (63, 0, 255), (191, 170, 255), (46, 0, 189), (141, 126, 189),
    (31, 0, 129), (96, 86, 129), (25, 0, 104), (78, 69, 104), (19, 0, 79), (59, 53, 79), (127, 0, 255), (212, 170, 255),
    (94, 0, 189), (157, 126, 189), (64, 0, 129), (107, 86, 129), (52, 0, 104), (86, 69, 104), (39, 0, 79), (66, 53, 79),
    (191, 0, 255), (234, 170, 255), (141, 0, 189), (173, 126, 189), (96, 0, 129), (118, 86, 129), (78, 0, 104), (95, 69, 104),
    (59, 0, 79), (73, 53, 79), (255, 0, 255), (255, 170, 255), (189, 0, 189), (189, 126, 189), (129, 0, 129), (129, 86, 129),
    (104, 0, 104), (104, 69, 104), (79, 0, 79), (79, 53, 79), (255, 0, 191), (255, 170, 234), (189, 0, 141), (189, 126, 173),
    (129, 0, 96), (129, 86, 118), (104, 0, 78), (104, 69, 95), (79, 0, 59), (79, 53, 73), (255, 0, 127), (255, 170, 212),
    (189, 0, 94), (189, 126, 157), (129, 0, 64), (129, 86, 107), (104, 0, 52), (104, 69, 86), (79, 0, 39), (79, 53, 66),
    (255, 0, 63), (255, 170, 191), (189, 0, 46), (189, 126, 141), (129, 0, 31), (129, 86, 96), (104, 0, 25), (104, 69, 78),
    (79, 0, 19), (79, 53, 59), (51, 51, 51), (80, 80, 80), (105, 105, 105), (130, 130, 130), (190, 190, 190), (255, 255, 255),
]


def _aci_to_drawing_color(aci_color):
    """ACI 0-255 -> System.Drawing.Color. None or out of range -> None."""
    if aci_color is None:
        return None
    try:
        from System.Drawing import Color
        aci_idx = min(max(int(aci_color), 0), 255)
        if aci_idx < len(_ACI_RGB):
            r, g, b = _ACI_RGB[aci_idx]
        else:
            r, g, b = (128, 128, 128)
        return Color.FromArgb(255, r, g, b)
    except Exception:
        return None


def _drawing_color_to_aci(draw_color):
    """System.Drawing.Color 또는 Rhino 색 -> 가장 가까운 ACI 0-255."""
    if draw_color is None:
        return None
    try:
        r = getattr(draw_color, "R", getattr(draw_color, "Red", 128))
        g = getattr(draw_color, "G", getattr(draw_color, "Green", 128))
        b = getattr(draw_color, "B", getattr(draw_color, "Blue", 128))
        if hasattr(r, "__call__"):
            r, g, b = int(r()), int(g()), int(b())
        else:
            r, g, b = int(r), int(g), int(b)
        best_aci = 0
        best_dist = 1e9
        for aci_idx in range(len(_ACI_RGB)):
            pr, pg, pb = _ACI_RGB[aci_idx]
            d = (r - pr) ** 2 + (g - pg) ** 2 + (b - pb) ** 2
            if d < best_dist:
                best_dist = d
                best_aci = aci_idx
        return best_aci
    except Exception:
        return None


def _ensure_layer(doc, layer_name, aci_color=None):
    """레이어 이름이 있으면 인덱스 반환, 없으면 생성 후 반환. aci_color: 1-255 ACI. 기존 레이어도 aci_color가 있으면 색상 갱신."""
    if not doc or not layer_name:
        return 0
    layer_table = doc.Layers
    idx = layer_table.Find(layer_name, True)
    if idx >= 0:
        if aci_color is not None and 1 <= aci_color <= 255:
            try:
                draw_color = _aci_to_drawing_color(aci_color)
                if draw_color is not None:
                    layer = layer_table[idx]
                    layer.Color = draw_color
                    layer_table.Modify(layer, idx, True)
            except Exception:
                pass
        return idx
    try:
        new_layer = Rhino.DocObjects.Layer()
        new_layer.Name = layer_name
        draw_color = _aci_to_drawing_color(aci_color)
        if draw_color is not None:
            new_layer.Color = draw_color
        idx = layer_table.Add(new_layer)
        return idx
    except Exception:
        return 0


def _geom_looks_closed_polygon(wkt):
    """WKT가 POLYGON, MULTIPOLYGON 또는 닫힌 LINESTRING(3점 이상, 시종점 일치)이면 True."""
    if not wkt or not isinstance(wkt, str):
        return False
    u = wkt.strip().upper()
    if u.startswith("POLYGON") or u.startswith("MULTIPOLYGON"):
        return True
    if u.startswith("LINESTRING"):
        try:
            m = re.match(r"LINESTRING\s*Z?\s*\(([^)]+)\)", wkt, re.I)
            if m:
                pts = [[float(x) for x in p.split()] for p in m.group(1).split(",")]
                if len(pts) >= 3 and len(pts[0]) >= 2 and len(pts[-1]) >= 2:
                    if abs(pts[0][0] - pts[-1][0]) <= 1e-9 and abs(pts[0][1] - pts[-1][1]) <= 1e-9:
                        return True
        except (ValueError, TypeError):
            pass
    return False


def _add_entity_from_wkt_to_doc(doc, entity_type, wkt, layer_name, layer_index, props, aci_color=None, color_from_layer=True, out_ids=None):
    """WKT + entity_type -> Rhino 문서에 객체 추가. out_ids가 리스트면 추가된 객체 Guid를 append."""
    if not wkt or "EMPTY" in wkt.upper():
        return 0
    wkt = wkt.strip()
    if re.match(r"^SRID=\d+;", wkt, re.I):
        wkt = re.sub(r"^SRID=\d+;\s*", "", wkt, flags=re.I)
    has_hatch_props = isinstance(props, dict) and (props.get("pattern_name") is not None or props.get("solid_fill") is not None)
    geom_closed = _geom_looks_closed_polygon(wkt)
    # 서버가 해치를 LWPOLYLINE/POLYLINE(경계만)으로 보낸 경우에도 닫힌 도형이면 해치로 시도
    effective_hatch = (
        (entity_type == "HATCH")
        or (has_hatch_props and geom_closed)
        or (geom_closed and (entity_type or "").upper() in ("LWPOLYLINE", "POLYLINE"))
    )
    added = 0
    attrs = Rhino.DocObjects.ObjectAttributes()
    attrs.LayerIndex = layer_index
    try:
        if color_from_layer:
            attrs.ColorSource = Rhino.DocObjects.ObjectColorSource.ColorFromLayer
        else:
            draw_color = _aci_to_drawing_color(aci_color)
            if draw_color is not None:
                attrs.ColorSource = Rhino.DocObjects.ObjectColorSource.ColorFromObject
                attrs.ObjectColor = draw_color
            else:
                attrs.ColorSource = Rhino.DocObjects.ObjectColorSource.ColorFromLayer
    except Exception:
        attrs.ColorSource = Rhino.DocObjects.ObjectColorSource.ColorFromLayer
    user_attrs = props.get("user_attrs") if isinstance(props, dict) else None
    if isinstance(user_attrs, dict):
        try:
            for k, v in user_attrs.items():
                attrs.SetUserString(str(k), str(v) if v is not None else "")
        except Exception:
            pass

    def add_curve(curve):
        if curve is None:
            return 0
        try:
            g = doc.Objects.Add(curve, attrs)
            if g is not None and str(g) != "00000000-0000-0000-0000-000000000000":
                if out_ids is not None:
                    out_ids.append(g)
                return 1
        except Exception:
            try:
                g = doc.Objects.AddCurve(curve, attrs)
                if g is not None and str(g) != "00000000-0000-0000-0000-000000000000":
                    if out_ids is not None:
                        out_ids.append(g)
                    return 1
            except Exception:
                pass
        return 0

    def pts_to_point3d(pts_2d):
        return [Rhino.Geometry.Point3d(p[0], p[1], 0.0) for p in pts_2d]

    def get_hatch_pattern_index():
        """props에서 pattern_name/solid_fill 읽어 해치 패턴 인덱스 반환."""
        pn = (props.get("pattern_name") or "SOLID").strip().upper() if isinstance(props, dict) else "SOLID"
        solid = props.get("solid_fill", True) if isinstance(props, dict) else True
        if solid or pn in ("SOLID", "SOLID_FILL", ""):
            idx = doc.HatchPatterns.Find("Solid", True)
            if idx >= 0:
                return idx
        idx = doc.HatchPatterns.Find(pn if pn else "Solid", True)
        if idx >= 0:
            return idx
        idx = doc.HatchPatterns.Find("Grid", True)
        if idx >= 0:
            return idx
        return 0 if doc.HatchPatterns.Count > 0 else -1

    def try_create_hatches(curves_or_single, pattern_index):
        """curves(list) or single curve로 Hatch.Create 시도. 성공 시 doc에 추가하고 추가된 개수 반환."""
        try:
            if isinstance(curves_or_single, list):
                curves_list = curves_or_single
                hatches = Rhino.Geometry.Hatch.Create(curves_list, pattern_index, 0, 1.0)
                if hatches is None and len(curves_list) == 1:
                    hatches = Rhino.Geometry.Hatch.Create(curves_list[0], pattern_index, 0, 1.0)
            else:
                hatches = Rhino.Geometry.Hatch.Create(curves_or_single, pattern_index, 0, 1.0)
            if hatches is None:
                return 0
            n = 0
            for hatch in hatches:
                g = doc.Objects.AddHatch(hatch)
                if g is not None and str(g) != "00000000-0000-0000-0000-000000000000":
                    robj = doc.Objects.Find(g)
                    if robj is not None:
                        robj.Attributes.LayerIndex = layer_index
                        if color_from_layer:
                            robj.Attributes.ColorSource = Rhino.DocObjects.ObjectColorSource.ColorFromLayer
                        elif aci_color is not None:
                            draw_color = _aci_to_drawing_color(aci_color)
                            if draw_color is not None:
                                robj.Attributes.ColorSource = Rhino.DocObjects.ObjectColorSource.ColorFromObject
                                robj.Attributes.ObjectColor = draw_color
                            else:
                                robj.Attributes.ColorSource = Rhino.DocObjects.ObjectColorSource.ColorFromLayer
                        else:
                            robj.Attributes.ColorSource = Rhino.DocObjects.ObjectColorSource.ColorFromLayer
                        robj.CommitChanges()
                    if out_ids is not None:
                        out_ids.append(g)
                    n += 1
            return n
        except Exception:
            return 0

    def try_hatch_then_fallback(curves_or_single, curve_list_for_fallback):
        """get_hatch_pattern_index()로 시도, 실패 시 Solid/Grid 재시도, 그래도 실패하면 add_curve."""
        pattern_index = get_hatch_pattern_index()
        if pattern_index >= 0:
            n = try_create_hatches(curves_or_single, pattern_index)
            if n > 0:
                return n
            for fallback_name in ("Solid", "Grid"):
                fidx = doc.HatchPatterns.Find(fallback_name, True)
                if fidx >= 0 and fidx != pattern_index:
                    n = try_create_hatches(curves_or_single, fidx)
                    if n > 0:
                        return n
        n = 0
        for pc in (curve_list_for_fallback if isinstance(curve_list_for_fallback, list) else [curve_list_for_fallback]):
            n += add_curve(pc)
        return n

    # MULTIPOLYGON 먼저 (POLYGON보다 먼저 체크)
    if wkt.upper().startswith("MULTIPOLYGON"):
        try:
            inner = wkt.replace("MULTIPOLYGON", "").strip().strip("()")
            if inner.startswith("("):
                inner = inner[1:]
            if inner.endswith(")"):
                inner = inner[:-1]
            poly_parts = re.split(r"\)\s*,\s*\(", inner)
            for poly_part in poly_parts:
                part = poly_part.strip().strip("()")
                rings = re.findall(r"\(([^()]+)\)", part)
                curves = []
                for ring_str in rings:
                    pts = [[float(x) for x in p.split()] for p in ring_str.split(",")]
                    if pts:
                        pts_2d = [p[:2] for p in pts]
                        pts3 = pts_to_point3d(pts_2d)
                        if len(pts3) > 1 and (abs(pts3[0].X - pts3[-1].X) > 1e-9 or abs(pts3[0].Y - pts3[-1].Y) > 1e-9):
                            pts3.append(pts3[0])
                        pl = Rhino.Geometry.Polyline(pts3)
                        pc = Rhino.Geometry.PolylineCurve(pl)
                        curves.append(pc)
                if curves and effective_hatch:
                    added += try_hatch_then_fallback(curves, curves)
                elif curves:
                    for pc in curves:
                        added += add_curve(pc)
        except (ValueError, TypeError):
            pass
        return added

    # POLYGON (HATCH는 주로 POLYGON으로 저장됨)
    m_poly = re.search(r"^POLYGON\s*Z?\s*\((.*)\)\s*$", wkt, re.I | re.DOTALL)
    if m_poly:
        try:
            poly_content = m_poly.group(1).strip()
            rings = re.findall(r"\(([^()]+)\)", poly_content)
            if rings:
                curves = []
                for ring_str in rings:
                    pts = [[float(x) for x in p.split()] for p in ring_str.split(",")]
                    if pts:
                        pts_2d = [p[:2] for p in pts]
                        pts3 = pts_to_point3d(pts_2d)
                        if len(pts3) > 1 and (abs(pts3[0].X - pts3[-1].X) > 1e-9 or abs(pts3[0].Y - pts3[-1].Y) > 1e-9):
                            pts3.append(pts3[0])
                        pl = Rhino.Geometry.Polyline(pts3)
                        pc = Rhino.Geometry.PolylineCurve(pl)
                        curves.append(pc)
                if curves and effective_hatch:
                    added += try_hatch_then_fallback(curves, curves)
                    if added > 0:
                        return added
                if curves:
                    for pc in curves:
                        added += add_curve(pc)
        except (ValueError, TypeError):
            pass
        return added

    # LINESTRING
    m_lin = re.match(r"LINESTRING\s*Z?\s*\(([^)]+)\)", wkt, re.I)
    if m_lin:
        try:
            pts = [[float(x) for x in p.split()] for p in m_lin.group(1).split(",")]
            if not pts:
                return 0
            pts_2d = [p[:2] for p in pts]
            pts3 = pts_to_point3d(pts_2d)
            closed = len(pts3) >= 3 and (abs(pts3[0].X - pts3[-1].X) <= 1e-9 and abs(pts3[0].Y - pts3[-1].Y) <= 1e-9)
            if effective_hatch and closed:
                if len(pts3) > 1 and (abs(pts3[0].X - pts3[-1].X) > 1e-9 or abs(pts3[0].Y - pts3[-1].Y) > 1e-9):
                    pts3 = list(pts3) + [pts3[0]]
                pl = Rhino.Geometry.Polyline(pts3)
                pc = Rhino.Geometry.PolylineCurve(pl)
                added += try_hatch_then_fallback(pc, pc)
                if added > 0:
                    return added
            elif entity_type == "LINE" and len(pts3) >= 2:
                line = Rhino.Geometry.LineCurve(pts3[0], pts3[1])
                added += add_curve(line)
            elif len(pts3) >= 2:
                pl = Rhino.Geometry.Polyline(pts3)
                pc = Rhino.Geometry.PolylineCurve(pl)
                added += add_curve(pc)
        except (ValueError, TypeError):
            pass
        return added

    # MULTILINESTRING
    if wkt.upper().startswith("MULTILINESTRING"):
        inner = wkt.replace("MULTILINESTRING", "").strip().strip("()")
        closed_curves = []
        open_parts = []
        for part in re.split(r"\)\s*,\s*\(", inner):
            part = part.strip("()")
            try:
                pts = [[float(x) for x in p.split()] for p in part.split(",")]
                if len(pts) >= 2:
                    pts_2d = [p[:2] for p in pts]
                    pts3 = pts_to_point3d(pts_2d)
                    if len(pts3) > 1 and (abs(pts3[0].X - pts3[-1].X) > 1e-9 or abs(pts3[0].Y - pts3[-1].Y) > 1e-9):
                        pts3.append(pts3[0])
                    pl = Rhino.Geometry.Polyline(pts3)
                    pc = Rhino.Geometry.PolylineCurve(pl)
                    if effective_hatch and len(pts3) >= 3:
                        closed_curves.append(pc)
                    else:
                        open_parts.append(pc)
            except (ValueError, TypeError):
                pass
        if effective_hatch and closed_curves:
            added += try_hatch_then_fallback(closed_curves, closed_curves)
            if added > 0:
                return added
        for pc in open_parts:
            added += add_curve(pc)
        return added

    # POINT / TEXT / MTEXT
    m_pt = re.match(r"POINT\s*Z?\s*\(([^)]+)\)", wkt, re.I)
    if m_pt:
        try:
            nums = [float(x) for x in m_pt.group(1).split()]
            if len(nums) >= 2:
                x, y = nums[0], nums[1]
                z = nums[2] if len(nums) >= 3 else 0.0
                pt = Rhino.Geometry.Point3d(x, y, z)
                if entity_type == "TEXT" or entity_type == "MTEXT":
                    text = (props.get("text") or "").strip()
                    if text:
                        height = 1.0
                        height_raw = props.get("height")
                        if height_raw is None:
                            height_raw = props.get("char_height")
                        if height_raw is not None:
                            try:
                                height = float(height_raw)
                            except (TypeError, ValueError):
                                pass
                        tx = _safe_float_or_none(props.get("text_align_x"))
                        ty = _safe_float_or_none(props.get("text_align_y"))
                        tz = _safe_float_or_none(props.get("text_align_z"))
                        if tx is None:
                            tx = _safe_float_or_none(props.get("insert_x"))
                        if ty is None:
                            ty = _safe_float_or_none(props.get("insert_y"))
                        if tz is None:
                            tz = _safe_float_or_none(props.get("insert_z"))
                        if tx is not None and ty is not None:
                            pt = Rhino.Geometry.Point3d(tx, ty, tz if tz is not None else z)

                        halign = _safe_int_or_none(props.get("halign"))
                        valign = _safe_int_or_none(props.get("valign"))
                        attachment_point = _safe_int_or_none(props.get("attachment_point"))
                        if (halign is None or valign is None) and attachment_point is not None:
                            halign, valign = _mtext_attachment_to_hv(attachment_point)
                        if halign is None:
                            halign = 0
                        if valign is None:
                            valign = 3 if entity_type == "MTEXT" else 0

                        rotation_deg = 0.0
                        rot_raw = props.get("rotation")
                        if rot_raw is not None:
                            try:
                                rotation_deg = float(rot_raw)
                            except (TypeError, ValueError):
                                rotation_deg = 0.0
                        try:
                            if abs(rotation_deg) > 1e-9:
                                import math
                                rad = math.radians(rotation_deg)
                                xaxis = Rhino.Geometry.Vector3d(math.cos(rad), math.sin(rad), 0.0)
                                yaxis = Rhino.Geometry.Vector3d(-math.sin(rad), math.cos(rad), 0.0)
                                plane = Rhino.Geometry.Plane(pt, xaxis, yaxis)
                            else:
                                plane = Rhino.Geometry.Plane(pt, Rhino.Geometry.Vector3d.ZAxis)
                            font = (props.get("style_name") or "Arial") if isinstance(props, dict) else "Arial"
                            id = None
                            try:
                                text_entity = Rhino.Geometry.TextEntity()
                                if hasattr(text_entity, "PlainText"):
                                    text_entity.PlainText = text
                                elif hasattr(text_entity, "Text"):
                                    text_entity.Text = text
                                if hasattr(text_entity, "Plane"):
                                    text_entity.Plane = plane
                                if hasattr(text_entity, "TextHeight"):
                                    text_entity.TextHeight = float(height)
                                elif hasattr(text_entity, "Height"):
                                    text_entity.Height = float(height)
                                try:
                                    if hasattr(doc, "Fonts"):
                                        fidx = doc.Fonts.FindOrCreate(font, False, False)
                                        if fidx is not None and int(fidx) >= 0 and hasattr(text_entity, "FontIndex"):
                                            text_entity.FontIndex = int(fidx)
                                except Exception:
                                    pass

                                just_enum = getattr(Rhino.Geometry, "TextJustification", None)
                                if just_enum is not None and hasattr(text_entity, "Justification"):
                                    vname = "Top" if valign == 3 else ("Middle" if valign == 2 else "Bottom")
                                    hname = "Center" if halign == 1 else ("Right" if halign == 2 else "Left")
                                    just = getattr(just_enum, vname + hname, None)
                                    if just is None:
                                        just = getattr(just_enum, "BottomLeft", None)
                                    if just is not None:
                                        text_entity.Justification = just

                                try:
                                    id = doc.Objects.AddText(text_entity, attrs)
                                except Exception:
                                    try:
                                        id = doc.Objects.AddText(text_entity)
                                    except Exception:
                                        id = None
                            except Exception:
                                id = None

                            if id is None or str(id) == "00000000-0000-0000-0000-000000000000":
                                id = doc.Objects.AddText(text, plane, height, font, False, False)
                            if id is not None and str(id) != "00000000-0000-0000-0000-000000000000":
                                if out_ids is not None:
                                    out_ids.append(id)
                                robj = doc.Objects.Find(id)
                                if robj is not None:
                                    robj.Attributes.LayerIndex = layer_index
                                    try:
                                        if color_from_layer:
                                            robj.Attributes.ColorSource = Rhino.DocObjects.ObjectColorSource.ColorFromLayer
                                        else:
                                            draw_color = _aci_to_drawing_color(aci_color)
                                            if draw_color is not None:
                                                robj.Attributes.ColorSource = Rhino.DocObjects.ObjectColorSource.ColorFromObject
                                                robj.Attributes.ObjectColor = draw_color
                                            else:
                                                robj.Attributes.ColorSource = Rhino.DocObjects.ObjectColorSource.ColorFromLayer
                                    except Exception:
                                        pass
                                    if isinstance(user_attrs, dict):
                                        try:
                                            for k, v in user_attrs.items():
                                                robj.Attributes.SetUserString(str(k), str(v) if v is not None else "")
                                        except Exception:
                                            pass
                                    robj.CommitChanges()
                                added += 1
                        except Exception:
                            dot = Rhino.Geometry.Point(pt)
                            g = doc.Objects.Add(dot, attrs)
                            if g is not None and str(g) != "00000000-0000-0000-0000-000000000000":
                                if out_ids is not None:
                                    out_ids.append(g)
                                added += 1
                    else:
                        dot = Rhino.Geometry.Point(pt)
                        g = doc.Objects.Add(dot, attrs)
                        if g is not None and str(g) != "00000000-0000-0000-0000-000000000000":
                            if out_ids is not None:
                                out_ids.append(g)
                            added += 1
                else:
                    dot = Rhino.Geometry.Point(pt)
                    g = doc.Objects.Add(dot, attrs)
                    if g is not None and str(g) != "00000000-0000-0000-0000-000000000000":
                        if out_ids is not None:
                            out_ids.append(g)
                        added += 1
        except (ValueError, TypeError):
            pass
        return added

    return added


def _parse_wkt_points(wkt):
    """WKT에서 좌표 리스트 추출. [(x,y)] 또는 [(x,y,z)]. LINESTRING/POINT/POLYGON 내부."""
    if not wkt or not wkt.strip():
        return []
    wkt = wkt.strip()
    if re.match(r"^SRID=\d+;", wkt, re.I):
        wkt = re.sub(r"^SRID=\d+;\s*", "", wkt, flags=re.I)
    points = []
    for m in re.finditer(r"\(([^)]+)\)", wkt):
        inner = m.group(1).strip()
        for part in re.split(r",\s*", inner):
            nums = re.findall(r"[-\d.eE]+", part)
            if len(nums) >= 2:
                x, y = float(nums[0]), float(nums[1])
                z = float(nums[2]) if len(nums) >= 3 else 0.0
                points.append((x, y, z))
    return points


def _transform_points_block_local_to_world(points, base_x, base_y, insert_x, insert_y, insert_z, scale_x, scale_y, scale_z, rotation_deg):
    """블록 로컬 점 -> 월드 좌표. CAD 규칙: world = insert + R( S * (local - base) )."""
    import math
    if not points:
        return []
    r = math.radians(float(rotation_deg or 0))
    c, s = math.cos(r), math.sin(r)
    sx = float(scale_x or 1) if scale_x not in (None, 0) else 1.0
    sy = float(scale_y or 1) if scale_y not in (None, 0) else 1.0
    sz = float(scale_z or 1) if scale_z not in (None, 0) else 1.0
    bx, by = float(base_x or 0), float(base_y or 0)
    ix, iy = float(insert_x or 0), float(insert_y or 0)
    iz = float(insert_z if insert_z is not None else 0)
    out = []
    for pt in points:
        lx = float(pt[0]) if len(pt) >= 1 else 0.0
        ly = float(pt[1]) if len(pt) >= 2 else 0.0
        lz = float(pt[2]) if len(pt) >= 3 else 0.0
        dx = (lx - bx) * sx
        dy = (ly - by) * sy
        wx = ix + dx * c - dy * s
        wy = iy + dx * s + dy * c
        wz = iz + lz * sz
        out.append((wx, wy, wz))
    return out


def _wkt_block_local_to_world(wkt, base_x, base_y, insert_x, insert_y, insert_z, scale_x, scale_y, scale_z, rotation_deg):
    """블록 로컬 WKT -> 월드 WKT. base=블록기준점(0,0)."""
    if not wkt or "EMPTY" in wkt.upper():
        return wkt
    pts = _parse_wkt_points(wkt)
    if not pts:
        return wkt
    out = _transform_points_block_local_to_world(pts, base_x, base_y, insert_x, insert_y, insert_z, scale_x, scale_y, scale_z, rotation_deg)
    if not out:
        return wkt
    wkt_upper = (wkt or "").upper().strip()
    if len(out) == 1:
        return "POINT Z ({0} {1} {2})".format(out[0][0], out[0][1], out[0][2])
    pts_str = ", ".join("{0} {1} {2}".format(p[0], p[1], p[2]) for p in out)
    if wkt_upper.startswith("POLYGON"):
        return "POLYGON Z (({0}))".format(pts_str)
    return "LINESTRING Z ({0})".format(pts_str)


def _transform_points_to_block_local(points, insert_x, insert_y, insert_z, scale_x, scale_y, rotation_deg, base_x, base_y):
    """점 리스트를 월드->블록로컬 역변환. block_local = base + inv(S)*inv(R)*(world - insert). Z는 insert_z 기준 보존."""
    import math
    if not points:
        return []
    r = math.radians(float(rotation_deg or 0))
    c, s = math.cos(r), math.sin(r)
    sx = float(scale_x or 1) if scale_x not in (None, 0) else 1.0
    sy = float(scale_y or 1) if scale_y not in (None, 0) else 1.0
    bx, by = float(base_x or 0), float(base_y or 0)
    ix, iy = float(insert_x or 0), float(insert_y or 0)
    iz = float(insert_z if insert_z is not None else 0)
    out = []
    for (wx, wy, wz) in points:
        dx = (wx - ix) * c + (wy - iy) * s
        dy = -(wx - ix) * s + (wy - iy) * c
        local_z = wz - iz
        out.append((bx + dx / sx, by + dy / sy, local_z))
    return out


def _wkt_world_to_block_local(wkt, insert_x, insert_y, insert_z, scale_x, scale_y, rotation_deg, base_x, base_y):
    """월드 좌표 WKT를 블록 로컬 좌표 WKT로 역변환. rotation_deg: 도 단위. Z는 insert_z 기준. MULTILINESTRING은 링별 보존."""
    if not wkt or "EMPTY" in wkt.upper():
        return wkt
    iz = insert_z if insert_z is not None else 0.0
    wkt_upper = wkt.upper().strip()
    if wkt_upper.startswith("MULTILINESTRING"):
        parts = []
        inner = wkt.replace("MULTILINESTRING", "").strip().strip("()")
        for part in re.split(r"\)\s*,\s*\(", inner):
            part = part.strip("()").strip()
            if not part:
                continue
            pts = []
            for p in part.split(","):
                nums = re.findall(r"[-\d.eE]+", p.strip())
                if len(nums) >= 2:
                    x, y = float(nums[0]), float(nums[1])
                    z = float(nums[2]) if len(nums) >= 3 else 0.0
                    pts.append((x, y, z))
            if len(pts) >= 2:
                out = _transform_points_to_block_local(pts, insert_x, insert_y, iz, scale_x, scale_y, rotation_deg, base_x, base_y)
                if out:
                    parts.append("({0})".format(", ".join("{0} {1} {2}".format(p[0], p[1], p[2]) for p in out)))
        if parts:
            return "MULTILINESTRING Z (" + ", ".join(parts) + ")"
        return wkt
    if wkt_upper.startswith("POLYGON"):
        idx_open = wkt.find("((")
        idx_close = wkt.rfind("))")
        if idx_open >= 0 and idx_close > idx_open:
            inner = wkt[idx_open + 2:idx_close].strip()
            ring_parts = re.split(r"\)\s*,\s*\(", inner)
            rings_out = []
            for part in ring_parts:
                part = part.strip().strip("()").strip()
                if not part:
                    continue
                pts = []
                for p in part.split(","):
                    nums = re.findall(r"[-\d.eE]+", p.strip())
                    if len(nums) >= 2:
                        x, y = float(nums[0]), float(nums[1])
                        z = float(nums[2]) if len(nums) >= 3 else 0.0
                        pts.append((x, y, z))
                if len(pts) >= 2:
                    out = _transform_points_to_block_local(pts, insert_x, insert_y, iz, scale_x, scale_y, rotation_deg, base_x, base_y)
                    if out:
                        rings_out.append("({0})".format(", ".join("{0} {1} {2}".format(p[0], p[1], p[2]) for p in out)))
            if rings_out:
                return "POLYGON Z (" + ", ".join(rings_out) + ")"
    points = _parse_wkt_points(wkt)
    if not points:
        return wkt
    out = _transform_points_to_block_local(points, insert_x, insert_y, iz, scale_x, scale_y, rotation_deg, base_x, base_y)
    if len(out) == 1:
        return "POINT Z ({0} {1} {2})".format(out[0][0], out[0][1], out[0][2])
    pts_str = ", ".join("{0} {1} {2}".format(p[0], p[1], p[2]) for p in out)
    if wkt_upper.startswith("POLYGON"):
        return "POLYGON Z (({0}))".format(pts_str)
    return "LINESTRING Z ({0})".format(pts_str)


def _point_from_wkt(wkt):
    """WKT POINT에서 (x, y) 추출. 실패 시 (0, 0)."""
    pts = _parse_wkt_points(wkt or "")
    if pts:
        return (pts[0][0], pts[0][1])
    return (0.0, 0.0)


def _point3d_from_geom(val):
    """API 응답의 insert_point/base_point 등에서 (x, y, z) -> Rhino.Geometry.Point3d. WKT/리스트/딕셔너리 지원."""
    x, y, z = 0.0, 0.0, 0.0
    if val is None:
        return Rhino.Geometry.Point3d(x, y, z)
    if isinstance(val, (list, tuple)) and len(val) >= 2:
        try:
            x, y = float(val[0]), float(val[1])
            z = float(val[2]) if len(val) >= 3 else 0.0
            return Rhino.Geometry.Point3d(x, y, z)
        except (TypeError, ValueError):
            pass
    if isinstance(val, dict):
        coords = val.get("coordinates")
        if isinstance(coords, (list, tuple)) and len(coords) >= 2:
            try:
                x, y = float(coords[0]), float(coords[1])
                z = float(coords[2]) if len(coords) >= 3 else 0.0
                return Rhino.Geometry.Point3d(x, y, z)
            except (TypeError, ValueError):
                pass
    if isinstance(val, str) and val.strip():
        pts = _parse_wkt_points(val)
        if pts:
            x, y = pts[0][0], pts[0][1]
            z = pts[0][2] if len(pts[0]) >= 3 else 0.0
            return Rhino.Geometry.Point3d(x, y, z)
    return Rhino.Geometry.Point3d(x, y, z)


def _point_from_geom(val):
    """API 응답의 insert_point/base_point 등에서 (x, y) 추출. WKT 문자열, GeoJSON dict, [x,y] 리스트 지원. 실패 시 (0, 0)."""
    if val is None:
        return (0.0, 0.0)
    if isinstance(val, (list, tuple)) and len(val) >= 2:
        try:
            return (float(val[0]), float(val[1]))
        except (TypeError, ValueError):
            pass
    if isinstance(val, dict):
        coords = val.get("coordinates")
        if isinstance(coords, (list, tuple)) and len(coords) >= 2:
            try:
                return (float(coords[0]), float(coords[1]))
            except (TypeError, ValueError):
                pass
        if "x" in val and "y" in val:
            try:
                return (float(val["x"]), float(val["y"]))
            except (TypeError, ValueError):
                pass
    if isinstance(val, str) and val.strip():
        return _point_from_wkt(val)
    return (0.0, 0.0)


def _entities_to_rhino(entities_list, layer_colors):
    """API entities JSON 목록을 현재 문서에 Rhino 객체로 추가. layer_colors: 레이어별 ACI 색상 dict. entity id 중복은 한 번만 추가."""
    doc = scriptcontext.doc
    if doc is None:
        return 0
    layer_colors = layer_colors or {}
    total = 0
    added_ids = set()
    for ent in entities_list:
        eid = ent.get("id")
        if eid is not None and eid in added_ids:
            continue
        if eid is not None:
            added_ids.add(eid)
        geom = ent.get("geom")
        entity_type = (ent.get("entity_type") or "LINE").strip().upper() or "LINE"
        layer = (ent.get("layer") or "0").strip() or "0"
        color = ent.get("color")
        if color is None and layer in layer_colors:
            color = layer_colors[layer]
        props = dict(ent.get("props") or {})
        user_attrs = dict(props.get("user_attrs") or {})
        block_name = ent.get("block_name")
        block_variant = ent.get("block_variant") if ent.get("block_variant") is not None else ent.get("block_insert_id")
        block_index = ent.get("block_index")
        if block_variant is not None:
            user_attrs["BLOCK_NAME"] = str(block_name) if block_name else str(block_variant)
            if block_index is not None:
                user_attrs["BLOCK_INDEX"] = str(block_index)
            user_attrs["BLOCK_VARIANT"] = str(block_variant)
        if user_attrs:
            props["user_attrs"] = user_attrs
        color_from_layer = props.get("color_bylayer") is not False
        layer_index = _ensure_layer(doc, layer, layer_colors.get(layer) or color)
        n = _add_entity_from_wkt_to_doc(doc, entity_type, geom, layer, layer_index, props, aci_color=color, color_from_layer=color_from_layer)
        total += n
    return total


def _block_defs_and_inserts_to_rhino(doc, block_defs, block_inserts, layer_colors):
    """블록 정의/배치를 Rhino InstanceDefinition + InstanceObject로 추가해 블록 단위 선택 가능하게 함. 반환: (추가된 블록참조 수, block_name->idef_index)."""
    if doc is None or not block_defs:
        return (0, {})
    layer_colors = layer_colors or {}
    name_to_index = {}
    temp_layer_name = "_CadManageBlockTemp"
    temp_layer_index = _ensure_layer(doc, temp_layer_name, None)

    for bd in block_defs:
        name = (bd.get("name") or "").strip()
        if not name:
            continue
        entities_in_def = (bd.get("props") or {}).get("entities") or []
        if not entities_in_def:
            continue
        base_pt = _point3d_from_geom(bd.get("base_point"))
        out_ids = []
        for ent in entities_in_def:
            wkt = ent.get("geom_wkt") or ent.get("geom")
            if not wkt:
                continue
            etype = (ent.get("entity_type") or "LINE").strip().upper() or "LINE"
            layer = (ent.get("layer") or "0").strip()
            color = ent.get("color")
            props = dict(ent.get("props") or {})
            layer_idx = _ensure_layer(doc, layer if layer else "0", layer_colors.get(layer) or color)
            _add_entity_from_wkt_to_doc(doc, etype, wkt, layer or "0", layer_idx, props, aci_color=color, color_from_layer=True, out_ids=out_ids)
        if not out_ids:
            continue
        geoms = []
        attrs = []
        try:
            for guid in out_ids:
                obj = doc.Objects.Find(guid)
                if obj is not None and obj.Geometry is not None:
                    geoms.append(obj.Geometry.Duplicate())
                    attrs.append(obj.Attributes.Duplicate())
            if geoms and attrs and len(geoms) == len(attrs):
                idef_index = doc.InstanceDefinitions.Add(name, "", base_pt, geoms, attrs)
                if idef_index >= 0:
                    name_to_index[name] = idef_index
        except Exception as e:
            _debug("InstanceDefinition Add {}: {}".format(name, e))
        for guid in out_ids:
            try:
                doc.Objects.Delete(guid, True)
            except Exception:
                pass

    added = 0
    for bi in (block_inserts or []):
        block_name = (bi.get("block_name") or "").strip()
        idef_index = name_to_index.get(block_name)
        if idef_index is None or idef_index < 0:
            continue
        insert_pt = _point3d_from_geom(bi.get("insert_point"))
        rot = float(bi.get("rotation") or 0)
        sx = float(bi.get("scale_x") or 1) if bi.get("scale_x") is not None else 1.0
        sy = float(bi.get("scale_y") or 1) if bi.get("scale_y") is not None else 1.0
        sz = float(bi.get("scale_z") or 1) if bi.get("scale_z") is not None else 1.0
        try:
            t = Rhino.Geometry.Transform.Identity
            if rot != 0:
                t = Rhino.Geometry.Transform.Rotation(rot * (3.141592653589793 / 180.0), Rhino.Geometry.Vector3d.ZAxis, Rhino.Geometry.Point3d.Origin)
            if sx != 1 or sy != 1 or sz != 1:
                scale_t = Rhino.Geometry.Transform.Scale(Rhino.Geometry.Point3d.Origin, sx, sy, sz)
                t = t * scale_t
            t = Rhino.Geometry.Transform.Translation(Rhino.Geometry.Vector3d(insert_pt.X, insert_pt.Y, insert_pt.Z)) * t
            guid = doc.Objects.AddInstanceObject(idef_index, t)
            if guid is not None and str(guid) != "00000000-0000-0000-0000-000000000000":
                added += 1
                obj = doc.Objects.Find(guid)
                if obj is not None:
                    layer_name = (bi.get("layer") or "0").strip() or "0"
                    layer_idx = _ensure_layer(doc, layer_name, layer_colors.get(layer_name) or bi.get("color"))
                    color = bi.get("color")
                    try:
                        obj.Attributes.LayerIndex = layer_idx
                        if color is not None and 1 <= color <= 255:
                            draw_color = _aci_to_drawing_color(color)
                            if draw_color is not None:
                                obj.Attributes.ColorSource = Rhino.DocObjects.ObjectColorSource.ColorFromObject
                                obj.Attributes.ObjectColor = draw_color
                        doc.Objects.Modify(obj, guid, True)
                    except Exception:
                        pass
        except Exception as e:
            _debug("AddInstanceObject {}: {}".format(block_name, e))

    try:
        doc.Layers.Delete(temp_layer_index, True)
    except Exception:
        pass
    return (added, name_to_index)


def _fetch_json(api_base, path, timeout=60):
    """GET api_base + path, return parsed JSON or None. IronPython compatible."""
    url = (api_base.rstrip("/") + "/" + path.lstrip("/"))
    try:
        if sys.version_info[0] >= 3:
            from urllib.request import urlopen, Request
            from urllib.error import URLError, HTTPError
        else:
            from urllib2 import urlopen, Request, URLError, HTTPError
        req = Request(url, headers={"Accept": "application/json", "User-Agent": "CadManage-Rhino/1.0"})
        resp = urlopen(req, timeout=timeout)
        body = resp.read().decode("utf-8", errors="replace")
        return json.loads(body)
    except Exception as e:
        _debug("_fetch_json {} 실패: {}".format(url, e))
        print("API 요청 실패:", e)
        return None


def _interactive_load_from_api(api_base):
    """API에서 프로젝트 목록 -> 커밋 목록 선택 후 해당 커밋을 현재 문서에 로드."""
    api_base = (api_base or "").rstrip("/")
    if not api_base:
        print("API 주소가 없습니다.")
        return
    if scriptcontext.doc is None:
        print("문서가 열려 있지 않습니다. 새 문서를 연 뒤 다시 시도하세요.")
        return
    try:
        if sys.version_info[0] >= 3:
            from urllib.request import urlopen, Request
            from urllib.error import URLError, HTTPError
        else:
            from urllib2 import urlopen, Request, URLError, HTTPError
    except Exception:
        pass
    print("CadManage 가져오기 — DB에서 불러올 프로젝트·버전을 선택하세요.")
    projects = _fetch_json(api_base, "/api/projects")
    if not projects or not isinstance(projects, list):
        print("프로젝트 목록을 가져오지 못했습니다. 서버 주소와 서버 상태를 확인하세요.")
        return
    if len(projects) == 0:
        print("프로젝트가 없습니다.")
        return
    lines = []
    for i, p in enumerate(projects):
        idx = i + 1
        pid = p.get("id")
        name = (p.get("name") or "").strip() or "(이름 없음)"
        code = (p.get("code") or "").strip()
        lines.append("{0}= {1} (code: {2})".format(idx, name, code or "-"))
    print("프로젝트: " + " | ".join(lines))
    default_p = "1"
    result = Rhino.Input.RhinoGet.GetString("프로젝트 번호 입력 (1-{})".format(len(projects)), False, default_p)
    if result[0] != Rhino.Commands.Result.Success:
        return
    try:
        pnum = int((result[1] or default_p).strip())
        if pnum < 1 or pnum > len(projects):
            print("잘못된 번호입니다.")
            return
        project = projects[pnum - 1]
        project_id = int(project.get("id"))
    except (ValueError, TypeError):
        print("숫자를 입력하세요.")
        return
    commits_data = _fetch_json(api_base, "/api/projects/{0}/commits".format(project_id))
    if not commits_data:
        print("버전 목록을 가져오지 못했습니다.")
        return
    commits = commits_data.get("commits") if isinstance(commits_data, dict) else commits_data
    if not commits or not isinstance(commits, list):
        print("버전 목록이 비어 있습니다.")
        return
    lines = []
    for i, c in enumerate(commits):
        idx = i + 1
        cid = c.get("id")
        label = (c.get("version_label") or "").strip() or "(버전 없음)"
        lines.append("{0}= {1} (id:{2})".format(idx, label, cid))
    print("버전: " + " | ".join(lines[:10]) + (" ..." if len(lines) > 10 else ""))
    default_c = "1"
    result = Rhino.Input.RhinoGet.GetString("버전 번호 입력 (1-{})".format(len(commits)), False, default_c)
    if result[0] != Rhino.Commands.Result.Success:
        return
    try:
        cnum = int((result[1] or default_c).strip())
        if cnum < 1 or cnum > len(commits):
            print("잘못된 번호입니다.")
            return
        commit = commits[cnum - 1]
        commit_id = int(commit.get("id"))
    except (ValueError, TypeError):
        print("숫자를 입력하세요.")
        return
    info = {"api_base": api_base, "project_id": project_id, "commit_id": commit_id}
    _do_open_from_info_impl(info)


def _do_open_from_info(info):
    """연동 정보 dict로 DB 엔티티를 받아 현재 문서에 객체로 불러오기. project/commit 없으면 API에서 선택."""
    debug_path = _debug_log_path()
    try:
        if os.path.exists(debug_path):
            os.remove(debug_path)
    except Exception:
        pass
    api_base = (info.get("api_base") or "").rstrip("/")
    project_id = info.get("project_id")
    commit_id = info.get("commit_id")
    if project_id is not None and commit_id is not None and api_base:
        try:
            _do_open_from_info_impl(info)
        except Exception as e:
            _debug("예외 발생: {}".format(e))
            import traceback
            _debug(traceback.format_exc())
            print("CadManage Open 실패:", e)
            print("디버그 로그: {}".format(debug_path))
    elif api_base:
        try:
            _interactive_load_from_api(api_base)
        except Exception as e:
            _debug("예외 발생: {}".format(e))
            import traceback
            _debug(traceback.format_exc())
            print("CadManage Open 실패:", e)
            print("디버그 로그: {}".format(debug_path))
    else:
        print("api_base가 필요합니다. launch.json 또는 연동 정보에 서버 주소가 있어야 합니다.")
    _debug("=== CadManage Open 종료 ===")


def _do_open_from_info_impl(info):
    _debug("=== CadManage Open 시작 ===")
    _debug("입력 info: {}".format(info))
    try:
        _debug("scriptcontext.doc: {}".format(scriptcontext.doc))
    except Exception as ex:
        _debug("scriptcontext.doc 확인 실패: {}".format(ex))

    api_base = (info.get("api_base") or "").rstrip("/")
    project_id = info.get("project_id")
    commit_id = info.get("commit_id")
    if not api_base or project_id is None or commit_id is None:
        _debug("오류: api_base, project_id, commit_id 가 필요합니다.")
        return
    url = "{0}/api/commits/{1}/entities".format(api_base, int(commit_id))
    _debug("요청 URL: {}".format(url))

    try:
        if sys.version_info[0] >= 3:
            from urllib.request import urlopen, Request
            from urllib.error import URLError, HTTPError
        else:
            from urllib2 import urlopen, Request, URLError, HTTPError
        req = Request(url, headers={"Accept": "application/json", "User-Agent": "CadManage-Rhino/1.0"})
        resp = urlopen(req, timeout=120)
        body = resp.read().decode("utf-8", errors="replace")
        data = json.loads(body)
    except HTTPError as e:
        _debug("API HTTP 오류: {} {}".format(e.code, e.reason))
        try:
            err_body = e.read().decode("utf-8", errors="replace")
            _debug("응답 본문(앞 800자): {}".format(err_body[:800]))
            if err_body:
                print(err_body[:500])
            if e.code == 404 and "Commit not found" in err_body:
                print("해당 버전(커밋 ID {})이 서버에 없습니다. 웹에서 프로젝트/버전 목록을 확인하거나, 서버가 켜져 있고 같은 DB를 쓰는지 확인하세요.".format(commit_id))
        except Exception as ex:
            _debug("응답 읽기 실패: {}".format(ex))
        return
    except URLError as e:
        _debug("연결 실패: {}".format(e.reason))
        print("연결 실패:", e.reason)
        return
    except Exception as e:
        _debug("엔티티 조회 예외: {}".format(e))
        import traceback
        _debug(traceback.format_exc())
        print("엔티티 조회 실패:", e)
        return

    entities = data.get("entities") or []

    layer_colors = data.get("layer_colors") or {}
    _debug("엔티티 수: {}".format(len(entities)))

    block_defs = []
    block_inserts = []
    blocks_data = _fetch_json(api_base, "/api/commits/{0}/blocks/defs".format(int(commit_id)))
    if blocks_data and isinstance(blocks_data, dict):
        block_defs = blocks_data.get("defs") or []
    inserts_data = _fetch_json(api_base, "/api/commits/{0}/blocks/inserts".format(int(commit_id)))
    if inserts_data and isinstance(inserts_data, dict):
        block_inserts = inserts_data.get("inserts") or []
    _debug("블록 정의: {}개, 블록 배치: {}개".format(len(block_defs), len(block_inserts)))

    root_entities = [e for e in entities if e.get("block_insert_id") is None and e.get("block_variant") is None]
    _debug("루트 엔티티(블록 외): {}개".format(len(root_entities)))

    link_data = {"api_base": api_base, "project_id": int(project_id), "parent_commit_id": int(commit_id)}
    if scriptcontext.doc is not None:
        _save_link(link_data)
    try:
        link_path = os.path.join(tempfile.gettempdir(), "_cadmanage_link.json")
        with codecs.open(link_path, "w", "utf-8") as f:
            json.dump(link_data, f, ensure_ascii=False, indent=2)
        _debug("연동 정보 저장: {}".format(link_path))
    except Exception as ex:
        _debug("연동 정보 저장 실패: {}".format(ex))

    if scriptcontext.doc is None:
        print("문서가 열려 있지 않습니다. 라이노에서 새 문서를 연 뒤 다시 '라이노에서 열기'를 시도하세요.")
        _debug("=== CadManage Open 종료 (문서 없음) ===")
        return

    doc = scriptcontext.doc
    block_count = 0
    if block_defs and block_inserts:
        block_count, _ = _block_defs_and_inserts_to_rhino(doc, block_defs, block_inserts, layer_colors)
        _debug("블록 참조 {}개 추가 (블록 단위 선택 가능)".format(block_count))
    root_count = _entities_to_rhino(root_entities, layer_colors)
    total = block_count + root_count
    print("도면 불러오기 완료. 객체 {}개 추가됨 (블록 {}개는 블록 단위로 선택 가능).".format(total, block_count))
    _debug("추가된 객체 수: 블록참조={}, 루트엔티티={}".format(block_count, root_count))
    _activate_rhino_view_and_zoom_extents()
    _debug("=== CadManage Open 종료 ===")


def CadManageOpen():
    """가져오기: 서버 API에서 프로젝트·버전을 선택해 현재 문서에 객체로 불러옵니다."""
    default_base = "http://127.0.0.1:8000"
    result = Rhino.Input.RhinoGet.GetString("서버 주소 (가져오기용, Enter=기본값)", False, default_base)
    if result[0] != Rhino.Commands.Result.Success:
        return
    api_base = (result[1] or default_base).strip()
    if not api_base:
        api_base = default_base
    _interactive_load_from_api(api_base)


def CadManageListen():
    """웹 '라이노에서 열기' 연동 대기. 켜 두고 웹에서 열기를 누르면 launch.json을 읽어 해당 버전이 열립니다.
    최대 약 30초 동안 2초 간격으로 확인 후 없으면 종료.
    """
    launch_path = _launch_file_path()
    poll_interval = 2.0
    poll_count = 15
    for i in range(poll_count):
        if os.path.exists(launch_path):
            try:
                info = _read_launch_json(launch_path)
                try:
                    os.remove(launch_path)
                except Exception:
                    pass
                print("연동 요청 수신. DB에서 객체 불러오는 중...")
                _do_open_from_info(info)
                return
            except Exception as e:
                print("연동 처리 실패:", e)
                return
        if i == 0:
            print("웹에서 '라이노에서 열기'를 누르세요. (최대 {0}초 대기)".format(int(poll_interval * poll_count)))
        time.sleep(poll_interval)
    print("대기 시간이 지났습니다. 웹에서 '라이노에서 열기'를 누른 뒤 다시 CadManageListen을 실행하세요.")


def _point_wkt(x, y, z=0.0):
    return "POINT Z({0} {1} {2})".format(x, y, z)


def _linestring_wkt(points):
    if not points:
        return None
    parts = []
    for p in points:
        if len(p) >= 3:
            parts.append("{0} {1} {2}".format(p[0], p[1], p[2]))
        elif len(p) >= 2:
            parts.append("{0} {1} 0".format(p[0], p[1]))
        else:
            continue
    if not parts:
        return None
    return "LINESTRING Z(" + ",".join(parts) + ")"


def _is_text_entity_geometry(geom):
    if geom is None:
        return False
    try:
        if hasattr(Rhino.Geometry, "TextEntity") and isinstance(geom, Rhino.Geometry.TextEntity):
            return True
    except Exception:
        pass
    try:
        tname = type(geom).__name__
        return tname == "TextEntity" or "TextEntity" in (getattr(type(geom), "FullName", None) or "")
    except Exception:
        return False


def _text_entity_point(geom):
    if geom is None:
        return None
    try:
        plane = getattr(geom, "Plane", None)
        if plane is not None:
            origin = getattr(plane, "Origin", None)
            if origin is not None:
                return Rhino.Geometry.Point3d(float(origin.X), float(origin.Y), float(origin.Z))
    except Exception:
        pass
    try:
        bbox = geom.GetBoundingBox(True)
        if bbox is not None and bbox.IsValid:
            return Rhino.Geometry.Point3d(
                (bbox.Min.X + bbox.Max.X) / 2.0,
                (bbox.Min.Y + bbox.Max.Y) / 2.0,
                (bbox.Min.Z + bbox.Max.Z) / 2.0,
            )
    except Exception:
        pass
    return None


def _text_entity_text(geom):
    if geom is None:
        return ""
    for attr in ("PlainText", "Text", "RichText"):
        try:
            raw = getattr(geom, attr, None)
            if raw is None:
                continue
            text = str(raw).replace("\r\n", "\n").replace("\r", "\n")
            if text.strip():
                return text.strip()
        except Exception:
            pass
    return ""


def _text_entity_height(geom):
    if geom is None:
        return None
    for attr in ("TextHeight", "Height"):
        try:
            h = getattr(geom, attr, None)
            if h is None:
                continue
            hf = float(h)
            if hf > 0:
                return hf
        except Exception:
            pass
    return None


def _safe_int_or_none(v):
    try:
        if v is None:
            return None
        return int(v)
    except (TypeError, ValueError):
        return None


def _safe_float_or_none(v):
    try:
        if v is None:
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def _mtext_attachment_to_hv(attachment_point):
    mapping = {
        1: (0, 3),
        2: (1, 3),
        3: (2, 3),
        4: (0, 2),
        5: (1, 2),
        6: (2, 2),
        7: (0, 1),
        8: (1, 1),
        9: (2, 1),
    }
    return mapping.get(_safe_int_or_none(attachment_point), (0, 3))


def _hv_to_mtext_attachment(halign, valign):
    hv = (_safe_int_or_none(halign), _safe_int_or_none(valign))
    reverse = {
        (0, 3): 1,
        (1, 3): 2,
        (2, 3): 3,
        (0, 2): 4,
        (1, 2): 5,
        (2, 2): 6,
        (0, 1): 7,
        (1, 1): 8,
        (2, 1): 9,
    }
    return reverse.get(hv, 1)


def _alignment_from_text_justification(justification, is_mtext):
    if justification is None:
        if is_mtext:
            return (0, 3)
        return (0, 0)
    try:
        s = str(justification).upper()
    except Exception:
        if is_mtext:
            return (0, 3)
        return (0, 0)
    halign = 0
    if "CENTER" in s:
        halign = 1
    elif "RIGHT" in s:
        halign = 2
    elif "MIDDLE" in s and "LEFT" not in s and "RIGHT" not in s:
        halign = 1
    valign = 0
    if "TOP" in s:
        valign = 3
    elif "MIDDLE" in s:
        valign = 2
    elif "BOTTOM" in s:
        valign = 1
    elif "BASE" in s:
        valign = 0
    elif is_mtext:
        valign = 3
    return (halign, valign)


def _text_entity_alignment_info(geom, is_mtext):
    if is_mtext:
        halign, valign = 0, 3
    else:
        halign, valign = 0, 0
    try:
        h_raw = getattr(geom, "TextHorizontalAlignment", None)
        v_raw = getattr(geom, "TextVerticalAlignment", None)
        h_i = _safe_int_or_none(h_raw)
        v_i = _safe_int_or_none(v_raw)
        if h_i is not None:
            halign = max(0, min(2, h_i))
        if v_i is not None:
            valign = max(0, min(3, v_i))
    except Exception:
        pass
    try:
        just = getattr(geom, "Justification", None)
        h2, v2 = _alignment_from_text_justification(just, is_mtext)
        halign = h2
        valign = v2
    except Exception:
        pass
    attachment_point = _hv_to_mtext_attachment(halign, valign) if is_mtext else None
    return (halign, valign, attachment_point)


def _text_entity_rotation_deg(geom):
    if geom is None:
        return None
    try:
        plane = getattr(geom, "Plane", None)
        if plane is not None:
            xaxis = getattr(plane, "XAxis", None)
            if xaxis is not None:
                import math
                return math.degrees(math.atan2(float(xaxis.Y), float(xaxis.X)))
    except Exception:
        pass
    return None


def _rhino_text_entity_to_wkt(geom):
    if not _is_text_entity_geometry(geom):
        return (None, None, None)
    pt = _text_entity_point(geom)
    if pt is None:
        return (None, None, None)
    text = _text_entity_text(geom)
    is_mtext = "\n" in text
    props = {"text": text}
    halign, valign, attachment_point = _text_entity_alignment_info(geom, is_mtext)
    props["halign"] = halign
    props["valign"] = valign
    if attachment_point is not None:
        props["attachment_point"] = attachment_point
    props["insert_x"] = float(pt.X)
    props["insert_y"] = float(pt.Y)
    props["insert_z"] = float(pt.Z)
    props["text_align_x"] = float(pt.X)
    props["text_align_y"] = float(pt.Y)
    props["text_align_z"] = float(pt.Z)
    h = _text_entity_height(geom)
    if h is not None:
        if is_mtext:
            props["char_height"] = h
            props["height"] = h
        else:
            props["height"] = h
    try:
        font_obj = getattr(geom, "Font", None)
        face = getattr(font_obj, "FaceName", None) if font_obj is not None else None
        if face:
            props["style_name"] = str(face)
    except Exception:
        pass
    rot = _text_entity_rotation_deg(geom)
    if rot is not None:
        props["rotation"] = rot
    etype = "MTEXT" if is_mtext else "TEXT"
    return (_point_wkt(pt.X, pt.Y, pt.Z), etype, props)


def _rhino_geometry_to_wkt(geom):
    if geom is None:
        return (None, None, None)
    try:
        if isinstance(geom, Rhino.Geometry.LineCurve):
            start, end = geom.PointAtStart, geom.PointAtEnd
            wkt = _linestring_wkt([(start.X, start.Y, start.Z), (end.X, end.Y, end.Z)])
            return (wkt, "LINE", None)
        if isinstance(geom, Rhino.Geometry.PolylineCurve):
            pl = geom.TryGetPolyline()
            if pl[0] and pl[1] is not None:
                pts = [(p.X, p.Y, p.Z) for p in pl[1]]
                return (_linestring_wkt(pts), "LWPOLYLINE", None)
        if isinstance(geom, Rhino.Geometry.ArcCurve):
            arc = geom.Arc
            if arc.IsCircle:
                import math
                pts = []
                for i in range(65):
                    t = i / 64.0 * 2.0 * math.pi
                    p = arc.PointAt(t)
                    pts.append((p.X, p.Y, p.Z))
                return (_linestring_wkt(pts), "CIRCLE", None)
            else:
                segs = max(16, int(arc.AngleDegrees / 5))
                pts = []
                for i in range(segs + 1):
                    t = arc.Domain.ParameterAt(float(i) / segs)
                    p = arc.PointAt(t)
                    pts.append((p.X, p.Y, p.Z))
                return (_linestring_wkt(pts), "ARC", None)
        if isinstance(geom, Rhino.Geometry.Point):
            loc = geom.Location
            return (_point_wkt(loc.X, loc.Y, loc.Z), "POINT", None)
        text_entity_item = _rhino_text_entity_to_wkt(geom)
        if text_entity_item[0] is not None:
            return text_entity_item
        if isinstance(geom, Rhino.Geometry.TextDot):
            pt, text = geom.Point, (geom.Text or "").strip()
            props = {
                "text": text,
                "halign": 0,
                "valign": 0,
                "insert_x": float(pt.X),
                "insert_y": float(pt.Y),
                "insert_z": float(pt.Z),
                "text_align_x": float(pt.X),
                "text_align_y": float(pt.Y),
                "text_align_z": float(pt.Z),
            }
            try:
                h = getattr(geom, "Height", None)
                if h is not None:
                    props["height"] = float(h)
            except Exception:
                pass
            return (_point_wkt(pt.X, pt.Y, pt.Z), "TEXT", props)
        if isinstance(geom, Rhino.Geometry.Hatch):
            try:
                curves = geom.GetEdges()
                if curves and len(curves) > 0:
                    all_pts = []
                    for c in curves:
                        if c.TryGetPolyline()[0]:
                            pl = c.TryGetPolyline()[1]
                            for i in range(pl.Count):
                                p = pl[i]
                                all_pts.append((p.X, p.Y, p.Z))
                            if all_pts and (abs(all_pts[0][0] - all_pts[-1][0]) > 1e-9 or abs(all_pts[0][1] - all_pts[-1][1]) > 1e-9):
                                all_pts.append(all_pts[0])
                        else:
                            for i in range(33):
                                t = c.Domain.ParameterAt(float(i) / 32)
                                p = c.PointAt(t)
                                all_pts.append((p.X, p.Y, p.Z))
                    if all_pts:
                        return (_linestring_wkt(all_pts), "HATCH", None)
            except Exception:
                pass
        if isinstance(geom, Rhino.Geometry.Curve):
            try:
                segs = min(200, max(16, int(geom.GetLength() / 0.1) if geom.GetLength() and geom.GetLength() > 0 else 32))
                pts = []
                for i in range(segs + 1):
                    t = geom.Domain.ParameterAt(float(i) / segs)
                    p = geom.PointAt(t)
                    pts.append((p.X, p.Y, p.Z))
                wkt = _linestring_wkt(pts)
                if wkt:
                    return (wkt, "LWPOLYLINE", None)
            except Exception:
                pass
    except Exception:
        pass
    return (None, None, None)


def _get_instance_xform_params(obj):
    """InstanceObject에서 InsertionPoint + InstanceXform 기반 scale/rotation 추출.
    반환: (ix, iy, iz, scale_x, scale_y, scale_z, rotation_deg)
    """
    import math
    ix = iy = iz = 0.0
    sx, sy, sz = 1.0, 1.0, 1.0
    rot_deg = 0.0
    try:
        ins_pt = getattr(obj, "InsertionPoint", None)
        if ins_pt is not None:
            ix, iy, iz = float(ins_pt.X), float(ins_pt.Y), float(ins_pt.Z)
    except Exception:
        pass
    try:
        xform = getattr(obj, "InstanceXform", None)
        if xform is not None:
            m00 = float(getattr(xform, "M00", 1) or 1)
            m10 = float(getattr(xform, "M10", 0) or 0)
            m20 = float(getattr(xform, "M20", 0) or 0)
            m01 = float(getattr(xform, "M01", 0) or 0)
            m11 = float(getattr(xform, "M11", 1) or 1)
            m21 = float(getattr(xform, "M21", 0) or 0)
            m02 = float(getattr(xform, "M02", 0) or 0)
            m12 = float(getattr(xform, "M12", 0) or 0)
            m22 = float(getattr(xform, "M22", 1) or 1)
            sx = math.sqrt(m00 * m00 + m10 * m10 + m20 * m20) or 1.0
            sy = math.sqrt(m01 * m01 + m11 * m11 + m21 * m21) or 1.0
            sz = math.sqrt(m02 * m02 + m12 * m12 + m22 * m22) or 1.0
            rot_rad = math.atan2(m10, m00)
            rot_deg = math.degrees(rot_rad)
    except Exception:
        pass
    return (ix, iy, iz, sx, sy, sz, rot_deg)


def _entity_list_bbox_min(entities):
    """엔티티 리스트에서 전체 bbox의 (min_x, min_y, min_z) 반환. geom_wkt/bbox_wkt 파싱. 라이노 위치 그대로 업로드."""
    min_x = min_y = min_z = None
    for e in entities:
        wkt = e.get("bbox_wkt") or e.get("geom_wkt")
        if not wkt:
            continue
        pts = _parse_wkt_points(wkt)
        for (x, y, z) in pts:
            if min_x is None or x < min_x:
                min_x = x
            if min_y is None or y < min_y:
                min_y = y
            if min_z is None or z < min_z:
                min_z = z
    if min_x is None:
        min_x = min_y = min_z = 0.0
    elif min_y is None:
        min_y = 0.0
    if min_z is None:
        min_z = 0.0
    return (min_x, min_y, min_z)


def _is_instance_object(obj):
    """Rhino InstanceObject(블록 참조) 여부. IronPython/Clr 호환 체크."""
    if obj is None:
        return False
    try:
        if hasattr(Rhino.DocObjects, "InstanceObject") and isinstance(obj, Rhino.DocObjects.InstanceObject):
            return True
        if getattr(obj, "InstanceDefinition", None) is not None:
            return True
        tname = type(obj).__name__
        if tname == "InstanceObject" or "InstanceObject" in (getattr(type(obj), "FullName", None) or ""):
            return True
    except Exception:
        pass
    return False


def _is_instance_reference_geometry(geom):
    """Geometry가 InstanceReferenceGeometry(블록 참조 지오메트리)인지."""
    if geom is None:
        return False
    try:
        if hasattr(Rhino.Geometry, "InstanceReferenceGeometry"):
            return isinstance(geom, Rhino.Geometry.InstanceReferenceGeometry)
        return type(geom).__name__ == "InstanceReferenceGeometry" or "InstanceReferenceGeometry" in (getattr(type(geom), "FullName", None) or "")
    except Exception:
        return False


def _rhino_doc_to_entity_list(doc):
    """문서를 엔티티 + 블록 정의/배치로 변환. 반환: {"entities": [...], "block_defs": [...], "block_inserts": [...], "layer_colors": {...}}."""
    if doc is None:
        return {"entities": [], "block_defs": [], "block_inserts": [], "layer_colors": {}}
    # 문서 레이어별 보이는 색상(ACI) 미리 수집 — 업로드 시 settings에 넣어 DB→Rhino 가져오기와 동일하게 복원
    doc_layer_colors = {}
    try:
        for i in range(doc.Layers.Count):
            layer = doc.Layers[i]
            name = getattr(layer, "Name", None) or "0"
            c = getattr(layer, "Color", None)
            if c is not None:
                aci = _drawing_color_to_aci(c)
                if aci is not None:
                    doc_layer_colors[name] = aci
    except Exception:
        pass
    layer_colors = dict(doc_layer_colors)
    out = []
    instance_objs = []
    try:
        for obj in doc.Objects:
            if obj.IsDeleted or obj.Geometry is None:
                continue
            is_block = _is_instance_object(obj) or _is_instance_reference_geometry(obj.Geometry)
            if is_block:
                try:
                    layer_index = obj.Attributes.LayerIndex
                    layer = doc.Layers[layer_index].Name if 0 <= layer_index < doc.Layers.Count else "0"
                except Exception:
                    layer = "0"
                color = None
                color_from_object = False
                try:
                    if obj.Attributes.ColorSource == Rhino.DocObjects.ObjectColorSource.ColorFromObject:
                        color = _drawing_color_to_aci(obj.Attributes.ObjectColor)
                        color_from_object = True
                    if color is None and layer in layer_colors:
                        color = layer_colors[layer]
                    if color is None and 0 <= obj.Attributes.LayerIndex < doc.Layers.Count:
                        lc = doc.Layers[obj.Attributes.LayerIndex].Color
                        color = _drawing_color_to_aci(lc)
                        if color is not None:
                            layer_colors[layer] = color
                except Exception:
                    pass
                instance_objs.append((obj, layer, color, not color_from_object))
                continue
            try:
                layer_index = obj.Attributes.LayerIndex
                layer = doc.Layers[layer_index].Name if 0 <= layer_index < doc.Layers.Count else "0"
            except Exception:
                layer = "0"
            color = None
            try:
                if obj.Attributes.ColorSource == Rhino.DocObjects.ObjectColorSource.ColorFromObject:
                    color = _drawing_color_to_aci(obj.Attributes.ObjectColor)
                if color is None and layer in layer_colors:
                    color = layer_colors[layer]
                if color is None and 0 <= obj.Attributes.LayerIndex < doc.Layers.Count:
                    layer_color = doc.Layers[obj.Attributes.LayerIndex].Color
                    color = _drawing_color_to_aci(layer_color)
                    if color is not None:
                        layer_colors[layer] = color
            except Exception:
                pass
            color_from_object = False
            try:
                color_from_object = (obj.Attributes.ColorSource == Rhino.DocObjects.ObjectColorSource.ColorFromObject)
            except Exception:
                pass
            user_attrs = {}
            try:
                keys = obj.Attributes.GetUserStrings()
                if keys:
                    for k in keys:
                        v = obj.Attributes.GetUserString(k)
                        user_attrs[str(k)] = str(v) if v is not None else ""
            except Exception:
                pass
            geom_wkt, entity_type, props_extra = _rhino_geometry_to_wkt(obj.Geometry)
            if geom_wkt is None or entity_type is None:
                continue
            props = dict(props_extra or {})
            props["color_bylayer"] = not color_from_object
            if user_attrs:
                props["user_attrs"] = user_attrs
            centroid_wkt, bbox_wkt = None, None
            try:
                bbox = obj.Geometry.GetBoundingBox(True)
                if bbox.IsValid:
                    cx = (bbox.Min.X + bbox.Max.X) / 2
                    cy = (bbox.Min.Y + bbox.Max.Y) / 2
                    cz = (bbox.Min.Z + bbox.Max.Z) / 2
                    centroid_wkt = _point_wkt(cx, cy, cz)
                    xs = [bbox.Min.X, bbox.Max.X]
                    ys = [bbox.Min.Y, bbox.Max.Y]
                    bbox_wkt = "POLYGON Z(({0} {1} {2},{3} {1} {2},{3} {4} {2},{0} {4} {2},{0} {1} {2}))".format(
                        min(xs), min(ys), bbox.Min.Z, max(xs), max(ys))
            except Exception:
                pass
            out.append({
                "entity_type": entity_type,
                "layer": layer or "0",
                "color": color,
                "linetype": None,
                "geom_wkt": geom_wkt,
                "centroid_wkt": centroid_wkt,
                "bbox_wkt": bbox_wkt,
                "props": props if props else None,
                "fingerprint": None,
            })
    except Exception as e:
        _debug("_rhino_doc_to_entity_list error: {}".format(e))
        return {"entities": [], "block_defs": [], "block_inserts": [], "layer_colors": {}}

    # 블록 속성(BLOCK_NAME, BLOCK_VARIANT, BLOCK_INDEX)으로 그룹 분리
    root_entities = []
    block_groups = {}  # (block_name, block_variant) -> list of entity dicts
    for e in out:
        user_attrs = (e.get("props") or {}).get("user_attrs") or {}
        block_variant = user_attrs.get("BLOCK_VARIANT")
        if block_variant is None or block_variant == "":
            root_entities.append(e)
            continue
        try:
            block_variant = int(block_variant)
        except (ValueError, TypeError):
            block_variant = block_variant
        block_name = (user_attrs.get("BLOCK_NAME") or "").strip() or str(block_variant)
        key = (block_name, block_variant)
        if key not in block_groups:
            block_groups[key] = []
        block_groups[key].append(e)

    block_defs = []
    block_inserts = []
    all_block_entities = []
    insert_temp_key = [0]

    def next_temp_key():
        insert_temp_key[0] += 1
        return int(insert_temp_key[0])

    if block_groups:
        sorted_keys = sorted(block_groups.keys(), key=lambda k: (k[0], str(k[1])))
        key_to_local_entities = {}
        for (block_name, block_variant) in sorted_keys:
            group = block_groups[(block_name, block_variant)]
            ix, iy, iz = _entity_list_bbox_min(group)
            local_entities = []
            for ent in group:
                gw = ent.get("geom_wkt")
                if not gw:
                    continue
                local_wkt = _wkt_world_to_block_local(gw, ix, iy, iz, 1.0, 1.0, 0.0, 0.0, 0.0)
                if not local_wkt:
                    continue
                local_entities.append({
                    "entity_type": ent.get("entity_type") or "LINE",
                    "geom_wkt": local_wkt,
                    "layer": ent.get("layer") or "0",
                    "color": ent.get("color"),
                    "props": ent.get("props"),
                })
            if local_entities:
                key_to_local_entities[(block_name, block_variant)] = (group, ix, iy, iz, local_entities)

        valid_group_keys = sorted(key_to_local_entities.keys(), key=lambda k: (k[0], str(k[1])))
        seen_def_names = set()
        for (block_name, block_variant) in valid_group_keys:
            if block_name in seen_def_names:
                continue
            seen_def_names.add(block_name)
            _, _, _, _, local_entities = key_to_local_entities[(block_name, block_variant)]
            block_defs.append({
                "name": block_name,
                "base_point_wkt": "POINT Z(0 0 0)",
                "base_x": 0.0,
                "base_y": 0.0,
                "props": {"entities": local_entities},
            })
        for (block_name, block_variant) in valid_group_keys:
            group, ix, iy, iz, _ = key_to_local_entities[(block_name, block_variant)]
            temp_key = next_temp_key()
            insert_point_wkt = _point_wkt(ix, iy, iz)
            layer = group[0].get("layer") if group else "0"
            color = group[0].get("color") if group else None
            block_inserts.append({
                "block_name": block_name,
                "layer": layer,
                "color": color,
                "insert_point_wkt": insert_point_wkt,
                "rotation": 0.0,
                "scale_x": 1.0,
                "scale_y": 1.0,
                "scale_z": 1.0,
                "transform": {},
                "props": None,
                "fingerprint": None,
                "_temp_insert_key": temp_key,
            })
            for ent in group:
                e2 = dict(ent)
                e2["_temp_insert_key"] = temp_key
                all_block_entities.append(e2)

    # 네이티브 InstanceObject(블록 참조) 처리
    native_block_defs = []
    native_block_inserts = []
    native_block_entities = []
    idef_key_to_local_entities = {}
    idef_key_to_block_name = {}
    used_native_block_names = set()
    MAX_NESTED_BLOCK_DEPTH = 20

    def _matrix_to_xform_params(xform):
        import math
        m00 = float(getattr(xform, "M00", 1) or 1)
        m10 = float(getattr(xform, "M10", 0) or 0)
        m20 = float(getattr(xform, "M20", 0) or 0)
        m01 = float(getattr(xform, "M01", 0) or 0)
        m11 = float(getattr(xform, "M11", 1) or 1)
        m21 = float(getattr(xform, "M21", 0) or 0)
        m02 = float(getattr(xform, "M02", 0) or 0)
        m12 = float(getattr(xform, "M12", 0) or 0)
        m22 = float(getattr(xform, "M22", 1) or 1)
        m03 = float(getattr(xform, "M03", 0) or 0)
        m13 = float(getattr(xform, "M13", 0) or 0)
        m23 = float(getattr(xform, "M23", 0) or 0)
        sx = math.sqrt(m00 * m00 + m10 * m10 + m20 * m20) or 1.0
        sy = math.sqrt(m01 * m01 + m11 * m11 + m21 * m21) or 1.0
        sz = math.sqrt(m02 * m02 + m12 * m12 + m22 * m22) or 1.0
        rot_deg = math.degrees(math.atan2(m10, m00))
        return (m03, m13, m23, sx, sy, sz, rot_deg)

    def _extract_ref_xform_matrix(ro):
        try:
            geom = getattr(ro, "Geometry", None)
            xform = getattr(geom, "Xform", None) if geom is not None else None
            if xform is None and geom is not None:
                xform = getattr(geom, "Transform", None)
            if xform is None and _is_instance_object(ro):
                xform = getattr(ro, "InstanceXform", None)
            return xform
        except Exception:
            return None

    def _transform_points_by_matrix(points, xform):
        if not points or xform is None:
            return []
        m00 = float(getattr(xform, "M00", 1) or 1)
        m01 = float(getattr(xform, "M01", 0) or 0)
        m02 = float(getattr(xform, "M02", 0) or 0)
        m03 = float(getattr(xform, "M03", 0) or 0)
        m10 = float(getattr(xform, "M10", 0) or 0)
        m11 = float(getattr(xform, "M11", 1) or 1)
        m12 = float(getattr(xform, "M12", 0) or 0)
        m13 = float(getattr(xform, "M13", 0) or 0)
        m20 = float(getattr(xform, "M20", 0) or 0)
        m21 = float(getattr(xform, "M21", 0) or 0)
        m22 = float(getattr(xform, "M22", 1) or 1)
        m23 = float(getattr(xform, "M23", 0) or 0)
        out = []
        for pt in points:
            x = float(pt[0]) if len(pt) >= 1 else 0.0
            y = float(pt[1]) if len(pt) >= 2 else 0.0
            z = float(pt[2]) if len(pt) >= 3 else 0.0
            wx = m00 * x + m01 * y + m02 * z + m03
            wy = m10 * x + m11 * y + m12 * z + m13
            wz = m20 * x + m21 * y + m22 * z + m23
            out.append((wx, wy, wz))
        return out

    def _parse_coords_text(part):
        pts = []
        if not part:
            return pts
        for token in part.split(","):
            nums = re.findall(r"[-\d.eE]+", token.strip())
            if len(nums) >= 2:
                x = float(nums[0])
                y = float(nums[1])
                z = float(nums[2]) if len(nums) >= 3 else 0.0
                pts.append((x, y, z))
        return pts

    def _coords_to_wkt_text(points):
        return ", ".join("{0} {1} {2}".format(p[0], p[1], p[2]) for p in points)

    def _wkt_apply_matrix(wkt, xform):
        if not wkt or "EMPTY" in (wkt or "").upper() or xform is None:
            return wkt
        raw = wkt.strip()
        if re.match(r"^SRID=\d+;", raw, re.I):
            raw = re.sub(r"^SRID=\d+;\s*", "", raw, flags=re.I)
        upper = raw.upper().strip()
        if upper.startswith("MULTILINESTRING"):
            idx_open = raw.find("(")
            idx_close = raw.rfind(")")
            if idx_open >= 0 and idx_close > idx_open:
                inner = raw[idx_open + 1:idx_close].strip().strip("()")
                parts = re.split(r"\)\s*,\s*\(", inner) if inner else []
                out_parts = []
                for part in parts:
                    pts = _parse_coords_text(part.strip().strip("()"))
                    if not pts:
                        continue
                    tpts = _transform_points_by_matrix(pts, xform)
                    if tpts:
                        out_parts.append("({0})".format(_coords_to_wkt_text(tpts)))
                if out_parts:
                    return "MULTILINESTRING Z (" + ", ".join(out_parts) + ")"
        if upper.startswith("POLYGON"):
            idx_open = raw.find("((")
            idx_close = raw.rfind("))")
            if idx_open >= 0 and idx_close > idx_open:
                inner = raw[idx_open + 2:idx_close].strip()
                rings = re.split(r"\)\s*,\s*\(", inner) if inner else []
                out_rings = []
                for ring in rings:
                    pts = _parse_coords_text(ring.strip().strip("()"))
                    if not pts:
                        continue
                    tpts = _transform_points_by_matrix(pts, xform)
                    if tpts:
                        out_rings.append("({0})".format(_coords_to_wkt_text(tpts)))
                if out_rings:
                    return "POLYGON Z (" + ", ".join(out_rings) + ")"
        pts = _parse_wkt_points(raw)
        if not pts:
            return raw
        out = _transform_points_by_matrix(pts, xform)
        if not out:
            return raw
        if len(out) == 1 or upper.startswith("POINT"):
            p0 = out[0]
            return "POINT Z ({0} {1} {2})".format(p0[0], p0[1], p0[2])
        if upper.startswith("POLYGON"):
            return "POLYGON Z (({0}))".format(_coords_to_wkt_text(out))
        return "LINESTRING Z ({0})".format(_coords_to_wkt_text(out))

    def _idef_visit_key(idef, fallback_name=None):
        if idef is None:
            return None
        try:
            idef_id = getattr(idef, "Id", None)
            if idef_id is not None:
                s = str(idef_id)
                if s and s != "00000000-0000-0000-0000-000000000000":
                    return "id:" + s
        except Exception:
            pass
        try:
            idx = getattr(idef, "Index", None)
            if idx is not None:
                return "idx:" + str(int(idx))
        except Exception:
            pass
        nm = (getattr(idef, "Name", None) or fallback_name or "").strip() or "<unnamed>"
        return "name:" + nm

    def _unique_native_block_name(raw_name, idef_key):
        base = (raw_name or "").strip() or "BLOCK"
        if base not in used_native_block_names:
            used_native_block_names.add(base)
            return base
        suffix = re.sub(r"[^A-Za-z0-9_-]+", "_", str(idef_key or "dup"))
        candidate = "{}__{}".format(base, suffix)
        if candidate not in used_native_block_names:
            used_native_block_names.add(candidate)
            return candidate
        n = 2
        while True:
            candidate = "{}__{}_{}".format(base, suffix, n)
            if candidate not in used_native_block_names:
                used_native_block_names.add(candidate)
                return candidate
            n += 1

    def _find_idef_by_ref(ref):
        if ref is None:
            return None
        idefs = getattr(doc, "InstanceDefinitions", None)
        if idefs is None:
            return None
        finder_id = getattr(idefs, "FindId", None)
        if finder_id is not None:
            try:
                got = finder_id(ref)
                if got is not None:
                    return got
            except Exception:
                pass
        try:
            idx = int(ref)
            if idx >= 0:
                try:
                    if idx < idefs.Count:
                        got = idefs[idx]
                        if got is not None:
                            return got
                except Exception:
                    pass
                finder = getattr(idefs, "Find", None)
                if finder is not None:
                    for args in ((idx,), (idx, True), (idx, False)):
                        try:
                            got = finder(*args)
                            if got is not None:
                                return got
                        except Exception:
                            pass
        except Exception:
            pass
        finder = getattr(idefs, "Find", None)
        if finder is not None:
            for args in ((ref,), (ref, True), (ref, False)):
                try:
                    got = finder(*args)
                    if got is not None:
                        return got
                except Exception:
                    pass
        return None

    def _resolve_layer_color_for_obj(ro, default_layer="0", default_color=None):
        layer_inner = default_layer or "0"
        color_inner = default_color
        color_from_object_inner = False
        try:
            if getattr(ro, "Attributes", None) and 0 <= ro.Attributes.LayerIndex < doc.Layers.Count:
                layer_inner = doc.Layers[ro.Attributes.LayerIndex].Name
        except Exception:
            pass
        try:
            if getattr(ro, "Attributes", None):
                if ro.Attributes.ColorSource == Rhino.DocObjects.ObjectColorSource.ColorFromObject:
                    color_inner = _drawing_color_to_aci(ro.Attributes.ObjectColor)
                    color_from_object_inner = True
                if color_inner is None and layer_inner in layer_colors:
                    color_inner = layer_colors[layer_inner]
                if color_inner is None and 0 <= ro.Attributes.LayerIndex < doc.Layers.Count:
                    lc = doc.Layers[ro.Attributes.LayerIndex].Color
                    color_inner = _drawing_color_to_aci(lc)
                    if color_inner is not None:
                        layer_colors[layer_inner] = color_inner
        except Exception:
            pass
        return (layer_inner, color_inner, color_from_object_inner)

    def _resolve_child_idef(ro, parent_idef=None):
        parent_key = _idef_visit_key(parent_idef)
        idef = getattr(ro, "InstanceDefinition", None)
        if idef is not None:
            child_key = _idef_visit_key(idef)
            if parent_key is None or child_key != parent_key:
                return idef
        geom = getattr(ro, "Geometry", None)
        if geom is None:
            return None
        for key in ("InstanceDefinitionId", "InstanceDefinitionIndex", "ParentIdefId", "ParentIdefIndex"):
            try:
                ref = getattr(geom, key, None)
                if ref is None:
                    continue
                got = _find_idef_by_ref(ref)
                if got is None:
                    continue
                child_key = _idef_visit_key(got)
                if parent_key is not None and child_key == parent_key:
                    continue
                return got
            except Exception:
                pass
        for key in ("InstanceDefinitionId", "InstanceDefinitionIndex"):
            try:
                ref = getattr(ro, key, None)
                if ref is None:
                    continue
                got = _find_idef_by_ref(ref)
                if got is None:
                    continue
                child_key = _idef_visit_key(got)
                if parent_key is not None and child_key == parent_key:
                    continue
                return got
            except Exception:
                pass
        return None

    def _extract_ref_xform_params(ro):
        ix, iy, iz, sx, sy, sz, rot = _get_instance_xform_params(ro)
        try:
            geom = getattr(ro, "Geometry", None)
            xform = getattr(geom, "Xform", None) if geom is not None else None
            if xform is None and geom is not None:
                xform = getattr(geom, "Transform", None)
            if xform is not None:
                mix, miy, miz, msx, msy, msz, mrot = _matrix_to_xform_params(xform)
                if not _is_instance_object(ro):
                    return (mix, miy, miz, msx, msy, msz, mrot)
                if abs(ix) + abs(iy) + abs(iz) < 1e-12 and (abs(mix) + abs(miy) + abs(miz) > 1e-12):
                    ix, iy, iz = mix, miy, miz
                if abs(sx - 1.0) < 1e-12 and abs(sy - 1.0) < 1e-12 and abs(sz - 1.0) < 1e-12:
                    sx, sy, sz = msx, msy, msz
                if abs(rot) < 1e-12:
                    rot = mrot
        except Exception:
            pass
        return (ix, iy, iz, sx, sy, sz, rot)

    def _sanitize_hierarchy_token(value):
        try:
            s = re.sub(r"[^A-Za-z0-9_.-]+", "_", (value or "BLOCK").strip())
            return s or "BLOCK"
        except Exception:
            return "BLOCK"

    def _make_hierarchy_instance_key(name, occurrence):
        return "{0}@{1}".format(_sanitize_hierarchy_token(name), int(occurrence or 1))

    def _clone_hierarchy_path(path):
        out = []
        if not isinstance(path, list):
            return out
        for seg in path:
            if not isinstance(seg, dict):
                continue
            sname = (seg.get("name") or "").strip() or "BLOCK"
            skey = str(seg.get("instance_key") or "").strip()
            if not skey:
                continue
            out.append({"name": sname, "instance_key": skey})
        return out

    def _collect_local_entities_from_idef(idef, depth, visited, path_prefix="", path_segments=None):
        if idef is None:
            return []
        path_prefix = path_prefix or ""
        path_segments = _clone_hierarchy_path(path_segments)
        name = (getattr(idef, "Name", None) or "").strip() or "<unnamed>"
        idef_key = _idef_visit_key(idef, name)
        if depth > MAX_NESTED_BLOCK_DEPTH:
            _debug("NestedBlockCollect depth limit: {} depth={}".format(name, depth))
            _debug(
                "NestedBlockCollect name={} depth={} entities={} nested_refs={} cycle_skips={}".format(
                    name, depth, 0, 0, 0
                )
            )
            return []
        if idef_key in visited:
            _debug("NestedBlockCollect cycle skip: {} depth={}".format(name, depth))
            _debug(
                "NestedBlockCollect name={} depth={} entities={} nested_refs={} cycle_skips={}".format(
                    name, depth, 0, 0, 1
                )
            )
            return []
        visited.add(idef_key)
        local_entities = []
        nested_ref_count = 0
        cycle_skip_count = 0
        nested_name_counts = {}
        try:
            inner = getattr(idef, "GetObjects", None)
            inner_objs = inner() if inner else []
            if inner_objs is None:
                inner_objs = []
            for ro in inner_objs:
                geom = getattr(ro, "Geometry", None) if ro is not None else None
                if geom is None:
                    continue
                layer_inner, color_inner, color_from_object_inner = _resolve_layer_color_for_obj(ro, "0", None)
                if _is_instance_object(ro) or _is_instance_reference_geometry(geom):
                    child_idef = _resolve_child_idef(ro, idef)
                    if child_idef is None:
                        _debug("NestedBlockCollect missing child idef in {}".format(name))
                        continue
                    child_name = (getattr(child_idef, "Name", None) or "").strip() or "<unnamed>"
                    child_key = _idef_visit_key(child_idef, child_name)
                    if child_key in visited:
                        cycle_skip_count += 1
                        _debug("NestedBlockCollect cycle skip: {} depth={}".format(child_name, depth + 1))
                        continue
                    nested_ref_count += 1
                    nested_name_counts[child_name] = nested_name_counts.get(child_name, 0) + 1
                    child_occurrence = nested_name_counts[child_name]
                    child_token = _make_hierarchy_instance_key(child_name, child_occurrence)
                    child_prefix = child_token if not path_prefix else (path_prefix + "/" + child_token)
                    child_segments = _clone_hierarchy_path(path_segments)
                    child_segments.append({
                        "name": child_name,
                        "instance_key": child_prefix,
                    })
                    child_xform = _extract_ref_xform_matrix(ro)
                    cix, ciy, ciz, csx, csy, csz, crot = _extract_ref_xform_params(ro)
                    child_entities = _collect_local_entities_from_idef(
                        child_idef, depth + 1, visited, child_prefix, child_segments
                    )
                    for child in child_entities:
                        child_wkt = child.get("geom_wkt")
                        if not child_wkt:
                            continue
                        transformed_wkt = _wkt_apply_matrix(child_wkt, child_xform)
                        if not transformed_wkt:
                            transformed_wkt = _wkt_block_local_to_world(
                                child_wkt, 0.0, 0.0, cix, ciy, ciz, csx, csy, csz, crot
                            )
                        if not transformed_wkt:
                            continue
                        child_props = dict(child.get("props") or {})
                        child_layer = child.get("layer") or "0"
                        child_color = child.get("color")
                        child_bylayer = child_props.get("color_bylayer")
                        if child_bylayer is None:
                            child_bylayer = True
                        use_insert = bool(child_bylayer) and child_layer == "0"
                        layer_out = layer_inner if use_insert else child_layer
                        color_out = color_inner if (use_insert or child_color in (None, 0, 256)) else child_color
                        child_props["color_bylayer"] = bool(child_bylayer)
                        local_entities.append({
                            "entity_type": child.get("entity_type") or "LINE",
                            "geom_wkt": transformed_wkt,
                            "layer": layer_out or "0",
                            "color": color_out,
                            "props": child_props,
                        })
                    continue
                geom_wkt, entity_type, props_extra = _rhino_geometry_to_wkt(geom)
                if geom_wkt is None or entity_type is None:
                    continue
                props_inner = dict(props_extra or {})
                props_inner["color_bylayer"] = not color_from_object_inner
                if path_segments:
                    props_inner["block_hierarchy_path"] = _clone_hierarchy_path(path_segments)
                local_entities.append({
                    "entity_type": entity_type,
                    "geom_wkt": geom_wkt,
                    "layer": layer_inner,
                    "color": color_inner,
                    "props": props_inner,
                })
        except Exception as ex:
            _debug("NestedBlockCollect {}: {}".format(name, ex))
        finally:
            visited.discard(idef_key)
        _debug(
            "NestedBlockCollect name={} depth={} entities={} nested_refs={} cycle_skips={}".format(
                name, depth, len(local_entities), nested_ref_count, cycle_skip_count
            )
        )
        return local_entities

    if instance_objs:
        for (obj, layer, color, color_bylayer) in instance_objs:
            try:
                idef = getattr(obj, "InstanceDefinition", None)
                if idef is None:
                    continue
                name = (getattr(idef, "Name", None) or "").strip()
                idef_key = _idef_visit_key(idef, name)
                if idef_key in idef_key_to_block_name:
                    continue
                block_name = _unique_native_block_name(name, idef_key)
                local_entities = _collect_local_entities_from_idef(idef, 0, set(), "", [])
                idef_key_to_local_entities[idef_key] = local_entities
                idef_key_to_block_name[idef_key] = block_name
                native_block_defs.append({
                    "name": block_name,
                    "base_point_wkt": "POINT Z(0 0 0)",
                    "base_x": 0.0,
                    "base_y": 0.0,
                    "props": {"entities": local_entities},
                })
            except Exception as ex:
                _debug("InstanceDefinition GetObjects: {}".format(ex))

        for (obj, layer, color, color_bylayer) in instance_objs:
            try:
                idef = getattr(obj, "InstanceDefinition", None)
                if idef is None:
                    continue
                name = (getattr(idef, "Name", None) or "").strip()
                idef_key = _idef_visit_key(idef, name)
                block_name = idef_key_to_block_name.get(idef_key)
                local_entities = idef_key_to_local_entities.get(idef_key)
                if block_name is None or local_entities is None:
                    block_name = _unique_native_block_name(name, idef_key)
                    local_entities = _collect_local_entities_from_idef(idef, 0, set(), "", [])
                    idef_key_to_block_name[idef_key] = block_name
                    idef_key_to_local_entities[idef_key] = local_entities
                    native_block_defs.append({
                        "name": block_name,
                        "base_point_wkt": "POINT Z(0 0 0)",
                        "base_x": 0.0,
                        "base_y": 0.0,
                        "props": {"entities": local_entities},
                    })
                ix, iy, iz, scale_x, scale_y, scale_z, rotation = _get_instance_xform_params(obj)
                ins_pt = getattr(obj, "InsertionPoint", None)
                if ins_pt is not None:
                    ix, iy, iz = float(ins_pt.X), float(ins_pt.Y), float(ins_pt.Z)
                temp_key = next_temp_key()
                obj_xform = _extract_ref_xform_matrix(obj)
                native_block_inserts.append({
                    "block_name": block_name,
                    "layer": layer or "0",
                    "color": color,
                    "insert_point_wkt": _point_wkt(ix, iy, iz),
                    "rotation": rotation,
                    "scale_x": scale_x,
                    "scale_y": scale_y,
                    "scale_z": scale_z,
                    "transform": {},
                    "props": {"color_bylayer": color_bylayer},
                    "fingerprint": None,
                    "_temp_insert_key": temp_key,
                })
                base_x, base_y = 0.0, 0.0
                for le in local_entities:
                    local_wkt = le.get("geom_wkt")
                    if not local_wkt:
                        continue
                    world_wkt = _wkt_apply_matrix(local_wkt, obj_xform)
                    if not world_wkt:
                        world_wkt = _wkt_block_local_to_world(
                            local_wkt, base_x, base_y, ix, iy, iz,
                            scale_x, scale_y, scale_z, rotation
                        )
                    if not world_wkt:
                        continue
                    pts = _parse_wkt_points(world_wkt)
                    centroid_wkt = bbox_wkt = None
                    if pts:
                        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
                        zs = [p[2] for p in pts if len(p) >= 3]
                        z_avg = sum(zs) / len(zs) if zs else 0.0
                        centroid_wkt = _point_wkt(sum(xs) / len(xs), sum(ys) / len(ys), z_avg)
                        if xs and ys:
                            bbox_wkt = "POLYGON Z(({0} {1} {2},{3} {1} {2},{3} {4} {2},{0} {4} {2},{0} {1} {2}))".format(
                                min(xs), min(ys), z_avg, max(xs), max(ys))
                    piece_props = dict(le.get("props") or {})
                    piece_props["color_bylayer"] = piece_props.get("color_bylayer", color_bylayer)
                    native_block_entities.append({
                        "entity_type": le.get("entity_type") or "LINE",
                        "layer": le.get("layer") or layer or "0",
                        "color": le.get("color") if le.get("color") is not None else color,
                        "linetype": None,
                        "geom_wkt": world_wkt,
                        "centroid_wkt": centroid_wkt,
                        "bbox_wkt": bbox_wkt,
                        "props": piece_props if piece_props else None,
                        "fingerprint": None,
                        "_temp_insert_key": temp_key,
                    })
            except Exception as ex:
                _debug("InstanceObject: {}".format(ex))

    entities = root_entities + all_block_entities + native_block_entities
    block_defs_final = block_defs + native_block_defs
    block_inserts_final = block_inserts + native_block_inserts
    return {"entities": entities, "block_defs": block_defs_final, "block_inserts": block_inserts_final, "layer_colors": layer_colors}


def _merge_settings_with_layer_colors(opts, layer_colors):
    """opts의 settings와 문서에서 수집한 layer_colors를 합쳐 커밋 설정 dict 반환."""
    settings = None
    if opts and opts.get("settings") is not None:
        s = opts.get("settings")
        if isinstance(s, dict):
            settings = dict(s)
        elif isinstance(s, str) and s.strip():
            try:
                settings = json.loads(s)
                if not isinstance(settings, dict):
                    settings = {}
            except Exception:
                settings = {}
    if settings is None:
        settings = {}
    if layer_colors is not None and isinstance(layer_colors, dict):
        settings["layer_colors"] = dict(layer_colors)
    return settings if settings else None


def CadManageSave(commit_options=None):
    """현재 문서를 DB로 직접 업로드해 같은 프로젝트에 새 버전으로 저장합니다. (DXF 업로드 없음)"""
    if scriptcontext.doc is None:
        print("문서가 열려 있지 않습니다.")
        return

    opts = dict(commit_options) if commit_options else {}
    link = _load_link()
    api_base = (opts.get("api_base") or "").rstrip("/") or (link.get("api_base") or "").rstrip("/") if link else ""
    project_id = opts.get("project_id") if opts.get("project_id") is not None else (link.get("project_id") if link else None)
    parent_commit_id = opts.get("parent_commit_id") if opts.get("parent_commit_id") is not None else (link.get("parent_commit_id") if link else None)
    if not api_base or project_id is None:
        print("연동 정보가 없습니다. CadManage 창에서 프로젝트를 선택한 뒤 저장하거나, 먼저 CadManageOpen 으로 웹에서 버전을 불러오세요.")
        return

    if sys.version_info[0] >= 3:
        from urllib.request import urlopen, Request
        from urllib.error import URLError, HTTPError
    else:
        from urllib2 import urlopen, Request, URLError, HTTPError

    data = _rhino_doc_to_entity_list(scriptcontext.doc)
    entities = data.get("entities") or []
    block_defs = data.get("block_defs") or []
    block_inserts = data.get("block_inserts") or []
    text_count = 0
    for ent in entities:
        et = (ent.get("entity_type") or "").strip().upper()
        if et == "TEXT" or et == "MTEXT":
            text_count += 1
    if not entities:
        print("내보낼 객체가 없습니다. 문서에 선·곡선·점·텍스트·해치 등 변환 가능한 객체가 있어야 합니다.")
        return

    _debug(
        "CadManageSave payload counts: entities={0}, block_defs={1}, block_inserts={2}, text={3}".format(
            len(entities), len(block_defs), len(block_inserts), text_count
        )
    )

    try:
        direct_url = "{0}/api/projects/{1}/commits/direct".format(api_base, int(project_id))
        payload = {
            "entities": entities,
            "block_defs": block_defs,
            "block_inserts": block_inserts,
            "parent_commit_id": parent_commit_id,
            "version_label": opts.get("version_label"),
            "assignee_name": opts.get("assignee_name"),
            "assignee_department": opts.get("assignee_department"),
            "change_notes": opts.get("change_notes"),
            "class_pre": opts.get("class_pre"),
            "class_major": opts.get("class_major"),
            "class_mid": opts.get("class_mid"),
            "class_minor": opts.get("class_minor"),
            "class_work_type": opts.get("class_work_type"),
            "settings": _merge_settings_with_layer_colors(opts, data.get("layer_colors")),
        }
        body_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        if sys.version_info[0] >= 3:
            req = Request(direct_url, data=body_bytes, method="POST")
        else:
            req = Request(direct_url, data=body_bytes)  # Python 2: data implies POST
        req.add_header("Content-Type", "application/json; charset=utf-8")
        req.add_header("User-Agent", "CadManage-Rhino/1.0")
        resp = urlopen(req, timeout=120)
        result = json.loads(resp.read().decode("utf-8"))
        print("저장 완료. 새 버전(커밋) ID:", result.get("id"), "- 웹에서 확인하세요.")
    except HTTPError as e:
        print("API 오류:", e.code, e.reason)
        try:
            body = e.read().decode("utf-8", errors="replace")
            if body:
                print(body[:800])
        except Exception:
            pass
    except URLError as e:
        print("연결 실패:", e.reason)
    except Exception as e:
        print("업로드 실패:", e)


# 모달리스 CadManage 창 참조 (가비지 컬렉션 방지)
_cadmanage_form = None


def _do_zoom_extents_all():
    """UI 스레드에서 실행: 모든 뷰 ZoomExtents."""
    doc = scriptcontext.doc
    if doc is None:
        return
    for cmd in ["ZEA", "ZoomExtentsAll", "Zoom Extents All"]:
        try:
            Rhino.RhinoApp.RunScript(cmd, False)
            try:
                doc.Views.Redraw()
            except Exception:
                pass
            return
        except Exception:
            pass
    try:
        import rhinoscriptsyntax as rs
        rs.ZoomExtents(blnAll=True)
        try:
            doc.Views.Redraw()
        except Exception:
            pass
        return
    except ImportError:
        pass
    except Exception:
        pass
    try:
        count = getattr(doc.Views, "Count", 0)
        if count is None or count <= 0:
            try:
                count = len(doc.Views)
            except Exception:
                count = 0
        for i in range(count):
            try:
                view = doc.Views[i] if hasattr(doc.Views, "__getitem__") else doc.Views.GetView(i)
                if view is None:
                    continue
                vp = getattr(view, "ActiveViewport", None) or getattr(view, "MainViewport", None)
                if vp is not None:
                    vp.ZoomExtents()
            except Exception:
                pass
        try:
            doc.Views.Redraw()
        except Exception:
            pass
    except Exception:
        try:
            view = doc.Views.ActiveView
            if view is not None and view.ActiveViewport is not None:
                view.ActiveViewport.ZoomExtents()
                doc.Views.Redraw()
        except Exception:
            pass


def _activate_rhino_view_and_zoom_extents():
    """Rhino 메인 창 활성화 후 모든 뷰에서 ZoomExtents (UI 스레드에서 실행)."""
    try:
        main = Rhino.UI.RhinoEtoApp.MainWindow
        if main is not None:
            try:
                main.Focus()
            except Exception:
                pass
    except Exception:
        pass
    try:
        if hasattr(Rhino.RhinoApp, "InvokeOnUiThread"):
            Rhino.RhinoApp.InvokeOnUiThread(lambda: _do_zoom_extents_all())
        else:
            _do_zoom_extents_all()
    except Exception:
        try:
            _do_zoom_extents_all()
        except Exception:
            pass


def _show_cadmanage_dialog():
    """Eto 폼 표시 (모달리스, 상시 떠 있는 실행창 스타일). Eto 사용 불가 시 False 반환."""
    global _cadmanage_form
    if CadManageEtoDialog is None:
        return False
    if _cadmanage_form is not None:
        try:
            if _cadmanage_form.Visible:
                _cadmanage_form.Focus()
                return True
        except Exception:
            pass
        _cadmanage_form = None
    _cadmanage_form = CadManageEtoDialog()
    _cadmanage_form.Closed += _on_cadmanage_form_closed
    _cadmanage_form.Show()
    return True


def _on_cadmanage_form_closed(sender, e):
    global _cadmanage_form
    if sender is _cadmanage_form:
        _cadmanage_form = None


# Eto 사용 가능할 때만 폼 클래스 정의 (eto_forms 없으면 클래스 미정의)
CadManageEtoDialog = None
if eto_forms is not None and eto_drawing is not None:
    class CadManageEtoDialog(eto_forms.Form):
        """CadManage Eto 폼: 서버 주소, 프로젝트·버전 선택, 가져오기/저장/닫기. 모달리스로 상시 표시."""

        def __init__(self):
            super(CadManageEtoDialog, self).__init__()
            self.Title = "CadManage"
            self.Padding = eto_drawing.Padding(10)
            self.Resizable = True
            self.ClientSize = eto_drawing.Size(540, 480)
            self.MinimumSize = eto_drawing.Size(500, 440)
            self._projects = []
            self._commits = []
            self._users = []
            self._departments = []
            self._minor_classes = []
            self._work_types = []

            self._lbl_server = eto_forms.Label()
            self._lbl_server.Text = "서버 주소"
            self._txt_server = eto_forms.TextBox()
            self._txt_server.Text = "http://127.0.0.1:8000"
            self._btn_refresh = eto_forms.Button()
            self._btn_refresh.Text = "프로젝트 목록 불러오기"
            self._btn_refresh.MinimumSize = eto_drawing.Size(120, 26)
            self._btn_refresh.Click += self._on_refresh_projects

            self._lbl_project = eto_forms.Label()
            self._lbl_project.Text = "프로젝트"
            self._drop_project = eto_forms.DropDown()
            self._drop_project.Items.Add("(먼저 목록 불러오기)")
            self._drop_project.SelectedIndex = 0
            self._drop_project.SelectedIndexChanged += self._on_project_changed

            self._lbl_commit = eto_forms.Label()
            self._lbl_commit.Text = "버전"
            self._drop_commit = eto_forms.DropDown()
            self._drop_commit.Items.Add("(프로젝트 선택)")
            self._drop_commit.SelectedIndex = 0
            self._btn_commit_detail = eto_forms.Button()
            self._btn_commit_detail.Text = ">"
            self._btn_commit_detail.ToolTip = "버전 상세 정보 펼치기/접기"
            self._btn_commit_detail.MinimumSize = eto_drawing.Size(28, 26)
            self._btn_commit_detail.Click += self._on_commit_detail_click

            self._lbl_commit_settings = eto_forms.Label()
            self._lbl_commit_settings.Text = "커밋 설정 (저장 시 신규 버전)"
            self._lbl_commit_project = eto_forms.Label()
            self._lbl_commit_project.Text = "프로젝트"
            self._drop_commit_project = eto_forms.DropDown()
            self._drop_commit_project.Items.Add("(먼저 목록 불러오기)")
            self._drop_commit_project.SelectedIndex = 0
            self._drop_commit_project.SelectedIndexChanged += self._on_commit_project_changed
            self._lbl_version = eto_forms.Label()
            self._lbl_version.Text = "버전 라벨"
            self._txt_version = eto_forms.TextBox()
            self._lbl_assignee = eto_forms.Label()
            self._lbl_assignee.Text = "담당자"
            self._drop_assignee = eto_forms.DropDown()
            self._drop_assignee.Items.Add("(선택)")
            self._drop_assignee.SelectedIndex = 0
            self._lbl_department = eto_forms.Label()
            self._lbl_department.Text = "부서"
            self._drop_department = eto_forms.DropDown()
            self._drop_department.Items.Add("(선택)")
            self._drop_department.SelectedIndex = 0
            self._lbl_change_notes = eto_forms.Label()
            self._lbl_change_notes.Text = "변화이력"
            self._txt_change_notes = eto_forms.TextBox()
            self._txt_change_notes.Height = 44

            self._lbl_class_pre = eto_forms.Label()
            self._lbl_class_pre.Text = "구조/건축 분류"
            self._drop_class_pre = eto_forms.DropDown()
            for opt in ["(선택)", "구조", "건축"]:
                self._drop_class_pre.Items.Add(opt)
            self._drop_class_pre.SelectedIndex = 0
            self._lbl_class_major = eto_forms.Label()
            self._lbl_class_major.Text = "대분류"
            self._drop_class_major = eto_forms.DropDown()
            for opt in ["(선택)", "지하주차장", "아파트", "부대시설", "단위세대"]:
                self._drop_class_major.Items.Add(opt)
            self._drop_class_major.SelectedIndex = 0
            self._lbl_class_mid = eto_forms.Label()
            self._lbl_class_mid.Text = "중분류"
            self._drop_class_mid = eto_forms.DropDown()
            for opt in ["(선택)", "평면", "단면", "일람"]:
                self._drop_class_mid.Items.Add(opt)
            self._drop_class_mid.SelectedIndex = 0
            self._lbl_class_minor = eto_forms.Label()
            self._lbl_class_minor.Text = "소분류"
            self._drop_class_minor = eto_forms.DropDown()
            self._drop_class_minor.Items.Add("(선택)")
            self._drop_class_minor.SelectedIndex = 0
            self._lbl_class_work_type = eto_forms.Label()
            self._lbl_class_work_type.Text = "공종"
            self._drop_class_work_type = eto_forms.DropDown()
            self._drop_class_work_type.Items.Add("(선택)")
            self._drop_class_work_type.SelectedIndex = 0

            self._btn_import = eto_forms.Button()
            self._btn_import.Text = "DB에서 가져오기"
            self._btn_import.Size = eto_drawing.Size(120, 28)
            self._btn_import.Click += self._on_import_click
            self._btn_save = eto_forms.Button()
            self._btn_save.Text = "저장"
            self._btn_save.MinimumSize = eto_drawing.Size(72, 26)
            self._btn_save.Click += self._on_save_click
            self._btn_close = eto_forms.Button()
            self._btn_close.Text = "닫기"
            self._btn_close.MinimumSize = eto_drawing.Size(72, 26)
            self._btn_close.Click += self._on_close_click

            tab_load = eto_forms.TabPage()
            tab_load.Text = "불러오기"
            load_layout = eto_forms.DynamicLayout()
            load_layout.Spacing = eto_drawing.Size(6, 6)
            load_layout.AddRow(self._lbl_server, self._txt_server)
            load_layout.AddRow(None, self._btn_refresh)
            load_layout.AddRow(None)
            load_layout.AddRow(self._lbl_project, self._drop_project)
            load_layout.AddRow(self._lbl_commit, self._drop_commit, self._btn_commit_detail)
            load_layout.AddRow(None)
            load_layout.AddRow(self._btn_import, None)
            load_layout.AddRow(None)
            tab_load.Content = load_layout

            self._lbl_next_commit = eto_forms.Label()
            self._lbl_next_commit.Text = "다음 커밋 번호: #-"
            tab_commit = eto_forms.TabPage()
            tab_commit.Text = "커밋 설정"
            commit_layout = eto_forms.DynamicLayout()
            commit_layout.Spacing = eto_drawing.Size(6, 6)
            commit_layout.AddRow(self._lbl_commit_settings)
            commit_layout.AddRow(None)
            commit_layout.AddRow(self._lbl_commit_project, self._drop_commit_project)
            commit_layout.AddRow(self._lbl_next_commit, None)
            commit_layout.AddRow(self._lbl_assignee, self._drop_assignee)
            commit_layout.AddRow(self._lbl_department, self._drop_department)
            commit_layout.AddRow(self._lbl_class_pre, self._drop_class_pre)
            commit_layout.AddRow(self._lbl_class_major, self._drop_class_major)
            commit_layout.AddRow(self._lbl_class_mid, self._drop_class_mid)
            commit_layout.AddRow(self._lbl_class_minor, self._drop_class_minor)
            commit_layout.AddRow(self._lbl_class_work_type, self._drop_class_work_type)
            commit_layout.AddRow(self._lbl_version, self._txt_version)
            commit_layout.AddRow(self._lbl_change_notes, self._txt_change_notes)
            commit_layout.AddRow(None)
            commit_layout.AddRow(self._btn_save, self._btn_close)
            tab_commit.Content = commit_layout

            tab_ctrl = eto_forms.TabControl()
            tab_ctrl.Pages.Add(tab_load)
            tab_ctrl.Pages.Add(tab_commit)
            self._base_width = 540
            self._detail_width = 260

            self._detail_panel = eto_forms.Panel()
            self._detail_panel.Padding = eto_drawing.Padding(8)
            self._detail_panel.MinimumSize = eto_drawing.Size(200, 0)
            self._detail_layout = eto_forms.DynamicLayout()
            self._detail_layout.Spacing = eto_drawing.Size(4, 4)
            self._detail_title = eto_forms.Label()
            self._detail_title.Text = "버전 상세"
            try:
                self._detail_title.Font = eto_drawing.Font(eto_drawing.FontFamilies.SansFamily, 10, eto_drawing.FontStyle.Bold)
            except Exception:
                pass
            self._detail_layout.AddRow(self._detail_title)
            self._detail_layout.AddRow(None)
            self._detail_table_layout = eto_forms.DynamicLayout()
            self._detail_table_layout.Spacing = eto_drawing.Size(4, 2)
            self._detail_value_labels = {}
            for key, label_text in [
                ("id", "버전 ID"), ("version_label", "버전 라벨"), ("assignee_name", "담당자"),
                ("assignee_department", "부서"), ("class_pre", "구조/건축"),
                ("class_major", "대분류"), ("class_mid", "중분류"), ("class_minor", "소분류"),
                ("class_work_type", "공종"), ("change_notes", "변화이력")
            ]:
                lbl = eto_forms.Label()
                lbl.Text = label_text + ":"
                val = eto_forms.Label()
                val.Text = ""
                try:
                    val.TextColor = eto_drawing.Colors.Black
                except Exception:
                    pass
                self._detail_value_labels[key] = val
                self._detail_table_layout.AddRow(lbl, val)
            try:
                scroll = eto_forms.Scrollable()
                scroll.Content = self._detail_table_layout
                scroll.MinimumSize = eto_drawing.Size(180, 280)
                self._detail_layout.AddRow(scroll)
            except Exception:
                self._detail_layout.AddRow(self._detail_table_layout)
            self._detail_panel.Content = self._detail_layout

            try:
                splitter = eto_forms.Splitter()
                if hasattr(eto_forms, "Orientation") and hasattr(eto_forms.Orientation, "Horizontal"):
                    splitter.Orientation = eto_forms.Orientation.Horizontal
                splitter.Panel1 = tab_ctrl
                splitter.Panel2 = self._detail_panel
                try:
                    splitter.Panel2MinimumSize = 0
                except Exception:
                    pass
                splitter.Position = self._base_width
                self.Content = splitter
                self._splitter = splitter
            except Exception:
                self._splitter = None
                layout = eto_forms.DynamicLayout()
                layout.Spacing = eto_drawing.Size(6, 6)
                layout.AddRow(tab_ctrl)
                layout.AddRow(self._detail_panel)
                self.Content = layout

        def _api_base(self):
            return (self._txt_server.Text or "").strip().rstrip("/") or "http://127.0.0.1:8000"

        def _on_refresh_projects(self, sender, e):
            try:
                api_base = self._api_base()
                projects = _fetch_json(api_base, "/api/projects")
                self._projects = list(projects) if projects and isinstance(projects, list) else []
                self._drop_project.Items.Clear()
                try:
                    self._drop_commit_project.SelectedIndexChanged -= self._on_commit_project_changed
                except Exception:
                    pass
                self._drop_commit_project.Items.Clear()
                if not self._projects:
                    self._drop_project.Items.Add("(프로젝트 없음)")
                    self._drop_project.SelectedIndex = 0
                    self._drop_commit_project.Items.Add("(프로젝트 없음)")
                    self._drop_commit_project.SelectedIndex = 0
                    self._drop_commit.Items.Clear()
                    self._drop_commit.Items.Add("(프로젝트 선택)")
                    self._drop_commit.SelectedIndex = 0
                    self._commits = []
                else:
                    for p in self._projects:
                        name = (p.get("name") or "").strip() or "(이름 없음)"
                        self._drop_project.Items.Add(name)
                        self._drop_commit_project.Items.Add(name)
                    self._drop_project.SelectedIndex = 0
                    self._drop_commit_project.SelectedIndex = 0
                    self._commits = []
                    self._drop_commit.Items.Clear()
                    self._drop_commit.Items.Add("(버전 선택)")
                    self._drop_commit.SelectedIndex = 0
                    self._load_commits_for_selected_project()
                try:
                    self._drop_commit_project.SelectedIndexChanged += self._on_commit_project_changed
                except Exception:
                    pass
                self._update_next_commit_label()
                users = _fetch_json(api_base, "/api/users")
                self._users = list(users) if users and isinstance(users, list) else []
                self._drop_assignee.Items.Clear()
                self._drop_assignee.Items.Add("(선택)")
                for u in self._users:
                    name = (u.get("name") or "").strip() or (u.get("email") or "")
                    self._drop_assignee.Items.Add(name)
                self._drop_assignee.SelectedIndex = 0
                departments = _fetch_json(api_base, "/api/departments")
                self._departments = list(departments) if departments and isinstance(departments, list) else []
                self._drop_department.Items.Clear()
                self._drop_department.Items.Add("(선택)")
                for d in self._departments:
                    self._drop_department.Items.Add(str(d).strip() or "(없음)")
                self._drop_department.SelectedIndex = 0
            except Exception as ex:
                eto_forms.MessageBox.Show(self, "목록 불러오기 실패: {0}".format(ex), "CadManage", eto_forms.MessageBoxType.Error)

        def _load_commits_for_selected_project(self):
            if not self._projects:
                return
            idx = self._drop_project.SelectedIndex
            if idx < 0 or idx >= len(self._projects):
                return
            project_id = int(self._projects[idx].get("id"))
            api_base = self._api_base()
            commits_data = _fetch_json(api_base, "/api/projects/{0}/commits".format(project_id))
            commits = []
            if commits_data and isinstance(commits_data, dict):
                commits = commits_data.get("commits") or commits_data
            if not isinstance(commits, list):
                commits = []
            self._commits = list(commits)
            self._drop_commit.Items.Clear()
            if not self._commits:
                self._drop_commit.Items.Add("(버전 없음)")
                self._drop_commit.SelectedIndex = 0
            else:
                for c in self._commits:
                    cid = c.get("id")
                    vlab = (c.get("version_label") or "").strip() or "(버전)"
                    label = "#{0} {1}".format(cid, vlab)
                    self._drop_commit.Items.Add(label)
                self._drop_commit.SelectedIndex = 0
            minor_data = _fetch_json(api_base, "/api/projects/{0}/minor-classes".format(project_id))
            self._minor_classes = list((minor_data or {}).get("labels") or [])
            self._drop_class_minor.Items.Clear()
            self._drop_class_minor.Items.Add("(선택)")
            for lbl in self._minor_classes:
                self._drop_class_minor.Items.Add(str(lbl))
            self._drop_class_minor.SelectedIndex = 0
            work_data = _fetch_json(api_base, "/api/projects/{0}/work-types".format(project_id))
            self._work_types = list((work_data or {}).get("labels") or [])
            self._drop_class_work_type.Items.Clear()
            self._drop_class_work_type.Items.Add("(선택)")
            for lbl in self._work_types:
                self._drop_class_work_type.Items.Add(str(lbl))
            self._drop_class_work_type.SelectedIndex = 0

        def _on_project_changed(self, sender, e):
            idx = self._drop_project.SelectedIndex
            if 0 <= idx < len(self._drop_commit_project.Items):
                self._drop_commit_project.SelectedIndexChanged -= self._on_commit_project_changed
                self._drop_commit_project.SelectedIndex = idx
                self._drop_commit_project.SelectedIndexChanged += self._on_commit_project_changed
            self._load_commits_for_selected_project()

        def _update_next_commit_label(self):
            if not self._projects:
                self._lbl_next_commit.Text = "다음 커밋 번호: #-"
                return
            idx = self._drop_commit_project.SelectedIndex
            if idx < 0 or idx >= len(self._projects):
                self._lbl_next_commit.Text = "다음 커밋 번호: #-"
                return
            project_id = int(self._projects[idx].get("id"))
            api_base = self._api_base()
            commits_data = _fetch_json(api_base, "/api/projects/{0}/commits".format(project_id))
            commits = []
            if commits_data and isinstance(commits_data, dict):
                commits = commits_data.get("commits") or commits_data
            if not isinstance(commits, list):
                commits = []
            max_id = 0
            for c in commits:
                try:
                    cid = int(c.get("id") or 0)
                    if cid > max_id:
                        max_id = cid
                except (TypeError, ValueError):
                    pass
            next_id = max_id + 1
            self._lbl_next_commit.Text = "다음 커밋 번호: #{0}".format(next_id)

        def _on_commit_project_changed(self, sender, e):
            if not self._projects:
                return
            idx = self._drop_commit_project.SelectedIndex
            if idx < 0 or idx >= len(self._projects):
                return
            project_id = int(self._projects[idx].get("id"))
            api_base = self._api_base()
            self._update_next_commit_label()
            minor_data = _fetch_json(api_base, "/api/projects/{0}/minor-classes".format(project_id))
            self._minor_classes = list((minor_data or {}).get("labels") or [])
            self._drop_class_minor.Items.Clear()
            self._drop_class_minor.Items.Add("(선택)")
            for lbl in self._minor_classes:
                self._drop_class_minor.Items.Add(str(lbl))
            self._drop_class_minor.SelectedIndex = 0
            work_data = _fetch_json(api_base, "/api/projects/{0}/work-types".format(project_id))
            self._work_types = list((work_data or {}).get("labels") or [])
            self._drop_class_work_type.Items.Clear()
            self._drop_class_work_type.Items.Add("(선택)")
            for lbl in self._work_types:
                self._drop_class_work_type.Items.Add(str(lbl))
            self._drop_class_work_type.SelectedIndex = 0

        def _is_detail_expanded(self):
            try:
                return self.ClientSize.Width > getattr(self, "_base_width", 540)
            except Exception:
                return False

        def _collapse_detail(self):
            if getattr(self, "_splitter", None) is not None:
                try:
                    base = getattr(self, "_base_width", 540)
                    self.ClientSize = eto_drawing.Size(base, 480)
                    self._splitter.Position = base
                    self._btn_commit_detail.Text = ">"
                except Exception:
                    pass

        def _expand_detail(self):
            if getattr(self, "_splitter", None) is not None:
                try:
                    base = getattr(self, "_base_width", 540)
                    extra = getattr(self, "_detail_width", 260)
                    self.ClientSize = eto_drawing.Size(base + extra, 480)
                    self._splitter.Position = base
                    self._btn_commit_detail.Text = "<"
                except Exception:
                    pass

        def _on_commit_detail_click(self, sender, e):
            if self._is_detail_expanded():
                self._collapse_detail()
                return
            cidx = self._drop_commit.SelectedIndex
            if cidx < 0 or cidx >= len(self._commits):
                eto_forms.MessageBox.Show(self, "버전을 먼저 선택하세요.", "CadManage", eto_forms.MessageBoxType.Information)
                return
            api_base = self._api_base()
            commit_id = int(self._commits[cidx].get("id"))
            data = _fetch_json(api_base, "/api/commits/{0}".format(commit_id))
            if not data:
                eto_forms.MessageBox.Show(self, "상세 정보를 가져오지 못했습니다.", "CadManage", eto_forms.MessageBoxType.Error)
                return
            def _val(k, d=data):
                v = (d.get(k) or "").strip() if isinstance(d.get(k), (str, type(None))) else str(d.get(k, ""))
                return v or "(없음)"
            chg = (data.get("change_notes") or "").strip()
            if len(chg) > 200:
                chg = chg[:200] + "..."
            for k, lbl in self._detail_value_labels.items():
                if k == "change_notes":
                    lbl.Text = chg or "(없음)"
                elif k == "id":
                    lbl.Text = str(data.get("id", ""))
                else:
                    lbl.Text = _val(k)
            self._expand_detail()

        def _on_import_click(self, sender, e):
            api_base = self._api_base()
            pidx = self._drop_project.SelectedIndex
            cidx = self._drop_commit.SelectedIndex
            if pidx < 0 or pidx >= len(self._projects) or cidx < 0 or cidx >= len(self._commits):
                eto_forms.MessageBox.Show(self, "프로젝트와 버전을 선택한 뒤 DB에서 가져오기를 누르세요.", "CadManage", eto_forms.MessageBoxType.Information)
                return
            project_id = int(self._projects[pidx].get("id"))
            commit_id = int(self._commits[cidx].get("id"))
            info = {"api_base": api_base, "project_id": project_id, "commit_id": commit_id}
            try:
                _do_open_from_info_impl(info)
                eto_forms.MessageBox.Show(self, "도면 불러오기 완료.", "CadManage", eto_forms.MessageBoxType.Information)
            except Exception as ex:
                eto_forms.MessageBox.Show(self, "불러오기 실패: {}".format(ex), "CadManage", eto_forms.MessageBoxType.Error)

        def _get_commit_options(self):
            """폼의 커밋 설정 필드값을 commit_options dict로 반환."""
            opts = {}
            if self._projects and self._drop_commit_project.SelectedIndex >= 0 and self._drop_commit_project.SelectedIndex < len(self._projects):
                opts["project_id"] = int(self._projects[self._drop_commit_project.SelectedIndex].get("id"))
                opts["api_base"] = self._api_base()
            link = _load_link()
            if link and opts.get("parent_commit_id") is None:
                opts["parent_commit_id"] = link.get("parent_commit_id")
            v = (self._txt_version.Text or "").strip()
            if v:
                opts["version_label"] = v
            idx = self._drop_assignee.SelectedIndex if self._drop_assignee.SelectedIndex is not None else -1
            if idx > 0 and idx - 1 < len(self._users):
                v = (self._users[idx - 1].get("name") or "").strip()
                if v:
                    opts["assignee_name"] = v
            idx = self._drop_department.SelectedIndex if self._drop_department.SelectedIndex is not None else -1
            if idx > 0 and idx - 1 < len(self._departments):
                v = str(self._departments[idx - 1]).strip()
                if v:
                    opts["assignee_department"] = v
            idx = self._drop_class_pre.SelectedIndex if self._drop_class_pre.SelectedIndex is not None else -1
            if idx > 0 and idx <= 2:
                v = ["구조", "건축"][idx - 1]
                opts["class_pre"] = v
            idx = self._drop_class_major.SelectedIndex if self._drop_class_major.SelectedIndex is not None else -1
            if idx > 0 and idx <= 4:
                v = ["지하주차장", "아파트", "부대시설", "단위세대"][idx - 1]
                opts["class_major"] = v
            idx = self._drop_class_mid.SelectedIndex if self._drop_class_mid.SelectedIndex is not None else -1
            if idx > 0 and idx <= 3:
                v = ["평면", "단면", "일람"][idx - 1]
                opts["class_mid"] = v
            idx = self._drop_class_minor.SelectedIndex if self._drop_class_minor.SelectedIndex is not None else -1
            if idx > 0 and idx - 1 < len(self._minor_classes):
                v = str(self._minor_classes[idx - 1]).strip()
                if v:
                    opts["class_minor"] = v
            idx = self._drop_class_work_type.SelectedIndex if self._drop_class_work_type.SelectedIndex is not None else -1
            if idx > 0 and idx - 1 < len(self._work_types):
                v = str(self._work_types[idx - 1]).strip()
                if v:
                    opts["class_work_type"] = v
            v = (self._txt_change_notes.Text or "").strip()
            if v:
                opts["change_notes"] = v
            return opts if opts else None

        def _on_save_click(self, sender, e):
            try:
                CadManageSave(commit_options=self._get_commit_options())
                eto_forms.MessageBox.Show(self, "저장이 완료되었습니다.", "CadManage", eto_forms.MessageBoxType.Information)
            except Exception as ex:
                eto_forms.MessageBox.Show(self, "저장 실패: {}".format(ex), "CadManage", eto_forms.MessageBoxType.Error)

        def _on_close_click(self, sender, e):
            self.Close(False)


# RunScript로 실행 시: launch.json 있으면 자동 Open, 없으면 Eto 대화상자
if __name__ == "__main__":
    launch_path = _launch_file_path()
    if os.path.exists(launch_path):
        try:
            info = _read_launch_json(launch_path)
            try:
                os.remove(launch_path)
            except Exception:
                pass
            _do_open_from_info(info)
            print("디버그 로그(문제 시 확인): {}".format(_debug_log_path()))
        except Exception as e:
            print("자동 연동 실패:", e)
            import traceback
            traceback.print_exc()
            print("디버그 로그: {}".format(_debug_log_path()))
    else:
        if not _show_cadmanage_dialog():
            result = Rhino.Input.RhinoGet.GetString("CadManage: [1] 가져오기  [2] 저장 (Eto 미사용 시) (1/2)", False, "1")
            if result[0] == Rhino.Commands.Result.Success:
                choice = (result[1] or "1").strip()
                if choice == "2":
                    CadManageSave()
                else:
                    CadManageOpen()
