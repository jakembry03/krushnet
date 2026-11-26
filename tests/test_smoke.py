"""Smoke tests: the package layout imports and the CLI entry point runs."""

from __future__ import annotations

import importlib

import pytest

import krushnet
from krushnet import cli


@pytest.mark.parametrize("name", ["cli", "db", "dns", "policy", "discovery", "portal"])
def test_subpackages_import(name: str) -> None:
    importlib.import_module(f"krushnet.{name}")


def test_version_is_set() -> None:
    assert krushnet.__version__


def test_cli_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        cli.main(["--version"])
    assert exit_info.value.code == 0
    assert capsys.readouterr().out.strip() == f"krushnet {krushnet.__version__}"


def test_cli_without_args_prints_help(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main([]) == 0
    assert "usage: krushnet" in capsys.readouterr().out
