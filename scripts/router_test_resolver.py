# /// script
# requires-python = ">=3.14"
# dependencies = ["dnslib>=0.9.24"]
# ///
"""Throwaway DNS forwarder for the Phase 0 router test.

Answers the question: does the Spectrum router hand clients alfred's IP as
their DNS server (queries arrive from each client's own IP), or does it
proxy them (every query arrives from the router's IP)?

It logs the source IP, name and type of each query, forwards the query to a
plain-UDP upstream and relays the answer. When stopped (Ctrl-C), it prints
how many queries came from each source IP.

This is NOT the Krushnet resolver. Deliberate shortcuts for a few minutes of
testing:
  * the upstream is plain UDP (Quad9 by default), not DNS-over-HTTPS;
  * no cache, no TCP, no policy, no database.
Delete it once the router test is recorded in docs/plan.md.
"""

from __future__ import annotations

import argparse
import asyncio
import collections
import signal
import sys
import time
from dataclasses import dataclass

from dnslib import QTYPE, RCODE, DNSError, DNSRecord

# A DNS header is 12 bytes, so anything shorter can't be a query.
MIN_MESSAGE_SIZE = 12
# Queries are tiny. Anything bigger than the largest common EDNS buffer is junk.
MAX_MESSAGE_SIZE = 4096
# Caps concurrent upstream lookups so a flood can't open unlimited sockets.
MAX_IN_FLIGHT = 256
# Longest DNS name is 253 characters; leave room for escapes in the log.
MAX_LOGGED_NAME = 300


@dataclass(frozen=True)
class Query:
    """The parts of a client query we need: the parsed record and what to log."""

    record: DNSRecord
    qname: str
    qtype: str


def parse_query(data: bytes) -> Query | None:
    """Parse a client datagram. Returns None for anything that isn't a sane query.

    All network input is untrusted, so every failure mode ends in None rather
    than an exception.
    """
    if not MIN_MESSAGE_SIZE <= len(data) <= MAX_MESSAGE_SIZE:
        return None
    try:
        record = DNSRecord.parse(data)
    except DNSError, ValueError, IndexError, UnicodeError:
        # dnslib raises several exception types on malformed input.
        return None
    # A response (QR=1) sent to us, or a query without exactly one question,
    # isn't something a normal client sends.
    if record.header.qr != 0 or len(record.questions) != 1:
        return None
    question = record.questions[0]
    qtype = QTYPE.get(question.qtype, f"TYPE{question.qtype}")
    return Query(record=record, qname=safe_name(str(question.qname)), qtype=str(qtype))


def safe_name(name: str) -> str:
    """Make a query name safe to print: escape control/non-ASCII chars, cap length."""
    escaped = "".join(
        ch if ch.isascii() and ch.isprintable() else f"\\x{ord(ch):02x}" for ch in name
    )
    return escaped[:MAX_LOGGED_NAME]


def is_matching_response(query: DNSRecord, data: bytes) -> bool:
    """Check an upstream reply really answers our query (same ID and question)."""
    if not MIN_MESSAGE_SIZE <= len(data) <= MAX_MESSAGE_SIZE:
        return False
    try:
        response = DNSRecord.parse(data)
    except DNSError, ValueError, IndexError, UnicodeError:
        return False
    return bool(
        response.header.qr == 1
        and response.header.id == query.header.id
        and response.questions == query.questions
    )


def servfail(query: DNSRecord) -> bytes:
    """Build a SERVFAIL reply so the client fails fast instead of timing out."""
    reply = query.reply()
    reply.header.rcode = RCODE.SERVFAIL
    return bytes(reply.pack())


def format_log_line(src_ip: str, query: Query, outcome: str) -> str:
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    return f"{stamp}  {src_ip:<39}  {query.qtype:<6}  {query.qname}  [{outcome}]"


class _UpstreamProtocol(asyncio.DatagramProtocol):
    """One-shot UDP client: resolves a future with the first matching reply."""

    def __init__(self, query: DNSRecord, result: asyncio.Future[bytes]) -> None:
        self._query = query
        self._result = result

    def datagram_received(self, data: bytes, addr: tuple[str | int, ...]) -> None:
        # Ignore stray or spoofed packets; keep waiting until the timeout.
        if not self._result.done() and is_matching_response(self._query, data):
            self._result.set_result(data)

    def error_received(self, exc: Exception) -> None:
        if not self._result.done():
            self._result.set_exception(exc)


