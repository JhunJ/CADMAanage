from pydantic import BaseModel


class ProjectWorkTypeCreate(BaseModel):
    label: str


class ProjectWorkTypeResponse(BaseModel):
    id: int
    project_id: int
    label: str
    sort_order: int

    class Config:
        from_attributes = True
