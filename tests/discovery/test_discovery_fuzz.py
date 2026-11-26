"""Fuzz parse_frame with mutated and random frames (seeded, so repeatable).

The contract under test: parse_frame never raises, and anything it returns
is well-formed. Every frame on the LAN is untrusted (hard rule 4).
"""

from __future__ import annotations

import ipaddress
import random
import re
import struct

import pytest
from discovery_packets import (
    ETH_ARP,
    ETH_IPV4,
    ETH_IPV6,
    LAPTOP_MAC,
    PHONE_MAC,
    all_valid_samples,
    ether,
    ipv4,
    ipv6,
    udp,
)

from krushnet.discovery.observations import AddressSeen, HostnameSeen, sanitise_hostname
from krushnet.discovery.parse import parse_frame

SEED = 20261126
MAC_PATTERN = re.compile(r"^[0-9a-f]{2}(:[0-9a-f]{2}){5}$")
SAMPLES = all_valid_samples()


def check(frame: bytes) -> None:
    """parse_frame must not raise and must return only well-formed observations."""
    for observation in parse_frame(frame):
        assert MAC_PATTERN.match(observation.mac), observation
        if isinstance(observation, AddressSeen):
            assert isinstance(observation.ip, ipaddress.IPv4Address | ipaddress.IPv6Address)
            assert observation.via in ("arp", "dhcp", "mdns")
        else:
            assert isinstance(observation, HostnameSeen)
            # A sanitised name survives sanitising again unchanged.
            assert sanitise_hostname(observation.hostname.encode()) == observation.hostname
            assert observation.via in ("dhcp", "mdns")


@pytest.mark.parametrize("name", sorted(SAMPLES))
def test_valid_samples_parse(name: str) -> None:
    assert parse_frame(SAMPLES[name]), f"{name} should produce observations"


@pytest.mark.parametrize("name", sorted(SAMPLES))
def test_every_truncation(name: str) -> None:
    frame = SAMPLES[name]
    for cut in range(len(frame)):
        check(frame[:cut])


@pytest.mark.parametrize("name", sorted(SAMPLES))
def test_every_single_bit_flip(name: str) -> None:
    frame = bytearray(SAMPLES[name])
    for index in range(len(frame)):
        for bit in range(8):
            frame[index] ^= 1 << bit
            check(bytes(frame))
            frame[index] ^= 1 << bit


@pytest.mark.parametrize("name", sorted(SAMPLES))
def test_random_mutations(name: str) -> None:
    rng = random.Random(f"{SEED}-{name}")
    original = SAMPLES[name]
    for _ in range(2000):
        frame = bytearray(original)
        for _ in range(rng.randint(1, 8)):
            index = rng.randrange(len(frame))
            match rng.randrange(3):
                case 0:  # overwrite a byte
                    frame[index] = rng.randrange(256)
                case 1:  # delete a run
                    del frame[index : index + rng.randint(1, 16)]
                case _:  # insert junk
                    frame[index:index] = rng.randbytes(rng.randint(1, 16))
            if not frame:
                break
        check(bytes(frame))


def random_frames(rng: random.Random) -> list[bytes]:
    """Random payloads behind valid headers, so the inner parsers get exercised."""
    junk = rng.randbytes(rng.randint(0, 600))
    return [
        ether(PHONE_MAC, "ff:ff:ff:ff:ff:ff", ETH_ARP, junk),
        ether(
            PHONE_MAC,
            "ff:ff:ff:ff:ff:ff",
            ETH_IPV4,
            ipv4("0.0.0.0", "255.255.255.255", udp(68, 67, junk)),
        ),
        ether(
            LAPTOP_MAC,
            "01:00:5e:00:00:fb",
            ETH_IPV4,
            ipv4("192.168.1.30", "224.0.0.251", udp(5353, 5353, junk)),
        ),
        ether(
            LAPTOP_MAC,
            "33:33:00:00:00:fb",
            ETH_IPV6,
            ipv6("fe80::1", "ff02::fb", udp(5353, 5353, junk)),
        ),
        # DHCP fixed header + cookie, then random options.
        ether(
            PHONE_MAC,
            "ff:ff:ff:ff:ff:ff",
            ETH_IPV4,
            ipv4(
                "0.0.0.0",
                "255.255.255.255",
                udp(68, 67, struct.pack("!BBB", 1, 1, 6) + bytes(233) + b"\x63\x82\x53\x63" + junk),
            ),
        ),
        # mDNS response header, then random records.
        ether(
            LAPTOP_MAC,
            "01:00:5e:00:00:fb",
            ETH_IPV4,
            ipv4(
                "192.168.1.30",
                "224.0.0.251",
                udp(5353, 5353, b"\x00\x00\x84\x00" + rng.randbytes(8) + junk),
            ),
        ),
        rng.randbytes(rng.randint(0, 200)),
    ]


def test_random_payloads_behind_valid_headers() -> None:
    rng = random.Random(SEED)
    for _ in range(800):  # 7 frames each: ~5,600 cases
        for frame in random_frames(rng):
            check(frame)
