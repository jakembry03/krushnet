"""MAC, IP and hostname checks shared by every parser."""

from __future__ import annotations

import ipaddress

import pytest

from krushnet.discovery.observations import (
    format_mac,
    is_usable_ip,
    is_usable_mac,
    sanitise_hostname,
)


def test_format_mac() -> None:
    assert format_mac(bytes.fromhex("3C22FB112233")) == "3c:22:fb:11:22:33"


@pytest.mark.parametrize(
    ("mac", "usable"),
    [
        ("3c22fb112233", True),
        ("3e22fb112233", True),  # locally administered (randomized) is still a device
        ("000000000000", False),
        ("ffffffffffff", False),
        ("01005e0000fb", False),  # multicast bit set
        ("3c22fb1122", False),  # too short
    ],
)
def test_is_usable_mac(mac: str, usable: bool) -> None:
    assert is_usable_mac(bytes.fromhex(mac)) is usable


@pytest.mark.parametrize(
    ("ip", "usable"),
    [
        ("192.168.1.20", True),
        ("169.254.10.10", True),  # link-local: a device without a DHCP lease
        ("fe80::1", True),
        ("0.0.0.0", False),
        ("255.255.255.255", False),
        ("224.0.0.251", False),
        ("127.0.0.1", False),
        ("::", False),
        ("ff02::fb", False),
    ],
)
def test_is_usable_ip(ip: str, usable: bool) -> None:
    assert is_usable_ip(ipaddress.ip_address(ip)) is usable


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (b"Jakes-iPhone", "Jakes-iPhone"),
        (b"Jakes-iPhone\x00", "Jakes-iPhone"),  # DHCP names are often NUL-terminated
        (b"  living-room-tv  ", "living-room-tv"),
        ("Café-Laptop".encode(), "Café-Laptop"),
        (b"a" * 63, "a" * 63),
    ],
)
def test_sanitise_hostname_accepts(raw: bytes, expected: str) -> None:
    assert sanitise_hostname(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        b"",
        b"\x00\x00",
        b"   ",
        b"a" * 64,  # rejected, not truncated
        b"\xff\xfe",  # not UTF-8
        b"evil\x1b[31mname",  # terminal escape
        b"two\nlines",
        b"nul\x00inside",
        "zero​width".encode(),  # format character
        "rtl‮override".encode(),
    ],
)
def test_sanitise_hostname_rejects(raw: bytes) -> None:
    assert sanitise_hostname(raw) is None
