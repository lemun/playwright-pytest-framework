"""Product detail page (``/inventory-item.html?id=N``)."""

from __future__ import annotations

from decimal import Decimal

import allure

from qa_framework.pages.base_page import BasePage
from qa_framework.utils.price import parse_price


class ItemPage(BasePage):
    NAME = ('[data-test="inventory-item-name"]', ".inventory_details_name")
    PRICE = ('[data-test="inventory-item-price"]', ".inventory_details_price")
    ADD = ('[data-test="add-to-cart"]', "#add-to-cart")
    REMOVE = ('[data-test="remove"]', "#remove")
    BACK = ('[data-test="back-to-products"]', "#back-to-products")

    @allure.step("Open item {url}")
    def open_item(self, url: str) -> ItemPage:
        self.open(url)
        return self.wait_loaded()

    def wait_loaded(self) -> ItemPage:
        # The catalogue renders the same name hook, so wait for the detail
        # page's own "Back to products" button before reading anything.
        self.wait_for_any(self.BACK)
        self.wait_for_any(self.NAME)
        return self

    def name(self) -> str:
        return self.first_text(self.NAME)

    def price(self) -> Decimal | None:
        return parse_price(self.first_text(self.PRICE))

    def in_cart(self) -> bool:
        """True when the page offers "Remove" rather than "Add to cart"."""
        self.wait_for_any((*self.ADD, *self.REMOVE))
        return self.locator_any(self.REMOVE).count() > 0

    @allure.step("Back to the catalogue")
    def back_to_products(self) -> None:
        self.locator_any(self.BACK).first.click()
