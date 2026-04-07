"""DXF 파싱 fixture 테스트."""
import io
import pytest
import ezdxf
from app.services.dxf_parser import parse_dxf
from app.utils.geom import wkt_points_to_list, transform_point_with_matrix


def _minimal_dxf_with_line() -> bytes:
    """LINE 하나만 있는 최소 DXF."""
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    msp.add_line((0, 0), (10, 10), dxfattribs={"layer": "0", "color": 1})
    buf = io.StringIO()
    doc.write(buf)
    return buf.getvalue().encode("utf-8")


def _minimal_dxf_with_circle() -> bytes:
    """CIRCLE 하나만 있는 DXF."""
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    msp.add_circle((5, 5), radius=3, dxfattribs={"layer": "0", "color": 2})
    buf = io.StringIO()
    doc.write(buf)
    return buf.getvalue().encode("utf-8")


def _minimal_dxf_with_wrapped_arc() -> bytes:
    """start>end 랩어라운드 ARC가 포함된 DXF."""
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    msp.add_arc(
        center=(10, 20),
        radius=5,
        start_angle=350,
        end_angle=10,
        dxfattribs={"layer": "0", "color": 2},
    )
    buf = io.StringIO()
    doc.write(buf)
    return buf.getvalue().encode("utf-8")


def _minimal_dxf_with_lwpolyline() -> bytes:
    """LWPOLYLINE 하나 있는 DXF."""
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    msp.add_lwpolyline([(0, 0), (1, 0), (1, 1)], dxfattribs={"layer": "0", "color": 1})
    buf = io.StringIO()
    doc.write(buf)
    return buf.getvalue().encode("utf-8")


def test_parse_dxf_line():
    dxf_bytes = _minimal_dxf_with_line()
    entities, block_defs, block_inserts, block_attrs, _ = parse_dxf(dxf_bytes)
    assert len(entities) == 1
    assert entities[0]["entity_type"] == "LINE"
    assert entities[0]["layer"] == "0"
    assert entities[0]["fingerprint"]
    assert "LINESTRING" in (entities[0].get("geom_wkt") or "")


def test_parse_dxf_circle():
    dxf_bytes = _minimal_dxf_with_circle()
    entities, block_defs, block_inserts, block_attrs, _ = parse_dxf(dxf_bytes)
    assert len(entities) == 1
    assert entities[0]["entity_type"] == "CIRCLE"
    assert entities[0]["fingerprint"]


def test_parse_dxf_arc_wraparound_uses_arc_path_not_center_point():
    dxf_bytes = _minimal_dxf_with_wrapped_arc()
    entities, _, _, _, _ = parse_dxf(dxf_bytes)
    assert len(entities) == 1
    arc = entities[0]
    assert arc["entity_type"] == "ARC"
    pts = wkt_points_to_list(arc.get("geom_wkt") or "")
    assert len(pts) >= 2

    center = (10.0, 20.0)
    # ARC 선분에 중심점이 포함되면 안 된다.
    assert not any(abs(p[0] - center[0]) < 1e-6 and abs(p[1] - center[1]) < 1e-6 for p in pts)

    # 시작/끝점이 350° -> 10°의 짧은 호를 따라가야 한다.
    import math

    exp_start = (10.0 + 5.0 * math.cos(math.radians(350.0)), 20.0 + 5.0 * math.sin(math.radians(350.0)))
    exp_end = (10.0 + 5.0 * math.cos(math.radians(10.0)), 20.0 + 5.0 * math.sin(math.radians(10.0)))
    assert pytest.approx(float(pts[0][0]), rel=0, abs=1e-5) == exp_start[0]
    assert pytest.approx(float(pts[0][1]), rel=0, abs=1e-5) == exp_start[1]
    assert pytest.approx(float(pts[-1][0]), rel=0, abs=1e-5) == exp_end[0]
    assert pytest.approx(float(pts[-1][1]), rel=0, abs=1e-5) == exp_end[1]


