"""Ethernet / VLAN / IPv4 / IPv6 / UDP layer handling."""

from __future__ import annotations

import ipaddress

from discovery_packets import (
    BROADCAST_MAC,
    ETH_ARP,
    ETH_IPV4,
    ETH_IPV6,
    PHONE_MAC,
    ether,
    ipv4,
    ipv6,
    mac_bytes,
    udp,
)

from krushnet.discovery.frames import MAX_FRAME_SIZE, Udp, parse_ethernet, parse_udp


def udp_v4_frame(**ip_kw: int) -> bytes:
    return ether(
        PHONE_MAC,
        BROADCAST_MAC,
        ETH_IPV4,
        ipv4("192.168.1.20", "192.168.1.255", udp(1234, 5678, b"hello"), **ip_kw),
    )


def test_ethernet() -> None:
    eth = parse_ethernet(ether(PHONE_MAC, BROADCAST_MAC, ETH_ARP, b"payload"))
    assert eth is not None
    assert eth.src_mac == mac_bytes(PHONE_MAC)
    assert eth.ethertype == ETH_ARP
    assert eth.payload == b"payload"


def test_vlan_tag_is_skipped() -> None:
    eth = parse_ethernet(ether(PHONE_MAC, BROADCAST_MAC, ETH_ARP, b"payload", vlan=10))
    assert eth is not None
    assert eth.ethertype == ETH_ARP
    assert eth.payload == b"payload"


def test_ethernet_rejects_short_oversized_and_8023() -> None:
    assert parse_ethernet(b"\x00" * 13) is None
    assert parse_ethernet(ether(PHONE_MAC, BROADCAST_MAC, ETH_ARP, b"", vlan=10)[:17]) is None
    assert parse_ethernet(ether(PHONE_MAC, BROADCAST_MAC, ETH_ARP, b"x" * MAX_FRAME_SIZE)) is None
    # An EtherType below 0x0600 is an 802.3 length field, not a type.
    assert parse_ethernet(ether(PHONE_MAC, BROADCAST_MAC, 0x0040, b"x" * 64)) is None


def test_udp_over_ipv4() -> None:
    eth = parse_ethernet(udp_v4_frame())
    assert eth is not None
    packet = parse_udp(eth)
    assert packet is not None
    assert packet.src_ip == ipaddress.ip_address("192.168.1.20")
    assert packet.dst_ip == ipaddress.ip_address("192.168.1.255")
    assert (packet.src_port, packet.dst_port) == (1234, 5678)
    assert packet.payload == b"hello"


def test_ethernet_padding_after_ip_packet_is_ignored() -> None:
    eth = parse_ethernet(udp_v4_frame() + b"\x00" * 20)
    assert eth is not None
    packet = parse_udp(eth)
    assert packet is not None
    assert packet.payload == b"hello"


def test_ipv4_options_are_skipped() -> None:
    eth = parse_ethernet(udp_v4_frame(ihl_words=6))
    assert eth is not None
    packet = parse_udp(eth)
    assert packet is not None
    assert packet.payload == b"hello"


def parse_udp_from(frame: bytes) -> Udp | None:
    eth = parse_ethernet(frame)
    return None if eth is None else parse_udp(eth)


def test_ipv4_rejects_bad_headers() -> None:
    assert parse_udp_from(udp_v4_frame(ihl_words=4)) is None
    # IHL claims a 60-byte header, but the whole packet is only 33 bytes.
    claims_long_header = bytearray(udp_v4_frame())
    claims_long_header[14] = 0x4F
    assert parse_udp_from(bytes(claims_long_header)) is None
    assert parse_udp_from(udp_v4_frame(total_length=10)) is None  # shorter than header
    assert parse_udp_from(udp_v4_frame(total_length=500)) is None  # longer than data


def test_ipv4_fragments_are_ignored() -> None:
    assert parse_udp_from(udp_v4_frame(flags_fragment=0x2000)) is None  # more fragments
    assert parse_udp_from(udp_v4_frame(flags_fragment=0x0010)) is None  # non-zero offset
    assert parse_udp_from(udp_v4_frame(flags_fragment=0x4000)) is not None  # don't-fragment


def test_non_udp_is_ignored() -> None:
    tcp = ether(
        PHONE_MAC, BROADCAST_MAC, ETH_IPV4, ipv4("192.168.1.20", "1.1.1.1", b"x" * 20, proto=6)
    )
    assert parse_udp_from(tcp) is None


def test_udp_rejects_bad_length() -> None:
    def frame(length: int) -> bytes:
        payload = udp(1, 2, b"hello", length=length)
        return ether(PHONE_MAC, BROADCAST_MAC, ETH_IPV4, ipv4("192.168.1.20", "1.1.1.1", payload))

    assert parse_udp_from(frame(7)) is None
    assert parse_udp_from(frame(100)) is None


def test_udp_over_ipv6() -> None:
    frame = ether(
        PHONE_MAC,
        "33:33:00:00:00:fb",
        ETH_IPV6,
        ipv6("fe80::1", "ff02::fb", udp(5353, 5353, b"hi")),
    )
    packet = parse_udp_from(frame)
    assert packet is not None
    assert packet.src_ip == ipaddress.ip_address("fe80::1")
    assert packet.payload == b"hi"


def test_ipv6_extension_headers_are_skipped() -> None:
    hop_by_hop = 0
    frame = ether(
        PHONE_MAC,
        "33:33:00:00:00:fb",
        ETH_IPV6,
        ipv6("fe80::1", "ff02::fb", b"\x11\x00" + b"\x00" * 6 + udp(5353, 5353, b"hi"), hop_by_hop),
    )
    assert parse_udp_from(frame) is None


def test_ipv6_payload_length_beyond_data_rejected() -> None:
    frame = ether(
        PHONE_MAC,
        "33:33:00:00:00:fb",
        ETH_IPV6,
        ipv6("fe80::1", "ff02::fb", udp(5353, 5353, b"hi")),
    )
    assert parse_udp_from(frame[:-1]) is None
