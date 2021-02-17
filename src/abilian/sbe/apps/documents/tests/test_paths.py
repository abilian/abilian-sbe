from itertools import count
from typing import Optional

from abilian.sbe.apps.documents.models import PathAndSecurityIndexable


class MockPath(PathAndSecurityIndexable):
    def __init__(self, id: int, parent: Optional["MockPath"] = None) -> None:
        self.id = id
        self.parent = parent


def get_obj() -> MockPath:
    id_gen = count()
    root = MockPath(next(id_gen))
    level1 = MockPath(next(id_gen), parent=root)
    level2 = MockPath(next(id_gen), parent=level1)
    level3 = MockPath(next(id_gen), parent=level2)
    return level3


def test_iter_to_root() -> None:
    obj = get_obj()
    assert [o.id for o in obj._iter_to_root()] == [3, 2, 1, 0]
    assert [o.id for o in obj._iter_to_root(skip_self=True)] == [2, 1, 0]


def test_indexable_parent_ids() -> None:
    obj = get_obj()
    assert obj._indexable_parent_ids == "/0/1/2"
