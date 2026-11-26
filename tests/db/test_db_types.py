"""UtcTimestamp: aware UTC datetimes in Python, integer milliseconds in SQLite."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import StatementError
from sqlalchemy.orm import Session

from krushnet.db.models import Event
from krushnet.db.types import utcnow


def test_round_trips_aware_datetime(session: Session) -> None:
    moment = datetime(2026, 11, 26, 14, 3, 22, 123000, tzinfo=UTC)
    session.add(Event(ts=moment, kind="test", message="x"))
    session.commit()
    session.expire_all()
    loaded = session.scalars(select(Event)).one()
    assert loaded.ts == moment
    assert loaded.ts.tzinfo is UTC


def test_stored_as_integer_milliseconds(session: Session) -> None:
    session.add(Event(ts=datetime(1970, 1, 1, 0, 0, 1, 500000, tzinfo=UTC), kind="t", message="x"))
    session.commit()
    raw = session.execute(text("SELECT ts, typeof(ts) FROM events")).one()
    assert tuple(raw) == (1500, "integer")


def test_other_timezones_are_converted_to_utc(session: Session) -> None:
    eastern = timezone(timedelta(hours=-5))
    session.add(Event(ts=datetime(2026, 11, 26, 9, 0, tzinfo=eastern), kind="t", message="x"))
    session.commit()
    session.expire_all()
    assert session.scalars(select(Event.ts)).one() == datetime(2026, 11, 26, 14, 0, tzinfo=UTC)


def test_naive_datetime_rejected(session: Session) -> None:
    session.add(Event(ts=datetime(2026, 11, 26, 14, 0), kind="t", message="x"))
    with pytest.raises(StatementError, match="naive datetime"):
        session.flush()


def test_sub_millisecond_precision_is_truncated(session: Session) -> None:
    session.add(Event(ts=datetime(2026, 1, 1, 0, 0, 0, 999, tzinfo=UTC), kind="t", message="x"))
    session.commit()
    session.expire_all()
    assert session.scalars(select(Event.ts)).one() == datetime(2026, 1, 1, tzinfo=UTC)


def test_comparisons_in_queries_use_the_same_encoding(session: Session) -> None:
    now = utcnow()
    session.add_all(
        [
            Event(ts=now - timedelta(days=40), kind="old", message="x"),
            Event(ts=now, kind="new", message="x"),
        ]
    )
    session.commit()
    recent = session.scalars(select(Event.kind).where(Event.ts > now - timedelta(days=30)))
    assert list(recent) == ["new"]
