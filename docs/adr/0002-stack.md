# 0002: Technology stack

- **Status:** Accepted
- **Date:** 2026-11-25
- **Decider:** Jake

## Context

Krushnet needs a DNS resolver, a device discovery service and a web portal. It runs on one modest home server (alfred), is developed on Jake's Arch laptop, and every diff gets reviewed by Jake. So the stack should be small, readable and in one language. The hard rules in `CLAUDE.md` (no root, no traffic content, non-blocking DNS hot path, untrusted input) also constrain the choices.

## Decision

| Area | Choice | Why |
|---|---|---|
| Language | Python 3.12+ | One language for all three services. Good libraries for DNS, packet parsing and web. Performance is enough for one apartment |
| Tooling | `uv` | Fast, single tool for dependencies, lockfile, virtualenv and running tools |
| DNS wire format | `dnslib` | Pure Python, small, handles parsing and building packets. We write the asyncio UDP/TCP server ourselves so we control timeouts and the hot path |
| Upstream DNS | Encrypted forwarding, DNS-over-HTTPS to Quad9 by default; provider list configurable | Keeps queries private from the ISP. Avoids running a recursive resolver in v1 |
| HTTP client | `httpx` with HTTP/2 | Async, supports HTTP/2 for DoH connection reuse |
| Discovery | `scapy` | ARP scans and passive ARP/mDNS/DHCP parsing. Needs only `CAP_NET_RAW` |
| Portal | FastAPI + Jinja2 + htmx | Server-rendered pages with small dynamic updates. No JS build step to maintain |
| Database | SQLite (WAL) + SQLAlchemy 2.x + Alembic | No database server to run. WAL allows concurrent readers alongside one writer. Alembic gives reviewed, versioned schema changes |
| Auth | `argon2-cffi`, server-side sessions, CSRF protection | Strong password hashing. Sessions can be revoked server-side |
| Config | TOML via stdlib `tomllib` | No extra dependency. Secrets stay in `/etc/krushnet/` on alfred |
| Tests | `pytest`, `pytest-asyncio` | Standard; async support for the resolver |
| Lint / types | `ruff`, `mypy` (strict on `dns/` and `policy/`) | Strict typing where correctness matters most |
| Deploy | `git pull` on alfred + one systemd unit per service | Simple. Per-service capabilities and sandboxing through systemd |

## Alternatives considered (briefly)

- **Existing filters (Pi-hole, AdGuard Home, Blocky):** would cover DNS filtering quickly, but not the device inventory and per-device views in one app, and Jake wants to own and understand the code.
- **Go or Rust:** faster and single-binary, but slower to iterate on and review for this project's size.
- **PostgreSQL:** more capable, but a server to run and back up for data that fits in SQLite.
- **SPA frontend (React etc.):** adds a JS build pipeline for little gain over htmx.

## Consequences

- Python's per-query overhead is fine for one apartment. If it ever isn't, the cache and policy engine are the parts to optimise first.
- SQLite has a single writer at a time. Three services write to it, so connections need a `busy_timeout`, and DNS query logging is batched by a background writer (hard rule 5).
- New dependencies need a stated reason in the PR. Bigger changes to this stack need a new ADR.
