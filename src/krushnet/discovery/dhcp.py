"""DHCP: hostnames (option 12) and addresses from client and server messages."""

from __future__ import annotations

from ipaddress import IPv4Address

from krushnet.discovery.frames import Udp
from krushnet.discovery.observations import (
    AddressSeen,
    HostnameSeen,
    Observation,
    format_mac,
    is_usable_ip,
    is_usable_mac,
    sanitise_hostname,
)

SERVER_PORT = 67
CLIENT_PORT = 68

_FIXED_HEADER = 236  # BOOTP header before the options
_MAGIC_COOKIE = b"\x63\x82\x53\x63"
_OPTIONS_START = _FIXED_HEADER + len(_MAGIC_COOKIE)

_OP_REQUEST = 1  # client -> server
_OP_REPLY = 2  # server -> client
_HTYPE_ETHERNET = 1

_OPTION_PAD = 0
_OPTION_HOSTNAME = 12
_OPTION_MESSAGE_TYPE = 53
_OPTION_END = 255

_DISCOVER, _REQUEST, _ACK, _INFORM = 1, 3, 5, 8
_CLIENT_MESSAGES = {_DISCOVER, _REQUEST, _INFORM}


def is_dhcp(packet: Udp) -> bool:
    """Client-to-server or server-to-client DHCP (relayed 67->67 is ignored)."""
    ports = (packet.src_port, packet.dst_port)
    return ports in ((CLIENT_PORT, SERVER_PORT), (SERVER_PORT, CLIENT_PORT))


def parse_dhcp(packet: Udp) -> list[Observation]:
    data = packet.payload
    if len(data) < _OPTIONS_START or data[_FIXED_HEADER:_OPTIONS_START] != _MAGIC_COOKIE:
        return []
    op, htype, hlen = data[0], data[1], data[2]
    if htype != _HTYPE_ETHERNET or hlen != 6:
        return []
    # chaddr identifies the client, even in server replies.
    chaddr = data[28:34]
    if not is_usable_mac(chaddr):
        return []
    mac = format_mac(chaddr)
    options = _parse_options(data[_OPTIONS_START:])
    message_type = options.get(_OPTION_MESSAGE_TYPE, b"")[:1]
    if not message_type:
        return []  # plain BOOTP, not something home devices send

    observations: list[Observation] = []
    if op == _OP_REQUEST and message_type[0] in _CLIENT_MESSAGES:
        hostname = sanitise_hostname(options.get(_OPTION_HOSTNAME, b""))
        if hostname is not None:
            observations.append(HostnameSeen(mac, hostname, "dhcp"))
        # ciaddr is set only when the client already holds the address.
        # Option 50 (requested IP) is deliberately not used: not granted yet.
        ciaddr = IPv4Address(data[12:16])
        if is_usable_ip(ciaddr):
            observations.append(AddressSeen(mac, ciaddr, "dhcp"))
    elif op == _OP_REPLY and message_type[0] == _ACK:
        # Only an ACK means the address is the client's; an OFFER isn't yet.
        yiaddr = IPv4Address(data[16:20])
        if is_usable_ip(yiaddr):
            observations.append(AddressSeen(mac, yiaddr, "dhcp"))
    return observations


def _parse_options(data: bytes) -> dict[int, bytes]:
    """Parse type-length-value options. Keeps the first copy of each option.

    Stops at End, or at the first option whose length runs past the data;
    options parsed before that point are kept.
    """
    options: dict[int, bytes] = {}
    index = 0
    while index < len(data):
        code = data[index]
        if code == _OPTION_PAD:
            index += 1
            continue
        if code == _OPTION_END or index + 1 >= len(data):
            break
        length = data[index + 1]
        start = index + 2
        if start + length > len(data):
            break
        options.setdefault(code, data[start : start + length])
        index = start + length
    return options
