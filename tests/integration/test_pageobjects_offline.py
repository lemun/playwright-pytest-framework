"""Integration tests for the page objects and the order-total check, driven in
a real headless browser against the offline fake store (see ``fake_store.py``).
No network.

The user journeys themselves run in ``test_journeys_offline.py``; this module
covers what they rely on: the login matrix, card parsing, resilient locators,
verified adds, logout and reset, and that the order-total check fails loudly
when the overview disagrees with the catalogue.
"""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

import allure
import pytest
from fake_store import BASE_URL, CATALOG, FakeStore

from qa_framework.config.settings import AuthConfig
from qa_framework.flows.store_flow import StoreFlow
from qa_framework.models import LoginCase
from qa_framework.pages import InventoryPage, LoginPage

pytestmark = [pytest.mark.integration, allure.feature("Page objects · offline")]

LOGIN_CASES = LoginCase.load_all("data/login_cases.yaml")


# --------------------------------------------------------------------------- #
# Login (same data file as the live login suite)
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("case", LOGIN_CASES, ids=[c.id for c in LOGIN_CASES])
def test_login_matrix(page, offline_settings, store, case: LoginCase):
    login = LoginPage(page, offline_settings).open_login()
    login.login(case.username, case.password)
    if case.should_succeed:
        assert InventoryPage(page, offline_settings).wait_loaded().heading() == "Products"
        assert login.error_message() == ""
    else:
        assert login.error_message() == case.expected_error
        assert page.url.rstrip("/") == BASE_URL


def test_login_rejects_bad_credentials(page, offline_settings, store):
    bad = replace(offline_settings, auth=AuthConfig(username="standard_user", password="nope"))
    with pytest.raises(AssertionError, match="do not match"):
        StoreFlow(page, bad).login()


def test_logout_returns_to_login(offline_flow, page):
    offline_flow.login()
    offline_flow.navbar.logout()
    assert page.url.rstrip("/") == BASE_URL
    assert offline_flow.login_page.wait_for_any(LoginPage.USERNAME).is_visible()


# --------------------------------------------------------------------------- #
# Catalogue parsing and locators
# --------------------------------------------------------------------------- #
def test_inventory_parses_every_card(offline_flow, offline_settings):
    offline_flow.login()
    items = offline_flow.inventory.items()
    assert [i.name for i in items] == sorted(p.name for p in CATALOG)  # default: A to Z
    by_name = {i.name: i for i in items}
    for product in CATALOG:
        item = by_name[product.name]
        assert item.price == product.price
        assert item.url == offline_settings.url(f"/inventory-item.html?id={product.id}")


def test_resilient_locator_falls_back_to_class_names(page, offline_settings):
    """A build without data-test hooks still parses through the class fallback."""
    page.set_content(
        '<div class="inventory_item"><a id="item_7_title_link" href="#">'
        '<div class="inventory_item_name">Plain Mug</div></a>'
        '<div class="inventory_item_price">$12.50</div></div>'
    )
    (item,) = InventoryPage(page, offline_settings).items()
    assert (item.name, item.price) == ("Plain Mug", Decimal("12.50"))
    assert item.url.endswith("/inventory-item.html?id=7")


def test_wait_for_any_supports_xpath_unions(page, offline_settings):
    page.set_content("<p class='late'>ok</p>")
    loc = InventoryPage(page, offline_settings).wait_for_any(
        ["xpath=//section[@id='missing']", "xpath=//p[contains(@class,'late')]"]
    )
    assert loc.inner_text() == "ok"


# --------------------------------------------------------------------------- #
# Cart buttons
# --------------------------------------------------------------------------- #
def test_card_add_is_verified_and_idempotent(offline_flow):
    offline_flow.login()
    assert offline_flow.inventory.add("Sauce Labs Backpack") is True
    assert offline_flow.inventory.add("Sauce Labs Backpack") is True  # already in the cart
    assert offline_flow.navbar.cart_count() == 1


def test_card_add_reports_a_silently_dropped_add(page, offline_settings, store):
    """The store's error_user drops adds of odd product ids without an error."""
    flow = StoreFlow(page, offline_settings)
    flow.login("error_user")
    assert flow.inventory.add("Sauce Labs Bolt T-Shirt") is False  # id 1
    assert flow.inventory.add("Sauce Labs Onesie") is True  # id 2
    assert flow.navbar.cart_count() == 1


def test_reset_app_state_empties_the_cart(offline_flow):
    offline_flow.login()
    offline_flow.add_products(["Sauce Labs Backpack", "Sauce Labs Onesie"])
    assert offline_flow.navbar.cart_count() == 2
    offline_flow.navbar.reset_app_state()
    assert offline_flow.navbar.cart_count() == 0


# --------------------------------------------------------------------------- #
# The order-total check must catch a wrong overview
# --------------------------------------------------------------------------- #
def _checkout(flow: StoreFlow, names: list[str]) -> dict[str, Decimal]:
    flow.login()
    prices = flow.catalogue_prices()
    assert flow.add_products(names) == names
    assert flow.start_checkout_as_configured() == ""
    return {name: prices[name] for name in names}


def test_order_check_catches_an_item_total_mismatch(page, offline_settings, context):
    FakeStore(overview_markup_cents=100).install(context)  # overview adds $1.00
    flow = StoreFlow(page, offline_settings)
    expected = _checkout(flow, ["Sauce Labs Onesie"])
    with pytest.raises(AssertionError, match="item total"):
        flow.verify_order(expected)


def test_order_check_catches_a_wrong_tax_rate(page, offline_settings, context):
    FakeStore(tax_basis_points=900).install(context)  # 9% instead of 8%
    flow = StoreFlow(page, offline_settings)
    expected = _checkout(flow, ["Sauce Labs Fleece Jacket"])
    with pytest.raises(AssertionError, match="tax"):
        flow.verify_order(expected)


def test_order_check_catches_a_missing_product(offline_flow):
    expected = _checkout(offline_flow, ["Sauce Labs Backpack"])
    expected["Sauce Labs Bike Light"] = Decimal("9.99")  # wanted, but never reached the cart
    with pytest.raises(AssertionError, match="overview lists"):
        offline_flow.verify_order(expected)


def test_tax_is_rounded_to_the_cent(offline_flow):
    assert offline_flow.expected_tax(Decimal("17.98")) == Decimal("1.44")  # 1.4384
    assert offline_flow.expected_tax(Decimal("29.99")) == Decimal("2.40")  # 2.3992
    assert offline_flow.expected_tax(Decimal("129.94")) == Decimal("10.40")  # 10.3952
