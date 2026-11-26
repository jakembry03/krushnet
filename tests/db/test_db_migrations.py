"""Migrations: they match the models, run both ways, and the CLI drives them."""

from __future__ import annotations

from pathlib import Path

import pytest
from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext
from sqlalchemy import Engine, inspect, text

from krushnet import cli
from krushnet.db import migrate
from krushnet.db.engine import make_engine
from krushnet.db.models import Base

EXPECTED_TABLES = {
    "groups",
    "devices",
    "device_addresses",
    "device_hostnames",
    "lists",
    "list_entries",
    "rules",
    "queries",
    "events",
    "users",
    "sessions",
    "meta",
}


def test_migrations_match_models(engine: Engine) -> None:
    """Catches a model change without a matching migration (or vice versa)."""
    with engine.connect() as connection:
        context = MigrationContext.configure(connection, opts={"render_as_batch": True})
        assert compare_metadata(context, Base.metadata) == []


def test_upgrade_creates_all_tables(engine: Engine) -> None:
    assert set(inspect(engine).get_table_names()) == EXPECTED_TABLES | {"alembic_version"}


def test_downgrade_and_upgrade_again(engine: Engine) -> None:
    migrate.downgrade(engine, "base")
    assert set(inspect(engine).get_table_names()) == {"alembic_version"}
    migrate.upgrade(engine)
    assert set(inspect(engine).get_table_names()) >= EXPECTED_TABLES


def test_up_to_date_only_after_migrating(empty_engine: Engine) -> None:
    assert migrate.current_revision(empty_engine) is None
    assert not migrate.is_up_to_date(empty_engine)
    migrate.upgrade(empty_engine)
    assert migrate.current_revision(empty_engine) == migrate.head_revision()
    assert migrate.is_up_to_date(empty_engine)


def test_connection_settings(engine: Engine) -> None:
    with engine.connect() as connection:
        assert connection.execute(text("PRAGMA journal_mode")).scalar() == "wal"
        assert connection.execute(text("PRAGMA foreign_keys")).scalar() == 1
        assert connection.execute(text("PRAGMA busy_timeout")).scalar() == 5000
        assert connection.execute(text("PRAGMA synchronous")).scalar() == 1  # NORMAL


# --- CLI ------------------------------------------------------------------------


@pytest.fixture
def config_file(tmp_path: Path) -> Path:
    path = tmp_path / "krushnet.toml"
    path.write_text(f'[database]\npath = "{tmp_path / "cli.db"}"\n', encoding="utf-8")
    return path


def test_cli_migrate_and_status(
    config_file: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert cli.main(["db-status", "--config", str(config_file)]) == 1
    assert "no database yet" in capsys.readouterr().out
    assert not (tmp_path / "cli.db").exists(), "db-status must not create the file"

    assert cli.main(["migrate", "--config", str(config_file)]) == 0
    assert migrate.head_revision() in capsys.readouterr().out

    assert cli.main(["db-status", "--config", str(config_file)]) == 0
    assert "up to date" in capsys.readouterr().out

    # Running again is harmless.
    assert cli.main(["migrate", "--config", str(config_file)]) == 0


def test_cli_status_of_unmigrated_database(
    config_file: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    make_engine(tmp_path / "cli.db").connect().close()  # an empty SQLite file
    assert cli.main(["db-status", "--config", str(config_file)]) == 1
    assert "not migrated" in capsys.readouterr().out


def test_cli_migrate_reports_unwritable_location(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config = tmp_path / "krushnet.toml"
    config.write_text(f'[database]\npath = "{tmp_path / "missing" / "x.db"}"\n', encoding="utf-8")
    assert cli.main(["migrate", "--config", str(config)]) == 1
    assert "can't open database" in capsys.readouterr().err


def test_cli_migrate_reports_bad_config(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    config = tmp_path / "krushnet.toml"
    config.write_text('[database]\npath = "relative.db"\n', encoding="utf-8")
    assert cli.main(["migrate", "--config", str(config)]) == 1
    assert "database.path" in capsys.readouterr().err
