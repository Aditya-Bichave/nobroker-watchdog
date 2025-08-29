import pytest

from nobroker_watchdog.utils import parse_indic_money


@pytest.mark.parametrize(
    "input_str,expected",
    [
        ("1 lakh", 100000),
        ("2 lakhs", 200000),
        ("3 lacs", 300000),
        ("4 lac", 400000),
        ("0.5 crore", 5000000),
        ("1 crore", 10000000),
        ("3 crores", 30000000),
        ("1.2 cr", 12000000),
        ("5 cr.", 50000000),
        ("25k", 25000),
        ("35000", 35000),
    ],
)
def test_parse_indic_money_variants(input_str, expected):
    assert parse_indic_money(input_str) == expected


def test_parse_indic_money_none():
    assert parse_indic_money(None) is None
