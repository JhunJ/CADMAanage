from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DirectEntityItem(BaseModel):
    """Single entity payload for direct commit."""

    model_config = ConfigDict(populate_by_name=True)

    entity_type: str
    geom_wkt: str
    layer: str | None = None
    color: int | None = None
    linetype: str | None = None
    centroid_wkt: str | None = None
    bbox_wkt: str | None = None
    props: dict[str, Any] | None = None
    fingerprint: str | None = None
    temp_insert_key: int | None = Field(default=None, alias="_temp_insert_key")


class DirectCommitCreate(BaseModel):
    """Rhino direct upload payload."""

    entities: list[DirectEntityItem]
    block_defs: list[dict[str, Any]] | None = None
    block_inserts: list[dict[str, Any]] | None = None
    block_attrs: list[dict[str, Any]] | None = None
    parent_commit_id: int | None = None
    version_label: str | None = None
    branch_name: str | None = None
    assignee_name: str | None = None
    assignee_department: str | None = None
    change_notes: str | None = None
    class_pre: str | None = None
    class_major: str | None = None
    class_mid: str | None = None
    class_minor: str | None = None
    class_work_type: str | None = None
    settings: dict[str, Any] | None = None
    created_by: int | None = None


class CommitCreate(BaseModel):
    created_by: int | None = None
    version_label: str | None = None
    parent_commit_id: int | None = None
    branch_name: str | None = None
    assignee_name: str | None = None
    assignee_department: str | None = None
    change_notes: str | None = None
    settings: dict[str, Any] | None = None


class CommitResponse(BaseModel):
    id: int
    project_id: int
    file_id: int
    original_filename: str | None = None
    parent_commit_id: int | None
    version_label: str | None
    branch_name: str | None = None
    assignee_name: str | None = None
    assignee_department: str | None = None
    change_notes: str | None = None
    status: str
    created_by: int | None
    created_at: datetime | None
    settings: dict[str, Any] | None
    error_message: str | None
    progress_message: str | None = None
    class_pre: str | None = None
    class_major: str | None = None
    class_mid: str | None = None
    class_minor: str | None = None
    class_work_type: str | None = None

    class Config:
        from_attributes = True


class CommitUpdate(BaseModel):
    version_label: str | None = None
    branch_name: str | None = None
    assignee_name: str | None = None
    assignee_department: str | None = None
    change_notes: str | None = None
    class_pre: str | None = None
    class_major: str | None = None
    class_mid: str | None = None
    class_minor: str | None = None
    class_work_type: str | None = None
    settings: dict[str, Any] | None = None


class CommitListResponse(BaseModel):
    commits: list[CommitResponse]


class CommitManageSessionStartBody(BaseModel):
    editor_user_id: int


class CommitManageSessionUserBody(BaseModel):
    editor_user_id: int


class CommitManageSessionInfo(BaseModel):
    id: int
    project_id: int
    commit_id: int
    editor_user_id: int
    status: str
    rev: int
    lock_expires_at: datetime
    created_at: datetime | None = None
    updated_at: datetime | None = None


class CommitManageSessionStartResponse(BaseModel):
    session: CommitManageSessionInfo
    resumed: bool = False
    lock_info: dict[str, Any] | None = None


class CommitManageSessionStateResponse(BaseModel):
    session: CommitManageSessionInfo | None = None


class CommitManageSessionHeartbeatResponse(BaseModel):
    lock_expires_at: datetime


class CommitManageSessionEndResponse(BaseModel):
    status: str
