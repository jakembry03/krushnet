"""DNS resolver service: asyncio UDP/TCP server, cache and encrypted upstream client.

The hot path never waits on disk I/O (hard rule 5): query logging goes through
an in-memory queue to a background writer. Type-checked with mypy --strict.
"""
