import pytest
from app.validators import is_valid_ip
from app.helpers import resolve_host

@pytest.mark.parametrize(
    "value, expected",
    [
        ("192.168.1.1", True),
        ("10.0.0.1", True),
        ("127.0.0.1", True),
        ("2001:db8::1", True),
        ("999.999.999.999", False),
        ("hello", False),
        ("", False),
        (123, False),
        (None, False),
    ],
)
def test_is_valid_ip(value, expected):
    assert is_valid_ip(value) is expected

def test_resolve_host_returns_ip_without_dns_lookup():
    result = resolve_host("192.168.1.1")

    assert result == "192.168.1.1"

    






