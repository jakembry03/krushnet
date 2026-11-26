"""Builders for synthetic test frames.

Every sample is made up: no real captures are committed, because they'd
contain real household device data. Checksums are left as zero; the parsers
don't verify them (the kernel already has, for frames it delivers).
"""

from __future__ import annotations

import ipaddress
import struct

from dnslib import AAAA, QTYPE, RR, A, DNSHeader, DNSRecord

PHONE_MAC = "3c:22:fb:11:22:33"
LAPTOP_MAC = "f0:2f:4b:44:55:66"
ROUTER_MAC = "00:1a:2b:3c:4d:5e"
BROADCAST_MAC = "ff:ff:ff:ff:ff:ff"

ETH_IPV4 = 0x0800
ETH_ARP = 0x0806
ETH_IPV6 = 0x86DD
ETH_VLAN = 0x8100

MDNS_V4 = "224.0.0.251"
MDNS_V6 = "ff02::fb"
DHCP_MAGIC = b"\x63\x82\x53\x63"


def mac_bytes(mac: str) -> bytes:
    return bytes.fromhex(mac.replace(":", ""))


def ip_bytes(ip: str) -> bytes:
    return ipaddress.ip_address(ip).packed


# --- layers ------------------------------------------------------------------------


def ether(src: str, dst: str, ethertype: int, payload: bytes, vlan: int | None = None) -> bytes:
    header = mac_bytes(dst) + mac_bytes(src)
    if vlan is not None:
        header += struct.pack("!HH", ETH_VLAN, vlan)
    return header + struct.pack("!H", ethertype) + payload


def ipv4(
    src: str,
    dst: str,
    payload: bytes,
    proto: int = 17,
    flags_fragment: int = 0,
    ihl_words: int = 5,
    total_length: int | None = None,
) -> bytes:
    options = b"\x00" * (max(ihl_words, 5) - 5) * 4
    length = total_length if total_length is not None else 20 + len(options) + len(payload)
    header = struct.pack(
        "!BBHHHBBH4s4s",
        (4 << 4) | ihl_words,
        0,
        length,
        0,
        flags_fragment,
        64,
        proto,
        0,
        ip_bytes(src),
        ip_bytes(dst),
    )
    return header + options + payload


def ipv6(src: str, dst: str, payload: bytes, next_header: int = 17) -> bytes:
    header = struct.pack(
        "!IHBB16s16s", 6 << 28, len(payload), next_header, 255, ip_bytes(src), ip_bytes(dst)
    )
    return header + payload


def udp(src_port: int, dst_port: int, payload: bytes, length: int | None = None) -> bytes:
    return struct.pack("!HHHH", src_port, dst_port, length or 8 + len(payload), 0) + payload


# --- ARP -----------------------------------------------------------------------------


def arp(
    opcode: int,
    sender_mac: str,
    sender_ip: str,
    target_mac: str = "00:00:00:00:00:00",
    target_ip: str = "192.168.1.1",
    htype: int = 1,
) -> bytes:
    return struct.pack(
        "!HHBBH6s4s6s4s",
        htype,
        ETH_IPV4,
        6,
        4,
        opcode,
        mac_bytes(sender_mac),
        ip_bytes(sender_ip),
        mac_bytes(target_mac),
        ip_bytes(target_ip),
    )


def arp_frame(
    sender_mac: str = PHONE_MAC, sender_ip: str = "192.168.1.20", opcode: int = 1, **kw: int
) -> bytes:
    return ether(sender_mac, BROADCAST_MAC, ETH_ARP, arp(opcode, sender_mac, sender_ip), **kw)


# --- DHCP ----------------------------------------------------------------------------


def dhcp_option(code: int, value: bytes) -> bytes:
    return bytes([code, len(value)]) + value


