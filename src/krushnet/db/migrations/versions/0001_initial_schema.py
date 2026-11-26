"""Initial schema (ADR 0004).

Generated with `alembic revision --autogenerate`, then reviewed.

Revision ID: 0001
Revises:
Create Date: 2026-11-26 08:58:42.951308
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import krushnet.db.types

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "groups",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100, collation="NOCASE"), nullable=False),
        sa.Column("created_at", krushnet.db.types.UtcTimestamp(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_groups")),
        sa.UniqueConstraint("name", name=op.f("uq_groups_name")),
    )
    op.create_table(
        "lists",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column(
            "kind",
            sa.Enum("allow", "block", name="kind", native_enum=False, create_constraint=True),
            nullable=False,
        ),
        sa.Column(
            "source",
            sa.Enum("url", "file", name="source", native_enum=False, create_constraint=True),
            nullable=False,
        ),
        sa.Column("location", sa.Text(), nullable=False),
        sa.Column(
            "format",
            sa.Enum("hosts", "domains", name="format", native_enum=False, create_constraint=True),
            nullable=False,
        ),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("entry_count", sa.Integer(), nullable=False),
        sa.Column("last_refreshed", krushnet.db.types.UtcTimestamp(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", krushnet.db.types.UtcTimestamp(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_lists")),
        sa.UniqueConstraint("name", name=op.f("uq_lists_name")),
    )
    op.create_table(
        "meta",
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("key", name=op.f("pk_meta")),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(length=100, collation="NOCASE"), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("created_at", krushnet.db.types.UtcTimestamp(), nullable=False),
        sa.Column("last_login_at", krushnet.db.types.UtcTimestamp(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("username", name=op.f("uq_users_username")),
    )
    op.create_table(
        "devices",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("mac", sa.String(length=17), nullable=False),
        sa.Column("current_ip", sa.String(length=45), nullable=True),
        sa.Column("hostname", sa.String(length=253), nullable=True),
        sa.Column("vendor", sa.String(length=100), nullable=True),
        sa.Column("is_randomized_mac", sa.Boolean(), nullable=False),
        sa.Column("display_name", sa.String(length=100), nullable=True),
        sa.Column("owner", sa.String(length=100), nullable=True),
        sa.Column("group_id", sa.Integer(), nullable=True),
        sa.Column("acknowledged", sa.Boolean(), nullable=False),
        sa.Column("first_seen", krushnet.db.types.UtcTimestamp(), nullable=False),
        sa.Column("last_seen", krushnet.db.types.UtcTimestamp(), nullable=False),
        sa.CheckConstraint("length(mac) = 17", name=op.f("ck_devices_mac_length")),
        sa.ForeignKeyConstraint(
            ["group_id"],
            ["groups.id"],
            name=op.f("fk_devices_group_id_groups"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_devices")),
        sa.UniqueConstraint("mac", name=op.f("uq_devices_mac")),
    )
    with op.batch_alter_table("devices", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_devices_current_ip"), ["current_ip"], unique=False)
        batch_op.create_index(batch_op.f("ix_devices_group_id"), ["group_id"], unique=False)

    op.create_table(
        "list_entries",
        sa.Column("list_id", sa.Integer(), nullable=False),
        sa.Column("domain", sa.String(length=253), nullable=False),
        sa.ForeignKeyConstraint(
            ["list_id"],
            ["lists.id"],
            name=op.f("fk_list_entries_list_id_lists"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("list_id", "domain", name=op.f("pk_list_entries")),
    )
    with op.batch_alter_table("list_entries", schema=None) as batch_op:
        batch_op.create_index("ix_list_entries_domain", ["domain"], unique=False)

    op.create_table(
        "sessions",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("csrf_token", sa.String(length=64), nullable=False),
        sa.Column("created_at", krushnet.db.types.UtcTimestamp(), nullable=False),
        sa.Column("last_used_at", krushnet.db.types.UtcTimestamp(), nullable=False),
        sa.Column("expires_at", krushnet.db.types.UtcTimestamp(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_sessions_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sessions")),
    )
    with op.batch_alter_table("sessions", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_sessions_expires_at"), ["expires_at"], unique=False)

    op.create_table(
        "device_addresses",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("device_id", sa.Integer(), nullable=False),
        sa.Column("ip", sa.String(length=45), nullable=False),
        sa.Column("first_seen", krushnet.db.types.UtcTimestamp(), nullable=False),
        sa.Column("last_seen", krushnet.db.types.UtcTimestamp(), nullable=False),
        sa.ForeignKeyConstraint(
            ["device_id"],
            ["devices.id"],
            name=op.f("fk_device_addresses_device_id_devices"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_device_addresses")),
    )
    with op.batch_alter_table("device_addresses", schema=None) as batch_op:
        batch_op.create_index("uq_device_addresses_device_id_ip", ["device_id", "ip"], unique=True)

    op.create_table(
        "device_hostnames",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("device_id", sa.Integer(), nullable=False),
        sa.Column("hostname", sa.String(length=253), nullable=False),
        sa.Column(
            "source",
            sa.Enum("dhcp", "mdns", name="source", native_enum=False, create_constraint=True),
            nullable=False,
        ),
        sa.Column("first_seen", krushnet.db.types.UtcTimestamp(), nullable=False),
        sa.Column("last_seen", krushnet.db.types.UtcTimestamp(), nullable=False),
        sa.ForeignKeyConstraint(
            ["device_id"],
            ["devices.id"],
            name=op.f("fk_device_hostnames_device_id_devices"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_device_hostnames")),
    )
    with op.batch_alter_table("device_hostnames", schema=None) as batch_op:
        batch_op.create_index(
            "uq_device_hostnames_device_id_hostname_source",
            ["device_id", "hostname", "source"],
            unique=True,
        )

    op.create_table(
        "events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ts", krushnet.db.types.UtcTimestamp(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("device_id", sa.Integer(), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["device_id"],
            ["devices.id"],
            name=op.f("fk_events_device_id_devices"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_events")),
    )
    with op.batch_alter_table("events", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_events_ts"), ["ts"], unique=False)

    op.create_table(
        "queries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ts", krushnet.db.types.UtcTimestamp(), nullable=False),
        sa.Column("client_ip", sa.String(length=45), nullable=False),
        sa.Column("device_id", sa.Integer(), nullable=True),
        sa.Column("qname", sa.String(length=253), nullable=False),
        sa.Column("qtype", sa.SmallInteger(), nullable=False),
        sa.Column(
            "decision",
            sa.Enum(
                "allowed",
                "blocked",
                "local",
                name="decision",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("reason", sa.String(length=100), nullable=True),
        sa.Column("rcode", sa.SmallInteger(), nullable=True),
        sa.Column("from_cache", sa.Boolean(), nullable=False),
        sa.Column("upstream_ms", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["device_id"],
            ["devices.id"],
            name=op.f("fk_queries_device_id_devices"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_queries")),
    )
    with op.batch_alter_table("queries", schema=None) as batch_op:
        batch_op.create_index("ix_queries_device_id_ts", ["device_id", "ts"], unique=False)
        batch_op.create_index("ix_queries_qname_ts", ["qname", "ts"], unique=False)
        batch_op.create_index("ix_queries_ts", ["ts"], unique=False)

    op.create_table(
        "rules",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "action",
            sa.Enum("allow", "block", name="action", native_enum=False, create_constraint=True),
            nullable=False,
        ),
        sa.Column("domain", sa.String(length=253), nullable=False),
        sa.Column("device_id", sa.Integer(), nullable=True),
        sa.Column("group_id", sa.Integer(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", krushnet.db.types.UtcTimestamp(), nullable=False),
        sa.CheckConstraint(
            "device_id IS NULL OR group_id IS NULL", name=op.f("ck_rules_single_scope")
        ),
        sa.ForeignKeyConstraint(
            ["device_id"],
            ["devices.id"],
            name=op.f("fk_rules_device_id_devices"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["group_id"], ["groups.id"], name=op.f("fk_rules_group_id_groups"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_rules")),
    )
    with op.batch_alter_table("rules", schema=None) as batch_op:
        batch_op.create_index(
            "uq_rules_device_domain",
            ["device_id", "domain"],
            unique=True,
            sqlite_where=sa.text("device_id IS NOT NULL"),
        )
        batch_op.create_index(
            "uq_rules_global_domain",
            ["domain"],
            unique=True,
            sqlite_where=sa.text("device_id IS NULL AND group_id IS NULL"),
        )
        batch_op.create_index(
            "uq_rules_group_domain",
            ["group_id", "domain"],
            unique=True,
            sqlite_where=sa.text("group_id IS NOT NULL"),
        )


def downgrade() -> None:
    with op.batch_alter_table("rules", schema=None) as batch_op:
        batch_op.drop_index("uq_rules_group_domain", sqlite_where=sa.text("group_id IS NOT NULL"))
        batch_op.drop_index(
            "uq_rules_global_domain", sqlite_where=sa.text("device_id IS NULL AND group_id IS NULL")
        )
        batch_op.drop_index("uq_rules_device_domain", sqlite_where=sa.text("device_id IS NOT NULL"))

    op.drop_table("rules")
    with op.batch_alter_table("queries", schema=None) as batch_op:
        batch_op.drop_index("ix_queries_ts")
        batch_op.drop_index("ix_queries_qname_ts")
        batch_op.drop_index("ix_queries_device_id_ts")

    op.drop_table("queries")
    with op.batch_alter_table("events", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_events_ts"))

    op.drop_table("events")
    with op.batch_alter_table("device_hostnames", schema=None) as batch_op:
        batch_op.drop_index("uq_device_hostnames_device_id_hostname_source")

    op.drop_table("device_hostnames")
    with op.batch_alter_table("device_addresses", schema=None) as batch_op:
        batch_op.drop_index("uq_device_addresses_device_id_ip")

    op.drop_table("device_addresses")
    with op.batch_alter_table("sessions", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_sessions_expires_at"))

    op.drop_table("sessions")
    with op.batch_alter_table("list_entries", schema=None) as batch_op:
        batch_op.drop_index("ix_list_entries_domain")

    op.drop_table("list_entries")
    with op.batch_alter_table("devices", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_devices_group_id"))
        batch_op.drop_index(batch_op.f("ix_devices_current_ip"))

    op.drop_table("devices")
    op.drop_table("users")
    op.drop_table("meta")
    op.drop_table("lists")
    op.drop_table("groups")
