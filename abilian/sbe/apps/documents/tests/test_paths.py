# coding=utf-8
""""""
from __future__ import absolute_import, division, print_function, \
    unicode_literals

from itertools import count

from ..models import PathAndSecurityIndexable


def get_obj():
    id_gen = count()
    obj = MockPath(next(id_gen))
    obj = MockPath(next(id_gen), parent=obj)
    obj = MockPath(next(id_gen), parent=obj)
    obj = MockPath(next(id_gen), parent=obj)
    return obj


class MockPath(PathAndSecurityIndexable):
    def __init__(self, id, parent=None):
        self.id = id
        self.parent = parent


def test_iter_to_root():
    obj = get_obj()
    assert [o.id for o in obj._iter_to_root()] == [3, 2, 1, 0]
    assert [o.id for o in obj._iter_to_root(skip_self=True)] == [2, 1, 0]


def test_indexable_parent_ids():
    obj = get_obj()
    assert obj._indexable_parent_ids == "/0/1/2"
