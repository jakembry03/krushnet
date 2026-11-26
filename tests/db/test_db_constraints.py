"""The database itself enforces the schema's rules, not just the Python code."""

from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from krushnet.db.models import (
    Device,
    DeviceAddress,
    DeviceHostname,
    DnsQuery,
    DomainList,
    DomainListEntry,
    Event,
    Group,
    HostnameSource,
    ListFormat,
    ListSource,
    PolicyAction,
    QueryDecision,
    Rule,
    User,
)
from krushnet.db.types import utcnow


def make_device(mac: str = "aa:bb:cc:dd:ee:01", **kwargs: object) -> Device:
    now = utcnow()
    return Device(mac=mac, is_randomized_mac=False, first_seen=now, last_seen=now, **kwargs)


def make_query(device: Device | None, ts: datetime | None = None) -> DnsQuery:
    return DnsQuery(
        ts=ts or utcnow(),
        client_ip="192.168.1.20",
        device_id=device.id if device else None,
        qname="example.com",
        qtype=1,
        decision=QueryDecision.ALLOWED,
    )


def count(session: Session, model: type) -> int:
    return session.scalar(select(func.count()).select_from(model)) or 0


# --- devices ----------------------------------------------------------------------


def test_duplicate_mac_rejected(session: Session) -> None:
    session.add_all([make_device(), make_device()])
    with pytest.raises(IntegrityError):
        session.flush()


def test_malformed_mac_rejected(session: Session) -> None:
    session.add(make_device(mac="aa:bb:cc"))
    with pytest.raises(IntegrityError, match="ck_devices_mac_length"):
        session.flush()


def test_new_device_defaults_to_unacknowledged(session: Session) -> None:
    device = make_device()
    session.add(device)
    session.flush()
    assert device.acknowledged is False


def test_group_names_unique_ignoring_case(session: Session) -> None:
    session.add_all([Group(name="Kids"), Group(name="kids")])
    with pytest.raises(IntegrityError):
        session.flush()


def test_usernames_unique_ignoring_case(session: Session) -> None:
    session.add_all(
        [User(username="Jake", password_hash="x"), User(username="jake", password_hash="x")]
    )
    with pytest.raises(IntegrityError):
        session.flush()


def test_deleting_device_cascades_and_keeps_history(session: Session) -> None:
    device = make_device()
    session.add(device)
    session.flush()
    now = utcnow()
    session.add_all(
        [
            DeviceAddress(device_id=device.id, ip="192.168.1.20", first_seen=now, last_seen=now),
            DeviceHostname(
                device_id=device.id,
                hostname="laptop",
                source=HostnameSource.DHCP,
                first_seen=now,
                last_seen=now,
            ),
            Rule(action=PolicyAction.BLOCK, domain="example.com", device_id=device.id),
            make_query(device),
            Event(kind="new_device", device_id=device.id, message="new"),
        ]
    )
    session.commit()

    session.execute(text("DELETE FROM devices WHERE id = :id"), {"id": device.id})
    session.commit()
    session.expire_all()

    # Owned rows go with the device...
    assert count(session, DeviceAddress) == 0
    assert count(session, DeviceHostname) == 0
    assert count(session, Rule) == 0
    # ...but the query log and events survive, just unattributed.
    assert session.scalars(select(DnsQuery.device_id)).all() == [None]
    assert session.scalars(select(Event.device_id)).all() == [None]


def test_deleting_group_ungroups_devices(session: Session) -> None:
    group = Group(name="IoT")
    session.add(group)
    session.flush()
    session.add(make_device(group_id=group.id))
    session.commit()

    session.execute(text("DELETE FROM groups WHERE id = :id"), {"id": group.id})
    session.commit()
    session.expire_all()
    assert session.scalars(select(Device.group_id)).one() is None


