"""The user journeys, written once and run by two suites:

* ``tests/integration/test_journeys_offline.py`` against the offline fake store;
* ``tests/e2e/test_journeys_e2e.py`` against saucedemo.com (``QA_RUN_E2E=1``).

Each journey takes a ``StoreFlow`` plus one data-driven case and asserts on
what the store renders. Expected values come from the case data or from an
independent read of the catalogue, never from the page being checked.
"""

from __future__ import annotations

import os
from collections import Counter
from collections.abc import Sequence

import allure
from playwright.sync_api import expect

from qa_framework.flows.store_flow import StoreFlow
from qa_framework.models import CheckoutFormCase, OrderCase, PersonaCase, SortCase

ORDERS = OrderCase.load_all(os.getenv("QA_ORDERS", "data/orders.json"))
SORT_OPTIONS = SortCase.load_all("data/sort_options.yaml")
CHECKOUT_FORM_CASES = CheckoutFormCase.load_all("data/checkout_form_cases.yaml")
PERSONAS = PersonaCase.load_all("data/personas.yaml")

CONFIRMATION = "Thank you for your order!"
#: A product every account can add (the faulty accounts drop odd product ids).
RELIABLE_PRODUCT = "Sauce Labs Backpack"


def ids(cases: Sequence[OrderCase | SortCase | CheckoutFormCase | PersonaCase]) -> list[str]:
    return [case.id for case in cases]


# --------------------------------------------------------------------------- #
# Catalogue
# --------------------------------------------------------------------------- #
def sort_orders_the_rendered_list(flow: StoreFlow, case: SortCase) -> None:
    flow.login()
    before = flow.inventory.items()
    flow.inventory.sort_by(case.option)
    expect(flow.inventory.locator_any(flow.inventory.ACTIVE_SORT)).to_have_text(case.label)

    after = flow.inventory.items()
    assert Counter(after) == Counter(before), "sorting must not add, drop or change products"
    if case.key == "price":
        prices = [item.price for item in after]
        assert None not in prices, f"unreadable price in {after}"
        assert prices == sorted(prices, reverse=case.descending), prices  # type: ignore[type-var]
    else:
        names = [item.name for item in after]
        assert names == sorted(names, key=str.casefold, reverse=case.descending), names


# --------------------------------------------------------------------------- #
# Cart
# --------------------------------------------------------------------------- #
def cart_survives_navigation_and_reload(flow: StoreFlow, order: OrderCase) -> None:
    wanted = list(order.products)
    flow.login()
    assert flow.add_products(wanted) == wanted
    assert flow.navbar.cart_count() == len(wanted)

    with allure.step("The detail page knows the product is in the cart"):
        flow.inventory.open_details(wanted[0])
        assert flow.item_page.wait_loaded().name() == wanted[0]
        assert flow.item_page.in_cart()
        flow.item_page.back_to_products()
        flow.inventory.wait_loaded()
        assert all(flow.inventory.in_cart(name) for name in wanted)

    with allure.step("The cart lists the products, also after a reload"):
        flow.navbar.open_cart()
        assert Counter(flow.cart.wait_loaded().names()) == Counter(wanted)
        flow.page.reload()
        assert Counter(flow.cart.wait_loaded().names()) == Counter(wanted)
        assert flow.navbar.cart_count() == len(wanted)

    with allure.step("Back in the catalogue the cart is unchanged"):
        flow.cart.continue_shopping()
        flow.inventory.wait_loaded()
        assert flow.navbar.cart_count() == len(wanted)


def remove_from_catalogue_and_cart(flow: StoreFlow) -> None:
    keep, from_card, from_cart = (
        "Sauce Labs Backpack",
        "Sauce Labs Bike Light",
        "Sauce Labs Onesie",
    )
    flow.login()
    assert flow.add_products([keep, from_card, from_cart]) == [keep, from_card, from_cart]

    assert flow.inventory.remove(from_card)
    assert flow.navbar.cart_count() == 2

    flow.navbar.open_cart()
    assert Counter(flow.cart.wait_loaded().names()) == Counter([keep, from_cart])
    flow.cart.remove(from_cart)
    assert flow.cart.names() == [keep]
    assert flow.navbar.cart_count() == 1

    flow.cart.continue_shopping()
    flow.inventory.wait_loaded()
    assert flow.inventory.in_cart(keep)
    assert not flow.inventory.in_cart(from_card)
    assert not flow.inventory.in_cart(from_cart)


# --------------------------------------------------------------------------- #
# Checkout
# --------------------------------------------------------------------------- #
def checkout_form_validation(flow: StoreFlow, case: CheckoutFormCase) -> None:
    flow.login()
    assert flow.add_products([RELIABLE_PRODUCT]) == [RELIABLE_PRODUCT]
    error = flow.start_checkout(case.first_name, case.last_name, case.postal_code)
    assert error == case.expected_error
    on_overview = flow.overview.PATH in flow.page.url
    assert on_overview is case.should_succeed, f"unexpected page {flow.page.url}"


def order_total_matches_the_catalogue(flow: StoreFlow, order: OrderCase) -> None:
    flow.login()
    prices = flow.catalogue_prices()
    expected = {name: prices[name] for name in order.products}
    assert flow.add_products(order.products) == list(order.products)

    assert flow.start_checkout_as_configured() == ""
    flow.verify_order(expected)
    assert flow.place_order() == CONFIRMATION
    assert flow.navbar.cart_count() == 0


# --------------------------------------------------------------------------- #
# Personas
# --------------------------------------------------------------------------- #
def persona_behaves_as_documented(flow: StoreFlow, persona: PersonaCase) -> None:
    allure.dynamic.description(persona.description)
    elapsed_ms = flow.login(persona.username)
    flow.inventory.attach_text(f"{elapsed_ms:.0f} ms", name="login-to-catalogue")
    if persona.min_login_ms:
        assert elapsed_ms >= persona.min_login_ms, (
            f"{persona.username}: catalogue rendered after {elapsed_ms:.0f} ms, expected the "
            f"documented slowdown (>= {persona.min_login_ms} ms)"
        )
    prices = flow.catalogue_prices()

    with allure.step("Sort by price, high to low"):
        flow.inventory.sort_by("hilo")
        shown = [item.price for item in flow.inventory.items()]
        is_sorted = shown == sorted(shown, reverse=True)  # type: ignore[type-var]
        assert is_sorted is persona.sort_applies, f"sort applied: {is_sorted}, prices {shown}"

    with allure.step("Add products from the catalogue"):
        sticks = flow.inventory.add(persona.sample_product)
        assert sticks is persona.sample_add_sticks
        assert flow.inventory.add(RELIABLE_PRODUCT)
        in_cart = [RELIABLE_PRODUCT, *([persona.sample_product] if sticks else [])]
        assert flow.navbar.cart_count() == len(in_cart)

    with allure.step("Check out with complete customer details"):
        error = flow.start_checkout_as_configured()
        assert error == persona.checkout_error
        if not error:
            flow.verify_order({name: prices[name] for name in in_cart})
