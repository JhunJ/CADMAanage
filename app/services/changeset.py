"""
parent_commit vs current commit 기반 ChangeSet 생성.
- 동일 fingerprint: same (스킵)
- from에만: DELETED
- to에만: ADDED
- MODIFIED: 휴리스틱(centroid 거리 + 타입/레이어 동일)으로 old/new 매칭 후, 매칭된 쌍은 DELETED/ADDED 제외
"""
import logging
import re
from typing import Any

from sqlalchemy.orm import Session

from app.models import Entity, Changeset, ChangesetItem

logger = logging.getLogger(__name__)


def _entity_fingerprint_map(db: Session, commit_id: int) -> dict[str, Entity]:
    """commit의 entity fingerprint -> Entity."""
    rows = db.query(Entity).filter(Entity.commit_id == commit_id).all()
    return {e.fingerprint: e for e in rows if e.fingerprint}


def _get_centroid_wkt(entity: Entity) -> str | None:
    if entity.centroid is None:
        return None
    if hasattr(entity.centroid, "wkt"):
        return entity.centroid.wkt
    return str(entity.centroid)


def _wkt_point_distance(wkt1: str, wkt2: str) -> float:
    def parse(s):
        m = re.search(r"\(([^)]+)\)", s)
        if not m:
            return None
        parts = m.group(1).split()
        if len(parts) >= 2:
            return (float(parts[0]), float(parts[1]))
        return None

    p1 = parse(wkt1)
    p2 = parse(wkt2)
    if p1 is None or p2 is None:
        return float("inf")
    return ((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2) ** 0.5


def _entity_snapshot(entity: Entity | None) -> dict[str, Any] | None:
    if entity is None:
        return None
    return {
        "entity_id": entity.id,
        "entity_type": entity.entity_type,
        "layer": entity.layer,
        "centroid_wkt": _get_centroid_wkt(entity),
    }


def build_changeset(db: Session, from_commit_id: int, to_commit_id: int) -> Changeset | None:
    """
    from_commit -> to_commit 변경분으로 Changeset 생성 및 저장.
    MODIFIED: from_only와 to_only 중 centroid 근접 + 타입/레이어 동일한 쌍을 먼저 찾고,
    나머지 from_only는 DELETED, to_only는 ADDED.
    """
    from_fp = _entity_fingerprint_map(db, from_commit_id)
    to_fp = _entity_fingerprint_map(db, to_commit_id)

    from_only = set(from_fp.keys()) - set(to_fp.keys())
    to_only = set(to_fp.keys()) - set(from_fp.keys())

    cs = Changeset(from_commit_id=from_commit_id, to_commit_id=to_commit_id)
    db.add(cs)
    db.flush()

    # MODIFIED 휴리스틱: to_only 엔티티 중 from_only와 centroid 근접 + 타입/레이어 동일 매칭
    modified_pairs: list[tuple[Entity, Entity]] = []
    used_from_fp = set()
    used_to_fp = set()
    to_list = [to_fp[fp] for fp in to_only]
    from_list = [from_fp[fp] for fp in from_only]

    for new_ent in to_list:
        new_centroid = _get_centroid_wkt(new_ent)
        if not new_centroid:
            continue
        best_old = None
        best_dist = float("inf")
        for old_ent in from_list:
            if old_ent.fingerprint in used_from_fp:
                continue
            if old_ent.entity_type != new_ent.entity_type or (old_ent.layer or "") != (new_ent.layer or ""):
                continue
            old_centroid = _get_centroid_wkt(old_ent)
            if not old_centroid:
                continue
            d = _wkt_point_distance(old_centroid, new_centroid)
            if d < best_dist:
                best_dist = d
                best_old = old_ent
        if best_old is not None and best_dist < 1e6:
            used_from_fp.add(best_old.fingerprint)
            used_to_fp.add(new_ent.fingerprint)
            modified_pairs.append((best_old, new_ent))

    for old_ent, new_ent in modified_pairs:
        db.add(ChangesetItem(
            changeset_id=cs.id,
            change_type="MODIFIED",
            old_fingerprint=old_ent.fingerprint,
            new_fingerprint=new_ent.fingerprint,
            old_entity_id=old_ent.id,
            new_entity_id=new_ent.id,
            diff={
                "old_fp": old_ent.fingerprint,
                "new_fp": new_ent.fingerprint,
                "old_snapshot": _entity_snapshot(old_ent),
                "new_snapshot": _entity_snapshot(new_ent),
            },
        ))

    for fp in from_only:
        if fp in used_from_fp:
            continue
        old_entity = from_fp[fp]
        db.add(ChangesetItem(
            changeset_id=cs.id,
            change_type="DELETED",
            old_fingerprint=fp,
            new_fingerprint=None,
            old_entity_id=old_entity.id,
            new_entity_id=None,
            diff={"fingerprint": fp, "old_snapshot": _entity_snapshot(old_entity)},
        ))

    for fp in to_only:
        if fp in used_to_fp:
            continue
        new_entity = to_fp[fp]
        db.add(ChangesetItem(
            changeset_id=cs.id,
            change_type="ADDED",
            old_fingerprint=None,
            new_fingerprint=fp,
            old_entity_id=None,
            new_entity_id=new_entity.id,
            diff={"fingerprint": fp, "new_snapshot": _entity_snapshot(new_entity)},
        ))

    return cs