def test_unknown_foreign_key_rejected(session: Session) -> None:
    """Proves foreign_keys=ON is in effect (SQLite ignores them by default)."""
    session.add(make_device(group_id=999))
    with pytest.raises(IntegrityError):
        session.flush()


# --- rules --------------------------------------------------------------------------


def test_rule_cannot_have_two_scopes(session: Session) -> None:
    group = Group(name="Kids")
    device = make_device()
    session.add_all([group, device])
    session.flush()
    session.add(
        Rule(action=PolicyAction.BLOCK, domain="a.com", device_id=device.id, group_id=group.id)
    )
    with pytest.raises(IntegrityError, match="ck_rules_single_scope"):
        session.flush()


def test_duplicate_global_rule_rejected(session: Session) -> None:
    session.add_all(
        [
            Rule(action=PolicyAction.BLOCK, domain="a.com"),
            Rule(action=PolicyAction.ALLOW, domain="a.com"),
        ]
    )
    with pytest.raises(IntegrityError):
        session.flush()


def test_duplicate_device_rule_rejected(session: Session) -> None:
    device = make_device()
    session.add(device)
    session.flush()
    session.add_all(
        [
            Rule(action=PolicyAction.BLOCK, domain="a.com", device_id=device.id),
            Rule(action=PolicyAction.BLOCK, domain="a.com", device_id=device.id),
        ]
    )
    with pytest.raises(IntegrityError):
        session.flush()


def test_same_domain_allowed_in_different_scopes(session: Session) -> None:
    group = Group(name="Kids")
    device_a, device_b = make_device("aa:bb:cc:dd:ee:01"), make_device("aa:bb:cc:dd:ee:02")
    session.add_all([group, device_a, device_b])
    session.flush()
    session.add_all(
        [
            Rule(action=PolicyAction.BLOCK, domain="a.com"),
            Rule(action=PolicyAction.ALLOW, domain="a.com", group_id=group.id),
            Rule(action=PolicyAction.ALLOW, domain="a.com", device_id=device_a.id),
            Rule(action=PolicyAction.ALLOW, domain="a.com", device_id=device_b.id),
        ]
    )
    session.flush()
    assert count(session, Rule) == 4


# --- lists ----------------------------------------------------------------------------


def test_deleting_list_removes_its_entries(session: Session) -> None:
    domain_list = DomainList(
        name="Test",
        kind=PolicyAction.BLOCK,
        source=ListSource.URL,
        location="https://example.com/list.txt",
        format=ListFormat.DOMAINS,
    )
    session.add(domain_list)
    session.flush()
    session.add_all([DomainListEntry(list_id=domain_list.id, domain=d) for d in ("a.com", "b.com")])
    session.commit()

    session.execute(text("DELETE FROM lists WHERE id = :id"), {"id": domain_list.id})
    session.commit()
    assert count(session, DomainListEntry) == 0


# --- CHECK constraints on enum columns (bypassing the Python enum) -----------------------


@pytest.mark.parametrize(
    ("table", "column", "constraint"),
    [
        ("queries", "decision", "ck_queries_decision"),
        ("rules", "action", "ck_rules_action"),
        ("lists", "kind", "ck_lists_kind"),
        ("device_hostnames", "source", "ck_device_hostnames_source"),
    ],
)
def test_enum_columns_have_check_constraints(
    session: Session, table: str, column: str, constraint: str
) -> None:
    sql = session.execute(
        text("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = :name"),
        {"name": table},
    ).scalar_one()
    assert constraint in sql
    assert f"CHECK ({column} IN (" in sql


def test_bad_enum_value_rejected_by_database(session: Session) -> None:
    with pytest.raises(IntegrityError, match="ck_queries_decision"):
        session.execute(
            text(
                "INSERT INTO queries (ts, client_ip, qname, qtype, decision, from_cache) "
                "VALUES (0, '192.168.1.20', 'a.com', 1, :decision, 0)"
            ),
            {"decision": "maybe"},
        )
