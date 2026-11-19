# Copyright (c) 2012-2024, Abilian SAS

from __future__ import annotations

from datetime import datetime, timedelta

from flask import request
from flask_sqlalchemy.query import Query
from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from abilian.core.extensions import db
from abilian.core.models.subjects import User

_MARK = object()

#: Idle this long, a sign-in is over: the next request starts another.
IDLE_LIMIT = timedelta(hours=1)


class LoginSessionQuery(Query):
    def get_active_for(
        self, user: User, user_agent: object = _MARK, ip_address: object = _MARK
    ) -> LoginSession:
        """Return last known session for given user.

        :param user: user session

        :param user_agent: *exact* user agent string to lookup, or `None` to have
        user_agent extracted from request object. If not provided at all, no
        filtering on user_agent.

        :param ip_address: client IP, or `None` to have ip_address extracted from
        request object (requires header 'X-Forwarded-For'). If not provided at
        all, no filtering on ip_address.

        :returns: `LoginSession` or `None` if no session is found.
        """
        conditions = [LoginSession.user == user]

        if user_agent is not _MARK:
            if user_agent is None:
                user_agent = request.environ.get("HTTP_USER_AGENT", "")
            conditions.append(LoginSession.user_agent == user_agent)

        if ip_address is not _MARK:
            if ip_address is None:
                ip_addresses = request.headers.getlist("X-Forwarded-For")
                ip_address = ip_addresses[0] if ip_addresses else request.remote_addr
            conditions.append(LoginSession.ip_address == ip_address)

        session = (
            LoginSession.query.filter(*conditions)
            .order_by(LoginSession.id.desc())
            .first()
        )
        return session


class LoginSession(db.Model):
    __tablename__ = "login_session"
    query_class = LoginSessionQuery
    # query: LoginSessionQuery

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    started_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    last_active_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime)

    user_id: Mapped[int] = mapped_column(ForeignKey(User.id), nullable=False)
    user = relationship(User)

    #: IP addres, should work with both IPv4 and IPv6.
    # FIXME: define a custom type to use postgres inet when on postgres
    # http://www.postgresql.org/docs/9.1/static/datatype-net-types.html
    ip_address: Mapped[str] = mapped_column(String(39), default="", nullable=False)

    #: Limited (somewhat artbitrarily) to 512 characters.
    user_agent: Mapped[str] = mapped_column(String(512), default="", nullable=False)

    @property
    def end(self) -> datetime | None:
        """When the sign-in ended, or None while it is still on.

        One left idle ended at its last request, though it is only closed when its
        user comes back.
        """
        if self.ended_at:
            return self.ended_at
        if datetime.utcnow() - self.last_active_at > IDLE_LIMIT:
            return self.last_active_at
        return None

    @staticmethod
    def new(user: User) -> LoginSession:
        user_agent = request.environ.get("HTTP_USER_AGENT", "")
        forwared_for = request.headers.getlist("X-Forwarded-For")
        if not forwared_for:
            ip_address = request.remote_addr
        else:
            ip_address = forwared_for[0]
        session = LoginSession(user=user, user_agent=user_agent, ip_address=ip_address)
        return session
