"""Unit tests for the small domain models."""

from __future__ import annotations

from decimal import Decimal

import pytest

from qa_framework.models import CatalogItem, LoginCase, OrderSummary


def test_order_summary_names_keep_display_order():
    summary = OrderSummary(
        lines=(CatalogItem("B", Decimal("2")), CatalogItem("A", Decimal("1"))),
        item_total=Decimal("3"),
        tax=Decimal("0.24"),
        total=Decimal("3.24"),
    )
    assert summary.names == ["B", "A"]


def test_catalog_items_compare_by_value():
    assert CatalogItem("A", Decimal("1.0")) == CatalogItem("A", Decimal("1.00"))
    assert len({CatalogItem("A", Decimal("1")), CatalogItem("A", Decimal("1"))}) == 1


def test_login_cases_load_and_classify():
    cases = {c.id: c for c in LoginCase.load_all("data/login_cases.yaml")}
    assert cases["standard-user"].should_succeed
    assert not cases["locked-out-user"].should_succeed
    assert all(
        c.expected_error.startswith("Epic sadface") for c in cases.values() if c.expected_error
    )


def test_login_case_requires_an_id():
    with pytest.raises(ValueError, match="id"):
        LoginCase.from_dict({"username": "x"})
