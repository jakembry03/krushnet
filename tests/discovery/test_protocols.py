"""ARP, DHCP and mDNS, end to end through parse_frame."""

from __future__ import annotations

import ipaddress

from discovery_packets import (
    BROADCAST_MAC,
    ETH_ARP,
    ETH_IPV4,
    LAPTOP_MAC,
    PHONE_MAC,
    ROUTER_MAC,
    arp,
    arp_frame,
    dhcp,
    dhcp_client_frame,
    dhcp_option,
    dhcp_server_frame,
    ether,
    ipv4,
    mdns_v4_frame,
    mdns_v6_frame,
    udp,
)

from krushnet.discovery.observations import AddressSeen, HostnameSeen
from krushnet.discovery.parse import parse_frame


def ip(text: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address:
    return ipaddress.ip_address(text)


# --- ARP -------------------------------------------------------------------------------


def test_arp_request_and_reply() -> None:
    expected = [AddressSeen(PHONE_MAC, ip("192.168.1.20"), "arp")]
    assert parse_frame(arp_frame(opcode=1)) == expected
    assert parse_frame(arp_frame(opcode=2)) == expected


def test_arp_with_vlan_tag() -> None:
    assert parse_frame(arp_frame(vlan=10)) == [AddressSeen(PHONE_MAC, ip("192.168.1.20"), "arp")]


def test_arp_probe_gives_nothing() -> None:
    assert parse_frame(arp_frame(sender_ip="0.0.0.0")) == []


def test_arp_rejects_unknown_opcode_and_hardware_type() -> None:
    assert parse_frame(arp_frame(opcode=3)) == []
    odd = ether(PHONE_MAC, BROADCAST_MAC, ETH_ARP, arp(1, PHONE_MAC, "192.168.1.20", htype=6))
    assert parse_frame(odd) == []


def test_arp_sender_must_match_ethernet_source() -> None:
    """A frame from one MAC claiming another MAC's address is spoofed or proxied."""
    spoofed = ether(ROUTER_MAC, BROADCAST_MAC, ETH_ARP, arp(2, PHONE_MAC, "192.168.1.20"))
    assert parse_frame(spoofed) == []


def test_arp_truncated() -> None:
    assert parse_frame(arp_frame()[: 14 + 27]) == []


# --- DHCP --------------------------------------------------------------------------------


def test_dhcp_discover_gives_hostname() -> None:
    assert parse_frame(dhcp_client_frame()) == [HostnameSeen(PHONE_MAC, "Jakes-iPhone", "dhcp")]


def test_dhcp_request_with_ciaddr_gives_address_and_hostname() -> None:
    frame = dhcp_client_frame(message_type=3, ciaddr="192.168.1.20", src_ip="192.168.1.20")
    assert set(parse_frame(frame)) == {
        HostnameSeen(PHONE_MAC, "Jakes-iPhone", "dhcp"),
        AddressSeen(PHONE_MAC, ip("192.168.1.20"), "dhcp"),
    }


def test_dhcp_without_hostname() -> None:
    assert parse_frame(dhcp_client_frame(hostname=None)) == []


def test_dhcp_bad_hostname_is_dropped() -> None:
    assert parse_frame(dhcp_client_frame(hostname=b"bad\x1bname")) == []


def test_dhcp_ack_gives_assigned_address() -> None:
    assert parse_frame(dhcp_server_frame()) == [AddressSeen(PHONE_MAC, ip("192.168.1.20"), "dhcp")]


def test_dhcp_offer_and_nak_give_nothing() -> None:
    assert parse_frame(dhcp_server_frame(message_type=2)) == []  # OFFER: not yet the device's
    assert parse_frame(dhcp_server_frame(message_type=6)) == []  # NAK


def dhcp_frame_with(payload: bytes) -> bytes:
    return ether(
        PHONE_MAC,
        BROADCAST_MAC,
        ETH_IPV4,
        ipv4("0.0.0.0", "255.255.255.255", udp(68, 67, payload)),
    )


def test_dhcp_requires_magic_cookie() -> None:
    payload = dhcp(1, PHONE_MAC, dhcp_option(53, b"\x01") + dhcp_option(12, b"x"), magic=b"\0" * 4)
    assert parse_frame(dhcp_frame_with(payload)) == []


def test_dhcp_requires_ethernet_hardware_type() -> None:
    payload = dhcp(1, PHONE_MAC, dhcp_option(53, b"\x01") + dhcp_option(12, b"x"), htype=6)
    assert parse_frame(dhcp_frame_with(payload)) == []


def test_dhcp_rejects_multicast_chaddr() -> None:
    payload = dhcp(1, "01:00:5e:00:00:01", dhcp_option(53, b"\x01") + dhcp_option(12, b"x"))
    assert parse_frame(dhcp_frame_with(payload)) == []


def test_dhcp_option_running_past_end_stops_parsing() -> None:
    options = dhcp_option(53, b"\x01") + bytes([12, 200]) + b"short"
    payload = dhcp(1, PHONE_MAC, options)[:-1]  # drop the End option too
    assert parse_frame(dhcp_frame_with(payload)) == []


def test_dhcp_pad_options_are_skipped() -> None:
    options = b"\x00\x00" + dhcp_option(53, b"\x01") + b"\x00" + dhcp_option(12, b"tv")
    assert parse_frame(dhcp_frame_with(dhcp(1, PHONE_MAC, options))) == [
        HostnameSeen(PHONE_MAC, "tv", "dhcp")
    ]


def test_dhcp_without_message_type_is_ignored() -> None:
    """Plain BOOTP (no option 53) isn't something home devices send."""
    payload = dhcp(1, PHONE_MAC, dhcp_option(12, b"tv"))
    assert parse_frame(dhcp_frame_with(payload)) == []


def test_dhcp_on_wrong_ports_is_ignored() -> None:
    payload = dhcp(1, PHONE_MAC, dhcp_option(53, b"\x01") + dhcp_option(12, b"tv"))
    frame = ether(
        PHONE_MAC,
        BROADCAST_MAC,
        ETH_IPV4,
        ipv4("0.0.0.0", "255.255.255.255", udp(1000, 67, payload)),
    )
    assert parse_frame(frame) == []


# --- mDNS ----------------------------------------------------------------------------------


def test_mdns_v4_announcement() -> None:
    assert set(parse_frame(mdns_v4_frame())) == {
        HostnameSeen(LAPTOP_MAC, "Jakes-MacBook", "mdns"),
        AddressSeen(LAPTOP_MAC, ip("192.168.1.30"), "mdns"),
    }


def test_mdns_v6_announcement() -> None:
    assert set(parse_frame(mdns_v6_frame())) == {
        HostnameSeen(LAPTOP_MAC, "Jakes-MacBook", "mdns"),
        AddressSeen(LAPTOP_MAC, ip("fe80::1234:5678:9abc:def0"), "mdns"),
    }


def test_mdns_record_for_another_address_is_ignored() -> None:
    """Sleep proxies announce other devices' names; don't pin them on the proxy."""
    proxied = mdns_v4_frame(records=[("Someone-Else.local", "192.168.1.99")])
    assert parse_frame(proxied) == []


def test_mdns_only_matching_records_used() -> None:
    frame = mdns_v4_frame(
        records=[("Someone-Else.local", "192.168.1.99"), ("Jakes-MacBook.local", "192.168.1.30")]
    )
    assert HostnameSeen(LAPTOP_MAC, "Jakes-MacBook", "mdns") in parse_frame(frame)
    assert all(
        not isinstance(o, HostnameSeen) or o.hostname != "Someone-Else" for o in parse_frame(frame)
    )


def test_mdns_queries_are_ignored() -> None:
    assert parse_frame(mdns_v4_frame(qr=0)) == []


def test_mdns_non_local_and_multi_label_names_ignored() -> None:
    assert parse_frame(mdns_v4_frame(records=[("host.example.com", "192.168.1.30")])) == []
    assert parse_frame(mdns_v4_frame(records=[("a.b.local", "192.168.1.30")])) == []


def test_mdns_wrong_source_port_ignored() -> None:
    """RFC 6762: multicast responses come from port 5353."""
    assert parse_frame(mdns_v4_frame(src_port=40000)) == []


def test_mdns_malformed_payload() -> None:
    # Header claiming one answer, then a name that's a compression pointer to itself.
    looping = b"\x00\x00\x84\x00\x00\x00\x00\x01\x00\x00\x00\x00" + b"\xc0\x0c" + b"\x00" * 10
    frame = ether(
        LAPTOP_MAC,
        "01:00:5e:00:00:fb",
        ETH_IPV4,
        ipv4("192.168.1.30", "224.0.0.251", udp(5353, 5353, looping)),
    )
    assert parse_frame(frame) == []


def test_mdns_to_unicast_destination_ignored() -> None:
    from discovery_packets import mdns_response

    frame = ether(
        LAPTOP_MAC,
        PHONE_MAC,
        ETH_IPV4,
        ipv4(
            "192.168.1.30",
            "192.168.1.20",
            udp(5353, 5353, mdns_response([("Jakes-MacBook.local", "192.168.1.30")])),
        ),
    )
    assert parse_frame(frame) == []


# --- general ------------------------------------------------------------------------------


def test_multicast_source_mac_is_dropped() -> None:
    assert parse_frame(arp_frame(sender_mac="01:00:5e:00:00:01")) == []


def test_irrelevant_traffic_gives_nothing() -> None:
    assert parse_frame(b"") == []
    assert parse_frame(ether(PHONE_MAC, BROADCAST_MAC, 0x88CC, b"lldp" * 10)) == []
