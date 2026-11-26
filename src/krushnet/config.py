"""Load and validate Krushnet's TOML configuration.

Every service calls `load_config(resolve_config_path(...))` at startup and
gets back an immutable, typed `Settings` object, or a `ConfigError` listing
every problem in the file. Validation is strict on purpose: unknown keys
are errors (catches typos), strings aren't coerced to numbers, and settings
that could break a hard rule (an unencrypted upstream, a portal reachable
from the internet) are rejected here rather than trusted downstream.

Defaults are safe for development: loopback addresses and unprivileged
ports. alfred's /etc/krushnet/krushnet.toml sets the real values.
"""

from __future__ import annotations

import ipaddress
import os
import re
import tomllib
from collections.abc import Mapping
from ipaddress import IPv4Address, IPv4Network, IPv6Address
from pathlib import Path
from typing import Annotated, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    IPvAnyAddress,
    Strict,
    ValidationError,
    field_validator,
)

DEFAULT_CONFIG_PATH = Path("/etc/krushnet/krushnet.toml")
CONFIG_ENV_VAR = "KRUSHNET_CONFIG"

# Longest bad value echoed back in an error message.
_MAX_SHOWN_VALUE = 80

LOOPBACK = ipaddress.ip_address("127.0.0.1")


class ConfigError(Exception):
    """The config file is missing, unreadable or invalid.

    `problems` holds one line per issue, as "dotted.key: message (got value)".
    """

    def __init__(self, path: Path, problems: list[str]) -> None:
        self.path = path
        self.problems = problems
        details = "\n".join(f"  - {p}" for p in problems)
        super().__init__(f"invalid config {path}:\n{details}")


# --- reusable field types ------------------------------------------------------


def _https_only(url: HttpUrl) -> HttpUrl:
    # Decision 3: upstream DNS is always encrypted.
    if url.scheme != "https":
        raise ValueError("upstream providers must use https:// (DNS-over-HTTPS)")
    return url


def _lan_only(address: IPv4Address | IPv6Address) -> IPv4Address | IPv6Address:
    """Allow only loopback and private (LAN/WireGuard) addresses (hard rule 3)."""
    # Check the IPv4 address inside an IPv4-mapped IPv6 one (::ffff:a.b.c.d).
    effective = (
        address.ipv4_mapped if isinstance(address, IPv6Address) and address.ipv4_mapped else address
    )
    # 0.0.0.0 counts as "private" in the ipaddress module, so check it first.
    if effective.is_unspecified:
        raise ValueError(
            "listening on all interfaces is not allowed (hard rule 3); "
            "list the LAN and WireGuard addresses instead"
        )
    if effective.is_multicast or not (effective.is_loopback or effective.is_private):
        raise ValueError(
            "must be a loopback or private (LAN/WireGuard) address; "
            "the portal is never exposed to the internet (hard rule 3)"
        )
    return address


def _private_scan_range(subnet: IPv4Network) -> IPv4Network:
    if not subnet.is_private:
        raise ValueError("must be a private network")
    # A /16 is already 65k addresses; anything bigger is almost certainly a typo.
    if subnet.prefixlen < 16:
        raise ValueError("must be /16 or smaller, to avoid accidentally huge ARP sweeps")
    return subnet


def _absolute_path(path: Path) -> Path:
    # Services run under systemd with no meaningful working directory.
    if not path.is_absolute():
        raise ValueError("must be an absolute path")
    return path


