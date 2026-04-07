"""
예시 기능 API. 등록 경로: /api/features/example/...
"""
from fastapi import APIRouter

router = APIRouter(prefix="/features/example", tags=["features-example"])


@router.get("")
def example_info():
    """기능 모듈 동작 확인용 엔드포인트."""
    return {"feature": "example", "status": "ok"}
