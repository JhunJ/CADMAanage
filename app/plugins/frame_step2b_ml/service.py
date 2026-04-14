"""
2b 추론: 백엔드별로 teacher_walls_step2a를 필터/재해석. 모델 없으면 교사 그대로 반환.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Literal

import joblib
import numpy as np

from app.plugins.frame_step2b_ml.features import (
    build_graph_tensors,
    iter_teacher_wall_dicts,
    payload_has_explicit_wall_labels,
    rasterize_segments,
    rasterize_teacher_mask,
    teacher_entity_positive_set,
    wall_center_grid,
    wall_feature_row,
    wall_train_label,
)
logger = logging.getLogger(__name__)

_STEP2B_META_KEYS = ("_step2b_train_label", "_step2b_train_note", "_step2b_export", "_step2b_teacher_source")


def _strip_step2b_train_meta_wall(w: dict[str, Any]) -> dict[str, Any]:
    d = dict(w)
    for k in _STEP2B_META_KEYS:
        d.pop(k, None)
    return d


def _strip_step2b_train_meta_walls(walls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [_strip_step2b_train_meta_wall(x) for x in walls]

BackendName = Literal["cnn", "xgb", "rf", "mlp", "gnn"]

PROJECT_ROOT = Path(__file__).resolve().parents[3]
MODEL_DIR = PROJECT_ROOT / "data" / "ml" / "step2b"


def _teacher_walls(payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw = payload.get("teacher_walls_step2a") or []
    return [dict(w) for w in raw if isinstance(w, dict)]


def _tabular_filter(
    backend: str,
    walls: list[dict[str, Any]],
    proba_threshold: float = 0.5,
) -> list[dict[str, Any]]:
    path = MODEL_DIR / f"{backend}.joblib"
    if not path.is_file():
        return walls
    try:
        bundle = joblib.load(path)
        model = bundle.get("model")
        if model is None or not walls:
            return walls
        X = np.stack([wall_feature_row(w) for w in walls], axis=0)
        if hasattr(model, "predict_proba"):
            pr = model.predict_proba(X)
            if pr.shape[1] > 1:
                keep = pr[:, 1] >= proba_threshold
            else:
                keep = model.predict(X).astype(bool)
        else:
            keep = model.predict(X).astype(bool)
        filtered = [w for w, k in zip(walls, keep) if k]
        return filtered if filtered else walls
    except Exception:
        logger.exception("tabular infer %s", backend)
        return walls


def _cnn_filter(walls: list[dict[str, Any]], payload: dict[str, Any]) -> list[dict[str, Any]]:
    path = MODEL_DIR / "cnn.pt"
    if not path.is_file() or not walls:
        return walls
    try:
        import torch

        from app.plugins.frame_step2b_ml.torch_models import TinyWallCNN

        try:
            ckpt = torch.load(path, map_location="cpu", weights_only=False)
        except TypeError:
            ckpt = torch.load(path, map_location="cpu")
        size = int(ckpt.get("grid_size", 64))
        net = TinyWallCNN(size)
        net.load_state_dict(ckpt["state_dict"])
        net.eval()
        grid, bounds = rasterize_segments(payload, size)
        x = torch.from_numpy(grid).float().unsqueeze(0).unsqueeze(0)
        with torch.no_grad():
            logits = net(x)
            mask = torch.sigmoid(logits[0, 0]).numpy()
        out: list[dict[str, Any]] = []
        thr = float(ckpt.get("threshold", 0.35))
        for w in walls:
            gi, gj = wall_center_grid(w, bounds, size)
            r = 2
            s = mask[
                max(0, gj - r) : min(size, gj + r + 1),
                max(0, gi - r) : min(size, gi + r + 1),
            ]
            if s.size == 0 or float(s.mean()) >= thr:
                out.append(w)
        return out if out else walls
    except Exception:
        logger.exception("cnn infer")
        return walls


def _gnn_filter(walls: list[dict[str, Any]], payload: dict[str, Any]) -> list[dict[str, Any]]:
    path = MODEL_DIR / "gnn.pt"
    if not path.is_file() or not walls:
        return walls
    try:
        import torch

        from app.plugins.frame_step2b_ml.torch_models import (
            TinySegGNN,
            nearest_node_index,
            symmetric_normalized_adjacency,
        )

        try:
            ckpt = torch.load(path, map_location="cpu", weights_only=False)
        except TypeError:
            ckpt = torch.load(path, map_location="cpu")
        Xn, E, mids_np, _bounds = build_graph_tensors(payload)
        if Xn.shape[0] == 0:
            return walls
        net = TinySegGNN(in_dim=Xn.shape[1], hidden=int(ckpt.get("hidden", 32)))
        net.load_state_dict(ckpt["state_dict"])
        net.eval()
        ei = torch.from_numpy(E).long()
        adj = symmetric_normalized_adjacency(Xn.shape[0], ei)
        x = torch.from_numpy(Xn).float()
        with torch.no_grad():
            logits = net(x, adj)
            prob = torch.sigmoid(logits).numpy()
        mids = torch.from_numpy(mids_np).double()
        thr = float(ckpt.get("threshold", 0.28))
        out: list[dict[str, Any]] = []
        for w in walls:
            sa, sb = w.get("seg_a") or {}, w.get("seg_b") or {}
            ok = True
            for seg in (sa, sb):
                p1, p2 = seg.get("p1") or {}, seg.get("p2") or {}
                qx = (float(p1.get("x") or 0) + float(p2.get("x") or 0)) / 2
                qy = (float(p1.get("y") or 0) + float(p2.get("y") or 0)) / 2
                ni = nearest_node_index(mids, qx, qy)
                if ni < 0 or prob[ni] < thr:
                    ok = False
                    break
            if ok:
                out.append(w)
        return out if out else walls
    except Exception:
        logger.exception("gnn infer")
        return walls


def infer_walls(backend: BackendName, payload: dict[str, Any]) -> list[dict[str, Any]]:
    walls = _teacher_walls(payload)
    if backend in ("rf", "xgb", "mlp"):
        out = _tabular_filter(backend, walls)
    elif backend == "cnn":
        out = _cnn_filter(walls, payload)
    elif backend == "gnn":
        out = _gnn_filter(walls, payload)
    else:
        out = walls
    return _strip_step2b_train_meta_walls(out)


def train_from_jsonl_dir(data_dir: Path) -> dict[str, Any]:
    """JSONL 샘플(한 줄 = infer 페이로드)로 RF/XGB/MLP/CNN/GNN 학습."""
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.neural_network import MLPClassifier

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    samples: list[dict[str, Any]] = []
    for p in sorted(data_dir.glob("*.jsonl")):
        with open(p, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                samples.append(json.loads(line))
    if not samples:
        return {"ok": False, "error": "no samples"}

    # --- Tabular ---
    # - 어떤 샘플에도 벽에 `_step2b_train_label` 이 없으면: 양성=2a 교사, 음성=가우시안 노이즈(부트스트랩).
    # - 라벨이 하나라도 있으면: `_step2b_train_label`: 0=음성, 1·생략=양성. 음성 행이 없으면 노이즈 음성만 보강.
    samples_have_explicit = any(payload_has_explicit_wall_labels(pl) for pl in samples)
    noise_scale = np.array([20, 200, 200, 200, 200, 0.5, 500, 500], dtype=np.float64)
    X_list: list[np.ndarray] = []
    y_list: list[int] = []
    for pl in samples:
        for w in iter_teacher_wall_dicts(pl):
            y = 0 if wall_train_label(w) == 0 else 1
            X_list.append(wall_feature_row(w))
            y_list.append(y)
            if not samples_have_explicit and y == 1:
                X_list.append(wall_feature_row(w) + np.random.randn(8) * noise_scale)
                y_list.append(0)
    if samples_have_explicit and sum(1 for y in y_list if y == 0) == 0:
        for pl in samples:
            for w in iter_teacher_wall_dicts(pl):
                if wall_train_label(w) != 0:
                    X_list.append(wall_feature_row(w) + np.random.randn(8) * noise_scale)
                    y_list.append(0)
                    break
    if len(X_list) < 4:
        return {"ok": False, "error": "too few wall rows for tabular train"}
    X = np.stack(X_list, axis=0)
    y = np.array(y_list, dtype=np.int64)
    rf = RandomForestClassifier(n_estimators=80, max_depth=12, random_state=42, n_jobs=-1)
    rf.fit(X, y)
    joblib.dump({"model": rf, "kind": "rf"}, MODEL_DIR / "rf.joblib")

    try:
        import xgboost as xgb

        xgb_clf = xgb.XGBClassifier(
            n_estimators=120,
            max_depth=6,
            learning_rate=0.08,
            subsample=0.9,
            random_state=42,
            n_jobs=-1,
        )
        xgb_clf.fit(X, y)
        joblib.dump({"model": xgb_clf, "kind": "xgb"}, MODEL_DIR / "xgb.joblib")
    except Exception as e:
        logger.warning("xgboost train skipped: %s", e)

    mlp = MLPClassifier(hidden_layer_sizes=(64, 32), max_iter=500, random_state=42)
    mlp.fit(X, y)
    joblib.dump({"model": mlp, "kind": "mlp"}, MODEL_DIR / "mlp.joblib")

    # --- CNN ---
    try:
        import torch
        import torch.nn.functional as F
        from torch import optim

        from app.plugins.frame_step2b_ml.torch_models import TinyWallCNN

        size = 64
        net = TinyWallCNN(size)
        opt = optim.Adam(net.parameters(), lr=1e-3)
        grids_x: list[np.ndarray] = []
        grids_y: list[np.ndarray] = []
        for pl in samples:
            gx, _ = rasterize_segments(pl, size)
            gy, _ = rasterize_teacher_mask(pl, size)
            grids_x.append(gx)
            grids_y.append(gy)
        if grids_x:
            tx = torch.from_numpy(np.stack(grids_x)).float().unsqueeze(1)
            ty = torch.from_numpy(np.stack(grids_y)).float().unsqueeze(1)
            for _ in range(80):
                opt.zero_grad()
                pred = net(tx)
                loss = F.binary_cross_entropy_with_logits(pred, ty)
                loss.backward()
                opt.step()
            torch.save(
                {"state_dict": net.state_dict(), "grid_size": size, "threshold": 0.35},
                MODEL_DIR / "cnn.pt",
            )
    except Exception:
        logger.exception("cnn train")

    # --- GNN ---
    try:
        import torch
        import torch.nn.functional as F
        from torch import optim

        from app.plugins.frame_step2b_ml.torch_models import TinySegGNN, symmetric_normalized_adjacency

        full_samples = []
        for pl in samples:
            Xn, E, _, _ = build_graph_tensors(pl, max_nodes=400)
            if Xn.shape[0] == 0:
                continue
            pos = teacher_entity_positive_set(pl)
            y_node = np.zeros(Xn.shape[0], dtype=np.float32)
            segs = [s for s in (pl.get("wall_step2a_source_segs") or []) if s][:400]
            n_node = Xn.shape[0]
            for idx, seg in enumerate(segs):
                if idx >= n_node:
                    break
                for eid in seg.get("entity_ids") or []:
                    try:
                        if int(eid) in pos:
                            y_node[idx] = 1.0
                            break
                    except (TypeError, ValueError):
                        continue
            full_samples.append((Xn, E, y_node))
        if full_samples:
            gnn2 = TinySegGNN(in_dim=full_samples[0][0].shape[1], hidden=32)
            opt2 = optim.Adam(gnn2.parameters(), lr=5e-3)
            for epoch in range(120):
                total = 0.0
                for Xn, E, y_node in full_samples:
                    ei = torch.from_numpy(E).long()
                    adj = symmetric_normalized_adjacency(Xn.shape[0], ei)
                    x = torch.from_numpy(Xn).float()
                    y = torch.from_numpy(y_node).float()
                    opt2.zero_grad()
                    logit = gnn2(x, adj)
                    loss = F.binary_cross_entropy_with_logits(logit, y)
                    loss.backward()
                    opt2.step()
                    total += float(loss.item())
                if epoch % 40 == 0:
                    logger.info("gnn epoch %s loss %s", epoch, total / max(len(full_samples), 1))
            torch.save(
                {"state_dict": gnn2.state_dict(), "hidden": 32, "threshold": 0.28},
                MODEL_DIR / "gnn.pt",
            )
    except Exception:
        logger.exception("gnn train")

    return {"ok": True, "n_samples": len(samples), "model_dir": str(MODEL_DIR)}
