"""Engine and session setup for the shared SQLite database."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

# Three services write to one file; wait this long for a lock before failing.
BUSY_TIMEOUT_MS = 5000


def make_engine(path: Path) -> Engine:
    """Create an engine for the SQLite file at `path`, with Krushnet's connection settings."""
    engine = create_engine(f"sqlite:///{path}")
    event.listen(engine, "connect", _configure_connection)
    return engine


def _configure_connection(dbapi_connection: Any, _connection_record: Any) -> None:
    """Applied to every new connection; these settings are per-connection in SQLite."""
    cursor = dbapi_connection.cursor()
    try:
        # WAL: readers don't block the writer and vice versa (ADR 0002).
        cursor.execute("PRAGMA journal_mode=WAL")
        # SQLite ignores foreign keys unless told otherwise, which would make
        # every ON DELETE rule in the schema silently do nothing.
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute(f"PRAGMA busy_timeout={BUSY_TIMEOUT_MS}")
        # Safe with WAL: a power cut can lose the last few commits (query-log
        # rows) but can't corrupt the database. Avoids an fsync per commit.
        cursor.execute("PRAGMA synchronous=NORMAL")
    finally:
        cursor.close()


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    # expire_on_commit=False: objects stay readable after commit, which suits
    # short request/batch-scoped sessions.
    return sessionmaker(engine, expire_on_commit=False)
