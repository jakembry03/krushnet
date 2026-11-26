# krushnet

Self-hosted DNS filtering and network monitoring for a home network. It runs on **alfred** and is managed from a LAN/WireGuard-only web portal.

- Scope, phases and status: [`docs/plan.md`](docs/plan.md)
- Rules and conventions for contributors (including Claude Code): [`CLAUDE.md`](CLAUDE.md)
- Decisions: [`docs/adr/`](docs/adr/)

## Development

Requires [uv](https://docs.astral.sh/uv/). uv installs the pinned Python (`.python-version`) if needed.

```bash
uv sync                                                  # install deps into .venv
uv run pytest                                            # tests
uv run ruff check . && uv run ruff format --check .      # lint + format check
uv run mypy                                              # type check (strict on dns/ and policy/)
uv run krushnet --version
```

During development, run the resolver on an unprivileged port (e.g. `5300`) and the portal on `127.0.0.1:8000`. Port 53 and raw sockets are for alfred only.
