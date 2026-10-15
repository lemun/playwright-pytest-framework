"""Product catalogue (``/inventory.html``): list, sort, and per-card cart buttons."""

from __future__ import annotations

import re

import allure
from playwright.sync_api import Locator
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from qa_framework.models.catalog_item import CatalogItem
from qa_framework.pages.base_page import BasePage
from qa_framework.utils.price import parse_price

# The title link carries the product id: id="item_4_title_link".
_ITEM_ID_RE = re.compile(r"item_(\d+)_title_link")


class InventoryPage(BasePage):
    PATH = "/inventory.html"

    TITLE = ('[data-test="title"]', ".title")
    ITEM = ('[data-test="inventory-item"]', ".inventory_item")
    NAME = ('[data-test="inventory-item-name"]', ".inventory_item_name")
    PRICE = ('[data-test="inventory-item-price"]', ".inventory_item_price")
    TITLE_LINK = ('a[id$="_title_link"]',)
    SORT = ('[data-test="product-sort-container"]', "select.product_sort_container")
    ACTIVE_SORT = ('[data-test="active-option"]', ".active_option")
    CARD_ADD = ('button[data-test^="add-to-cart"]', "button.btn_primary")
    CARD_REMOVE = ('button[data-test^="remove"]', "button.btn_secondary")

    #: How long a card button may take to flip after a click.
    BUTTON_FLIP_MS = 3000

    @allure.step("Wait for the product list")
    def wait_loaded(self, timeout: int | None = None) -> InventoryPage:
        # The detail page reuses the item hook, so wait for the catalogue's own
        # sort control first, then for the cards.
        self.wait_for_any(self.SORT, timeout=timeout)
        self.wait_for_any(self.ITEM, timeout=timeout)
        return self

    def heading(self) -> str:
        return self.first_text(self.TITLE)

    # ------------------------------------------------------------------ #
    # Sorting
    # ------------------------------------------------------------------ #
    @allure.step("Sort the catalogue by '{option}'")
    def sort_by(self, option: str) -> None:
        """Choose a sort option by its value (``az``, ``za``, ``lohi``, ``hilo``)."""
        self.locator_any(self.SORT).first.select_option(option)

    def active_sort_label(self) -> str:
        """The label the store shows for the sort currently applied."""
        return self.first_text(self.ACTIVE_SORT)

    # ------------------------------------------------------------------ #
    # Reading the list
    # ------------------------------------------------------------------ #
    def items(self) -> list[CatalogItem]:
        """Every product card currently rendered, in display order."""
        cards = self.locator_any(self.ITEM)
        found: list[CatalogItem] = []
        for i in range(cards.count()):
            card = cards.nth(i)
            name = self.first_text(self.NAME, root=card)
            price = parse_price(self.first_text(self.PRICE, root=card))
            link_id = card.locator(self.TITLE_LINK[0]).first.get_attribute("id") or ""
            match = _ITEM_ID_RE.search(link_id)
            if not name or match is None:
                self.log.warning("skipping unparseable card #%d (id=%r)", i, link_id)
                continue
            url = self.settings.url(f"/inventory-item.html?id={match.group(1)}")
            found.append(CatalogItem(name=name, price=price, url=url))
        return found

    def names(self) -> list[str]:
        return [item.name for item in self.items()]

    def item(self, name: str) -> CatalogItem:
        for item in self.items():
            if item.name == name:
                return item
        raise LookupError(f"no product named {name!r} in the catalogue")

    # ------------------------------------------------------------------ #
    # Per-card cart buttons
    # ------------------------------------------------------------------ #
    def card(self, name: str) -> Locator:
        """The card whose product name is exactly ``name``."""
        named = self.any_of(self.NAME).filter(has_text=re.compile(rf"^{re.escape(name)}$"))
        return self.any_of(self.ITEM).filter(has=named)

    def in_cart(self, name: str) -> bool:
        """True when the card offers "Remove", i.e. the store thinks it is in the cart."""
        return self.locator_any(self.CARD_REMOVE, root=self.card(name)).count() > 0

    def _flip(self, name: str, click: tuple[str, ...], expect: tuple[str, ...]) -> bool:
        card = self.card(name)
        if card.count() != 1:
            raise LookupError(f"expected one card named {name!r}, found {card.count()}")
        self.locator_any(click, root=card).first.click()
        try:
            self.locator_any(expect, root=card).first.wait_for(timeout=self.BUTTON_FLIP_MS)
        except PlaywrightTimeoutError:
            return False
        return True

    @allure.step("Add '{name}' from its catalogue card")
    def add(self, name: str) -> bool:
        """Click "Add to cart" and *verify* it took: the button must flip to
        "Remove". Returns ``False`` (never an optimistic ``True``) when it does
        not, as with the store's faulty accounts that silently drop some adds."""
        if self.in_cart(name):
            return True
        added = self._flip(name, self.CARD_ADD, self.CARD_REMOVE)
        if not added:
            self.log.warning("add of '%s' did not take", name)
        return added

    @allure.step("Remove '{name}' from its catalogue card")
    def remove(self, name: str) -> bool:
        """Click "Remove" and verify the button flips back to "Add to cart"."""
        if not self.in_cart(name):
            return True
        removed = self._flip(name, self.CARD_REMOVE, self.CARD_ADD)
        if not removed:
            self.log.warning("removal of '%s' did not take", name)
        return removed

    @allure.step("Open the details of '{name}'")
    def open_details(self, name: str) -> None:
        self.locator_any(self.NAME, root=self.card(name)).first.click()
