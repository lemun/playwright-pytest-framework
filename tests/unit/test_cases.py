"""Unit tests for the data-driven case models: coercion and validation."""

from __future__ import annotations

import allure
import pytest

from qa_framework.models import CheckoutFormCase, OrderCase, PersonaCase, SortCase

pytestmark = allure.feature("Data-driven · case models")


@pytest.mark.smoke
@pytest.mark.parametrize("path", ["data/orders.json", "data/orders.yaml", "data/orders.csv"])
def test_orders_load_as_typed_cases(path):
    orders = OrderCase.load_all(path)
    assert orders
    for order in orders:
        assert isinstance(order.products, tuple)
        assert order.products
        assert all(isinstance(name, str) and name for name in order.products)


def test_csv_product_lists_are_split():
    order = OrderCase.from_dict({"id": "x", "products": "A| B |C"})
    assert order.products == ("A", "B", "C")


@pytest.mark.parametrize(
    "bad",
    [
        {"id": "x", "products": ""},  # empty
        {"id": "x", "products": []},  # empty
        {"id": "x", "products": "A|A"},  # duplicate
        {"id": "x", "products": 3},  # wrong type
        {"id": "x"},  # missing key
    ],
)
def test_invalid_orders_raise(bad):
    with pytest.raises(ValueError, match=r"(?i)order"):
        OrderCase.from_dict(bad)


def test_sort_options_cover_all_four_orders():
    cases = SortCase.load_all("data/sort_options.yaml")
    assert {(c.key, c.descending) for c in cases} == {
        ("name", False),
        ("name", True),
        ("price", False),
        ("price", True),
    }
    assert {c.option for c in cases} == {"az", "za", "lohi", "hilo"}


@pytest.mark.parametrize(
    "bad",
    [
        {"id": "x", "option": "az", "label": "L", "key": "rating", "descending": False},
        {"id": "x", "option": "az", "label": "L", "key": "name", "descending": "maybe"},
        {"id": "x", "option": "az", "key": "name", "descending": False},  # no label
    ],
)
def test_invalid_sort_cases_raise(bad):
    with pytest.raises(ValueError, match=r"(?i)sort"):
        SortCase.from_dict(bad)


def test_checkout_form_cases_cover_each_required_field():
    cases = {c.id: c for c in CheckoutFormCase.load_all("data/checkout_form_cases.yaml")}
    assert cases["complete"].should_succeed
    errors = {c.expected_error for c in cases.values() if c.expected_error}
    assert errors == {
        "Error: First Name is required",
        "Error: Last Name is required",
        "Error: Postal Code is required",
    }


def test_csv_style_strings_are_coerced_for_personas():
    persona = PersonaCase.from_dict(
        {
            "id": "p",
            "username": "u",
            "sort_applies": "false",
            "sample_product": "A",
            "sample_add_sticks": "yes",
            "min_login_ms": "1500",
        }
    )
    assert (persona.sort_applies, persona.sample_add_sticks, persona.min_login_ms) == (
        False,
        True,
        1500,
    )
    assert persona.checkout_error == ""


def test_personas_file_has_the_documented_accounts():
    personas = {p.username: p for p in PersonaCase.load_all("data/personas.yaml")}
    assert set(personas) == {"standard_user", "problem_user", "performance_glitch_user"}
    assert personas["standard_user"].sort_applies
    assert not personas["problem_user"].sort_applies
    assert personas["performance_glitch_user"].min_login_ms > 0


def test_duplicate_case_ids_are_rejected(tmp_path):
    path = tmp_path / "orders.json"
    path.write_text('[{"id": "a", "products": ["X"]}, {"id": "a", "products": ["Y"]}]')
    with pytest.raises(ValueError, match="unique"):
        OrderCase.load_all(path)
