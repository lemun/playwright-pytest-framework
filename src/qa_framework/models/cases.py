"""Data-driven test cases: the single place that coerces and validates raw rows.

External data can be JSON (typed), YAML (typed) or CSV (every field is a
string), so type coercion and validation belong in the data layer, not in the
tests. Each ``from_dict`` normalises a row from any source to the same typed,
immutable object and fails with the offending row in the message.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, TypeVar

T = TypeVar("T")

SortKey = Literal["name", "price"]

_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"0", "false", "no", "off"}


def _load(path: str | Path, parse: Callable[[dict[str, Any]], T]) -> list[T]:
    # Imported lazily to avoid a models <-> utils import cycle at module load.
    from qa_framework.utils.data_loader import DataLoader

    rows = DataLoader.load(path)
    if not isinstance(rows, list) or not rows:
        raise ValueError(f"{path}: expected a non-empty list of cases")
    cases = [parse(row) for row in rows]
    ids = [getattr(case, "id", None) for case in cases]
    if len(set(ids)) != len(ids):
        raise ValueError(f"{path}: case ids must be unique, got {ids}")
    return cases


def _bool(raw: dict[str, Any], key: str) -> bool:
    value = raw[key]
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in _TRUE:
        return True
    if text in _FALSE:
        return False
    raise ValueError(f"{key} must be a boolean, got {value!r}")


def _str(raw: dict[str, Any], key: str) -> str:
    value = raw.get(key)
    return "" if value is None else str(value)


def _row_error(kind: str, raw: dict[str, Any], exc: Exception) -> ValueError:
    if isinstance(exc, KeyError):
        return ValueError(f"{kind} row missing required key {exc} in {raw!r}")
    return ValueError(f"Invalid {kind} row {raw!r}: {exc}")


@dataclass(frozen=True)
class OrderCase:
    """A set of products to buy. In CSV, ``products`` is ``"A|B|C"``."""

    id: str
    products: tuple[str, ...]
    description: str = ""

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> OrderCase:
        try:
            products = raw["products"]
            if isinstance(products, str):
                products = products.split("|")
            if not isinstance(products, list):
                raise TypeError(f"products must be a list or 'A|B' string, got {products!r}")
            names = tuple(str(p).strip() for p in products if str(p).strip())
            if not names:
                raise ValueError("products must not be empty")
            if len(set(names)) != len(names):
                raise ValueError(f"products must be distinct, got {names}")
            return cls(id=str(raw["id"]), products=names, description=_str(raw, "description"))
        except (KeyError, TypeError, ValueError) as exc:
            raise _row_error("order", raw, exc) from exc

    @classmethod
    def load_all(cls, path: str | Path) -> list[OrderCase]:
        return _load(path, cls.from_dict)


@dataclass(frozen=True)
class SortCase:
    """A catalogue sort option and the order it must produce."""

    id: str
    option: str  # the <select> value, e.g. "hilo"
    label: str  # what the store shows as the active option
    key: SortKey
    descending: bool

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> SortCase:
        try:
            key = str(raw["key"])
            if key not in ("name", "price"):
                raise ValueError(f"key must be 'name' or 'price', got {key!r}")
            return cls(
                id=str(raw["id"]),
                option=str(raw["option"]),
                label=str(raw["label"]),
                key="name" if key == "name" else "price",
                descending=_bool(raw, "descending"),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise _row_error("sort", raw, exc) from exc

    @classmethod
    def load_all(cls, path: str | Path) -> list[SortCase]:
        return _load(path, cls.from_dict)


@dataclass(frozen=True)
class CheckoutFormCase:
    """Customer details typed into checkout and the error the form must show."""

    id: str
    first_name: str
    last_name: str
    postal_code: str
    #: Expected error banner text; empty means the form must be accepted.
    expected_error: str = ""

    @property
    def should_succeed(self) -> bool:
        return not self.expected_error

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> CheckoutFormCase:
        try:
            return cls(
                id=str(raw["id"]),
                first_name=_str(raw, "first_name"),
                last_name=_str(raw, "last_name"),
                postal_code=_str(raw, "postal_code"),
                expected_error=_str(raw, "expected_error"),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise _row_error("checkout form", raw, exc) from exc

    @classmethod
    def load_all(cls, path: str | Path) -> list[CheckoutFormCase]:
        return _load(path, cls.from_dict)


@dataclass(frozen=True)
class PersonaCase:
    """A demo-store account and the behaviour the suite expects from it.

    The store ships accounts with deliberate defects; a persona case states
    each one as data, so the same test proves both the healthy account and the
    faulty ones.
    """

    id: str
    username: str
    #: Choosing "Price (high to low)" actually reorders the catalogue.
    sort_applies: bool
    #: A product added from its catalogue card; does the add stick?
    sample_product: str
    sample_add_sticks: bool
    #: Error shown when submitting complete customer details; "" = accepted.
    checkout_error: str = ""
    #: Lower bound for login -> catalogue rendered, in ms (0 = not checked).
    min_login_ms: int = 0
    description: str = field(default="", compare=False)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> PersonaCase:
        try:
            min_login_ms = int(raw.get("min_login_ms") or 0)
            if min_login_ms < 0:
                raise ValueError(f"min_login_ms must be >= 0, got {min_login_ms}")
            return cls(
                id=str(raw["id"]),
                username=str(raw["username"]),
                sort_applies=_bool(raw, "sort_applies"),
                sample_product=str(raw["sample_product"]),
                sample_add_sticks=_bool(raw, "sample_add_sticks"),
                checkout_error=_str(raw, "checkout_error"),
                min_login_ms=min_login_ms,
                description=_str(raw, "description"),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise _row_error("persona", raw, exc) from exc

    @classmethod
    def load_all(cls, path: str | Path) -> list[PersonaCase]:
        return _load(path, cls.from_dict)
