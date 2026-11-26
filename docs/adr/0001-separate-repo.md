# 0001: Krushnet lives in its own private repo

- **Status:** Accepted
- **Date:** 2026-11-25
- **Decider:** Jake

## Context

Krushnet shares a domain with krushcomics.com (the portal is served at `net.krushcomics.com`), so it could have gone into the krushcomics.com codebase. But Krushnet is a different kind of software: it runs on alfred, handles untrusted network input, and stores per-device domain logs for everyone in the apartment.

## Options

### Option A: Part of the krushcomics.com codebase
- Pros: one repo to manage.
- Cons: mixes a public website with private network tooling. Deploys, dependencies and access are coupled. A leak or mistake in one affects the other.

### Option B: Separate private `krushnet` repo
- Pros: separate deploy (`git pull` on alfred), separate dependencies, and the repo can stay private. History and reviews stay focused.
- Cons: a second repo to maintain.

## Decision

Option B. Krushnet is a separate, private repository. The only link to krushcomics.com is the internal hostname `net.krushcomics.com`, which resolves only inside the home network and over WireGuard (split-horizon DNS served by Krushnet).

## Consequences

- No shared code with krushcomics.com. If something needs sharing later, it gets copied or packaged deliberately.
- The future endpoint/EDR product ("KrushNet - Endpoint" / "Stoneward") also gets its own repo, not this one.
- The HTTPS certificate for `net.krushcomics.com` still depends on the krushcomics.com DNS provider (DNS-01 challenge). That is an operational link, not a code link.
