"""Walk an Ethernet frame down to the layer a protocol parser needs.

Handles Ethernet II (with at most one 802.1Q VLAN tag), IPv4, IPv6 without
extension headers, and UDP. Every length field is checked against the bytes
actually present; anything inconsistent returns None. No checksums are
verified: the kernel has already done that for frames it delivers.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from ipaddress import IPv4Address, IPv6Address

ETHERTYPE_IPV4 = 0x0800
ETHERTYPE_ARP = 0x0806
ETHERTYPE_IPV6 = 0x86DD
ETHERTYPE_VLAN = 0x8100

IP_PROTO_UDP = 17

# Jumbo-frame size; nothing on a home LAN should be bigger.
MAX_FRAME_SIZE = 9216

_ETHERNET_HEADER = 14
_VLAN_TAG = 4
_IPV4_MIN_HEADER = 20
_IPV6_HEADER = 40
_UDP_HEADER = 8


@dataclass(frozen=True, slots=True)
class Ethernet:
    src_mac: bytes
    ethertype: int
    payload: bytes


@dataclass(frozen=True, slots=True)
class Udp:
    """A UDP datagram plus the lower-layer fields the parsers need."""

    src_mac: bytes
    src_ip: IPv4Address | IPv6Address
    dst_ip: IPv4Address | IPv6Address
    src_port: int
    dst_port: int
    payload: bytes


def parse_ethernet(frame: bytes) -> Ethernet | None:
    if not _ETHERNET_HEADER <= len(frame) <= MAX_FRAME_SIZE:
        return None
    src_mac = frame[6:12]
    (ethertype,) = struct.unpack_from("!H", frame, 12)
    offset = _ETHERNET_HEADER
    if ethertype == ETHERTYPE_VLAN:
        if len(frame) < _ETHERNET_HEADER + _VLAN_TAG:
            return None
        (ethertype,) = struct.unpack_from("!H", frame, 16)
        offset += _VLAN_TAG
    # Values below 0x0600 are 802.3 length fields, not EtherTypes.
    if ethertype < 0x0600:
        return None
    return Ethernet(src_mac=src_mac, ethertype=ethertype, payload=frame[offset:])


def parse_udp(eth: Ethernet) -> Udp | None:
    """Return the UDP datagram inside an IPv4 or IPv6 packet, or None."""
    network: tuple[IPv4Address | IPv6Address, IPv4Address | IPv6Address, bytes] | None
    if eth.ethertype == ETHERTYPE_IPV4:
        network = _parse_ipv4(eth.payload)
    elif eth.ethertype == ETHERTYPE_IPV6:
        network = _parse_ipv6(eth.payload)
    else:
        return None
    if network is None:
        return None
    src_ip, dst_ip, segment = network

    if len(segment) < _UDP_HEADER:
        return None
    src_port, dst_port, length = struct.unpack_from("!HHH", segment)
    if not _UDP_HEADER <= length <= len(segment):
        return None
    return Udp(
        src_mac=eth.src_mac,
        src_ip=src_ip,
        dst_ip=dst_ip,
        src_port=src_port,
        dst_port=dst_port,
        payload=segment[_UDP_HEADER:length],
    )


def _parse_ipv4(packet: bytes) -> tuple[IPv4Address, IPv4Address, bytes] | None:
    """Return (src, dst, UDP segment) for an unfragmented IPv4/UDP packet."""
    if len(packet) < _IPV4_MIN_HEADER:
        return None
    version_ihl = packet[0]
    (total_length,) = struct.unpack_from("!H", packet, 2)
    (flags_fragment,) = struct.unpack_from("!H", packet, 6)
    protocol = packet[9]
    header_length = (version_ihl & 0x0F) * 4
    if version_ihl >> 4 != 4 or header_length < _IPV4_MIN_HEADER:
        return None
    # total_length may be shorter than the data (Ethernet pads small frames).
    if not header_length <= total_length <= len(packet):
        return None
    more_fragments = flags_fragment & 0x2000
    fragment_offset = flags_fragment & 0x1FFF
    if more_fragments or fragment_offset or protocol != IP_PROTO_UDP:
        return None
    return (
        IPv4Address(packet[12:16]),
        IPv4Address(packet[16:20]),
        packet[header_length:total_length],
    )


def _parse_ipv6(packet: bytes) -> tuple[IPv6Address, IPv6Address, bytes] | None:
    """Return (src, dst, UDP segment) when UDP directly follows the fixed header.

    Packets with extension headers are skipped: home-LAN mDNS doesn't use them,
    and walking them is extra attack surface for no gain.
    """
    if len(packet) < _IPV6_HEADER or packet[0] >> 4 != 6:
        return None
    (payload_length,) = struct.unpack_from("!H", packet, 4)
    next_header = packet[6]
    if next_header != IP_PROTO_UDP or _IPV6_HEADER + payload_length > len(packet):
        return None
    return (
        IPv6Address(packet[8:24]),
        IPv6Address(packet[24:40]),
        packet[_IPV6_HEADER : _IPV6_HEADER + payload_length],
    )
