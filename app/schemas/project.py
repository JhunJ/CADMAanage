from datetime import datetime
from typing import Any

from pydantic import BaseModel


class ProjectCreate(BaseModel):
    name: str
    code: str
    created_by: int | None = None


class ProjectResponse(BaseModel):
    id: int
    name: str
    code: str
    created_by: int | None
    created_at: datetime | None
    settings: dict[str, Any] | None = None

    class Config:
        from_attributes = True


class ProjectUpdate(BaseModel):
    name: str | None = None
    code: str | None = None
    created_by: int | None = None
    settings: dict[str, Any] | None = None


class ProjectAttributeKeysResponse(BaseModel):
    common: list[str]
    individual: list[str]
