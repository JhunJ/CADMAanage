from types import SimpleNamespace

from app.api import commits


class _DeleteOrderQuery:
    def __init__(self, db_obj, model):
        self._db_obj = db_obj
        self._model = model

    def filter(self, *args, **kwargs):
        return self

    def all(self):
        if self._model is commits.Changeset:
            return []
        if self._model is commits.BlockInsert:
            return [SimpleNamespace(id=25547)]
        return []

    def first(self):
        if self._model is commits.File:
            return SimpleNamespace(id=10, storage_path=None)
        return None

    def delete(self, synchronize_session=False):
        self._db_obj.delete_order.append(self._model)
        return 1


class _DeleteOrderDB:
    def __init__(self):
        self.delete_order = []
        self.deleted_objects = []
        self.flush_called = False

    def query(self, model):
        return _DeleteOrderQuery(self, model)

    def delete(self, obj):
        self.deleted_objects.append(obj)

    def flush(self):
        self.flush_called = True


def test_delete_commit_dependencies_deletes_entities_before_block_inserts():
    db = _DeleteOrderDB()
    commit_obj = SimpleNamespace(id=145, file_id=10)

    commits._delete_commit_with_dependencies(db, commit_obj)

    assert commits.Entity in db.delete_order
    assert commits.BlockInsert in db.delete_order
    assert db.delete_order.index(commits.Entity) < db.delete_order.index(commits.BlockInsert)
