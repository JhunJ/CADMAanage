"""
기능 모듈(플러그인) discovery 및 라우터 등록.
app/features/<name>/router.py 가 있고 그 안에 router 가 정의된 패키지만 로드합니다.
"""
import importlib.util
import logging
from pathlib import Path

from fastapi import FastAPI

logger = logging.getLogger(__name__)

FEATURES_DIR = Path(__file__).resolve().parent


def register_feature_routers(app: FastAPI) -> None:
    """
    app/features/ 하위 디렉터리를 스캔하여 router.py 가 있는 기능만
    동적 로드 후 app.include_router(router, prefix="/api") 로 등록합니다.
    import 실패 시 해당 기능만 스킵하고 다른 기능에는 영향을 주지 않습니다.
    """
    if not FEATURES_DIR.is_dir():
        return
    for path in sorted(FEATURES_DIR.iterdir()):
        if not path.is_dir():
            continue
        name = path.name
        if name.startswith("_"):
            continue
        router_file = path / "router.py"
        if not router_file.is_file():
            continue
        try:
            spec = importlib.util.spec_from_file_location(
                f"app.features.{name}.router",
                router_file,
            )
            if spec is None or spec.loader is None:
                logger.warning("Feature %s: could not create module spec for router.py", name)
                continue
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            router = getattr(mod, "router", None)
            if router is None:
                logger.warning("Feature %s: router.py has no 'router' attribute", name)
                continue
            app.include_router(router, prefix="/api")
            logger.info("Registered feature router: %s", name)
        except Exception as e:
            logger.exception("Feature %s: failed to load router: %s", name, e)
