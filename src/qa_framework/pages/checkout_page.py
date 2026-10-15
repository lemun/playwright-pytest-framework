"""Checkout: customer info (step one), overview with totals (step two), and
the completion page."""

from __future__ import annotations

from decimal import Decimal

import allure

from qa_framework.models.catalog_item import CatalogItem, OrderSummary
from qa_framework.pages.base_page import BasePage
from qa_framework.utils.price import parse_price


class CheckoutInfoPage(BasePage):
    PATH = "/checkout-step-one.html"

    FIRST_NAME = ('[data-test="firstName"]', "#first-name")
    LAST_NAME = ('[data-test="lastName"]', "#last-name")
    POSTAL_CODE = ('[data-test="postalCode"]', "#postal-code")
    CONTINUE = ('[data-test="continue"]', "#continue")
    ERROR = ('[data-test="error"]', ".error-message-container h3")

    def wait_loaded(self) -> CheckoutInfoPage:
        self.wait_for_any(self.FIRST_NAME)
        return self

    @allure.step("Fill in the customer details and continue")
    def submit(self, first_name: str, last_name: str, postal_code: str) -> None:
        """Type each field (empty values leave the field blank) and continue.
        Does not assert the outcome, so validation cases stay testable."""
        self.wait_loaded()
        self.locator_any(self.FIRST_NAME).first.fill(first_name)
        self.locator_any(self.LAST_NAME).first.fill(last_name)
        self.locator_any(self.POSTAL_CODE).first.fill(postal_code)
        self.locator_any(self.CONTINUE).first.click()

    def field_values(self) -> tuple[str, str, str]:
        """What the three inputs hold now (first, last, postal code)."""
        return (
            self.locator_any(self.FIRST_NAME).first.input_value(),
            self.locator_any(self.LAST_NAME).first.input_value(),
            self.locator_any(self.POSTAL_CODE).first.input_value(),
        )

    def error_message(self) -> str:
        return self.first_text(self.ERROR)


class CheckoutOverviewPage(BasePage):
    PATH = "/checkout-step-two.html"

    ROW = ('[data-test="inventory-item"]', ".cart_item")
    NAME = ('[data-test="inventory-item-name"]', ".inventory_item_name")
    PRICE = ('[data-test="inventory-item-price"]', ".inventory_item_price")
    ITEM_TOTAL = ('[data-test="subtotal-label"]', ".summary_subtotal_label")
    TAX = ('[data-test="tax-label"]', ".summary_tax_label")
    TOTAL = ('[data-test="total-label"]', ".summary_total_label")
    FINISH = ('[data-test="finish"]', "#finish")

    def wait_loaded(self) -> CheckoutOverviewPage:
        self.wait_for_any(self.ITEM_TOTAL)
        return self

    def _amount(self, selectors: tuple[str, ...], label: str) -> Decimal:
        text = self.first_text(selectors)
        value = parse_price(text)
        if value is None:
            raise AssertionError(f"could not read the {label} from {text!r}")
        return value

    def summary(self) -> OrderSummary:
        """The lines and the three amounts exactly as the store renders them."""
        self.wait_loaded()
        rows = self.locator_any(self.ROW)
        lines = tuple(
            CatalogItem(
                name=self.first_text(self.NAME, root=rows.nth(i)),
                price=parse_price(self.first_text(self.PRICE, root=rows.nth(i))),
            )
            for i in range(rows.count())
        )
        return OrderSummary(
            lines=lines,
            item_total=self._amount(self.ITEM_TOTAL, "item total"),
            tax=self._amount(self.TAX, "tax"),
            total=self._amount(self.TOTAL, "total"),
        )

    @allure.step("Finish the order")
    def finish(self) -> None:
        self.locator_any(self.FINISH).first.click()


class CheckoutCompletePage(BasePage):
    PATH = "/checkout-complete.html"

    HEADER = ('[data-test="complete-header"]', ".complete-header")

    def confirmation(self) -> str:
        self.wait_for_any(self.HEADER)
        return self.first_text(self.HEADER)
