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

Database (SQLite) commands read the database path from the config file:

```bash
KRUSHNET_CONFIG=./dev.toml uv run krushnet migrate      # create / upgrade the schema
KRUSHNET_CONFIG=./dev.toml uv run krushnet db-status    # is the schema up to date?
# after changing src/krushnet/db/models.py, generate and then review a migration:
KRUSHNET_CONFIG=./dev.toml uv run alembic revision --autogenerate -m "describe change"
```

`dev.toml` is your local config (git-ignored). For example, copy `config.example.toml` and set `[database] path` to a file under this directory.

During development, run the resolver on an unprivileged port (e.g. `5300`) and the portal on `127.0.0.1:8000`. Port 53 and raw sockets are for alfred only.
