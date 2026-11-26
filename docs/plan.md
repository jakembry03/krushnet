# Krushnet — Plan

_Last updated: 2026-11-25_
_Status: Phase 0 in progress_

## Vision

Krushnet is a self-hosted network monitoring and filtering app for Jake's apartment network. It runs on alfred.

- **v1:** see every device on the network, and filter DNS with allowlists, blocklists and a per-device domain log, all managed from a web portal at `net.krushcomics.com`. That name resolves only inside the home network and over WireGuard.
- **Later (optional):** gateway mode, where Krushnet (or a router Jake owns) takes over DHCP, NAT and the firewall.
- **Long term, separate product:** endpoint monitoring / EDR for personal devices. Working names: "KrushNet - Endpoint" or "Stoneward". **Out of scope for this repo.**

### In scope

- Device discovery and inventory
- DNS filtering and logging
- Web portal
- Internal-only hostname with HTTPS

### Out of scope (decided)

- Packet inspection or reading traffic content
- TLS decryption or MITM
- Endpoint agents
- Public internet exposure of the portal

### Privacy agreement

Everyone on the network has agreed to domain-level visibility. Krushnet logs **domains, devices and timestamps only, never content.**

---

## Decisions

| # | Decision | Choice |
|---|---|---|
| 1 | Repo | Separate `krushnet` repo, private; not part of the krushcomics.com codebase |
| 2 | DNS wire format | `dnslib` |
| 3 | Upstream DNS | Encrypted forwarding (DoH, default Quad9; configurable) |
| 4 | Portal | FastAPI + Jinja2 + htmx |
| 5 | Tooling | `uv` |
| 6 | Database | SQLite (WAL) + SQLAlchemy + Alembic |
| 7 | Portal access | LAN + WireGuard only; `net.krushcomics.com` via split-horizon DNS served by Krushnet itself |

Full stack and rules are in `CLAUDE.md`. New decisions get an ADR in `docs/adr/`.

---

## Network facts (apartment)

| Item | Detail |
|---|---|
| ISP | Spectrum |
| Modem | Spectrum ET2251 (DOCSIS 3.1, modem only) |
| Router | Spectrum SBE1V1R, managed only through the My Spectrum app |
| Krushnet host | alfred: HP EliteBook 840 G6, Ubuntu Server LTS, wired through a USB Ethernet adapter (to the router or a switch). Also runs WireGuard |
| Dev machine | Jake's laptop (Arch Linux) |

**Known router constraints:**
- The app has **Advanced Settings → DNS Server → Manage DNS**.
- There's no DHCP range control and no way to turn DHCP off.
- IP reservation reportedly exists.

**Unknowns, resolved in Phase 0:**

1. **Does the router give clients alfred's IP as their DNS server, or proxy queries itself?**
   - *Direct:* the router hands out alfred's IP, so per-device attribution works router-wide.
   - *Proxied:* the router hands out 192.168.1.1, so every query looks like it came from the router. Fall back to setting DNS manually on the devices that matter, or plan your own router (see Later).
2. **IPv6 DNS:** can it be set, and do clients receive the router's IPv6 DNS? If they do, IPv6 lookups bypass Krushnet.
3. **Reservation:** can alfred get a reserved IP?
4. **DNS host for krushcomics.com:** where is its DNS hosted, and does that provider have an API supported by certbot or acme.sh? This is needed for HTTPS via the Let's Encrypt DNS-01 challenge.

---

## Architecture

```
[devices] --DNS :53--> [krushnet-dns] --DoH--> [Quad9 / configured upstream]
                           |   \
                           |    `--> in-memory queue --> [log writer] --> SQLite
                        [policy engine] <-- lists & rules -- SQLite
                                                              ^
[krushnet-discovery] -- ARP scan + passive ARP/mDNS/DHCP --> SQLite (devices)
                                                              ^
