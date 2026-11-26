# 0004: Database schema and migrations

- **Status:** Accepted
- **Date:** 2026-11-26
- **Decider:** Jake

## Context

All three services share one SQLite database (ADR 0002). Discovery writes devices. The DNS service reads policy into memory and writes the query log. The portal reads and edits everything. The schema has to support per-device attribution, global, group and device policy, and a query log of up to millions of rows. It also has to respect the hard rules: no traffic content (rule 1) and parameterized SQL only (rule 4).

## Decisions

Jake chose the recommended option for each of these:

1. **One group per device** (`devices.group_id`). Policy stays unambiguous: device rules, then the device's group rules, then global rules. Tags, if wanted later, would be a separate table for labels only.
   - *Rejected:* many-to-many tags. Rules attached to tags can conflict, so the policy engine would need a precedence order between tags.
2. **All hand-made entries go in one `rules` table**, scoped as global (no device or group), group, or device. `lists` and `list_entries` hold only imported lists (from a URL or file).
   - *Rejected:* a special "manual" list for global entries plus scoped rules, which splits hand-made entries across two places.
3. **Timestamps are integer Unix milliseconds**, through the `UtcTimestamp` column type. Python only ever sees timezone-aware UTC datetimes, and naive ones are rejected.
   - *Rejected:* SQLAlchemy's default ISO text, which is about 3 times larger per timestamp and handles timezones by convention only.
4. **Migrations are explicit.** `krushnet migrate` is a deploy step. Services check `db.migrate.is_up_to_date()` at startup and refuse to run if it fails.
   - *Rejected:* automatic upgrades on start, where three services could race and a bad migration would run without anyone choosing to run it.

## Schema

| Table | Purpose | Key points |
|---|---|---|
| `groups` | Device groups | Name unique, case-insensitive |
| `devices` | One row per MAC | `mac` unique, CHECK length 17. `current_ip` indexed for attribution (not unique: DHCP reassignment can briefly overlap). `group_id` `ON DELETE SET NULL`. `acknowledged` drives the new-device banner |
| `device_addresses` | IP history | UNIQUE(device_id, ip). Cascades with the device |
| `device_hostnames` | Hostname history | `source` is `dhcp` or `mdns`. UNIQUE(device_id, hostname, source). Cascades |
| `lists` | Imported allow/block lists | `kind`, `source` (`url`/`file`), `format` (`hosts`/`domains`), refresh status. Network-wide |
| `list_entries` | Domains in a list | PK (list_id, domain), plus an index on `domain` for "which list contains X?". Cascades with the list |
| `rules` | Hand-made allow/block entries | CHECK: not both device and group. Partial unique indexes: one rule per domain per scope |
| `queries` | DNS query log | `device_id` records who the IP belonged to at query time (`SET NULL` on delete). `reason` is a text snapshot, not a foreign key. Indexes on (ts), (device_id, ts) and (qname, ts). **No answer data** (rule 1) |
| `events` | Notable events | Free-text `kind`, so new kinds don't need a migration |
| `users` | Portal users | Username unique, case-insensitive. Argon2 hash |
| `sessions` | Portal sessions | `id` is the SHA-256 of the token, so a copied database gives no working logins. `expires_at` indexed |
| `meta` | Key/value store | How it's used is decided per feature (e.g. policy reload, PR 2.6) |

Conventions:
- MACs are lowercase with colons. Domains are lowercase with no trailing dot. IPs are canonical text.
- Fixed sets of values are TEXT with a CHECK constraint.
- Constraint names follow a naming convention, so Alembic's batch mode can alter SQLite tables later.

Every connection sets `journal_mode=WAL`, `foreign_keys=ON`, `busy_timeout=5000` and `synchronous=NORMAL`. With `synchronous=NORMAL`, a power cut can lose the last few commits but can't corrupt the database.

Database access uses plain (synchronous) SQLAlchemy 2.x, with no async driver. Async code calls it through a worker thread.

## Consequences

- **Deploy steps gain** `krushnet migrate` (run as the `krushnet` user, so it owns the file) before services restart. `krushnet db-status` checks the state without changing anything.
- **Migrations ship inside the package**, at `src/krushnet/db/migrations/`. New ones are generated with `KRUSHNET_CONFIG=<dev config> uv run alembic revision --autogenerate`, then reviewed. A test fails if the models and migrations disagree.
- **Phones with rotating random MACs** appear as new devices each time. That's accepted for v1, and `is_randomized_mac` makes it visible.
- **Query log size** is estimated at up to about 1 GB at 30 days' retention, to be measured during rollout. Retention is configurable.
- **Whether a list entry or rule also matches subdomains** is decided by the policy engine (PR 2.3). Exact-match entries would be a later `match` column.