async def forward(query: DNSRecord, raw: bytes, upstream: tuple[str, int], timeout: float) -> bytes:
    """Send the client's query upstream and return the reply bytes.

    A fresh socket per query gives each lookup a random source port, which
    makes spoofed upstream replies harder.
    """
    loop = asyncio.get_running_loop()
    result: asyncio.Future[bytes] = loop.create_future()
    transport, _ = await loop.create_datagram_endpoint(
        lambda: _UpstreamProtocol(query, result), remote_addr=upstream
    )
    try:
        transport.sendto(raw)
        return await asyncio.wait_for(result, timeout)
    finally:
        transport.close()


class ResolverProtocol(asyncio.DatagramProtocol):
    """Listens for client queries, logs them and forwards them upstream."""

    def __init__(self, upstream: tuple[str, int], timeout: float) -> None:
        self.upstream = upstream
        self.timeout = timeout
        self.counts: collections.Counter[str] = collections.Counter()
        self._transport: asyncio.DatagramTransport | None = None
        self._in_flight = 0
        self._tasks: set[asyncio.Task[None]] = set()

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        # Always true for a datagram endpoint; checked explicitly, not with
        # assert, so it still holds under `python -O`.
        if not isinstance(transport, asyncio.DatagramTransport):
            raise TypeError(f"expected a datagram transport, got {type(transport).__name__}")
        self._transport = transport

    def datagram_received(self, data: bytes, addr: tuple[str | int, ...]) -> None:
        src_ip = str(addr[0])
        query = parse_query(data)
        if query is None:
            # Don't log the payload: it's untrusted and could be anything.
            print(
                f"dropped malformed packet ({len(data)} bytes) from {src_ip}",
                flush=True,
            )
            return
        self.counts[src_ip] += 1
        if self._in_flight >= MAX_IN_FLIGHT:
            print(format_log_line(src_ip, query, "dropped: busy"), flush=True)
            return
        self._in_flight += 1
        task = asyncio.create_task(self._answer(data, query, addr))
        # Keep a reference so the task isn't garbage-collected mid-flight.
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _answer(self, raw: bytes, query: Query, addr: tuple[str | int, ...]) -> None:
        src_ip = str(addr[0])
        try:
            reply = await forward(query.record, raw, self.upstream, self.timeout)
            outcome = "ok"
        except (TimeoutError, OSError) as exc:
            reply = servfail(query.record)
            outcome = f"servfail: {type(exc).__name__}"
        finally:
            self._in_flight -= 1
        print(format_log_line(src_ip, query, outcome), flush=True)
        if self._transport is not None:
            self._transport.sendto(reply, addr)


def format_summary(counts: collections.Counter[str]) -> str:
    lines = ["", "Queries per source IP:"]
    if not counts:
        lines.append("  (none received)")
    for ip, count in counts.most_common():
        lines.append(f"  {ip:<39}  {count}")
    lines.append(
        "One IP that is the router's (e.g. 192.168.1.1) => router PROXIES DNS.\n"
        "Each client's own IP => router hands out alfred directly."
    )
    return "\n".join(lines)


def parse_host_port(value: str) -> tuple[str, int]:
    """Parse 'host:port' or '[v6addr]:port' for argparse."""
    host, sep, port_text = value.rpartition(":")
    if not sep or not host or not port_text.isdigit():
        raise argparse.ArgumentTypeError(f"expected HOST:PORT, got {value!r}")
    port = int(port_text)
    if not 0 < port < 65536:
        raise argparse.ArgumentTypeError(f"port out of range: {port}")
    return host.strip("[]"), port


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0] if __doc__ else None)
    parser.add_argument(
        "--listen",
        type=parse_host_port,
        default=("127.0.0.1", 5300),
        help="address to listen on (default 127.0.0.1:5300; on alfred use <LAN-IP>:53)",
    )
    parser.add_argument(
        "--upstream",
        type=parse_host_port,
        default=("9.9.9.9", 53),
        help="plain-UDP upstream resolver (default Quad9, 9.9.9.9:53)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=3.0,
        help="upstream timeout in seconds (default 3)",
    )
    return parser.parse_args(argv)


async def serve(args: argparse.Namespace) -> collections.Counter[str]:
    loop = asyncio.get_running_loop()
    transport, protocol = await loop.create_datagram_endpoint(
        lambda: ResolverProtocol(args.upstream, args.timeout), local_addr=args.listen
    )
    stop = asyncio.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)
    host, port = args.listen
    print(f"listening on {host}:{port}, forwarding to {args.upstream[0]}:{args.upstream[1]}")
    print("Ctrl-C to stop and print the per-source summary.", flush=True)
    try:
        await stop.wait()
    finally:
        transport.close()
    return protocol.counts


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    counts = asyncio.run(serve(args))
    print(format_summary(counts))
    return 0


if __name__ == "__main__":
    sys.exit(main())