def test_parse_dxf_lwpolyline():
    dxf_bytes = _minimal_dxf_with_lwpolyline()
    entities, block_defs, block_inserts, block_attrs, _ = parse_dxf(dxf_bytes)
    assert len(entities) == 1
    assert entities[0]["entity_type"] == "LWPOLYLINE"
    assert entities[0]["fingerprint"]


def _minimal_dxf_with_hatch() -> bytes:
    """HATCH (solid fill) 하나만 있는 DXF."""
    doc = ezdxf.new("R2000")
    msp = doc.modelspace()
    hatch = msp.add_hatch(color=3)
    hatch.paths.add_polyline_path([(0, 0), (10, 0), (10, 10), (0, 10)], is_closed=True)
    buf = io.StringIO()
    doc.write(buf)
    return buf.getvalue().encode("utf-8")


def _minimal_dxf_with_hatch_edge_arc_full_circle() -> bytes:
    """EdgePath ArcEdge(0~360) 해치를 포함한 DXF."""
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    hatch = msp.add_hatch(color=3)
    hatch.set_pattern_fill("ANSI31", scale=1.0)
    edge_path = hatch.paths.add_edge_path()
    edge_path.add_arc((0, 0), radius=5, start_angle=0, end_angle=360, ccw=True)
    buf = io.StringIO()
    doc.write(buf)
    return buf.getvalue().encode("utf-8")


def test_parse_dxf_hatch():
    """HATCH가 파싱되어 entities에 포함되는지 검증."""
    dxf_bytes = _minimal_dxf_with_hatch()
    entities, block_defs, block_inserts, block_attrs, _ = parse_dxf(dxf_bytes)
    assert len(entities) == 1
    assert entities[0]["entity_type"] == "HATCH"
    assert "POLYGON" in (entities[0].get("geom_wkt") or "")
    assert entities[0].get("geom_wkt")


def test_parse_dxf_hatch_edge_arc_full_circle_fallback():
    dxf_bytes = _minimal_dxf_with_hatch_edge_arc_full_circle()
    entities, _, _, _, _ = parse_dxf(dxf_bytes)
    assert len(entities) == 1
    assert entities[0]["entity_type"] == "HATCH"
    assert "POLYGON" in (entities[0].get("geom_wkt") or "")


def _minimal_dxf_with_wipeout() -> bytes:
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    msp.add_wipeout([(0, 0), (10, 0), (10, 10), (0, 10)], dxfattribs={"layer": "0"})
    buf = io.StringIO()
    doc.write(buf)
    return buf.getvalue().encode("utf-8")


def test_parse_dxf_wipeout():
    dxf_bytes = _minimal_dxf_with_wipeout()
    entities, _, _, _, _ = parse_dxf(dxf_bytes)
    assert len(entities) == 1
    assert entities[0]["entity_type"] == "WIPEOUT"
    assert "POLYGON" in (entities[0].get("geom_wkt") or "")


def _dxf_with_invisible_entities() -> bytes:
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    msp.add_line((0, 0), (10, 0), dxfattribs={"layer": "0", "color": 1})
    msp.add_line((0, 1), (10, 1), dxfattribs={"layer": "0", "color": 2, "invisible": 1})

    child = doc.blocks.new("CHILD")
    child.add_line((0, 0), (2, 0), dxfattribs={"layer": "0", "color": 5})

    block = doc.blocks.new("PARENT")
    block.add_line((0, 0), (1, 0), dxfattribs={"layer": "0", "color": 3})
    block.add_line((0, 1), (1, 1), dxfattribs={"layer": "0", "color": 4, "invisible": 1})
    block.add_blockref("CHILD", (10, 0), dxfattribs={"invisible": 1})
    block.add_blockref("CHILD", (20, 0))

    msp.add_blockref("PARENT", (100, 0))
    buf = io.StringIO()
    doc.write(buf)
    return buf.getvalue().encode("utf-8")


