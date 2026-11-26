"""Admin command line: `krushnet <command>`.

Commands:
  check-config   validate a config file and print the settings in effect
  migrate        bring the database schema up to date
  db-status      show whether the database schema is up to date

Later PRs add more, such as `create-user` and `import-list`.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence

from sqlalchemy.exc import OperationalError

from krushnet import __version__
from krushnet.config import ConfigError, Settings, load_config, resolve_config_path
from krushnet.db import migrate
from krushnet.db.engine import make_engine


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="krushnet", description="Krushnet admin commands.")
    parser.add_argument("--version", action="version", version=f"krushnet {__version__}")

    # Shared by every command that reads the config file.
    config_options = argparse.ArgumentParser(add_help=False)
    config_options.add_argument(
        "--config",
        metavar="PATH",
        help="config file (default: $KRUSHNET_CONFIG, then /etc/krushnet/krushnet.toml)",
    )

    commands = parser.add_subparsers(dest="command", metavar="COMMAND")
    commands.add_parser(
        "check-config",
        parents=[config_options],
        help="validate the config file and print the settings in effect",
    )
    commands.add_parser(
        "migrate",
        parents=[config_options],
        help="bring the database schema up to date (run after each deploy)",
    )
    commands.add_parser(
        "db-status",
        parents=[config_options],
        help="show whether the database schema is up to date (exit 1 if not)",
    )
    return parser


def _load_settings(config_flag: str | None) -> Settings | None:
    """Load the config, printing the problems and returning None if it's invalid."""
    try:
        return load_config(resolve_config_path(config_flag))
    except ConfigError as exc:
        print(exc, file=sys.stderr)
        return None


def check_config(config_flag: str | None) -> int:
    settings = _load_settings(config_flag)
    if settings is None:
        return 1
    print(f"OK: {resolve_config_path(config_flag)}")
    print(json.dumps(settings.model_dump(mode="json"), indent=2))
    return 0


def run_migrate(config_flag: str | None) -> int:
    settings = _load_settings(config_flag)
    if settings is None:
        return 1
    path = settings.database.path
    engine = make_engine(path)
    try:
        before = migrate.current_revision(engine)
        migrate.upgrade(engine)
    except OperationalError as exc:
        print(f"can't open database {path}: {exc.orig}", file=sys.stderr)
        return 1
    finally:
        engine.dispose()
    head = migrate.head_revision()
    if before == head:
        print(f"{path}: already at revision {head}")
    else:
        print(f"{path}: migrated {before or '(empty)'} -> {head}")
    return 0


def db_status(config_flag: str | None) -> int:
    settings = _load_settings(config_flag)
    if settings is None:
        return 1
    path = settings.database.path
    head = migrate.head_revision()
    # Opening a missing SQLite file creates it; a status check shouldn't.
    if not path.exists():
        print(f"{path}: no database yet, latest is {head}. Run `krushnet migrate`.")
        return 1
    engine = make_engine(path)
    try:
        current = migrate.current_revision(engine)
    except OperationalError as exc:
        print(f"can't open database {path}: {exc.orig}", file=sys.stderr)
        return 1
    finally:
        engine.dispose()
    if current == head:
        print(f"{path}: up to date (revision {head})")
        return 0
    state = f"at revision {current}" if current else "not migrated"
    print(f"{path}: {state}, latest is {head}. Run `krushnet migrate`.")
    return 1


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    match args.command:
        case "check-config":
            return check_config(args.config)
        case "migrate":
            return run_migrate(args.config)
        case "db-status":
            return db_status(args.config)
    # No command given: show usage instead of silently doing nothing.
    parser.print_help()
    return 0
