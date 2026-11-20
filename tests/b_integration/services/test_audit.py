# Copyright (c) 2012-2024, Abilian SAS

""""""

from __future__ import annotations

import datetime as dt
from itertools import count

import sqlalchemy as sa
from sqlalchemy import Column, Date, ForeignKey, Integer, Text, Unicode, UnicodeText
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import backref, relationship
from sqlalchemy.orm.attributes import NEVER_SET

from abilian.core.entities import Entity
from abilian.core.extensions import db
from abilian.core.models.base import AUDITABLE_HIDDEN, SEARCHABLE
from abilian.core.models.subjects import create_root_user
from abilian.services.audit import CREATION, DELETION, UPDATE, AuditEntry, audit_service


class IntegerCollection(db.Model):
    __tablename__ = "integer_collection"
    id = Column(Integer, primary_key=True)

    def __str__(self) -> str:
        return str(self.id)


class DummyAccount(Entity):
    name = Column(UnicodeText, default="", info=SEARCHABLE)
    password = Column(Unicode, default="*", info=AUDITABLE_HIDDEN)
    website = Column(Text, default="")
    office_phone = Column(UnicodeText, default="")
    birthday = Column(Date)

    @declared_attr
    def integers(cls):
        secondary_tbl = sa.Table(
            "account_integers",
            db.Model.metadata,
            Column("integer_id", ForeignKey(IntegerCollection.id)),
            Column("account_id", ForeignKey(cls.id)),
            sa.schema.UniqueConstraint("account_id", "integer_id"),
        )

        return sa.orm.relationship(IntegerCollection, secondary=secondary_tbl)


class AccountRelated(db.Model):
    __tablename__ = "account_related"
    __auditable_entity__ = ("account", "data", ("id",))
    id = Column(Integer, primary_key=True)

    account_id = Column(Integer, ForeignKey(DummyAccount.id), nullable=False)
    account = relationship(
        DummyAccount,
        backref=backref(
            "data", order_by="AccountRelated.id", cascade="all, delete-orphan"
        ),
    )

    text = Column(UnicodeText, default="")


class CommentRelated(db.Model):
    __tablename__ = "account_related_comment"
    __auditable_entity__ = ("related.account", "data.comments", ("related.id", "id"))
    id = Column(Integer, primary_key=True)

    related_id = Column(Integer, ForeignKey(AccountRelated.id), nullable=False)
    related = relationship(
        AccountRelated,
        backref=backref(
            "comments", order_by="CommentRelated.id", cascade="all, delete-orphan"
        ),
    )
    text = Column(UnicodeText, default="")


def test_audit(app, session) -> None:
    create_root_user()
    audit_service.start()
    assert len(AuditEntry.query.all()) == 0

    # Creation of system user(0) should have created one entry.
    # We clear it for this test.
    AuditEntry.query.delete()
    session.flush()
    assert len(AuditEntry.query.all()) == 0

    account = DummyAccount(name="John SARL")
    session.add(account)
    session.commit()
    assert len(AuditEntry.query.all()) == 1

    entry = AuditEntry.query.one()
    assert entry.type == CREATION
    assert entry.entity_id == account.id
    assert entry.entity == account

    account.website = "http://www.john.com/"
    session.commit()
    assert len(AuditEntry.query.all()) == 2

    entry = AuditEntry.query.order_by(AuditEntry.happened_at).all()[1]
    assert entry.type == UPDATE
    assert entry.entity_id == account.id
    assert entry.entity == account
    assert entry.changes.columns == {"website": ("", "http://www.john.com/")}

    account.birthday = dt.date(2012, 12, 25)
    session.commit()
    assert len(AuditEntry.query.all()) == 3

    entry = AuditEntry.query.order_by(AuditEntry.happened_at).all()[2]
    assert entry.type == UPDATE
    assert entry.entity_id == account.id
    assert entry.entity == account
    assert entry.changes.columns == {"birthday": (None, dt.date(2012, 12, 25))}

    # content hiding
    account.password = "new super secret password"  # noqa: S105
    assert account.__changes__.columns == {"password": ("******", "******")}
    session.commit()

    entry = AuditEntry.query.order_by(AuditEntry.happened_at).all()[3]
    assert entry.type == UPDATE
    assert entry.entity_id == account.id
    assert entry.entity == account
    assert entry.changes.columns == {"password": ("******", "******")}

    # deletion
    session.delete(account)
    session.commit()
    assert len(AuditEntry.query.all()) == 5

    entry = AuditEntry.query.order_by(AuditEntry.happened_at).all()[4]
    assert entry.type == DELETION
    assert entry.entity_id == account.id
    assert entry.entity is None

    # check all entries are still present (but have lost reference to
    # entity)
    entries = AuditEntry.query.all()
    assert len(entries) == 5
    assert all(e.entity_id == account.id for e in entries)
    assert all(e.entity is None for e in entries)


