"""Tests for krushnet.config: loading, defaults, validation and path resolution."""

from __future__ import annotations

import ipaddress
from pathlib import Path

import pydantic
import pytest

from krushnet import cli
from krushnet.config import (
    DEFAULT_CONFIG_PATH,
    ConfigError,
    Settings,
    load_config,
    resolve_config_path,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


def write_config(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "krushnet.toml"
    path.write_text(text, encoding="utf-8")
    return path


def problems_for(tmp_path: Path, text: str) -> list[str]:
    """Load a config that must fail, returning the reported problems."""
    with pytest.raises(ConfigError) as exc_info:
        load_config(write_config(tmp_path, text))
    return exc_info.value.problems


# --- loading valid files ------------------------------------------------------


def test_empty_file_gives_dev_safe_defaults(tmp_path: Path) -> None:
    settings = load_config(write_config(tmp_path, ""))
    loopback = ipaddress.ip_address("127.0.0.1")
    assert settings.dns.listen == (loopback,)
    assert settings.dns.port == 5300
    assert settings.dns.block_response == "null_ip"
    assert settings.upstream.providers[0].scheme == "https"
    assert settings.portal.listen == (loopback,)
    assert settings.portal.port == 8000
    assert settings.database.path == Path("/var/lib/krushnet/krushnet.db")
    assert settings.database.query_retention_days == 30


def test_full_file_loads(tmp_path: Path) -> None:
    settings = load_config(
        write_config(
            tmp_path,
            """
            [dns]
            listen = ["192.168.1.50", "10.8.0.1"]
            port = 53
            block_response = "nxdomain"
            [dns.local_records]
            "Net.KrushComics.com." = "192.168.1.50"

            [upstream]
            providers = ["https://dns.quad9.net/dns-query", "https://cloudflare-dns.com/dns-query"]
            timeout_seconds = 1.5

            [discovery]
            interface = "enx00e04c680001"
            subnet = "192.168.1.0/24"
            scan_interval_seconds = 120

            [portal]
            listen = ["192.168.1.50", "10.8.0.1", "fd00::1"]
            port = 8443
            session_hours = 8

            [database]
            path = "/var/lib/krushnet/test.db"
            query_retention_days = 14
            """,
        )
    )
    assert settings.dns.port == 53
    assert settings.dns.block_response == "nxdomain"
    # Names are normalised: lower case, no trailing dot.
    assert settings.dns.local_records == {
        "net.krushcomics.com": ipaddress.ip_address("192.168.1.50")
    }
    assert len(settings.upstream.providers) == 2
    assert settings.discovery.interface == "enx00e04c680001"
    assert settings.discovery.subnet == ipaddress.ip_network("192.168.1.0/24")
    assert settings.portal.listen[2] == ipaddress.ip_address("fd00::1")
    assert settings.database.query_retention_days == 14


def test_example_config_is_valid() -> None:
    """config.example.toml must always load, so it can't drift from the code."""
    settings = load_config(REPO_ROOT / "config.example.toml")
    assert isinstance(settings, Settings)


def test_settings_are_immutable(tmp_path: Path) -> None:
    settings = load_config(write_config(tmp_path, ""))
    with pytest.raises(pydantic.ValidationError):
        settings.dns.port = 53  # type: ignore[misc]


def test_integer_timeout_is_accepted(tmp_path: Path) -> None:
    settings = load_config(write_config(tmp_path, "[upstream]\ntimeout_seconds = 2\n"))
    assert settings.upstream.timeout_seconds == 2.0


# --- file-level errors ----------------------------------------------------------


def test_missing_file(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="not found"):
        load_config(tmp_path / "nope.toml")


def test_invalid_toml(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="not valid TOML"):
        load_config(write_config(tmp_path, "[dns\nport = 53\n"))


def test_error_message_names_the_file(tmp_path: Path) -> None:
    path = write_config(tmp_path, "[dns]\nport = 0\n")
    with pytest.raises(ConfigError) as exc_info:
        load_config(path)
    assert str(path) in str(exc_info.value)


# --- validation errors ------------------------------------------------------------


@pytest.mark.parametrize(
    ("toml", "expected_location"),
    [
        ("typo_section = 1", "typo_section"),
        ("[dns]\nprot = 53", "dns.prot"),
        ('[dns]\nport = "53"', "dns.port"),  # wrong type: strings aren't coerced
        ("[dns]\nport = 0", "dns.port"),
        ("[dns]\nport = 70000", "dns.port"),
        ("[dns]\nlisten = []", "dns.listen"),
        ('[dns]\nlisten = ["not-an-ip"]', "dns.listen.0"),
        ('[dns]\nblock_response = "refuse"', "dns.block_response"),
        ('[dns.local_records]\n"bad_name!.com" = "192.168.1.50"', "dns.local_records"),
        ('[dns.local_records]\n"a.com" = "nope"', "dns.local_records.a.com"),
        ('[upstream]\nproviders = ["http://dns.quad9.net/dns-query"]', "upstream.providers.0"),
        ("[upstream]\nproviders = []", "upstream.providers"),
        ("[upstream]\ntimeout_seconds = 0", "upstream.timeout_seconds"),
        ("[upstream]\ntimeout_seconds = 30", "upstream.timeout_seconds"),
        ('[discovery]\ninterface = "eth0; rm -rf /"', "discovery.interface"),
        ('[discovery]\nsubnet = "10.0.0.0/8"', "discovery.subnet"),
        ('[discovery]\nsubnet = "8.8.8.0/24"', "discovery.subnet"),
        ('[discovery]\nsubnet = "192.168.1.5/24"', "discovery.subnet"),  # host bits set
        ("[discovery]\nscan_interval_seconds = 5", "discovery.scan_interval_seconds"),
        ('[portal]\nlisten = ["0.0.0.0"]', "portal.listen.0"),
        ('[portal]\nlisten = ["::"]', "portal.listen.0"),
        ('[portal]\nlisten = ["8.8.8.8"]', "portal.listen.0"),
        ('[portal]\nlisten = ["2001:4860:4860::8888"]', "portal.listen.0"),
        ('[portal]\nlisten = ["::ffff:8.8.8.8"]', "portal.listen.0"),  # v4-mapped public
        ("[portal]\nsession_hours = 0", "portal.session_hours"),
        ('[database]\npath = "relative/krushnet.db"', "database.path"),
        ("[database]\nquery_retention_days = 0", "database.query_retention_days"),
        ("[database]\nquery_retention_days = 1000", "database.query_retention_days"),
    ],
)
def test_invalid_values_are_rejected(tmp_path: Path, toml: str, expected_location: str) -> None:
    problems = problems_for(tmp_path, toml)
    assert any(p.startswith(expected_location + ":") for p in problems), problems


def test_all_problems_are_reported_together(tmp_path: Path) -> None:
    problems = problems_for(
        tmp_path,
        """
        [dns]
        port = 0
        [portal]
        listen = ["0.0.0.0"]
        [database]
        path = "relative.db"
        """,
    )
    locations = {p.split(":")[0] for p in problems}
    assert {"dns.port", "portal.listen.0", "database.path"} <= locations


def test_bad_list_item_is_not_also_reported_as_empty_list(tmp_path: Path) -> None:
    problems = problems_for(tmp_path, '[portal]\nlisten = ["0.0.0.0"]\n')
    assert len(problems) == 1
    assert problems[0].startswith("portal.listen.0:")


def test_genuinely_empty_list_is_still_reported(tmp_path: Path) -> None:
    assert problems_for(tmp_path, "[portal]\nlisten = []\n")[0].startswith("portal.listen:")


def test_problem_values_are_truncated(tmp_path: Path) -> None:
    problems = problems_for(tmp_path, f'[discovery]\ninterface = "{"x" * 500}"\n')
    assert all(len(p) < 300 for p in problems)


# --- config path resolution -------------------------------------------------------


def test_cli_flag_wins() -> None:
    env = {"KRUSHNET_CONFIG": "/from/env.toml"}
    assert resolve_config_path("/from/cli.toml", env) == Path("/from/cli.toml")


def test_env_var_used_without_flag() -> None:
    env = {"KRUSHNET_CONFIG": "/from/env.toml"}
    assert resolve_config_path(None, env) == Path("/from/env.toml")


def test_default_path() -> None:
    assert resolve_config_path(None, {}) == DEFAULT_CONFIG_PATH
    assert resolve_config_path(None, {"KRUSHNET_CONFIG": ""}) == DEFAULT_CONFIG_PATH


# --- krushnet check-config ----------------------------------------------------------


def test_check_config_ok(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = write_config(tmp_path, "[dns]\nport = 5353\n")
    assert cli.main(["check-config", "--config", str(path)]) == 0
    out = capsys.readouterr().out
    assert "OK" in out
    assert "5353" in out


def test_check_config_invalid(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = write_config(tmp_path, "[dns]\nport = 0\n")
    assert cli.main(["check-config", "--config", str(path)]) == 1
    assert "dns.port" in capsys.readouterr().err
