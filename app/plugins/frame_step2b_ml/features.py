"""
2b ML: 기하 특징·래스터 유틸. 교사 신호는 2a 벽 목록(teacher_walls_step2a).
"""
from __future__ import annotations

import math
from typing import Any

import numpy as np


def _mid(seg: dict[str, Any] | None) -> tuple[float, float]:
    if not seg:
        return 0.0, 0.0
    p1 = seg.get("p1") or {}
    p2 = seg.get("p2") or {}
    return (
        (float(p1.get("x") or 0) + float(p2.get("x") or 0)) / 2,
        (float(p1.get("y") or 0) + float(p2.get("y") or 0)) / 2,
    )


def wall_feature_row(w: dict[str, Any]) -> np.ndarray:
    """표 형 모델용 8차원 특징."""
    sa = w.get("seg_a") or {}
    sb = w.get("seg_b") or {}
    la = float(sa.get("len") or 0)
    lb = float(sb.get("len") or 0)
    th = float(w.get("thickness_mm") or 0)
    aa = float(sa.get("axis_angle") or 0)
    ab = float(sb.get("axis_angle") or 0)
    da = abs(aa - ab)
    while da > math.pi:
        da -= math.pi
    ma, mb = _mid(sa), _mid(sb)
    cx = (ma[0] + mb[0]) / 2
    cy = (ma[1] + mb[1]) / 2
    return np.array(
        [th, la, lb, min(la, lb), max(la, lb), da, cx, cy],
        dtype=np.float64,
    )


def payload_bounds(payload: dict[str, Any], pad_ratio: float = 0.02) -> tuple[float, float, float, float]:
    xs: list[float] = []
    ys: list[float] = []
    for seg in payload.get("wall_step2a_source_segs") or []:
        if not seg:
            continue
        for p in (seg.get("p1"), seg.get("p2")):
            if p:
                xs.append(float(p.get("x") or 0))
                ys.append(float(p.get("y") or 0))
    for w in payload.get("teacher_walls_step2a") or []:
        for key in ("seg_a", "seg_b"):
            s = (w or {}).get(key) or {}
            for p in (s.get("p1"), s.get("p2")):
                if p:
                    xs.append(float(p.get("x") or 0))
                    ys.append(float(p.get("y") or 0))
    tw12 = payload.get("teacher_walls_step12")
    if isinstance(tw12, dict):
        for _ck in ("121", "122", "123", "124"):
            for w in tw12.get(_ck) or []:
                if not isinstance(w, dict):
                    continue
                for key in ("seg_a", "seg_b"):
                    s = w.get(key) or {}
                    for p in (s.get("p1"), s.get("p2")):
                        if p:
                            xs.append(float(p.get("x") or 0))
                            ys.append(float(p.get("y") or 0))
    if not xs:
        return -1.0, -1.0, 1.0, 1.0
    x0, x1 = min(xs), max(xs)
    y0, y1 = min(ys), max(ys)
    dx = max(x1 - x0, 1.0)
    dy = max(y1 - y0, 1.0)
    px, py = dx * pad_ratio, dy * pad_ratio
    return x0 - px, y0 - py, x1 + px, y1 + py


def world_to_grid(
    x: float, y: float, x0: float, y0: float, x1: float, y1: float, size: int
) -> tuple[int, int]:
    if x1 <= x0 or y1 <= y0:
        return 0, 0
    gx = int((x - x0) / (x1 - x0) * (size - 1))
    gy = int((y - y0) / (y1 - y0) * (size - 1))
    return max(0, min(size - 1, gx)), max(0, min(size - 1, gy))


def rasterize_segments(payload: dict[str, Any], size: int = 64) -> tuple[np.ndarray, tuple[float, float, float, float]]:
    x0, y0, x1, y1 = payload_bounds(payload)
    grid = np.zeros((size, size), dtype=np.float32)
    for seg in payload.get("wall_step2a_source_segs") or []:
        if not seg or not seg.get("p1") or not seg.get("p2"):
            continue
        p1, p2 = seg["p1"], seg["p2"]
        x_a, y_a = float(p1.get("x") or 0), float(p1.get("y") or 0)
        x_b, y_b = float(p2.get("x") or 0), float(p2.get("y") or 0)
        ia, ja = world_to_grid(x_a, y_a, x0, y0, x1, y1, size)
        ib, jb = world_to_grid(x_b, y_b, x0, y0, x1, y1, size)
        n = max(abs(ib - ia), abs(jb - ja), 1)
        for t in range(n + 1):
            u = t / n
            ii = int(ia + (ib - ia) * u)
            jj = int(ja + (jb - ja) * u)
            if 0 <= ii < size and 0 <= jj < size:
                grid[jj, ii] = 1.0
    return grid, (x0, y0, x1, y1)


# JSONL 학습용: 벽 객체에만 사용. 추론 응답에서는 제거됨.
STEP2B_TRAIN_LABEL_KEY = "_step2b_train_label"
STEP2B_TRAIN_NOTE_KEY = "_step2b_train_note"


def wall_train_label(w: dict[str, Any] | None) -> int | None:
    """
    None: 양성으로 간주(2a 교사 기본).
    0: 학습 시 음성(오탐·제외할 벽).
    1: 양성 명시.
    """
    if not isinstance(w, dict) or STEP2B_TRAIN_LABEL_KEY not in w:
        return None
    v = w[STEP2B_TRAIN_LABEL_KEY]
    if v in (0, "0", False):
        return 0
    return 1