def test_parse_dxf_skips_invisible_entities_and_nested_invisible_inserts():
    dxf_bytes = _dxf_with_invisible_entities()
    entities, _, block_inserts, _, _ = parse_dxf(dxf_bytes)

    lines = [e for e in entities if e["entity_type"] == "LINE"]
    assert len(lines) == 3  # model visible + block visible + nested visible insert
    assert len(block_inserts) == 1  # only visible modelspace INSERT

    ys = []
    for line in lines:
        pts = wkt_points_to_list(line.get("geom_wkt") or "")
        ys.extend([float(p[1]) for p in pts])
    assert not any(abs(y - 1.0) < 1e-6 for y in ys)  # invisible y=1 lines removed


def _dxf_with_block_and_insert() -> bytes:
    """BLOCK 정의(LINE, CIRCLE, closed LWPOLYLINE) + modelspace INSERT."""
    doc = ezdxf.new("R2010")
    block = doc.blocks.new("MYBLOCK")
    block.add_line((0, 0), (2, 0), dxfattribs={"layer": "0", "color": 1})
    block.add_circle((1, 1), radius=0.5, dxfattribs={"layer": "0", "color": 2})
    block.add_lwpolyline(
        [(0, 0), (1, 0), (1, 1), (0, 1)],
        close=True,
        dxfattribs={"layer": "0", "color": 3},
    )
    msp = doc.modelspace()
    msp.add_blockref("MYBLOCK", (5, 5))
    buf = io.StringIO()
    doc.write(buf)
    return buf.getvalue().encode("utf-8")


def test_parse_dxf_block_insert_world_coords():
    """블록 내부 LINE, CIRCLE, closed LWPOLYLINE가 월드 좌표로 파싱되는지 검증."""
    dxf_bytes = _dxf_with_block_and_insert()
    entities, block_defs, block_inserts, block_attrs, _ = parse_dxf(dxf_bytes)
    # 블록 폭발 시 LINE, CIRCLE, LWPOLYLINE 3개 엔티티
    assert len(entities) >= 3
    types = {e["entity_type"] for e in entities}
    assert "LINE" in types
    assert "CIRCLE" in types
    assert "LWPOLYLINE" in types
    # LINE (0,0)-(2,0) -> insert (5,5) 이면 (5,5)-(7,5)
    line_ent = next(e for e in entities if e["entity_type"] == "LINE")
    wkt = line_ent.get("geom_wkt") or ""
    assert "5" in wkt or "7" in wkt  # 월드 좌표에 insert offset 반영
    assert len(block_inserts) == 1
    assert block_inserts[0]["block_name"] == "MYBLOCK"


def _dxf_with_array_insert() -> bytes:
    """배열 INSERT (row_count=2, column_count=3)가 포함된 DXF."""
    doc = ezdxf.new("R2010")
    block = doc.blocks.new("DOT")
    block.add_circle((0, 0), radius=0.5, dxfattribs={"layer": "0", "color": 1})
    msp = doc.modelspace()
    insert = msp.add_blockref("DOT", (0, 0))
    insert.dxf.row_count = 2
    insert.dxf.column_count = 3
    insert.dxf.row_spacing = 10
    insert.dxf.column_spacing = 10
    buf = io.StringIO()
    doc.write(buf)
    return buf.getvalue().encode("utf-8")


def test_parse_dxf_array_insert():
    """배열 INSERT가 row x column 개수의 복제로 폭발하는지 검증."""
    dxf_bytes = _dxf_with_array_insert()
    entities, block_defs, block_inserts, block_attrs, _ = parse_dxf(dxf_bytes)
    # 2x3 = 6개 insert, 각각 CIRCLE 1개 -> 6개 CIRCLE
    assert len(entities) == 6
    circles = [e for e in entities if e["entity_type"] == "CIRCLE"]
    assert len(circles) == 6


def _dxf_with_nested_blocks() -> bytes:
    doc = ezdxf.new("R2010")
    leaf = doc.blocks.new("C_LEAF")
    leaf.add_line((0, 0), (1, 0), dxfattribs={"layer": "0", "color": 1})

    mid = doc.blocks.new("B_MID")
    mid.add_blockref("C_LEAF", (10, 0))

    top = doc.blocks.new("A_TOP")
    top.add_blockref("B_MID", (100, 0))

    msp = doc.modelspace()
    msp.add_blockref("A_TOP", (1000, 0))

    buf = io.StringIO()
    doc.write(buf)
    return buf.getvalue().encode("utf-8")


