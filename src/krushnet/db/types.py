"""Custom column types."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import override

from sqlalchemy import BigInteger, Dialect
from sqlalchemy.types import TypeDecorator

_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
_ONE_MS = timedelta(milliseconds=1)


def utcnow() -> datetime:
    """Current time as a timezone-aware UTC datetime (the only kind we store)."""
    return datetime.now(UTC)


class UtcTimestamp(TypeDecorator[datetime]):
    """A UTC datetime stored as an integer count of Unix milliseconds (ADR 0004).

    Python code always sees timezone-aware UTC datetimes. SQLite stores a
    compact integer, which keeps the query log small and time-range queries
    fast. Naive datetimes are rejected rather than guessed at.

    To read it in the sqlite3 shell: datetime(ts / 1000, 'unixepoch').
    """

    impl = BigInteger
    cache_ok = True

    @override
    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> int | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(f"naive datetime not allowed, use an aware UTC datetime: {value!r}")
        # Integer arithmetic on timedeltas, so no float rounding.
        return (value - _EPOCH) // _ONE_MS

    @override
    def process_result_value(self, value: int | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        return _EPOCH + value * _ONE_MS
