from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Commit, Changeset, ChangesetItem
from app.schemas.changeset import ChangesetResponse, ChangesetItemResponse

router = APIRouter(tags=["changesets"])


@router.get("/commits/{commit_id}/changeset", response_model=ChangesetResponse)
def get_changeset(commit_id: int, db: Session = Depends(get_db)):
    commit = db.query(Commit).filter(Commit.id == commit_id).first()
    if not commit:
        raise HTTPException(status_code=404, detail="Commit not found")
    if not commit.parent_commit_id:
        raise HTTPException(status_code=404, detail="No parent commit (first version)")

    cs = db.query(Changeset).filter(
        Changeset.from_commit_id == commit.parent_commit_id,
        Changeset.to_commit_id == commit_id,
    ).first()
    if not cs:
        raise HTTPException(status_code=404, detail="Changeset not found")

    items = db.query(ChangesetItem).filter(ChangesetItem.changeset_id == cs.id).all()
    return ChangesetResponse(
        id=cs.id,
        from_commit_id=cs.from_commit_id,
        to_commit_id=cs.to_commit_id,
        created_at=cs.created_at,
        items=items,
    )
