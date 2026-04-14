"""2b ML: 추론·학습 API."""
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.plugins.frame_step2b_ml.service import infer_walls, train_from_jsonl_dir

router = APIRouter(prefix="/frame-step2b", tags=["frame-step2b-ml"])


class InferRequest(BaseModel):
    backend: Literal["cnn", "xgb", "rf", "mlp", "gnn"]
    payload: dict[str, Any] = Field(default_factory=dict)


class InferResponse(BaseModel):
    backend: str
    walls: list[dict[str, Any]]
    n_walls: int


@router.post("/infer", response_model=InferResponse)
def post_infer(req: InferRequest) -> InferResponse:
    walls = infer_walls(req.backend, req.payload)
    return InferResponse(backend=req.backend, walls=walls, n_walls=len(walls))


class TrainRequest(BaseModel):
    """data/ml/step2b/datasets 아래 *.jsonl 을 읽습니다(상대 경로는 프로젝트 루트 기준)."""

    data_dir: str = "data/ml/step2b/datasets"


@router.post("/train")
def post_train(req: TrainRequest) -> dict[str, Any]:
    root = Path(__file__).resolve().parents[3]
    d = Path(req.data_dir)
    if not d.is_absolute():
        d = root / d
    if not d.is_dir():
        raise HTTPException(status_code=400, detail=f"data_dir not found: {d}")
    result = train_from_jsonl_dir(d)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error", "train failed"))
    return result
