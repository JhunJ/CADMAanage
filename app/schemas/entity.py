from datetime import datetime
from pydantic import BaseModel, field_serializer
from typing import Any


def _geom_serializer(v: Any) -> Any:
    if v is None:
        return None
    if hasattr(v, "wkt"):
        return v.wkt
    # DB에서 로드한 Geometry는 WKBElement일 수 있음 → Shapely로 WKT 변환
    try:
        from geoalchemy2.shape import to_shape
        return to_shape(v).wkt
    except Exception:
        pass
    return str(v)


class EntityResponse(BaseModel):
    id: int
    commit_id: int
    entity_type: str
    layer: str | None
    color: int | None
    linetype: str | None
    geom: Any = None
    centroid: Any = None
    bbox: Any = None
    props: dict[str, Any] | None
    fingerprint: str | None
    block_insert_id: int | None = None
    block_name: str | None = None
    block_variant: int | None = None
    block_index: int | None = None
    created_at: datetime | None

    class Config:
        from_attributes = True

    @field_serializer("geom", "centroid", "bbox")
    def ser_geom(self, v: Any) -> Any:
        return _geom_serializer(v)


class EntityUserAttrsUpdate(BaseModel):
    """PATCH 시 user_attrs만 갱신."""
    user_attrs: dict[str, str] | None = None


class EntityListResponse(BaseModel):
    entities: list[EntityResponse]
    layer_colors: dict[str, int] | None = None


class AttrRenameBody(BaseModel):
    old_key: str
    new_key: str


class AttrDeleteKeyBody(BaseModel):
    key: str


class AttributeKeysResponse(BaseModel):
    common: list[str]
    individual: list[str]
    used_keys: list[str]
