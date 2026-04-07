from pydantic import BaseModel


class ProjectMinorClassCreate(BaseModel):
    label: str


class ProjectMinorClassResponse(BaseModel):
    id: int
    project_id: int
    label: str
    sort_order: int

    class Config:
        from_attributes = True
