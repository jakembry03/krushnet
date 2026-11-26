"""Run and inspect Alembic migrations from code.

Migrations are applied explicitly with `krushnet migrate` (ADR 0004), never
automatically by a service. Services call `is_up_to_date()` at startup and
refuse to run against an out-of-date database.
"""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Connection, Engine

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def _alembic_config(connection: Connection | None = None) -> Config:
    """Build Alembic's config in code, so no alembic.ini is needed at runtime."""
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    # env.py uses this connection instead of opening its own.
    config.attributes["connection"] = connection
    return config


def head_revision() -> str:
    """The latest migration revision in this version of the code."""
    head = ScriptDirectory.from_config(_alembic_config()).get_current_head()
    if head is None:
        raise RuntimeError(f"no migrations found in {MIGRATIONS_DIR}")
    return head


def current_revision(engine: Engine) -> str | None:
    """The revision the database is at, or None if it has never been migrated."""
    with engine.connect() as connection:
        return MigrationContext.configure(connection).get_current_revision()


def is_up_to_date(engine: Engine) -> bool:
    return current_revision(engine) == head_revision()


def upgrade(engine: Engine, revision: str = "head") -> None:
    with engine.begin() as connection:
        command.upgrade(_alembic_config(connection), revision)


def downgrade(engine: Engine, revision: str) -> None:
    with engine.begin() as connection:
        command.downgrade(_alembic_config(connection), revision)
