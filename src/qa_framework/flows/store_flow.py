"""StoreFlow: the page objects of one browser page, composed into the user
journeys the suites share (log in, fill a cart, check out, verify an order).

Tests call these steps or reach the pages through the flow's attributes
(``flow.inventory``, ``flow.cart``, ...), so a test reads like the user journey
while selectors and waits stay inside the page objects.
"""

from __future__ import annotations

import time
from collections import Counter
from collections.abc import Iterable, Mapping
from decimal import ROUND_HALF_UP, Decimal

import allure
from playwright.sync_api import Page

from qa_framework.config.settings import Settings
from qa_framework.models.catalog_item import OrderSummary
from qa_framework.pages import (
    CartPage,
    CheckoutCompletePage,
    CheckoutInfoPage,
    CheckoutOverviewPage,
    InventoryPage,
    ItemPage,
    LoginPage,
    Navbar,
)
from qa_framework.utils.attachments import Reporter
from qa_framework.utils.logger import get_logger

CENT = Decimal("0.01")


class StoreFlow:
    def __init__(self, page: Page, settings: Settings):
        self.page = page
        self.settings = settings
        self.log = get_logger("StoreFlow")
        reporter = Reporter(settings.artifacts_dir)  # one reporter, shared by all pages
        self.login_page = LoginPage(page, settings, reporter)
        self.navbar = Navbar(page, settings, reporter)
        self.inventory = InventoryPage(page, settings, reporter)
        self.item_page = ItemPage(page, settings, reporter)
        self.cart = CartPage(page, settings, reporter)
        self.checkout_info = CheckoutInfoPage(page, settings, reporter)
        self.overview = CheckoutOverviewPage(page, settings, reporter)
        self.complete = CheckoutCompletePage(page, settings, reporter)

    # ------------------------------------------------------------------ #
    # Session
    # ------------------------------------------------------------------ #
    @allure.step("Log in")
    def login(self, username: str | None = None, password: str | None = None) -> float:
        """Log in (default: the configured account) and wait for the catalogue.

        Returns the milliseconds from submitting the form to the first rendered
        product card, which the persona checks use.
        """
        auth = self.settings.auth
        username = auth.username if username is None else username
        password = auth.password if password is None else password
        if not (username and password):
            raise ValueError("no credentials configured (auth.username / QA_PASSWORD)")
        self.login_page.open_login()
        started = time.monotonic()
        self.login_page.login(username, password)
        error = self.login_page.error_message()
        if error:
            raise AssertionError(f"login as '{username}' failed: {error}")
        self.inventory.wait_loaded(timeout=self.settings.timeouts.navigation_ms)
        elapsed_ms = (time.monotonic() - started) * 1000
        self.log.info("logged in as %s; catalogue rendered after %.0f ms", username, elapsed_ms)
        return elapsed_ms

    # ------------------------------------------------------------------ #
    # Cart
    # ------------------------------------------------------------------ #
    @allure.step("Add products from the catalogue")
    def add_products(self, names: Iterable[str]) -> list[str]:
        """Add each product from its catalogue card; return those verified added."""
        self.inventory.wait_loaded()
        return [name for name in names if self.inventory.add(name)]

    def catalogue_prices(self) -> dict[str, Decimal]:
        """Name -> price as the catalogue renders them (the order-total oracle's input)."""
        self.inventory.wait_loaded()
        prices: dict[str, Decimal] = {}
        for item in self.inventory.items():
            if item.price is None:
                raise AssertionError(f"could not read the price of {item.name!r}")
            prices[item.name] = item.price
        return prices

    # ------------------------------------------------------------------ #
    # Checkout
    # ------------------------------------------------------------------ #
    @allure.step("Check out with the customer details")
    def start_checkout(self, first_name: str, last_name: str, postal_code: str) -> str:
        """Cart -> checkout -> submit the details. Returns the form's error text,
        or ``""`` once the order overview is shown."""
        self.cart.open_cart()
        self.cart.checkout()
        self.checkout_info.submit(first_name, last_name, postal_code)
        # Either the form shows an error or the overview renders; wait for whichever.
        self.checkout_info.wait_for_any((*CheckoutInfoPage.ERROR, *CheckoutOverviewPage.ITEM_TOTAL))
        return self.checkout_info.error_message()

    def start_checkout_as_configured(self) -> str:
        info = self.settings.checkout
        return self.start_checkout(info.first_name, info.last_name, info.postal_code)

    def expected_tax(self, item_total: Decimal) -> Decimal:
        """The store's tax rule: ``rate x item total``, rounded to the cent.

        Prices are whole cents and the rate is 8%, so a tax amount never lands
        exactly on half a cent and the rounding mode cannot change the result.
        """
        return (item_total * self.settings.store.tax_rate).quantize(CENT, rounding=ROUND_HALF_UP)

    @allure.step("Verify the order overview")
    def verify_order(self, expected_prices: Mapping[str, Decimal]) -> OrderSummary:
        """Check the checkout overview against an independent expectation.

        ``expected_prices`` comes from the catalogue, not from the overview, so
        the overview has to agree with what was offered: the same products (no
        drops, no extras), item total = sum of their prices, tax = rate x item
        total rounded to the cent, and total = item total + tax.

        The live store adds prices as binary floats and prints the raw sum, so
        some product combinations show an item total such as
        ``39.980000000000004``. The displayed item total is therefore rounded
        to the cent before it is compared (the raw value is attached).
        """
        summary = self.overview.summary()
        item_total = summary.item_total.quantize(CENT, rounding=ROUND_HALF_UP)
        expected_total = sum(expected_prices.values(), Decimal(0))
        expected_tax = self.expected_tax(expected_total)
        self.overview.attach_text(
            "\n".join(f"{line.price}  {line.name}" for line in summary.lines)
            + f"\n\nitem total = {summary.item_total} (expected {expected_total})"
            f"\ntax        = {summary.tax} (expected {expected_tax},"
            f" rate {self.settings.store.tax_rate})"
            f"\ntotal      = {summary.total} (expected {expected_total + expected_tax})",
            name="order-summary",
        )
        self.overview.screenshot("checkout-overview", full_page=True)

        assert Counter(summary.names) == Counter(expected_prices.keys()), (
            f"overview lists {sorted(summary.names)}, expected {sorted(expected_prices)}"
        )
        for line in summary.lines:
            assert line.price == expected_prices[line.name], (
                f"{line.name}: overview price {line.price} != catalogue price "
                f"{expected_prices[line.name]}"
            )
        assert item_total == expected_total, (
            f"item total {summary.item_total} != sum of the products {expected_total}"
        )
        assert summary.tax == expected_tax, (
            f"tax {summary.tax} != {self.settings.store.tax_rate} x {expected_total}"
            f" = {expected_tax}"
        )
        assert summary.total == item_total + summary.tax, (
            f"total {summary.total} != item total {item_total} + tax {summary.tax}"
        )
        return summary

    @allure.step("Place the order")
    def place_order(self) -> str:
        """Finish from the overview page; return the confirmation heading."""
        self.overview.finish()
        confirmation = self.complete.confirmation()
        self.complete.screenshot("order-complete")
        return confirmation
