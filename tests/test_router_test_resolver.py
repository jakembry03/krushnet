"""Tests for the Phase 0 throwaway resolver (scripts/router_test_resolver.py).

The script isn't part of the package, so it's loaded from its path. Async
tests use asyncio.run so they don't need pytest-asyncio before the scaffold.
"""

from __future__ import annotations

import argparse
import asyncio
import collections
import importlib.util
import sys
from pathlib import Path

import pytest
from dnslib import QTYPE, RCODE, RR, A, DNSRecord

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "router_test_resolver.py"
_spec = importlib.util.spec_from_file_location("router_test_resolver", SCRIPT)
assert _spec is not None and _spec.loader is not None
rtr = importlib.util.module_from_spec(_spec)
sys.modules["router_test_resolver"] = rtr
_spec.loader.exec_module(rtr)


def make_query(name: str = "example.com", qtype: str = "A") -> DNSRecord:
    return DNSRecord.question(name, qtype)


# --- parse_query: untrusted input -------------------------------------------


def test_parse_valid_query() -> None:
    query = rtr.parse_query(bytes(make_query("example.com", "AAAA").pack()))
    assert query is not None
    assert query.qname == "example.com."
    assert query.qtype == "AAAA"


@pytest.mark.parametrize(
    "data",
    [
        b"",
        b"\x00" * 11,  # shorter than a DNS header
        b"\xff" * 5000,  # over the size cap
        b"\x12\x34\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00\x07examp",  # truncated name
        b"\x12\x34\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00\xc0\x0c\x00\x01\x00\x01",  # ptr loop
    ],
)
def test_parse_rejects_malformed(data: bytes) -> None:
    assert rtr.parse_query(data) is None


def test_parse_rejects_truncated_valid_query() -> None:
    packed = bytes(make_query().pack())
    for cut in range(len(packed)):
        assert rtr.parse_query(packed[:cut]) is None, f"accepted {cut}-byte prefix"


def test_parse_rejects_responses() -> None:
    response = make_query().reply()
    assert rtr.parse_query(bytes(response.pack())) is None


def test_parse_rejects_multiple_questions() -> None:
    query = make_query()
    query.add_question(make_query("example.org").questions[0])
    assert rtr.parse_query(bytes(query.pack())) is None


def test_safe_name_escapes_control_chars_and_caps_length() -> None:
    assert rtr.safe_name("bad\x1b[31m.com") == "bad\\x1b[31m.com"
    assert len(rtr.safe_name("a" * 1000)) == rtr.MAX_LOGGED_NAME


# --- upstream reply validation ----------------------------------------------


def test_matching_response_accepted() -> None:
    query = make_query()
    assert rtr.is_matching_response(query, bytes(query.reply().pack()))


def test_response_with_wrong_id_rejected() -> None:
    query = make_query()
    reply = query.reply()
    reply.header.id = (query.header.id + 1) % 65536
    assert not rtr.is_matching_response(query, bytes(reply.pack()))


def test_response_for_other_question_rejected() -> None:
    query = make_query("example.com")
    other = make_query("evil.example")
    other.header.id = query.header.id
    assert not rtr.is_matching_response(query, bytes(other.reply().pack()))


def test_servfail_keeps_id_and_question() -> None:
    query = make_query()
    reply = DNSRecord.parse(rtr.servfail(query))
    assert reply.header.id == query.header.id
    assert reply.header.rcode == RCODE.SERVFAIL
    assert reply.questions == query.questions


# --- CLI helpers --------------------------------------------------------------


def test_parse_host_port() -> None:
    assert rtr.parse_host_port("192.168.1.50:53") == ("192.168.1.50", 53)
    assert rtr.parse_host_port("[::1]:5300") == ("::1", 5300)
    for bad in ("nope", ":53", "host:", "host:99999", "host:abc"):
        with pytest.raises(argparse.ArgumentTypeError):
            rtr.parse_host_port(bad)


def test_summary_lists_sources_by_count() -> None:
    summary = rtr.format_summary(
        collections.Counter({"192.168.1.1": 9, "192.168.1.20": 2})
    )
    assert summary.index("192.168.1.1 ") < summary.index("192.168.1.20")


# --- end to end over loopback -------------------------------------------------


class FakeUpstream(asyncio.DatagramProtocol):
    """Answers every A query with 203.0.113.7, or stays silent if mute."""

    def __init__(self, mute: bool = False) -> None:
        self.mute = mute
        self.transport: asyncio.DatagramTransport | None = None

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        assert isinstance(transport, asyncio.DatagramTransport)
        self.transport = transport

    def datagram_received(self, data: bytes, addr: tuple[str | int, ...]) -> None:
        if self.mute or self.transport is None:
            return
        reply = DNSRecord.parse(data).reply()
        reply.add_answer(RR(reply.q.qname, QTYPE.A, rdata=A("203.0.113.7"), ttl=60))
        self.transport.sendto(bytes(reply.pack()), addr)


class Client(asyncio.DatagramProtocol):
    def __init__(self) -> None:
        self.reply: asyncio.Future[bytes] = asyncio.get_running_loop().create_future()

    def datagram_received(self, data: bytes, addr: tuple[str | int, ...]) -> None:
        if not self.reply.done():
            self.reply.set_result(data)


async def round_trip(
    mute_upstream: bool,
) -> tuple[DNSRecord, DNSRecord, collections.Counter[str]]:
    loop = asyncio.get_running_loop()
    up_transport, _ = await loop.create_datagram_endpoint(
        lambda: FakeUpstream(mute=mute_upstream), local_addr=("127.0.0.1", 0)
    )
    upstream_addr = up_transport.get_extra_info("sockname")[:2]
    res_transport, resolver = await loop.create_datagram_endpoint(
        lambda: rtr.ResolverProtocol(upstream_addr, timeout=0.3),
        local_addr=("127.0.0.1", 0),
    )
    resolver_addr = res_transport.get_extra_info("sockname")[:2]
    client_transport, client = await loop.create_datagram_endpoint(
        Client, remote_addr=resolver_addr
    )
    try:
        client_transport.sendto(b"garbage")  # must be dropped without breaking anything
        query = make_query("example.com")
        client_transport.sendto(bytes(query.pack()))
        reply = DNSRecord.parse(await asyncio.wait_for(client.reply, 2))
        return query, reply, resolver.counts
    finally:
        client_transport.close()
        res_transport.close()
        up_transport.close()


def test_forwards_and_relays_answer() -> None:
    query, reply, counts = asyncio.run(round_trip(mute_upstream=False))
    assert reply.header.id == query.header.id
    assert str(reply.rr[0].rdata) == "203.0.113.7"
    assert counts == {"127.0.0.1": 1}


def test_upstream_timeout_returns_servfail() -> None:
    query, reply, _ = asyncio.run(round_trip(mute_upstream=True))
    assert reply.header.id == query.header.id
    assert reply.header.rcode == RCODE.SERVFAIL
