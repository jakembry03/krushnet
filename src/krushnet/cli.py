"""Admin command line: `krushnet <command>`.

Commands:
  check-config   validate a config file and print the settings in effect

Later PRs add more, such as `create-user` and `import-list`.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence

from krushnet import __version__
from krushnet.config import ConfigError, load_config, resolve_config_path


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
    return parser


def check_config(config_flag: str | None) -> int:
    path = resolve_config_path(config_flag)
    try:
        settings = load_config(path)
    except ConfigError as exc:
        print(exc, file=sys.stderr)
        return 1
    print(f"OK: {path}")
    print(json.dumps(settings.model_dump(mode="json"), indent=2))
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "check-config":
        return check_config(args.config)
    # No command given: show usage instead of silently doing nothing.
    parser.print_help()
    return 0
