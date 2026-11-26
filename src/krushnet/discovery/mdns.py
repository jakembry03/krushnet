"""mDNS: hostnames that devices announce for themselves (A/AAAA "name.local")."""

from __future__ import annotations

import struct
from ipaddress import IPv4Address, IPv6Address, ip_address

from dnslib import QTYPE, DNSError, DNSRecord
from dnslib.buffer import BufferError as DnslibBufferError

from krushnet.discovery.frames import Udp
from krushnet.discovery.observations import (
    AddressSeen,
    HostnameSeen,
    Observation,
    format_mac,
    is_usable_ip,
    sanitise_hostname,
)

MDNS_PORT = 5353
MDNS_GROUPS = (IPv4Address("224.0.0.251"), IPv6Address("ff02::fb"))

# Real announcements are a few hundred bytes; cap the work per packet.
MAX_PAYLOAD = 9000
MAX_RECORDS = 50

# Everything dnslib is known to raise on malformed input. The fuzz tests
# check nothing else escapes.
_DNSLIB_ERRORS = (
    DNSError,
    DnslibBufferError,
    ValueError,
    IndexError,
    UnicodeError,
    struct.error,
)


def is_mdns(packet: Udp) -> bool:
    """Multicast mDNS from a responder (RFC 6762: source port 5353)."""
    return (
        packet.src_port == MDNS_PORT
        and packet.dst_port == MDNS_PORT
        and packet.dst_ip in MDNS_GROUPS
    )


def parse_mdns(packet: Udp) -> list[Observation]:
    """A/AAAA records for "<name>.local" that point at the sender itself.

    The address must equal the packet's source IP: Bonjour sleep proxies
    (e.g. an Apple TV) announce records for *other* devices, and those names
    mustn't be pinned on the proxy's MAC. Service records (PTR/SRV/TXT) are
    ignored; they describe services, not device identity.
    """
    if len(packet.payload) > MAX_PAYLOAD:
        return []
    try:
        message = DNSRecord.parse(packet.payload)
    except _DNSLIB_ERRORS:
        return []
    if message.header.qr != 1:
        return []  # queries say what a device wants, not who it is

    mac = format_mac(packet.src_mac)
    observations: list[Observation] = []
    for record in (message.rr + message.ar)[:MAX_RECORDS]:
        if record.rtype not in (QTYPE.A, QTYPE.AAAA):
            continue
        labels = record.rname.label
        # Exactly "<hostname>.local": multi-label .local names are service-ish.
        if len(labels) != 2 or labels[1].lower() != b"local":
            continue
        try:
            address = ip_address(str(record.rdata))
        except ValueError:
            continue
        if address != packet.src_ip or not is_usable_ip(address):
            continue
        hostname = sanitise_hostname(labels[0])
        if hostname is None:
            continue
        observations.append(HostnameSeen(mac, hostname, "mdns"))
        observations.append(AddressSeen(mac, address, "mdns"))
    # Announcements often repeat records; keep each observation once, in order.
    return list(dict.fromkeys(observations))