def dhcp(
    op: int,
    chaddr: str,
    options: bytes,
    ciaddr: str = "0.0.0.0",
    yiaddr: str = "0.0.0.0",
    htype: int = 1,
    hlen: int = 6,
    magic: bytes = DHCP_MAGIC,
) -> bytes:
    fixed = struct.pack(
        "!BBBBIHH4s4s4s4s16s64s128s",
        op,
        htype,
        hlen,
        0,
        0x12345678,
        0,
        0,
        ip_bytes(ciaddr),
        ip_bytes(yiaddr),
        ip_bytes("0.0.0.0"),
        ip_bytes("0.0.0.0"),
        mac_bytes(chaddr).ljust(16, b"\x00"),
        b"",
        b"",
    )
    return fixed + magic + options + b"\xff"


def dhcp_client_frame(
    hostname: bytes | None = b"Jakes-iPhone",
    message_type: int = 1,  # DISCOVER
    mac: str = PHONE_MAC,
    ciaddr: str = "0.0.0.0",
    src_ip: str = "0.0.0.0",
) -> bytes:
    options = dhcp_option(53, bytes([message_type]))
    if hostname is not None:
        options += dhcp_option(12, hostname)
    payload = dhcp(1, mac, options, ciaddr=ciaddr)
    return ether(
        mac, BROADCAST_MAC, ETH_IPV4, ipv4(src_ip, "255.255.255.255", udp(68, 67, payload))
    )


def dhcp_server_frame(
    message_type: int = 5,  # ACK
    client_mac: str = PHONE_MAC,
    yiaddr: str = "192.168.1.20",
) -> bytes:
    payload = dhcp(2, client_mac, dhcp_option(53, bytes([message_type])), yiaddr=yiaddr)
    return ether(
        ROUTER_MAC,
        BROADCAST_MAC,
        ETH_IPV4,
        ipv4("192.168.1.1", "255.255.255.255", udp(67, 68, payload)),
    )


# --- mDNS ----------------------------------------------------------------------------


def mdns_response(records: list[tuple[str, str]], qr: int = 1) -> bytes:
    """records: (name, address) pairs; A or AAAA chosen from the address family."""
    message = DNSRecord(DNSHeader(id=0, qr=qr, aa=1))
    for name, address in records:
        if ipaddress.ip_address(address).version == 4:
            message.add_answer(RR(name, QTYPE.A, rdata=A(address), ttl=120))
        else:
            message.add_answer(RR(name, QTYPE.AAAA, rdata=AAAA(address), ttl=120))
    return bytes(message.pack())


def mdns_v4_frame(
    records: list[tuple[str, str]] | None = None,
    src_ip: str = "192.168.1.30",
    mac: str = LAPTOP_MAC,
    qr: int = 1,
    src_port: int = 5353,
) -> bytes:
    if records is None:
        records = [("Jakes-MacBook.local", src_ip)]
    payload = mdns_response(records, qr=qr)
    return ether(
        mac, "01:00:5e:00:00:fb", ETH_IPV4, ipv4(src_ip, MDNS_V4, udp(src_port, 5353, payload))
    )


def mdns_v6_frame(
    records: list[tuple[str, str]] | None = None,
    src_ip: str = "fe80::1234:5678:9abc:def0",
    mac: str = LAPTOP_MAC,
) -> bytes:
    if records is None:
        records = [("Jakes-MacBook.local", src_ip)]
    payload = mdns_response(records)
    return ether(
        mac, "33:33:00:00:00:fb", ETH_IPV6, ipv6(src_ip, MDNS_V6, udp(5353, 5353, payload))
    )


def all_valid_samples() -> dict[str, bytes]:
    """One valid frame per path through the parser, for fuzzing."""
    return {
        "arp_request": arp_frame(),
        "arp_vlan": arp_frame(vlan=10),
        "dhcp_discover": dhcp_client_frame(),
        "dhcp_request_ciaddr": dhcp_client_frame(
            message_type=3, ciaddr="192.168.1.20", src_ip="192.168.1.20"
        ),
        "dhcp_ack": dhcp_server_frame(),
        "mdns_v4": mdns_v4_frame(),
        "mdns_v6": mdns_v6_frame(),
    }
