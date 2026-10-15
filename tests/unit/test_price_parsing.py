"""Unit tests for price parsing — the most failure-prone bit of any money check.

Runs offline (no browser), so it always exercises the reporting pipeline.
"""

from __future__ import annotations

from decimal import Decimal

import allure
import pytest

from qa_framework.utils.price import extract_amounts, parse_price


@allure.feature("Utilities · price parsing")
@pytest.mark.smoke
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("$24.99", Decimal("24.99")),
        ("US $24.99", Decimal("24.99")),
        ("C $30.00", Decimal("30.00")),
        ("ILS 44.21", Decimal("44.21")),  # non-USD localised store
        ("£19.99", Decimal("19.99")),
        ("$1,234.56", Decimal("1234.56")),
        ("$12345.67", Decimal("12345.67")),  # large, ungrouped -> not truncated
        ("$24.99/ea", Decimal("24.99")),
        ("$10.00 to $20.00", Decimal("10.00")),  # range -> lowest by default
        # Irregular grouping must read as ONE amount, never a tiny fragment — a
        # fragment would make `min` understate the price and false-pass a price check.
        ("$1,23,456.78", Decimal("123456.78")),  # Indian-style grouping
        ("$1,2345.00", Decimal("12345.00")),  # wrong group size
        ("$3.999", Decimal("3.999")),  # 3 decimals -> no orphan digit
        ("Tap item to see price", None),
        ("", None),
        (None, None),
    ],
)
def test_parse_price(text, expected):
    assert parse_price(text) == expected


def test_parse_price_prefers_max_on_request():
    assert parse_price("$10.00 to $20.00", prefer="max") == Decimal("20.00")


def test_extract_amounts_returns_all_in_order():
    assert extract_amounts("from $5.00 up to $9,999.99") == [
        Decimal("5.00"),
        Decimal("9999.99"),
    ]
