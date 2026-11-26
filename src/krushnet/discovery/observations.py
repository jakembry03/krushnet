"""What the discovery parsers report, and the checks every report must pass.

A parser turns one captured frame into zero or more observations: "this MAC
has this IP" or "this MAC calls itself this name". Nothing else from the
frame is kept (hard rule 1).
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from ipaddress import IPv4Address, IPv6Address
from typing import Literal

# DNS label limit; longer names are rejected rather than truncated so a
# mangled name never looks like a real one.
MAX_HOSTNAME_LENGTH = 63

_LIMITED_BROADCAST = IPv4Address("255.255.255.255")


@dataclass(frozen=True, slots=True)
class AddressSeen:
    mac: str  # "aa:bb:cc:dd:ee:ff"
    ip: IPv4Address | IPv6Address
    via: Literal["arp", "dhcp", "mdns"]


@dataclass(frozen=True, slots=True)
class HostnameSeen:
    mac: str
    hostname: str  # sanitised, see sanitise_hostname()
    via: Literal["dhcp", "mdns"]


type Observation = AddressSeen | HostnameSeen


def format_mac(raw: bytes) -> str:
    return ":".join(f"{byte:02x}" for byte in raw)


def is_usable_mac(raw: bytes) -> bool:
    """True for a 6-byte unicast MAC that could belong to a real device.

    Locally administered (randomized) MACs count: they're still devices.
    """
    if len(raw) != 6 or raw == bytes(6):
        return False
    is_multicast = raw[0] & 0x01  # also covers broadcast ff:ff:...
    return not is_multicast


def is_usable_ip(ip: IPv4Address | IPv6Address) -> bool:
    """True for an address a device could actually be using on the LAN."""
    return not (ip.is_unspecified or ip.is_multicast or ip.is_loopback or ip == _LIMITED_BROADCAST)


def sanitise_hostname(raw: bytes) -> str | None:
    """Return a hostname that's safe to store and display, or None.

    Accepts UTF-8, strips trailing NULs (DHCP names are often NUL-terminated)
    and surrounding whitespace, and rejects anything with control or format
    characters (terminal escapes, newlines, embedded NULs, bidi overrides,
    zero-width characters) or over MAX_HOSTNAME_LENGTH characters.
    """
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return None
    text = text.rstrip("\x00").strip()
    if not text or len(text) > MAX_HOSTNAME_LENGTH:
        return None
    # Unicode category "C*": control, format, surrogate, private use, unassigned.
    if any(unicodedata.category(char).startswith("C") for char in text):
        return None
    return text
