from pydantic import BaseModel, field_serializer
from typing import Any


def _geom_serializer(v: Any) -> Any:
    if v is None:
        return None
    try:
        if hasattr(v, "wkt"):
            w = getattr(v, "wkt")
            if isinstance(w, str) and w.strip().upper().startswith(("POINT", "LINESTRING", "POLYGON", "MULTI")):
                return w
    except Exception:
        pass
    try:
        from geoalchemy2.shape import to_shape
        shape = to_shape(v)
        if shape is not None and hasattr(shape, "wkt"):
            w = shape.wkt
            if isinstance(w, str):
                return w
    except Exception:
        pass
    try:
        if hasattr(v, "data"):
            data = getattr(v, "data")
            if isinstance(data, str) and data.strip().upper().startswith(("POINT", "LINESTRING", "POLYGON", "MULTI")):
                return data
            if isinstance(data, (bytes, memoryview)):
                from shapely import wkb
                geom = wkb.loads(bytes(data))
                if geom is not None and hasattr(geom, "wkt"):
                    return geom.wkt
    except Exception:
        pass
    return None


class BlockDefResponse(BaseModel):
    id: int
    commit_id: int
    name: str
    base_point: Any = None
    props: dict[str, Any] | None

    class Config:
        from_attributes = True

    @field_serializer("base_point")
    def ser_base_point(self, v: Any) -> Any:
        return _geom_serializer(v)


class BlockInsertResponse(BaseModel):
    id: int
    commit_id: int
    block_def_id: int | None
    block_name: str
    layer: str | None
    color: int | None
    insert_point: Any = None
    rotation: float | None
    scale_x: float | None
    scale_y: float | None
    scale_z: float | None
    transform: dict[str, Any] | None
    props: dict[str, Any] | None
    fingerprint: str | None

    class Config:
        from_attributes = True

    @field_serializer("insert_point")
    def ser_insert_point(self, v: Any) -> Any:
        return _geom_serializer(v)


class BlockInsertUpdate(BaseModel):
    """블록 배치의 props (예: user_attrs) 갱신."""
    props: dict[str, Any] | None = None


class BlockAttrResponse(BaseModel):
    id: int
    insert_id: int
    tag: str
    value: str | None
    props: dict[str, Any] | None

    class Config:
        from_attributes = True
