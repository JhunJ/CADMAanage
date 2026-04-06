"""
에셋 기능 플러그인 API. data/asset_plugins.json 에 저장.
"""
import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/plugins", tags=["plugins"])

RESERVED_IDS = {"version-compare", "rhino"}


def _plugins_path() -> Path:
    base = Path(__file__).resolve().parent.parent.parent
    return base / "data" / "asset_plugins.json"


def _read_plugins() -> list[dict]:
    path = _plugins_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("plugins", [])
    except (json.JSONDecodeError, OSError):
        return []


def _write_plugins(plugins: list[dict]) -> None:
    path = _plugins_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"plugins": plugins}, ensure_ascii=False, indent=2), encoding="utf-8")


class PluginCreate(BaseModel):
    id: str = Field(..., min_length=1)
    label: str = Field(..., min_length=1)
    panel_html_id: str = Field(..., min_length=1)
    activate_label: str = Field("활성화")
    panel_html: str = Field("")
    on_activate_body: str = Field("")


class PluginUpdate(BaseModel):
    label: str | None = None
    panel_html_id: str | None = None
    activate_label: str | None = None
    panel_html: str | None = None
    on_activate_body: str | None = None


def _to_response(p: dict) -> dict:
    return {
        "id": p.get("id"),
        "label": p.get("label"),
        "panelHtmlId": p.get("panelHtmlId", p.get("panel_html_id", "")),
        "activateLabel": p.get("activateLabel", p.get("activate_label", "활성화")),
        "panelHtml": p.get("panelHtml", p.get("panel_html", "")),
        "onActivateBody": p.get("onActivateBody", p.get("on_activate_body", "")),
    }


def _to_storage(p: dict) -> dict:
    return {
        "id": p.get("id"),
        "label": p.get("label"),
        "panelHtmlId": p.get("panelHtmlId", p.get("panel_html_id", "")),
        "activateLabel": p.get("activateLabel", p.get("activate_label", "활성화")),
        "panelHtml": p.get("panelHtml", p.get("panel_html", "")),
        "onActivateBody": p.get("onActivateBody", p.get("on_activate_body", "")),
    }


@router.get("")
def list_plugins():
    """등록된 플러그인 목록."""
    plugins = _read_plugins()
    return [_to_response(p) for p in plugins]


@router.post("")
def create_plugin(body: PluginCreate):
    """플러그인 1건 추가."""
    plugin_id = body.id.strip()
    if plugin_id in RESERVED_IDS:
        raise HTTPException(status_code=400, detail=f"Reserved id: {plugin_id}")
    plugins = _read_plugins()
    if any(p.get("id") == plugin_id for p in plugins):
        raise HTTPException(status_code=400, detail="Plugin id already exists")
    entry = {
        "id": plugin_id,
        "label": body.label.strip(),
        "panelHtmlId": body.panel_html_id.strip(),
        "activateLabel": body.activate_label.strip() or "활성화",
        "panelHtml": body.panel_html or "",
        "onActivateBody": body.on_activate_body or "",
    }
    plugins.append(entry)
    _write_plugins(plugins)
    return _to_response(entry)


@router.patch("/{plugin_id}")
def update_plugin(plugin_id: str, body: PluginUpdate):
    """플러그인 수정."""
    plugins = _read_plugins()
    idx = next((i for i, p in enumerate(plugins) if p.get("id") == plugin_id), None)
    if idx is None:
        raise HTTPException(status_code=404, detail="Plugin not found")
    entry = plugins[idx]
    if body.label is not None:
        entry["label"] = body.label.strip()
    if body.panel_html_id is not None:
        entry["panelHtmlId"] = body.panel_html_id.strip()
    if body.activate_label is not None:
        entry["activateLabel"] = body.activate_label.strip() or "활성화"
    if body.panel_html is not None:
        entry["panelHtml"] = body.panel_html
    if body.on_activate_body is not None:
        entry["onActivateBody"] = body.on_activate_body
    _write_plugins(plugins)
    return _to_response(entry)


@router.delete("/{plugin_id}")
def delete_plugin(plugin_id: str):
    """플러그인 삭제."""
    if plugin_id in RESERVED_IDS:
        raise HTTPException(status_code=400, detail="Cannot delete reserved plugin")
    plugins = _read_plugins()
    new_list = [p for p in plugins if p.get("id") != plugin_id]
    if len(new_list) == len(plugins):
        raise HTTPException(status_code=404, detail="Plugin not found")
    _write_plugins(new_list)
    return {"ok": True}