_DNS_LABEL = re.compile(r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$")


def normalise_dns_name(name: str) -> str:
    """Lower-case a hostname and drop the trailing dot; reject invalid names."""
    normalised = name.lower().removesuffix(".")
    if not 0 < len(normalised) <= 253 or not all(
        _DNS_LABEL.match(label) for label in normalised.split(".")
    ):
        raise ValueError(f"invalid DNS name {name[:_MAX_SHOWN_VALUE]!r}")
    return normalised


type Port = Annotated[int, Strict(), Field(ge=1, le=65535)]
type HttpsUrl = Annotated[HttpUrl, AfterValidator(_https_only)]
type LanAddress = Annotated[IPvAnyAddress, AfterValidator(_lan_only)]


# --- settings sections -----------------------------------------------------------


class _Section(BaseModel):
    # frozen: settings can't be changed after loading.
    # extra="forbid": unknown keys (usually typos) are errors.
    model_config = ConfigDict(frozen=True, extra="forbid")


class DnsSettings(_Section):
    listen: tuple[IPvAnyAddress, ...] = Field(default=(LOOPBACK,), min_length=1)
    port: Port = 5300
    # What a blocked query gets: 0.0.0.0 / :: ("null_ip") or NXDOMAIN.
    block_response: Literal["null_ip", "nxdomain"] = "null_ip"
    # Split-horizon names Krushnet answers itself, e.g. net.krushcomics.com.
    local_records: Mapping[str, IPvAnyAddress] = Field(default_factory=dict)

    @field_validator("local_records", mode="after")
    @classmethod
    def _normalise_names(
        cls, records: Mapping[str, IPv4Address | IPv6Address]
    ) -> dict[str, IPv4Address | IPv6Address]:
        return {normalise_dns_name(name): ip for name, ip in records.items()}


class UpstreamSettings(_Section):
    providers: tuple[HttpsUrl, ...] = Field(
        default=(HttpUrl("https://dns.quad9.net/dns-query"),), min_length=1
    )
    timeout_seconds: Annotated[float, Strict(), Field(gt=0, le=10)] = 2.0


class DiscoverySettings(_Section):
    # Required by the discovery service itself (PR 1.4); optional here so a
    # dev config for DNS or the portal alone still loads.
    interface: Annotated[str, Field(pattern=r"^[A-Za-z0-9_.-]{1,15}$")] | None = None
    subnet: Annotated[IPv4Network, AfterValidator(_private_scan_range)] = IPv4Network(
        "192.168.1.0/24"
    )
    scan_interval_seconds: Annotated[int, Strict(), Field(ge=30)] = 300


class PortalSettings(_Section):
    listen: tuple[LanAddress, ...] = Field(default=(LOOPBACK,), min_length=1)
    port: Port = 8000
    session_hours: Annotated[int, Strict(), Field(ge=1, le=720)] = 12


class DatabaseSettings(_Section):
    path: Annotated[Path, AfterValidator(_absolute_path)] = Path("/var/lib/krushnet/krushnet.db")
    query_retention_days: Annotated[int, Strict(), Field(ge=1, le=365)] = 30


class Settings(_Section):
    dns: DnsSettings = Field(default_factory=DnsSettings)
    upstream: UpstreamSettings = Field(default_factory=UpstreamSettings)
    discovery: DiscoverySettings = Field(default_factory=DiscoverySettings)
    portal: PortalSettings = Field(default_factory=PortalSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)


# --- loading -----------------------------------------------------------------------


def resolve_config_path(cli_value: str | None, environ: Mapping[str, str] = os.environ) -> Path:
    """Pick the config file: --config flag, then $KRUSHNET_CONFIG, then the default."""
    if cli_value:
        return Path(cli_value)
    if env_value := environ.get(CONFIG_ENV_VAR):
        return Path(env_value)
    return DEFAULT_CONFIG_PATH


def load_config(path: Path) -> Settings:
    """Read and validate a config file. Raises ConfigError with every problem found."""
    try:
        with path.open("rb") as f:
            data = tomllib.load(f)
    except FileNotFoundError:
        raise ConfigError(path, ["file not found"]) from None
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(path, [f"not valid TOML: {exc}"]) from None
    except OSError as exc:
        raise ConfigError(path, [f"can't read file: {exc.strerror}"]) from None

    try:
        return Settings.model_validate(data)
    except ValidationError as exc:
        raise ConfigError(path, _describe(exc)) from None


def _describe(exc: ValidationError) -> list[str]:
    """Turn pydantic's errors into "dotted.key: message (got value)" lines."""
    errors = exc.errors(include_url=False)
    problems = []
    for error in errors:
        # When an item in a list fails, pydantic also reports the list as
        # "too short" (it counts only valid items). That's noise: skip it if
        # an error inside the same list explains the real problem.
        if error["type"] == "too_short" and any(
            other["loc"][: len(error["loc"])] == error["loc"] and other is not error
            for other in errors
        ):
            continue
        location = ".".join(str(part) for part in error["loc"]) or "(top level)"
        message = error["msg"].removeprefix("Value error, ")
        if error["type"] == "missing":
            problems.append(f"{location}: {message}")
            continue
        shown = repr(error["input"])
        if len(shown) > _MAX_SHOWN_VALUE:
            shown = shown[:_MAX_SHOWN_VALUE] + "..."
        problems.append(f"{location}: {message} (got {shown})")
    return problems
