"""Unit tests for the data-driven loader (JSON / YAML / CSV)."""

from __future__ import annotations

import allure
import pytest

from qa_framework.utils.data_loader import DataLoader

_REQUIRED_KEYS = {"id", "products"}


_SOURCES = [
    "data/orders.json",
    "data/orders.yaml",
    "data/orders.csv",
]


@allure.feature("Utilities · data loader")
@pytest.mark.smoke
@pytest.mark.parametrize("path", _SOURCES)
def test_orders_load_with_expected_schema(path):
    rows = DataLoader.load(path)
    assert isinstance(rows, list)
    assert rows
    for row in rows:
        assert _REQUIRED_KEYS.issubset(row.keys()), f"missing keys in {row}"


def test_all_sources_agree_on_ids():
    id_sets = [{s["id"] for s in DataLoader.load(p)} for p in _SOURCES]
    assert id_sets[0] == id_sets[1] == id_sets[2]


def test_all_sources_agree_on_values():
    """Every format must yield the SAME orders, not merely the same ids.

    Compares fully-coerced OrderCase objects (so the CSV's "A|B" product lists
    line up with JSON/YAML lists), catching value drift such as a description or
    a product that differs per file.
    """
    from qa_framework.models import OrderCase

    per_source = [
        sorted((OrderCase.from_dict(row) for row in DataLoader.load(p)), key=lambda o: o.id)
        for p in _SOURCES
    ]
    assert per_source[0] == per_source[1] == per_source[2]


def test_unknown_format_is_rejected():
    with pytest.raises(ValueError, match="Unsupported data format"):
        DataLoader.load("pyproject.toml")


def test_missing_file_raises():
    with pytest.raises(FileNotFoundError):
        DataLoader.load("data/does_not_exist.json")
