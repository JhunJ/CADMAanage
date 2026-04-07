from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CadEditSessionStartBody(BaseModel):
    project_id: int
    base_commit_id: int
    editor_user_id: int


class CadEditSessionStartResponse(BaseModel):
    session_id: int
    draft_commit_id: int
    resumed: bool = False
    lock_info: dict[str, Any] | None = None


class CadEditOperationCreate(BaseModel):
    command: str
    forward_patch: dict[str, Any] = Field(default_factory=dict)
    inverse_patch: dict[str, Any] = Field(default_factory=dict)
    ui_meta: dict[str, Any] | None = None


class CadEditOperationApplyResponse(BaseModel):
    cursor: int
    applied: bool
    created_entity_id_map: dict[str, int] = Field(default_factory=dict)


class CadEditSessionDetailResponse(BaseModel):
    session: dict[str, Any]
    cursor: int
    operations: list[dict[str, Any]]
    draft_commit_meta: dict[str, Any] | None = None


class CadEditTempSaveResponse(BaseModel):
    checkpoint_at: datetime
    rev: int


class CadEditHeartbeatResponse(BaseModel):
    lock_expires_at: datetime


class CadEditCommitBody(BaseModel):
    version_label: str | None = None
    change_notes: str
    class_pre: str | None = None
    class_major: str | None = None
    class_mid: str | None = None
    class_minor: str | None = None
    class_work_type: str | None = None
    assignee_name: str | None = None
    assignee_department: str | None = None


class CadEditCommitResponse(BaseModel):
    commit_id: int
    changeset_id: int | None = None


class UserCadShortcutBody(BaseModel):
    bindings: dict[str, str]


class UserCadShortcutResponse(BaseModel):
    user_id: int
    bindings: dict[str, str]
    updated_at: datetime | None = None