def test_audit_related(app, session) -> None:
    create_root_user()
    audit_service.start()

    #  helper
    audit_idx = count()
    audit_query = AuditEntry.query.order_by(AuditEntry.happened_at)

    def next_entry():
        return audit_query.all()[next(audit_idx)]

    account = DummyAccount(name="John SARL")
    session.add(account)
    session.commit()
    assert len(AuditEntry.query.all()) == 1
    next(audit_idx)

    data = AccountRelated(account=account, text="text 1")
    session.add(data)
    session.commit()

    entry = next_entry()
    assert entry.op == CREATION
    assert entry.related
    assert entry.entity_type == account.entity_type
    assert entry.entity_id == account.id
    assert entry.entity == account

    changes = entry.changes.columns
    assert len(changes) == 1
    assert "data 1" in changes
    changes = changes["data 1"]
    assert changes.columns == {
        "text": (NEVER_SET, "text 1"),
        "account_id": (NEVER_SET, 1),
        "id": (NEVER_SET, 1),
    }

    comment = CommentRelated(related=data, text="comment")
    session.add(comment)
    session.commit()
    entry = next_entry()
    assert entry.op == CREATION
    assert entry.related
    assert entry.entity_type == account.entity_type
    assert entry.entity_id == account.id

    changes = entry.changes.columns
    assert len(changes) == 1
    assert "data.comments 1 1" in changes
    changes = changes["data.comments 1 1"]
    assert changes.columns == {
        "text": (NEVER_SET, "comment"),
        "related_id": (NEVER_SET, 1),
        "id": (NEVER_SET, 1),
    }

    comment = CommentRelated(related=data, text="comment 2")
    session.add(comment)
    session.commit()
    entry = next_entry()
    assert entry.op == CREATION
    assert entry.related
    assert entry.entity_type == account.entity_type
    assert entry.entity_id == account.id

    changes = entry.changes.columns
    assert len(changes) == 1
    assert "data.comments 1 2" in changes

    changes = changes["data.comments 1 2"]
    assert changes.columns == {
        "text": (NEVER_SET, "comment 2"),
        "related_id": (NEVER_SET, 1),
        "id": (NEVER_SET, 2),
    }

    # deletion
    session.delete(comment)
    session.commit()

    entry = next_entry()
    assert entry.op == DELETION
    assert entry.related
    assert entry.entity_id == account.id
    # entity not deleted: audit should still have reference to it
    assert entry.entity == account


def test_audit_collections(app, session) -> None:
    create_root_user()
    audit_service.start()

    I1 = IntegerCollection(id=1)
    I2 = IntegerCollection(id=2)
    session.add(I1)
    session.add(I2)
    session.flush()

    account = DummyAccount(name="John")
    account.integers.append(I1)
    session.add(account)
    session.flush()

    entry = AuditEntry.query.one()
    changes = entry.changes
    assert changes.collections == {"integers": (["1"], [])}
