"""Alembic environment for Krushnet.

Normally run through krushnet.db.migrate (`krushnet migrate`), which passes
in an open connection. When run with the `alembic` command during
development (e.g. `uv run alembic revision --autogenerate`), it opens the
database named in the Krushnet config ($KRUSHNET_CONFIG or --config path).
"""

from __future__ import annotations

from alembic import context
from sqlalchemy import Connection

from krushnet.config import load_config, resolve_config_path
from krushnet.db.engine import make_engine
from krushnet.db.models import Base


def run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=Base.metadata,
        # SQLite can't ALTER most things in place; batch mode rebuilds the
        # table instead. Needs the naming convention in models.py.
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def main() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline (SQL script) migrations aren't supported")
    connection = context.config.attributes.get("connection")
    if connection is not None:
        run_migrations(connection)
        return
    settings = load_config(resolve_config_path(None))
    with make_engine(settings.database.path).begin() as own_connection:
        run_migrations(own_connection)


main()
