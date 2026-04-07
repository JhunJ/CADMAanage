from datetime import datetime, timedelta
from types import SimpleNamespace

from app.api import cad_edit


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
        self.flush_called = False
        self.commits = 0
        self.rollbacks = 0

    def query(self, model):
        return _DummyQuery(self._session_obj)

    def flush(self):
        self.flush_called = True

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


def test_abort_clears_draft_fk_before_delete(monkeypatch):
    now = datetime(2026, 3, 4, 12, 0, 0)
    session_obj = SimpleNamespace(
        id=1,
        status="ACTIVE",
        lock_expires_at=now + timedelta(minutes=5),
        draft_commit_id=99,
        updated_at=None,
        rev=3,
    )
    db = _DummyDB(session_obj)
    observed = {}

    monkeypatch.setattr(cad_edit, "_utcnow", lambda: now)

    def _fake_delete(db_arg, draft_id):
        observed["draft_id"] = draft_id
        observed["draft_fk_value_during_delete"] = session_obj.draft_commit_id
        observed["flush_called_before_delete"] = db.flush_called

    monkeypatch.setattr(cad_edit, "_delete_draft_commit_data", _fake_delete)

    result = cad_edit.abort_cad_edit_session(1, db)

    assert result["status"] == "ABORTED"
    assert session_obj.status == "ABORTED"
    assert session_obj.draft_commit_id is None
    assert session_obj.rev == 4
    assert db.commits == 1
    assert observed["draft_id"] == 99
    assert observed["draft_fk_value_during_delete"] is None
    assert observed["flush_called_before_delete"] is True


def test_abort_idempotent_when_session_not_active():
    now = datetime(2026, 3, 4, 12, 0, 0)
    session_obj = SimpleNamespace(
        id=2,
        status="COMMITTED",
        lock_expires_at=now + timedelta(minutes=5),
        draft_commit_id=None,
        updated_at=None,
        rev=1,
    )
    db = _DummyDB(session_obj)

    result = cad_edit.abort_cad_edit_session(2, db)

    assert result == {"status": "COMMITTED"}
    assert db.commits == 0
    assert db.flush_called is False


def test_abort_marks_expired_when_lock_timed_out(monkeypatch):
    now = datetime(2026, 3, 4, 12, 0, 0)
    session_obj = SimpleNamespace(
        id=3,
        status="ACTIVE",
        lock_expires_at=now - timedelta(seconds=1),
        draft_commit_id=123,
        updated_at=None,
        rev=7,
    )
    db = _DummyDB(session_obj)
    monkeypatch.setattr(cad_edit, "_utcnow", lambda: now)

    result = cad_edit.abort_cad_edit_session(3, db)

    assert result == {"status": "EXPIRED"}
    assert session_obj.status == "EXPIRED"
    assert db.commits == 1
    assert session_obj.draft_commit_id == 123


class _DeleteOrderQuery:
    def __init__(self, db_obj, model):
        self._db_obj = db_obj
        self._model = model

    def filter(self, *args, **kwargs):
        return self

    def all(self):
        if self._model is cad_edit.Changeset:
            return []
        if self._model is cad_edit.BlockInsert:
            return [SimpleNamespace(id=25547)]
        return []

    def delete(self, synchronize_session=False):
        self._db_obj.delete_order.append(self._model)
        return 1


class _DeleteOrderDB:
    def __init__(self):
        self.delete_order = []

    def query(self, model):
        return _DeleteOrderQuery(self, model)


def test_delete_draft_data_deletes_entities_before_block_inserts():
    db = _DeleteOrderDB()

    cad_edit._delete_draft_commit_data(db, 145)

    assert cad_edit.Entity in db.delete_order
    assert cad_edit.BlockInsert in db.delete_order
    assert db.delete_order.index(cad_edit.Entity) < db.delete_order.index(cad_edit.BlockInsert)
