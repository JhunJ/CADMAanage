from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api import commits


class _DummyQuery:
    def __init__(self, session_obj):
        self._session_obj = session_obj

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self._session_obj


class _DummyDB:
    def __init__(self, session_obj):
        self._session_obj = session_obj
        self.flush_count = 0
        self.commit_count = 0

    def query(self, model):
        return _DummyQuery(self._session_obj)

    def flush(self):
        self.flush_count += 1

    def commit(self):
        self.commit_count += 1


def test_apply_commit_update_fields_merges_and_trims():
    commit_obj = SimpleNamespace(
        version_label="old",
        branch_name="old",
        assignee_name="old",
        assignee_department="old",
        change_notes="old",
        class_pre="old",
        class_major="old",
        class_mid="old",
        class_minor="old",
        class_work_type="old",
        settings={"a": 1, "keep": True},
    )
    body = commits.CommitUpdate(
        version_label="  V1  ",
        branch_name="  BR  ",
        assignee_name="  Kim  ",
        assignee_department="  Struct  ",
        change_notes="  note  ",
        class_pre="  건축  ",
        class_major="  대분류  ",
        class_mid="  중분류  ",
        class_minor="  소분류  ",
        class_work_type="  공종  ",
        settings={"a": 2, "b": 3},
    )

    commits._apply_commit_update_fields(commit_obj, body)

    assert commit_obj.version_label == "V1"
    assert commit_obj.branch_name == "BR"
    assert commit_obj.assignee_name == "Kim"
    assert commit_obj.assignee_department == "Struct"
    assert commit_obj.change_notes == "note"
    assert commit_obj.class_pre == "건축"
    assert commit_obj.class_major == "대분류"
    assert commit_obj.class_mid == "중분류"
    assert commit_obj.class_minor == "소분류"
    assert commit_obj.class_work_type == "공종"
    assert commit_obj.settings == {"a": 2, "keep": True, "b": 3}


def test_require_manage_session_rejects_owner_mismatch():
    now = datetime(2026, 3, 4, 12, 0, 0)
    session_obj = SimpleNamespace(
        id=10,
        commit_id=22,
        editor_user_id=7,
        status="ACTIVE",
        lock_expires_at=now + timedelta(minutes=5),
        updated_at=None,
    )
    db = _DummyDB(session_obj)

    with pytest.raises(HTTPException) as exc:
        commits._require_manage_session(db, 10, commit_id=22, editor_user_id=99)

    assert exc.value.status_code == 403


def test_require_manage_session_marks_expired_and_commits(monkeypatch):
    now = datetime(2026, 3, 4, 12, 0, 0)
    session_obj = SimpleNamespace(
        id=11,
        commit_id=33,
        editor_user_id=7,
        status="ACTIVE",
        lock_expires_at=now - timedelta(seconds=1),
        updated_at=None,
    )
    db = _DummyDB(session_obj)
    monkeypatch.setattr(commits, "_utcnow", lambda: now)

    with pytest.raises(HTTPException) as exc:
        commits._require_manage_session(db, 11, commit_id=33, editor_user_id=7)

    assert exc.value.status_code == 409
    assert session_obj.status == "EXPIRED"
    assert db.flush_count == 1
    assert db.commit_count == 1
