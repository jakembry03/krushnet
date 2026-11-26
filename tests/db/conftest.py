"""Shared fixtures: a fresh SQLite file per test, migrated through Alembic.

Tests build the schema through the real migrations (not create_all), so they
exercise exactly what `krushnet migrate` creates on alfred.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from krushnet.db import migrate
from krushnet.db.engine import make_engine, make_session_factory


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "krushnet.db"


@pytest.fixture
def empty_engine(db_path: Path) -> Iterator[Engine]:
    engine = make_engine(db_path)
    yield engine
    engine.dispose()


@pytest.fixture
def engine(empty_engine: Engine) -> Engine:
    migrate.upgrade(empty_engine)
    return empty_engine


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    with make_session_factory(engine)() as session:
        yield session
