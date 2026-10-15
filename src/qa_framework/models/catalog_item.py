"""Domain models shared across page objects and tests."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class CatalogItem:
    """One product as a page renders it.

    ``price`` is parsed from the page and is ``None`` when it cannot be read;
    ``url`` is the product's detail page, or ``""`` where the page has no link
    (cart and checkout rows).
    """

    name: str
    price: Decimal | None = None
    url: str = ""


@dataclass(frozen=True)
class OrderSummary:
    """What the checkout overview shows before the order is placed."""

    lines: tuple[CatalogItem, ...]
    item_total: Decimal
    tax: Decimal
    total: Decimal

    @property
    def names(self) -> list[str]:
        return [line.name for line in self.lines]
