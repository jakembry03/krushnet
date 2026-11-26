"""ARP: the most reliable "this MAC has this IP" signal on the LAN."""

from __future__ import annotations

import struct
from ipaddress import IPv4Address

from krushnet.discovery.frames import ETHERTYPE_IPV4, Ethernet
from krushnet.discovery.observations import (
    AddressSeen,
    Observation,
    format_mac,
    is_usable_ip,
    is_usable_mac,
)

_ARP_IPV4_LENGTH = 28
_HTYPE_ETHERNET = 1
_OP_REQUEST = 1
_OP_REPLY = 2


def parse_arp(eth: Ethernet) -> list[Observation]:
    """Ethernet/IPv4 ARP request or reply -> the sender's MAC and IP.

    Only sender fields are used: the target is a device that didn't send
    anything. ARP probes (sender IP 0.0.0.0, RFC 5227) carry no address.
    """
    packet = eth.payload
    if len(packet) < _ARP_IPV4_LENGTH:
        return []
    htype, ptype, hlen, plen, opcode = struct.unpack_from("!HHBBH", packet)
    if (htype, ptype, hlen, plen) != (_HTYPE_ETHERNET, ETHERTYPE_IPV4, 6, 4):
        return []
    if opcode not in (_OP_REQUEST, _OP_REPLY):
        return []

    sender_mac = packet[8:14]
    sender_ip = IPv4Address(packet[14:18])
    # A sender MAC that differs from the frame's source is proxy ARP or
    # spoofing; either way it's not a device telling us about itself.
    if sender_mac != eth.src_mac or not is_usable_mac(sender_mac):
        return []
    if not is_usable_ip(sender_ip):
        return []
    return [AddressSeen(format_mac(sender_mac), sender_ip, "arp")]
