from datetime import datetime
from pydantic import BaseModel
from typing import Any


class ChangesetItemResponse(BaseModel):
    id: int
    changeset_id: int
    change_type: str
    old_fingerprint: str | None
    new_fingerprint: str | None
    old_entity_id: int | None
    new_entity_id: int | None
    diff: dict[str, Any] | None

    class Config:
        from_attributes = True


class ChangesetResponse(BaseModel):
    id: int
    from_commit_id: int
    to_commit_id: int
    created_at: datetime | None
    items: list[ChangesetItemResponse] = []

    class Config:
        from_attributes = True