def iter_teacher_wall_dicts(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """2a 교사 + 1.2.1~1.2.4(teacher_walls_step12) 벽 객체를 순서대로 나열. 학습·마스크·GNN 양성 집합용."""
    out: list[dict[str, Any]] = []
    for w in payload.get("teacher_walls_step2a") or []:
        if isinstance(w, dict):
            out.append(w)
    tw12 = payload.get("teacher_walls_step12")
    if isinstance(tw12, dict):
        for ck in ("121", "122", "123", "124"):
            for w in tw12.get(ck) or []:
                if isinstance(w, dict):
                    out.append(w)
    return out


def payload_has_explicit_wall_labels(payload: dict[str, Any]) -> bool:
    for w in iter_teacher_wall_dicts(payload):
        if STEP2B_TRAIN_LABEL_KEY in w:
            return True
    return False


def rasterize_teacher_mask(
    payload: dict[str, Any], size: int = 64
) -> tuple[np.ndarray, tuple[float, float, float, float]]:
    x0, y0, x1, y1 = payload_bounds(payload)
    mask = np.zeros((size, size), dtype=np.float32)
    for w in iter_teacher_wall_dicts(payload):
        if wall_train_label(w) == 0:
            continue
        sa, sb = w.get("seg_a") or {}, w.get("seg_b") or {}
        pts = []
        for s in (sa, sb):
            for p in (s.get("p1"), s.get("p2")):
                if p:
                    gx, gy = world_to_grid(
                        float(p.get("x") or 0),
                        float(p.get("y") or 0),
                        x0,
                        y0,
                        x1,
                        y1,
                        size,
                    )
                    pts.append((gx, gy))
        if len(pts) >= 3:
            for gx, gy in pts:
                if 0 <= gx < size and 0 <= gy < size:
                    mask[gy, gx] = 1.0
            mxa = int(round(sum(p[0] for p in pts) / len(pts)))
            mya = int(round(sum(p[1] for p in pts) / len(pts)))
            if 0 <= mxa < size and 0 <= mya < size:
                mask[mya, mxa] = 1.0
    return mask, (x0, y0, x1, y1)


def wall_center_grid(
    w: dict[str, Any], bounds: tuple[float, float, float, float], size: int
) -> tuple[int, int]:
    x0, y0, x1, y1 = bounds
    sa, sb = w.get("seg_a") or {}, w.get("seg_b") or {}
    ma, mb = _mid(sa), _mid(sb)
    cx, cy = (ma[0] + mb[0]) / 2, (ma[1] + mb[1]) / 2
    return world_to_grid(cx, cy, x0, y0, x1, y1, size)


def build_graph_tensors(
    payload: dict[str, Any], max_nodes: int = 400, k: int = 8
) -> tuple[np.ndarray, np.ndarray, np.ndarray, tuple[float, float, float, float]]:
    """노드 특징 (N,F), edge_index (2,E) 무향 중복 포함, bounds."""
    segs = [s for s in (payload.get("wall_step2a_source_segs") or []) if s and s.get("p1") and s.get("p2")][:max_nodes]
    n = len(segs)
    x0, y0, x1, y1 = payload_bounds(payload)
    dx = max(x1 - x0, 1.0)
    dy = max(y1 - y0, 1.0)
    feats = []
    mids = []
    for seg in segs:
        p1, p2 = seg["p1"], seg["p2"]
        x_a, y_a = float(p1.get("x") or 0), float(p1.get("y") or 0)
        x_b, y_b = float(p2.get("x") or 0), float(p2.get("y") or 0)
        mx, my = (x_a + x_b) / 2, (y_a + y_b) / 2
        leng = float(seg.get("len") or math.hypot(x_b - x_a, y_b - y_a))
        ang = float(seg.get("axis_angle") or math.atan2(y_b - y_a, x_b - x_a))
        feats.append(
            [
                leng / 5000.0,
                math.cos(ang),
                math.sin(ang),
                (mx - x0) / dx,
                (my - y0) / dy,
            ]
        )
        mids.append((mx, my))
    X = np.array(feats, dtype=np.float32) if feats else np.zeros((0, 5), dtype=np.float32)
    edges: list[list[int]] = []
    if n > 1:
        dist = np.zeros((n, n), dtype=np.float64)
        for i in range(n):
            for j in range(i + 1, n):
                d = math.hypot(mids[i][0] - mids[j][0], mids[i][1] - mids[j][1])
                dist[i, j] = d
                dist[j, i] = d
        for i in range(n):
            neigh = np.argsort(dist[i])[: k + 1]
            for j in neigh:
                if j != i:
                    edges.append([i, j])
                    edges.append([j, i])
    if not edges and n > 0:
        for i in range(n):
            edges.append([i, i])
    E = np.array(edges, dtype=np.int64).T if edges else np.zeros((2, 0), dtype=np.int64)
    return X, E, np.array(mids, dtype=np.float64), (x0, y0, x1, y1)


def teacher_entity_positive_set(payload: dict[str, Any]) -> set[int]:
    pos: set[int] = set()
    for w in iter_teacher_wall_dicts(payload):
        if wall_train_label(w) == 0:
            continue
        for eid in w.get("entity_ids") or []:
            try:
                pos.add(int(eid))
            except (TypeError, ValueError):
                continue
        for key in ("seg_a", "seg_b"):
            s = w.get(key) or {}
            for eid in s.get("entity_ids") or []:
                try:
                    pos.add(int(eid))
                except (TypeError, ValueError):
                    continue
    return pos
