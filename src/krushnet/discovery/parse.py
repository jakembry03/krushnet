"""Entry point: one captured Ethernet frame in, a list of observations out."""

from __future__ import annotations

import struct

from krushnet.discovery.arp import parse_arp
from krushnet.discovery.dhcp import is_dhcp, parse_dhcp
from krushnet.discovery.frames import ETHERTYPE_ARP, parse_ethernet, parse_udp
from krushnet.discovery.mdns import is_mdns, parse_mdns
from krushnet.discovery.observations import Observation, is_usable_mac

# The parsers check every length before reading, so these should never
# happen. They're caught here as a last line of defence: a bug in one parser
# must cost one frame, never crash the discovery service (hard rule 4).
_PARSE_ERRORS = (ValueError, IndexError, struct.error, UnicodeError)


def parse_frame(frame: bytes) -> list[Observation]:
    """Never raises. Returns [] for anything irrelevant, malformed or suspicious."""
    try:
        return _parse(frame)
    except _PARSE_ERRORS:
        return []


def _parse(frame: bytes) -> list[Observation]:
    eth = parse_ethernet(frame)
    if eth is None or not is_usable_mac(eth.src_mac):
        return []
    if eth.ethertype == ETHERTYPE_ARP:
        return parse_arp(eth)

    packet = parse_udp(eth)
    if packet is None:
        return []
    if is_dhcp(packet):
        return parse_dhcp(packet)
    if is_mdns(packet):
        return parse_mdns(packet)
    return []