[krushnet-portal] (FastAPI + htmx, LAN/WireGuard only) -------'
```

**Services** (each is a separate systemd unit running as the `krushnet` user):

| Service | Job | Capability |
|---|---|---|
| `krushnet-dns` | asyncio UDP+TCP resolver: policy check → cache → encrypted upstream → async logging | `CAP_NET_BIND_SERVICE` |
| `krushnet-discovery` | Active ARP sweeps, passive listening (ARP, mDNS, DHCP option 12 hostnames), OUI vendor lookup, randomized-MAC flag | `CAP_NET_RAW` |
| `krushnet-portal` | Web UI: devices, query log, lists, rules, settings | none |

**Policy evaluation order:** per-device allow → per-device block → global allow → global block → resolve.
**Device attribution:** the client IP is mapped to a device through discovery data (IP → MAC → device record). If the router proxies DNS, attribution falls back to "router" for devices whose DNS isn't set manually.

---

## Phase 0: Setup and router test

**Jake (hands-on):**
- [ ] Buy a USB 3 / USB-C gigabit Ethernet adapter for alfred. An unmanaged switch is optional.
- [ ] Wire alfred in and reserve its IP in the My Spectrum app.
- [ ] Create the private `krushnet` repo. Add `CLAUDE.md` and this plan.
- [ ] **Router DNS test.** Run a throwaway resolver on alfred, set it as the router's DNS in the app, reconnect a client, and check which DNS server the client got:
  - Linux: `resolvectl status`
  - Windows: `ipconfig /all`
  - Phone: Wi-Fi details

  Record **direct** or **proxied** below.
- [ ] Check whether IPv6 DNS can be set in the app, and whether clients receive IPv6 DNS servers.
- [ ] Find out where krushcomics.com's DNS is hosted and whether it has an API.
- [ ] Run tcpdump or Wireshark on alfred for an evening. Note which broadcasts are visible (ARP, mDNS, DHCP).

**Claude Code:**
- [x] Scaffold the repo: `pyproject.toml` with uv, ruff/mypy/pytest config, the package skeleton from `CLAUDE.md`, and `config.example.toml`.
- [x] Config loader (TOML → typed settings object) with tests. Uses pydantic (ADR 0003); `krushnet check-config` validates a file.
- [x] DB setup: SQLAlchemy models (devices, queries, lists, list entries, rules, users) + first Alembic migration. Propose the schema to Jake first. Schema and decisions in ADR 0004 (one group per device, one `rules` table for hand-made entries, integer-ms UTC timestamps, explicit `krushnet migrate`).
- [x] `docs/adr/0001-separate-repo.md` and `0002-stack.md`, recording the decisions above.
- [x] A minimal throwaway resolver script for the router test (`scripts/router_test_resolver.py`; run steps in `scripts/README.md`): logs each query's source IP and forwards it upstream.

**Phase 0 results** (fill in):
- Router DNS behavior: _TBD_
- IPv6 DNS: _TBD_
- alfred reserved IP: _TBD_
- DNS host / API for krushcomics.com: _TBD_

**Exit:** the repo is scaffolded, the router's behavior is known, and the attribution strategy is chosen.

---

## Phase 1: Inventory (read-only)

- [ ] Discovery: periodic ARP sweep of the LAN subnet (configurable interval).
- [ ] Discovery: passive listeners for ARP, mDNS and DHCP. Pull hostnames from DHCP option 12 and mDNS.
- [ ] OUI vendor lookup from a bundled, updatable OUI file. Flag randomized MACs using the locally administered bit.
- [ ] Device records:
  - MAC, current IP, hostname, vendor
  - First-seen and last-seen times
  - Randomized flag
  - User-set name and owner, plus tags/groups
- [ ] Merge logic: the same MAC means the same device. Update IP and hostname history.
- [ ] Portal: login (Argon2, sessions, CSRF), a CLI command to create the first user, a device list (online/offline, last seen) and a device detail page with edit for name, owner and group.
- [ ] New-device alert: a portal banner and a log entry.
- [ ] systemd units for `krushnet-discovery` and `krushnet-portal` in `deploy/systemd/`, for Jake to install.

**Exit:** every device in the apartment appears within a few minutes of connecting and can be named in the portal.

---

## Phase 2: DNS filtering

- [ ] Resolver: asyncio UDP + TCP on a configurable port, parsing and building with dnslib, handling malformed packets safely.
- [ ] Upstream: DoH client (httpx, HTTP/2) with a configurable provider list, timeouts and failover between providers.
- [ ] Cache that respects each record's TTL, with a size limit and negative caching.
- [ ] Policy engine: global allow/block lists, per-device and per-group rules, wildcard/subdomain matching, allow taking priority over block. Thorough unit tests.
- [ ] Blocklist import (hosts-file and plain domain-list formats) from a URL or file, with a scheduled refresh.
- [ ] Block response is configurable: `0.0.0.0` / `::` or NXDOMAIN.
- [ ] Answer NXDOMAIN for `use-application-dns.net`, the Firefox DoH canary domain.
- [ ] Split-horizon: answer `net.krushcomics.com` (configurable) with alfred's LAN IP.
- [ ] Query logging: in-memory queue → batched background writer. Retention is configurable (default 30 days) with nightly pruning.
- [ ] Portal pages:
  - Query log with filters (device, domain, blocked/allowed, time range).
  - Top domains per device.
  - List and rule management.
  - One-click block or allow from a log entry.
- [ ] Health endpoint, plus `Restart=on-failure` in the systemd units.
- [ ] HTTPS for the portal: a Let's Encrypt certificate through the DNS-01 challenge (depends on Phase 0 item 4). Fall back to a self-signed certificate if needed.
- [ ] Rollout:
  1. Set DNS manually on Jake's own devices and run for 1 week.
  2. Set the router's DNS (both entries) to alfred.
  3. Watch for 2 weeks.

**Exit:** the whole apartment resolves through Krushnet for 2 or more weeks with no noticeable problems, and Jake can see and control which domains each device uses.

### v1 = Phases 0–2 complete

---

## Availability

- If alfred is down, the apartment has no DNS, and so no internet. Mitigations:
  - The laptop battery acts as a built-in UPS.
  - systemd auto-restarts the services.
  - The health endpoint.
- **Panic button:** in the My Spectrum app, set DNS back to "Use Spectrum DNS". Keep this written down at home.
- Both router DNS entries point to alfred, accepting the panic button as the fallback. A public secondary resolver would let some queries skip Krushnet unfiltered.

---

## Later (not v1)

- **Gateway mode:** Krushnet, or a router Jake owns running OpenWrt, takes over DHCP, NAT and the firewall, with the Spectrum router retired or used as an access point. This gives:
  - Full DHCP control.
  - Forced DNS (redirect port 53, block known DoH endpoints).
  - Per-device connection stats and IP-level blocking.

  It's also the fix if the router proxies DNS.
- Push notifications for new devices.
- Scheduled policies, such as time-based blocks.
- Optional local recursive resolver (unbound) as an upstream choice.
- Endpoint/EDR product: separate repo, separate plan.
