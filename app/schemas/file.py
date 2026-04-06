from datetime import datetime
from pydantic import BaseModel


class FileResponse(BaseModel):
    id: int
    project_id: int
    original_filename: str
    storage_path: str
    sha256: str | None
    file_size: int | None
    uploaded_by: int | None
    uploaded_at: datetime | None

    class Config:
        from_attributes = True
