import logging
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, BackgroundTasks
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.session import get_db
from app.models import Project, File as FileModel, Commit
from app.schemas.commit import CommitResponse
from app.schemas.file import FileResponse
from app.services.storage import save_upload
from app.workers.commit_processor import process_commit

logger = logging.getLogger(__name__)

router = APIRouter(tags=["uploads"])


def _parse_json_form(value: str | None) -> dict[str, Any] | None:
    if not value or value.strip() in ("", "null"):
        return None
    import json
    try:
        return json.loads(value)
    except Exception:
        return None


@router.post("/projects/{project_id}/uploads", response_model=CommitResponse)
def upload_file(
    project_id: int,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    created_by: int | None = Form(None),
    version_label: str | None = Form(None),
    parent_commit_id: int | None = Form(None),
    branch_name: str | None = Form(None),
    assignee_name: str | None = Form(None),
    assignee_department: str | None = Form(None),
    change_notes: str | None = Form(None),
    class_pre: str | None = Form(None),
    class_major: str | None = Form(None),
    class_mid: str | None = Form(None),
    class_minor: str | None = Form(None),
    class_work_type: str | None = Form(None),
    settings: str | None = Form(None),
    db: Session = Depends(get_db),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    parent_id = None
    if parent_commit_id is not None:
        try:
            parent_id = int(parent_commit_id) if str(parent_commit_id).strip() else None
        except (ValueError, TypeError):
            parent_id = None

    settings_dict = _parse_json_form(settings)
    allow_dxf = get_settings().dev_allow_dxf_upload
    filename = file.filename or "upload"
    suffix = (filename.rsplit(".", 1)[-1].upper() if "." in filename else "")
    if suffix == "DWG":
        pass  # DWG 허용, 백그라운드에서 ODA 또는 dwg2dxf로 변환 시도
    elif suffix == "DXF" and allow_dxf:
        pass
    elif suffix == "DXF":
        raise HTTPException(
            status_code=400,
            detail="DXF upload disabled. Set DEV_ALLOW_DXF_UPLOAD=true.",
        )
    else:
        raise HTTPException(status_code=400, detail="지원 형식: DWG, DXF")

    f = FileModel(
        project_id=project_id,
        original_filename=filename,
        storage_path="",
        sha256=None,
        file_size=None,
        uploaded_by=created_by,
    )
    db.add(f)
    db.flush()

    storage_path, sha256, file_size = save_upload(project_id, f.id, filename, file.file)
    storage_path_str = str(storage_path).replace("\\", "/")
    f.storage_path = storage_path_str
    f.sha256 = sha256
    f.file_size = file_size

    commit = Commit(
        project_id=project_id,
        file_id=f.id,
        parent_commit_id=parent_id,
        version_label=version_label,
        branch_name=branch_name.strip() if branch_name else None,
        assignee_name=assignee_name.strip() if assignee_name else None,
        assignee_department=assignee_department.strip() if assignee_department else None,
        change_notes=change_notes.strip() if change_notes else None,
        class_pre=class_pre.strip() if class_pre else None,
        class_major=class_major.strip() if class_major else None,
        class_mid=class_mid.strip() if class_mid else None,
        class_minor=class_minor.strip() if class_minor else None,
        class_work_type=class_work_type.strip() if class_work_type else None,
        status="PENDING",
        created_by=created_by,
        settings=settings_dict,
    )
    db.add(commit)
    db.commit()
    db.refresh(commit)

    # 파일 레코드의 storage_path에 file_id 반영하려면 업데이트 가능. MVP에서는 0으로 저장했으므로 경로에 0이 들어감. 개선: save_upload에 file_id 전달하려면 flush 후 다시 저장해야 함. 간단히 file_id를 save_upload 전에 알 수 없으므로, save_upload에서 project_id와 임시 이름만 쓰고 나중에 rename 하거나, 그냥 0_file.dxf 형태로 두어도 동작함.
    background_tasks.add_task(process_commit, commit.id)

    return commit