def _dxf_with_repeated_same_name_nested_inserts() -> bytes:
    doc = ezdxf.new("R2010")
    leaf = doc.blocks.new("LEAF")
    leaf.add_line((0, 0), (1, 0), dxfattribs={"layer": "0", "color": 2})

    mid = doc.blocks.new("MID")
    mid.add_blockref("LEAF", (0, 0))
    mid.add_blockref("LEAF", (10, 0))

    top = doc.blocks.new("TOP")
    top.add_blockref("MID", (0, 0))

    msp = doc.modelspace()
    msp.add_blockref("TOP", (0, 0))

    buf = io.StringIO()
    doc.write(buf)
    return buf.getvalue().encode("utf-8")


def test_parse_dxf_nested_block_hierarchy_path_is_created():
    dxf_bytes = _dxf_with_nested_blocks()
    entities, block_defs, block_inserts, block_attrs, _ = parse_dxf(dxf_bytes)

    assert len(block_inserts) == 1
    line_ents = [e for e in entities if e["entity_type"] == "LINE"]
    assert line_ents, "nested line entity must be emitted"

    path = (line_ents[0].get("props") or {}).get("block_hierarchy_path")
    assert isinstance(path, list)
    assert len(path) >= 2
    assert path[0]["name"] == "B_MID"
    assert path[1]["name"] == "C_LEAF"
    assert isinstance(path[0].get("instance_key"), str) and path[0]["instance_key"]
    assert isinstance(path[1].get("instance_key"), str) and path[1]["instance_key"]


def test_parse_dxf_repeated_same_name_nested_inserts_get_distinct_instance_keys():
    dxf_bytes = _dxf_with_repeated_same_name_nested_inserts()
    entities, block_defs, block_inserts, block_attrs, _ = parse_dxf(dxf_bytes)

    assert len(block_inserts) == 1
    line_ents = [e for e in entities if e["entity_type"] == "LINE"]
    assert len(line_ents) == 2

    leaf_keys = []
    for ent in line_ents:
        path = (ent.get("props") or {}).get("block_hierarchy_path") or []
        assert len(path) >= 2
        assert path[-1]["name"] == "LEAF"
        leaf_keys.append(path[-1]["instance_key"])

    assert len(set(leaf_keys)) == 2


def test_parse_dxf_non_block_entities_keep_no_block_hierarchy_path():
    dxf_bytes = _minimal_dxf_with_line()
    entities, block_defs, block_inserts, block_attrs, _ = parse_dxf(dxf_bytes)
    assert len(entities) == 1
    props = entities[0].get("props") or {}
    assert "block_hierarchy_path" not in props


def _dxf_with_text_alignment() -> bytes:
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()

    txt = msp.add_text("ALIGN_TXT", dxfattribs={"layer": "0", "color": 1, "height": 2.5})
    try:
        from ezdxf.enums import TextEntityAlignment

        txt.set_placement((100.0, 200.0), align=TextEntityAlignment.MIDDLE_CENTER)
    except Exception:
        txt.dxf.insert = (90.0, 190.0, 0.0)
        txt.dxf.align_point = (100.0, 200.0, 0.0)
        txt.dxf.halign = 1
        txt.dxf.valign = 2

    mt = msp.add_mtext("ALIGN_MTEXT", dxfattribs={"layer": "0", "color": 2, "char_height": 3.0})
    mt.dxf.insert = (300.0, 400.0, 0.0)
    mt.dxf.attachment_point = 5  # middle-center

    buf = io.StringIO()
    doc.write(buf)
    return buf.getvalue().encode("utf-8")


