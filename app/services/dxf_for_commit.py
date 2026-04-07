"""
커밋에 연결된 파일을 DXF 바이트로 로드. DWG는 ODA 변환 후 반환.
blocks API, debug API 등에서 공통 사용.
"""
from sqlalchemy.orm import Session

from app.models import Commit, File
from app.services.storage import get_full_path
from app.services.oda_converter import dwg_to_dxf


def get_dxf_bytes_for_commit(commit_id: int, db: Session):
    """
    커밋에 연결된 파일을 DXF로 로드(DWG이면 변환).
    Returns: (commit, file, dxf_bytes) or (None, None, None).
    """
    commit = db.query(Commit).filter(Commit.id == commit_id).first()
    if not commit:
        return None, None, None
    if commit.status != "READY":
        return None, None, None
    file = db.query(File).filter(File.id == commit.file_id).first()
    if not file:
        return None, None, None
    full_path = get_full_path(file.storage_path)
    if not full_path.exists():
        return None, None, None
    suffix = full_path.suffix.upper()
    if suffix == ".DWG":
        dxf_path = dwg_to_dxf(full_path)
        if dxf_path is None:
            return None, None, None
        dxf_bytes = dxf_path.read_bytes()
    else:
        dxf_bytes = full_path.read_bytes()
    return commit, file, dxf_bytes
