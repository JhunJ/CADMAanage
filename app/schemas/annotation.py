from datetime import datetime
from pydantic import BaseModel
from typing import Any


class AnnotationCreate(BaseModel):
    title: str | None = None
    content: str | None = None
    category: str | None = None
    strokes: list[dict[str, Any]]
    created_by: int | None = None
    entity_id: int | None = None
    position_x: float | None = None
    position_y: float | None = None
    view_bounds: dict[str, float] | None = None


class AnnotationUpdate(BaseModel):
    title: str | None = None
    content: str | None = None
    category: str | None = None
    strokes: list[dict[str, Any]] | None = None
    entity_id: int | None = None
    position_x: float | None = None
    position_y: float | None = None


class AnnotationResponse(BaseModel):
    id: int
    commit_id: int
    created_by: int | None
    title: str | None
    content: str | None
    category: str | None
    strokes: list[dict[str, Any]]
    entity_id: int | None
    position_x: float | None
    position_y: float | None
    image_paths: list[str] | None
    created_at: datetime | None
    updated_at: datetime | None

    class Config:
        from_attributes = True