def test_parse_dxf_text_alignment_props_and_anchor_point():
    dxf_bytes = _dxf_with_text_alignment()
    entities, block_defs, block_inserts, block_attrs, _ = parse_dxf(dxf_bytes)

    text_ent = next(e for e in entities if e["entity_type"] == "TEXT")
    props = text_ent.get("props") or {}
    assert props.get("halign") == 1
    assert props.get("valign") == 2
    assert pytest.approx(float(props.get("text_align_x")), rel=0, abs=1e-6) == 100.0
    assert pytest.approx(float(props.get("text_align_y")), rel=0, abs=1e-6) == 200.0
    assert "POINT" in (text_ent.get("geom_wkt") or "")
    assert "100" in (text_ent.get("geom_wkt") or "")
    assert "200" in (text_ent.get("geom_wkt") or "")


def test_parse_dxf_mtext_attachment_maps_to_halign_valign():
    dxf_bytes = _dxf_with_text_alignment()
    entities, block_defs, block_inserts, block_attrs, _ = parse_dxf(dxf_bytes)

    mtext_ent = next(e for e in entities if e["entity_type"] == "MTEXT")
    props = mtext_ent.get("props") or {}
    assert props.get("attachment_point") == 5
    assert props.get("halign") == 1
    assert props.get("valign") == 2
    assert pytest.approx(float(props.get("text_align_x")), rel=0, abs=1e-6) == 300.0
    assert pytest.approx(float(props.get("text_align_y")), rel=0, abs=1e-6) == 400.0


def _transform_point_chain(point, matrices):
    x, y, z = float(point[0]), float(point[1]), float(point[2]) if len(point) > 2 else 0.0
    for m in matrices:
        x, y, z = transform_point_with_matrix(x, y, z, matrix=m)
    return (x, y, z)


def test_parse_dxf_nested_block_transform_matches_recursive_virtual_entities():
    doc = ezdxf.new("R2010")
    leaf = doc.blocks.new("LEAF")
    leaf.add_line((0, 0), (1, 0), dxfattribs={"layer": "L1", "color": 2})

    mid = doc.blocks.new("MID")
    i1 = mid.add_blockref("LEAF", (10, 0))
    i1.dxf.rotation = 30
    i1.dxf.xscale = 2
    i1.dxf.yscale = 1

    top = doc.blocks.new("TOP")
    i2 = top.add_blockref("MID", (100, 50))
    i2.dxf.rotation = 45
    i2.dxf.xscale = 1.5
    i2.dxf.yscale = 0.5

    msp = doc.modelspace()
    root_insert = msp.add_blockref("TOP", (1000, 2000))
    root_insert.dxf.rotation = 15
    root_insert.dxf.xscale = -1
    root_insert.dxf.yscale = 2

    chain = [i1.matrix44(), i2.matrix44(), root_insert.matrix44()]
    exp_start = _transform_point_chain((0.0, 0.0, 0.0), chain)
    exp_end = _transform_point_chain((1.0, 0.0, 0.0), chain)

    buf = io.StringIO()
    doc.write(buf)
    entities, _, _, _, _ = parse_dxf(buf.getvalue().encode("utf-8"))

    lines = [e for e in entities if e["entity_type"] == "LINE"]
    assert len(lines) == 1
    parsed_pts = wkt_points_to_list(lines[0]["geom_wkt"])
    assert len(parsed_pts) >= 2
    p0 = (float(parsed_pts[0][0]), float(parsed_pts[0][1]))
    p1 = (float(parsed_pts[1][0]), float(parsed_pts[1][1]))
    forward = (
        abs(p0[0] - exp_start[0]) < 1e-6
        and abs(p0[1] - exp_start[1]) < 1e-6
        and abs(p1[0] - exp_end[0]) < 1e-6
        and abs(p1[1] - exp_end[1]) < 1e-6
    )
    reverse = (
        abs(p0[0] - exp_end[0]) < 1e-6
        and abs(p0[1] - exp_end[1]) < 1e-6
        and abs(p1[0] - exp_start[0]) < 1e-6
        and abs(p1[1] - exp_start[1]) < 1e-6
    )
    assert forward or reverse


