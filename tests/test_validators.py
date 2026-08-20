import pytest
from app.validators import is_valid_ip

def test_sum():
    assert (0.1 + 0.2) == pytest.approx(0.3)

def test_is_valid_ip():
    result = is_valid_ip("192.168.1.1")

    assert result is True











