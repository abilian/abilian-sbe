# Copyright (c) 2012-2024, Abilian SAS

"""The view tracker: one view per user and entity, a hit per time it is seen."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
import sqlalchemy as sa

from abilian.sbe.apps.documents.models import Folder
from abilian.services.viewtracker import viewtracker
from abilian.services.viewtracker.models import Hit, View

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from abilian.core.models.subjects import User


@pytest.fixture
def folder(session: Session) -> Folder:
    folder = Folder(title="root")
    session.add(folder)
    session.commit()
    return folder


def test_two_hits_by_a_user_make_one_view(
    session: Session, folder: Folder, user: User
) -> None:
    viewtracker.record_hit(entity=folder, user=user)
    viewtracker.record_hit(entity=folder, user=user)

    (view,) = viewtracker.get_views(entity=folder)
    assert view.user_id == user.id
    assert len(viewtracker.get_hits(view=view)) == 2


def test_a_hit_is_committed_by_the_caller(
    session: Session, folder: Folder, user: User
) -> None:
    viewtracker.record_hit(entity=folder, user=user)

    session.rollback()

    assert session.query(View).count() == 0
    assert session.query(Hit).count() == 0


def test_a_user_has_one_view_of_an_entity(
    session: Session, folder: Folder, user: User
) -> None:
    session.add(View(entity=folder, user_id=user.id))
    session.flush()

    session.add(View(entity=folder, user_id=user.id))
    with pytest.raises(sa.exc.IntegrityError):
        session.flush()
