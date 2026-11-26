"""SQLAlchemy models: the Krushnet database schema (ADR 0004).

Conventions (see the ADR for the reasons):
  * Timestamps are UtcTimestamp: aware UTC datetimes in Python, integer Unix
    milliseconds in SQLite.
  * MACs are lower case with colons; domains are lower case with no trailing
    dot; IPs are text in canonical `ipaddress` form. Callers normalise before
    writing.
  * Fixed sets of values are short text with a CHECK constraint.
  * Constraint names follow NAMING_CONVENTION so Alembic can alter tables on
    SQLite (which rebuilds the table in "batch mode").
  * The query log stores names, types, devices, times and outcomes only,
    never answer data (hard rule 1).
"""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Any, ClassVar

from sqlalchemy import (
    CheckConstraint,
    Enum,
    ForeignKey,
    Index,
    MetaData,
    SmallInteger,
    String,
    Text,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from krushnet.db.types import UtcTimestamp, utcnow

NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

# Length limits. Generous, but bounded: values may come from the network.
MAC_LENGTH = 17  # aa:bb:cc:dd:ee:ff
IP_LENGTH = 45  # longest textual IPv6 (with embedded IPv4)
DOMAIN_LENGTH = 253
NAME_LENGTH = 100  # human-entered names, labels, hostnames as shown


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    type_annotation_map: ClassVar[dict[Any, Any]] = {datetime: UtcTimestamp()}


def _text_enum(enum_class: type[enum.StrEnum], name: str) -> Enum:
    """Store a StrEnum as its value in a short TEXT column with a CHECK constraint."""
    return Enum(
        enum_class,
        name=name,
        native_enum=False,
        create_constraint=True,
        length=max(len(member.value) for member in enum_class),
        values_callable=lambda members: [member.value for member in members],
    )


class PolicyAction(enum.StrEnum):
    ALLOW = "allow"
    BLOCK = "block"


class ListSource(enum.StrEnum):
    URL = "url"
    FILE = "file"


class ListFormat(enum.StrEnum):
    HOSTS = "hosts"  # "0.0.0.0 example.com" lines
    DOMAINS = "domains"  # one domain per line


class HostnameSource(enum.StrEnum):
    DHCP = "dhcp"  # DHCP option 12
    MDNS = "mdns"


class QueryDecision(enum.StrEnum):
    ALLOWED = "allowed"
    BLOCKED = "blocked"
    LOCAL = "local"  # answered by Krushnet itself: split-horizon, DoH canary


# --- devices -------------------------------------------------------------------


class Group(Base):
    __tablename__ = "groups"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(NAME_LENGTH, collation="NOCASE"), unique=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class Device(Base):
    __tablename__ = "devices"
    __table_args__ = (CheckConstraint(f"length(mac) = {MAC_LENGTH}", name="mac_length"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    mac: Mapped[str] = mapped_column(String(MAC_LENGTH), unique=True)
    # Used to attribute DNS queries to a device. Not unique: after DHCP hands
    # an address to a new device, two rows can briefly share it. The one with
    # the latest last_seen wins.
    current_ip: Mapped[str | None] = mapped_column(String(IP_LENGTH), index=True)
    hostname: Mapped[str | None] = mapped_column(String(DOMAIN_LENGTH))
    vendor: Mapped[str | None] = mapped_column(String(NAME_LENGTH))
    is_randomized_mac: Mapped[bool]
    display_name: Mapped[str | None] = mapped_column(String(NAME_LENGTH))
    owner: Mapped[str | None] = mapped_column(String(NAME_LENGTH))
    group_id: Mapped[int | None] = mapped_column(
        ForeignKey("groups.id", ondelete="SET NULL"), index=True
    )
    # False until Jake has seen the device; drives the new-device banner.
    acknowledged: Mapped[bool] = mapped_column(default=False)
    first_seen: Mapped[datetime]
    last_seen: Mapped[datetime]

    group: Mapped[Group | None] = relationship()
    # passive_deletes: let the database's ON DELETE CASCADE do the work.
    addresses: Mapped[list[DeviceAddress]] = relationship(
        back_populates="device", passive_deletes=True
    )
    hostnames: Mapped[list[DeviceHostname]] = relationship(
        back_populates="device", passive_deletes=True
    )


class DeviceAddress(Base):
    """Every IP a device has been seen with."""

    __tablename__ = "device_addresses"

    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id", ondelete="CASCADE"))
    ip: Mapped[str] = mapped_column(String(IP_LENGTH))
    first_seen: Mapped[datetime]
    last_seen: Mapped[datetime]

    device: Mapped[Device] = relationship(back_populates="addresses")

    __table_args__ = (Index("uq_device_addresses_device_id_ip", "device_id", "ip", unique=True),)


class DeviceHostname(Base):
    """Every hostname a device has announced, and where it came from."""

    __tablename__ = "device_hostnames"

    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id", ondelete="CASCADE"))
    hostname: Mapped[str] = mapped_column(String(DOMAIN_LENGTH))
    source: Mapped[HostnameSource] = mapped_column(_text_enum(HostnameSource, "source"))
    first_seen: Mapped[datetime]
    last_seen: Mapped[datetime]

    device: Mapped[Device] = relationship(back_populates="hostnames")

    __table_args__ = (
        Index(
            "uq_device_hostnames_device_id_hostname_source",
            "device_id",
            "hostname",
            "source",
            unique=True,
        ),
    )


# --- policy --------------------------------------------------------------------


class DomainList(Base):
    """An imported blocklist or allowlist (from a URL or file). Applies network-wide.

    Hand-made entries are Rules, not lists.
    """

    __tablename__ = "lists"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(NAME_LENGTH), unique=True)
    kind: Mapped[PolicyAction] = mapped_column(_text_enum(PolicyAction, "kind"))
    source: Mapped[ListSource] = mapped_column(_text_enum(ListSource, "source"))
    location: Mapped[str] = mapped_column(Text)  # URL or file path
    format: Mapped[ListFormat] = mapped_column(_text_enum(ListFormat, "format"))
    enabled: Mapped[bool] = mapped_column(default=True)
    entry_count: Mapped[int] = mapped_column(default=0)
    last_refreshed: Mapped[datetime | None]
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class DomainListEntry(Base):
    """One domain from an imported list. Lists can hold hundreds of thousands of these.

    Deliberately no relationship() back to DomainList: lazily loading a whole
    list into memory by accident would be expensive.
    """

    __tablename__ = "list_entries"

    list_id: Mapped[int] = mapped_column(
        ForeignKey("lists.id", ondelete="CASCADE"), primary_key=True
    )
    domain: Mapped[str] = mapped_column(String(DOMAIN_LENGTH), primary_key=True)

    # Answers "which lists contain X?" without scanning every list.
    __table_args__ = (Index("ix_list_entries_domain", "domain"),)


class Rule(Base):
    """A hand-made allow/block entry.

    Scope: device_id set -> that device; group_id set -> that group;
    neither -> the whole network. Never both.
    """

    __tablename__ = "rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    action: Mapped[PolicyAction] = mapped_column(_text_enum(PolicyAction, "action"))
    domain: Mapped[str] = mapped_column(String(DOMAIN_LENGTH))
    device_id: Mapped[int | None] = mapped_column(ForeignKey("devices.id", ondelete="CASCADE"))
    group_id: Mapped[int | None] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"))
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    __table_args__ = (
        CheckConstraint("device_id IS NULL OR group_id IS NULL", name="single_scope"),
        # One rule per domain per scope. Partial indexes, because a plain
        # UNIQUE treats NULLs as distinct and would allow duplicate globals.
        Index(
            "uq_rules_global_domain",
            "domain",
            unique=True,
            sqlite_where=text("device_id IS NULL AND group_id IS NULL"),
        ),
        Index(
            "uq_rules_device_domain",
            "device_id",
            "domain",
            unique=True,
            sqlite_where=text("device_id IS NOT NULL"),
        ),
        Index(
            "uq_rules_group_domain",
            "group_id",
            "domain",
            unique=True,
            sqlite_where=text("group_id IS NOT NULL"),
        ),
    )


# --- query log and events --------------------------------------------------------


class DnsQuery(Base):
    """One DNS query, as logged by the resolver's background writer.

    device_id is who the client IP belonged to *at query time*, so history
    stays right when IPs move. `reason` is a text snapshot (e.g. "list:OISD",
    "rule:12"), not a foreign key: deleting a list mustn't rewrite millions of
    log rows, and old rows should still say why they were blocked.

    No answer data (resolved addresses or records) is ever stored (hard rule 1).
    """

    __tablename__ = "queries"

    id: Mapped[int] = mapped_column(primary_key=True)
    ts: Mapped[datetime]
    client_ip: Mapped[str] = mapped_column(String(IP_LENGTH))
    device_id: Mapped[int | None] = mapped_column(ForeignKey("devices.id", ondelete="SET NULL"))
    qname: Mapped[str] = mapped_column(String(DOMAIN_LENGTH))
    qtype: Mapped[int] = mapped_column(SmallInteger)  # numeric: 1 = A, 28 = AAAA, ...
    decision: Mapped[QueryDecision] = mapped_column(_text_enum(QueryDecision, "decision"))
    reason: Mapped[str | None] = mapped_column(String(NAME_LENGTH))
    rcode: Mapped[int | None] = mapped_column(SmallInteger)
    from_cache: Mapped[bool] = mapped_column(default=False)
    upstream_ms: Mapped[int | None]

    __table_args__ = (
        Index("ix_queries_ts", "ts"),  # retention pruning, time filters
        Index("ix_queries_device_id_ts", "device_id", "ts"),  # per-device views
        Index("ix_queries_qname_ts", "qname", "ts"),  # domain search
    )


class Event(Base):
    """Something worth showing Jake: a new device, a failed list refresh, ...

    `kind` is free text (not a CHECK'd enum) so new kinds don't need a migration.
    """

    __tablename__ = "events"

    id: Mapped[int] = mapped_column(primary_key=True)
    ts: Mapped[datetime] = mapped_column(default=utcnow, index=True)
    kind: Mapped[str] = mapped_column(String(32))
    device_id: Mapped[int | None] = mapped_column(ForeignKey("devices.id", ondelete="SET NULL"))
    message: Mapped[str] = mapped_column(Text)


# --- portal auth -----------------------------------------------------------------


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(NAME_LENGTH, collation="NOCASE"), unique=True)
    password_hash: Mapped[str] = mapped_column(Text)  # Argon2 encoded hash
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    last_login_at: Mapped[datetime | None]


class UserSession(Base):
    """A portal login session.

    `id` is the SHA-256 (hex) of the session token, never the token itself,
    so a copy of the database can't be used to log in.
    """

    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    csrf_token: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    last_used_at: Mapped[datetime] = mapped_column(default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(index=True)

    user: Mapped[User] = relationship()


# --- misc ------------------------------------------------------------------------


class Meta(Base):
    """Small key/value store for service state (its uses are decided per feature)."""

    __tablename__ = "meta"

    key: Mapped[str] = mapped_column(String(NAME_LENGTH), primary_key=True)
    value: Mapped[str] = mapped_column(Text)
