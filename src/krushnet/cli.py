"""Admin command line: `krushnet <command>`.

Only `--version` exists so far. Later PRs add subcommands such as
`create-user` and `import-list`.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from krushnet import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="krushnet", description="Krushnet admin commands.")
    parser.add_argument("--version", action="version", version=f"krushnet {__version__}")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    parser.parse_args(argv)
    # No subcommands yet; show usage instead of silently doing nothing.
    parser.print_help()
    return 0
