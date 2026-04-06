"""
CAD Manage MVP - FastAPI 앱.
DWG/DXF 업로드 -> ODA 변환 -> ezdxf 파싱 -> PostGIS 적재 -> ChangeSet -> API 조회.
"""
import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.api import users, projects, uploads, commits, commits_direct, entities, blocks, changesets, export_dxf, debug_api, annotations, departments, project_minor_classes, project_work_types, admin, schema, query, plugins, cad_edit
from app.plugins._loader import register_feature_routers

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="CAD Manage API",
    description="DWG/DXF → DXF → ezdxf 파싱 → PostGIS 적재 → ChangeSet → API 조회",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(users.router, prefix="/api")
app.include_router(admin.router, prefix="/api")
app.include_router(project_minor_classes.router, prefix="/api")  # projects/{id}/minor-classes
app.include_router(project_work_types.router, prefix="/api")     # projects/{id}/work-types
app.include_router(projects.router, prefix="/api")
app.include_router(uploads.router, prefix="/api")
app.include_router(commits.router, prefix="/api")
app.include_router(commits_direct.router, prefix="/api")
app.include_router(entities.router, prefix="/api")
app.include_router(blocks.router, prefix="/api")
app.include_router(changesets.router, prefix="/api")
app.include_router(export_dxf.router, prefix="/api")
app.include_router(debug_api.router, prefix="/api")
app.include_router(annotations.router, prefix="/api")
app.include_router(departments.router, prefix="/api")
app.include_router(schema.router, prefix="/api")
app.include_router(query.router, prefix="/api")
app.include_router(plugins.router, prefix="/api")
app.include_router(cad_edit.router, prefix="/api")

register_feature_routers(app)

# /static/* 경로로 app/static 디렉터리 파일 제공
STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


def _read_html_with_fallback(path: Path) -> str:
    raw = path.read_bytes()
    # workspace.html can be accidentally saved as UTF-16 on Windows.
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16")
    return raw.decode("utf-8")


@app.get("/", response_class=HTMLResponse)
def root():
    """첫 화면: 워크스페이스 (Autodesk Build 스타일)."""
    path = Path(__file__).parent / "static" / "workspace.html"
    if not path.exists():
        return "<h1>workspace.html not found</h1>"
    return _read_html_with_fallback(path)


@app.get("/upload", response_class=HTMLResponse)
def upload_page():
    """리다이렉트: / 로 이동."""
    return RedirectResponse(url="/", status_code=302)


@app.get("/manage", response_class=HTMLResponse)
def manage_page():
    """등록자·프로젝트 관리 페이지 (독립)."""
    path = Path(__file__).parent / "static" / "manage.html"
    if not path.exists():
        return "<h1>manage.html not found</h1>"
    return _read_html_with_fallback(path)


@app.get("/dev", response_class=HTMLResponse)
def dev_page():
    """개발 페이지: 플러그인(에셋 기능) 추가·수정·삭제."""
    path = Path(__file__).parent / "static" / "dev.html"
    if not path.exists():
        return "<h1>dev.html not found</h1>"
    return _read_html_with_fallback(path)


@app.get("/view", response_class=HTMLResponse)
def view_page():
    """리다이렉트: / 로 이동."""
    return RedirectResponse(url="/", status_code=302)


@app.get("/health")
def health():
    return {"status": "ok"}
