# 0003: Validate configuration with pydantic

- **Status:** Accepted
- **Date:** 2026-11-26
- **Decider:** Jake

## Context

Every service reads `/etc/krushnet/krushnet.toml` (parsed with stdlib `tomllib`, ADR 0002) at startup. The values need real validation, not just parsing: IP addresses, ports, URLs, CIDR subnets and paths. Some settings guard hard rules. The portal must not bind to `0.0.0.0` or a public address (rule 3), and upstream DNS must be encrypted (plan decision 3). A config mistake should fail at startup with a clear message that lists every problem, not partway through running.

Dependencies are added only when first used (decided in the scaffold PR), so this would be the first runtime dependency beyond `dnslib`.

## Options

### Option A: pydantic v2
- Pros: typed, immutable models in little code. Built-in IP, URL and network types. Collects every error with its location (`portal.listen.0`). Rejects unknown keys. FastAPI depends on it, so it arrives in Phase 1 anyway. Includes a mypy plugin.
- Cons: an extra dependency now, with a compiled core (`pydantic-core`). Prebuilt wheels exist for Python 3.14 on both machines.

### Option B: stdlib dataclasses + hand-written validation
- Pros: no new dependency.
- Cons: about 200 more lines of type checking, conversion and error collection to write, test and review. That custom code would itself parse untrusted-ish input.

## Decision

Option A: pydantic v2, in `src/krushnet/config.py`.

## Consequences

- Config is a frozen `Settings` model with one sub-model per TOML section. Unknown keys are errors, and numbers aren't coerced from strings.
- Defaults are development-safe (loopback, unprivileged ports). alfred's file sets the production values.
- Rule 3 and decision 3 are checked when the config is loaded. Changing them needs a code change, not just a config edit.
- `krushnet check-config` validates a file before services are restarted.
- The pydantic mypy plugin is enabled, and `krushnet.config` is type-checked strictly.
- Later phases add fields to their own sections. `tests/test_config.py` loads `config.example.toml`, so the example can't drift from the code.
