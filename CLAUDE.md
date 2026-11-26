# CLAUDE.md — Krushnet

Krushnet is a self-hosted DNS filtering and network-monitoring app for Jake's apartment network. It runs on **alfred**, a home server (HP EliteBook 840 G6, Ubuntu Server LTS, wired to the Spectrum router). Read `docs/plan.md` for scope, phases and current status before starting any task.

## Roles

- **Jake owns every technical decision and the final review.** You do most of the implementation.
- When a task involves a real design choice (new dependency, schema change, new service, security trade-off), **stop and propose options with trade-offs**. Don't pick one silently. Record accepted decisions as an ADR in `docs/adr/`.
- Jake reviews every diff. Write code he can read: clear names, small functions, comments on *why* rather than *what*. Explain anything non-obvious in the PR description.

## Hard rules (never break these)

1. **No traffic content.** Krushnet logs domains, devices and timestamps. It never captures, stores or inspects packet payloads beyond what's needed to parse DNS, ARP, mDNS and DHCP.
2. **No root.** Each service runs as the `krushnet` system user with only the Linux capabilities it needs:
   - DNS service: `CAP_NET_BIND_SERVICE`
   - Discovery service: `CAP_NET_RAW`
   - Portal: no extra capabilities
3. **The portal is never exposed to the internet.** It binds to the LAN interface and the WireGuard interface only. Don't add port forwarding, tunnels or public DNS records.
4. **All network input is untrusted.** Validate lengths and types, and handle malformed packets without crashing. Never use `eval`/`exec`, never build shell commands from input, and always use parameterized SQL.
5. **The DNS hot path never blocks.** Resolving a query must not wait on disk I/O. Query logging goes through an in-memory queue to a background writer.
6. **No secrets in the repo.** Config with secrets lives in `/etc/krushnet/` on alfred. The repo only holds `config.example.toml`.
7. **Never run `sudo` or change system config** (systemd units, network settings, `/etc`) without asking Jake first. Provide the commands or files for him to apply.

## Stack

| Area | Choice |
|---|---|
| Language | Python 3.12+ |
| Project tooling | `uv` (dependencies, lockfile, virtualenv, running tools) |
| DNS | `dnslib` for wire format; asyncio UDP + TCP server |
| Upstream DNS | Encrypted forwarding; default DNS-over-HTTPS to Quad9, with the provider list configurable |
| HTTP client | `httpx` (HTTP/2 for DoH) |
| Discovery | `scapy` (ARP scan, passive ARP/mDNS/DHCP listening) |
| Web portal | FastAPI + Jinja2 templates + htmx. No JS build step |
| Database | SQLite in WAL mode, accessed through SQLAlchemy 2.x, with Alembic for migrations |
| Auth | Argon2 password hashing (`argon2-cffi`), server-side sessions, CSRF protection |
| Config | TOML (`/etc/krushnet/krushnet.toml`, using `tomllib`) |
| Tests | `pytest`, `pytest-asyncio` |
| Lint / types | `ruff` (lint + format), `mypy` (strict on `policy/` and `dns/`) |
| Deploy | `git pull` on alfred + systemd units (one per service) |

Don't add a dependency without explaining in the PR why it's needed and what the alternative was.

## Intended layout

These are starting proposals; changes go through an ADR.

```
krushnet/
├── CLAUDE.md
├── README.md
├── pyproject.toml
├── uv.lock
├── config.example.toml
├── docs/
│   ├── plan.md
│   └── adr/
├── deploy/
│   └── systemd/            # unit files for Jake to install
├── src/krushnet/
│   ├── config.py
│   ├── db/                 # models, session, migrations (alembic)
│   ├── dns/                # resolver server, upstream client, cache
│   ├── policy/             # allow/block lists, per-device rules, list import
│   ├── discovery/          # ARP scan, passive listeners, OUI lookup
│   ├── portal/             # FastAPI app, routes, templates, static
│   └── cli.py              # admin commands (create user, import list, etc.)
└── tests/
```

## Commands

```bash
uv sync                          # install deps
uv run pytest                    # tests
uv run ruff check . && uv run ruff format --check .
uv run mypy src/krushnet/policy src/krushnet/dns
```

During development on Jake's laptop (Arch), run the resolver on an unprivileged port (e.g. `5300`) and the portal on `127.0.0.1:8000`. Port 53 and raw sockets are for alfred only.

## Workflow

- **Plan first.** For any feature, write a short plan (what, which files, risks, tests) and wait for Jake's go-ahead before writing code.
- **One task per branch, small PRs.** Never commit directly to `main`.
- **Tests are required** for `policy/`, `dns/` (parsing, caching, policy decisions) and anything that handles untrusted input. Write the test first when the behavior is clear.
- **Keep `docs/plan.md` current:** tick off tasks and note anything learned (for example, the router DNS test result).
- **Commit messages:** short imperative subject (`Add TTL-aware DNS cache`), body explains why.
- **Stuck or unsure?** Say so and ask. Don't guess at network behavior; propose a way to test it on the real network instead.
