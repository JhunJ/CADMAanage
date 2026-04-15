#!/usr/bin/env python3
"""
JSONL 학습 샘플로 2b 모델을 저장합니다.

  프로젝트 루트에서:
    python scripts/ml/train_step2b.py --data-dir data/ml/step2b/datasets

  각 줄은 브라우저 `frameDefExportStep2bPayload()` 와 동일한 JSON 객체입니다.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> None:
    from app.plugins.frame_step2b_ml.service import train_from_jsonl_dir

    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--data-dir",
        default="data/ml/step2b/datasets",
        help="*.jsonl 이 있는 디렉터리(프로젝트 루트 기준 상대 경로 가능)",
    )
    args = ap.parse_args()
    d = Path(args.data_dir)
    if not d.is_absolute():
        d = ROOT / d
    out = train_from_jsonl_dir(d)
    print(out)
    if not out.get("ok"):
        sys.exit(1)


if __name__ == "__main__":
    main()
