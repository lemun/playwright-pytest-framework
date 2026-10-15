"""Cart (``/cart.html``): line items, removal, and the way on to checkout."""

from __future__ import annotations

import re

import allure
from playwright.sync_api import expect

from qa_framework.models.catalog_item import CatalogItem
from qa_framework.pages.base_page import BasePage
from qa_framework.utils.price import parse_price


class CartPage(BasePage):
    PATH = "/cart.html"

    CONTAINER = ('[data-test="cart-list"]', ".cart_list")
    ROW = ('[data-test="inventory-item"]', ".cart_item")
    NAME = ('[data-test="inventory-item-name"]', ".inventory_item_name")
    PRICE = ('[data-test="inventory-item-price"]', ".inventory_item_price")
    REMOVE = ('button[data-test^="remove"]', "button.cart_button")
    CONTINUE_SHOPPING = ('[data-test="continue-shopping"]', "#continue-shopping")
    CHECKOUT = ('[data-test="checkout"]', "#checkout")

    @allure.step("Open the cart")
    def open_cart(self) -> CartPage:
        self.open()
        return self.wait_loaded()

    def wait_loaded(self) -> CartPage:
        self.wait_for_any(self.CONTAINER, state="attached")
        return self

    def line_items(self) -> list[CatalogItem]:
        """(name, price) for every row, in display order."""
        rows = self.locator_any(self.ROW)
        return [
            CatalogItem(
                name=self.first_text(self.NAME, root=rows.nth(i)),
                price=parse_price(self.first_text(self.PRICE, root=rows.nth(i))),
            )
            for i in range(rows.count())
        ]

    def names(self) -> list[str]:
        return [line.name for line in self.line_items()]

    def item_count(self) -> int:
        return self.locator_any(self.ROW).count()

    @allure.step("Remove '{name}' from the cart")
    def remove(self, name: str) -> None:
        """Remove one line and wait until it is gone."""
        named = self.any_of(self.NAME).filter(has_text=re.compile(rf"^{re.escape(name)}$"))
        row = self.any_of(self.ROW).filter(has=named)
        before = self.item_count()
        self.locator_any(self.REMOVE, root=row).first.click()
        expect(self.locator_any(self.ROW)).to_have_count(before - 1)

    @allure.step("Continue shopping")
    def continue_shopping(self) -> None:
        self.locator_any(self.CONTINUE_SHOPPING).first.click()

    @allure.step("Proceed to checkout")
    def checkout(self) -> None:
        self.locator_any(self.CHECKOUT).first.click()