def test_parse_dxf_block_bylayer_keeps_nonzero_child_layer_and_layer0_inherits_insert_layer():
    doc = ezdxf.new("R2010")
    doc.layers.add("L1", color=1)
    doc.layers.add("L2", color=5)

    block = doc.blocks.new("B")
    block.add_line((0, 0), (1, 0), dxfattribs={"layer": "L2", "color": 256})
    block.add_line((0, 1), (1, 1), dxfattribs={"layer": "0", "color": 256})

    msp = doc.modelspace()
    msp.add_blockref("B", (10, 0), dxfattribs={"layer": "L1", "color": 256})

    buf = io.StringIO()
    doc.write(buf)
    entities, _, _, _, layer_colors = parse_dxf(buf.getvalue().encode("utf-8"))
    lines = [e for e in entities if e["entity_type"] == "LINE"]
    assert len(lines) == 2

    l2_line = next(e for e in lines if e["layer"] == "L2")
    l1_line = next(e for e in lines if e["layer"] == "L1")
    assert l2_line["color"] == 256
    assert l1_line["color"] == 256
    assert layer_colors.get("L1") == 1
    assert layer_colors.get("L2") == 5


def test_parse_dxf_block_text_alignment_props_are_transformed_to_world():
    doc = ezdxf.new("R2010")
    block = doc.blocks.new("TB")
    txt = block.add_text("HELLO", dxfattribs={"layer": "0", "color": 1, "height": 2.5})
    try:
        from ezdxf.enums import TextEntityAlignment

        txt.set_placement((1.0, 1.0), align=TextEntityAlignment.MIDDLE_CENTER)
    except Exception:
        txt.dxf.insert = (0.5, 0.5, 0.0)
        txt.dxf.align_point = (1.0, 1.0, 0.0)
        txt.dxf.halign = 1
        txt.dxf.valign = 2
    doc.modelspace().add_blockref("TB", (10, 0))

    buf = io.StringIO()
    doc.write(buf)
    entities, _, _, _, _ = parse_dxf(buf.getvalue().encode("utf-8"))
    text_ent = next(e for e in entities if e["entity_type"] == "TEXT")
    props = text_ent.get("props") or {}
    geom_pts = wkt_points_to_list(text_ent["geom_wkt"])
    assert geom_pts
    assert pytest.approx(float(geom_pts[0][0]), rel=0, abs=1e-6) == 11.0
    assert pytest.approx(float(geom_pts[0][1]), rel=0, abs=1e-6) == 1.0
    assert pytest.approx(float(props.get("text_align_x")), rel=0, abs=1e-6) == 11.0
    assert pytest.approx(float(props.get("text_align_y")), rel=0, abs=1e-6) == 1.0
    assert pytest.approx(float(props.get("insert_x")), rel=0, abs=1e-6) == 11.0
    assert pytest.approx(float(props.get("insert_y")), rel=0, abs=1e-6) == 1.0


def _dxf_with_extended_supported_types() -> bytes:
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    msp.add_ellipse((0, 0), major_axis=(10, 0), ratio=0.5, dxfattribs={"layer": "0", "color": 1})
    msp.add_spline([(0, 0), (4, 6), (9, -1), (15, 0)], dxfattribs={"layer": "0", "color": 2})
    msp.add_3dface([(0, 0, 0), (2, 0, 0), (2, 1, 0), (0, 1, 0)], dxfattribs={"layer": "0", "color": 3})
    msp.add_solid([(5, 5, 0), (7, 5, 0), (7, 6, 0), (5, 6, 0)], dxfattribs={"layer": "0", "color": 4})
    buf = io.StringIO()
    doc.write(buf)
    return buf.getvalue().encode("utf-8")


def test_parse_dxf_extended_supported_types_in_modelspace():
    dxf_bytes = _dxf_with_extended_supported_types()
    entities, _, _, _, _ = parse_dxf(dxf_bytes)
    wanted = {"ELLIPSE", "SPLINE", "3DFACE", "SOLID"}
    found = {e["entity_type"] for e in entities}
    assert wanted.issubset(found)
    for et in wanted:
        ent = next(e for e in entities if e["entity_type"] == et)
        assert "LINESTRING" in (ent.get("geom_wkt") or "")
        pts = wkt_points_to_list(ent.get("geom_wkt") or "")
        assert len(pts) >= 3
        assert ent.get("fingerprint")


def _virtual_entity_points(virtual_entity):
    dt = virtual_entity.dxftype()
    if dt == "ELLIPSE":
        return [(float(v[0]), float(v[1]), float(v[2]) if len(v) > 2 else 0.0) for v in virtual_entity.flattening(0.5, segments=16)]
    if dt == "SPLINE":
        return [(float(v[0]), float(v[1]), float(v[2]) if len(v) > 2 else 0.0) for v in virtual_entity.flattening(0.5, segments=8)]
    if dt in ("3DFACE", "SOLID"):
        verts = list(virtual_entity.wcs_vertices()) if hasattr(virtual_entity, "wcs_vertices") else []
        pts = []
        for v in verts:
            pts.append((float(v[0]), float(v[1]), float(v[2]) if len(v) > 2 else 0.0))
        if pts and pts[0] != pts[-1]:
            pts.append(pts[0])
        return pts
    return []


def test_parse_dxf_nested_insert_world_coords_for_extended_supported_types():
    doc = ezdxf.new("R2010")
    leaf = doc.blocks.new("EXT_LEAF")
    leaf.add_ellipse((0, 0), major_axis=(4, 0), ratio=0.4, dxfattribs={"layer": "0", "color": 1})
    leaf.add_spline([(0, 0), (2, 3), (6, -1), (9, 0)], dxfattribs={"layer": "0", "color": 2})
    leaf.add_3dface([(0, 0, 0), (1, 0, 0), (1, 2, 0), (0, 2, 0)], dxfattribs={"layer": "0", "color": 3})
    leaf.add_solid([(2, 2, 0), (3, 2, 0), (3, 3, 0), (2, 3, 0)], dxfattribs={"layer": "0", "color": 4})

    mid = doc.blocks.new("EXT_MID")
    i1 = mid.add_blockref("EXT_LEAF", (10, 0))
    i1.dxf.rotation = 35
    i1.dxf.xscale = 1.7
    i1.dxf.yscale = 0.8

    top = doc.blocks.new("EXT_TOP")
    i2 = top.add_blockref("EXT_MID", (120, 50))
    i2.dxf.rotation = -20
    i2.dxf.xscale = -1.2
    i2.dxf.yscale = 1.4

    msp = doc.modelspace()
    root_insert = msp.add_blockref("EXT_TOP", (1000, 2000))
    root_insert.dxf.rotation = 15
    root_insert.dxf.xscale = 0.9
    root_insert.dxf.yscale = 1.1

    chain = [i1.matrix44(), i2.matrix44(), root_insert.matrix44()]
    expected = {}
    for ent in leaf:
        dt = ent.dxftype()
        if dt not in ("ELLIPSE", "SPLINE", "3DFACE", "SOLID"):
            continue
        pts = _virtual_entity_points(ent)
        assert pts
        world = [_transform_point_chain(p, chain) for p in pts]
        xs = [p[0] for p in world]
        ys = [p[1] for p in world]
        expected[dt] = (min(xs), min(ys), max(xs), max(ys))

    buf = io.StringIO()
    doc.write(buf)
    entities, _, _, _, _ = parse_dxf(buf.getvalue().encode("utf-8"))

    for et in ("ELLIPSE", "SPLINE", "3DFACE", "SOLID"):
        ent = next(e for e in entities if e["entity_type"] == et)
        pts = wkt_points_to_list(ent.get("geom_wkt") or "")
        assert pts
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        got_bbox = (min(xs), min(ys), max(xs), max(ys))
        exp_bbox = expected[et]
        assert pytest.approx(got_bbox[0], rel=0, abs=1e-6) == exp_bbox[0]
        assert pytest.approx(got_bbox[1], rel=0, abs=1e-6) == exp_bbox[1]
        assert pytest.approx(got_bbox[2], rel=0, abs=1e-6) == exp_bbox[2]
        assert pytest.approx(got_bbox[3], rel=0, abs=1e-6) == exp_bbox[3]
