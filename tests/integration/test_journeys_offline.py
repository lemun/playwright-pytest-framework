"""The user journeys of ``tests/journeys.py`` against the offline fake store.

Same journeys and data as the live suite, driven through the real page objects
in a real headless browser, with every request answered locally.
"""

from __future__ import annotations

import allure
import journeys as j
import pytest

pytestmark = [pytest.mark.integration, allure.epic("Fake store")]


@allure.feature("Catalogue sorting")
@pytest.mark.parametrize("case", j.SORT_OPTIONS, ids=j.ids(j.SORT_OPTIONS))
def test_sort_orders_the_rendered_list(offline_flow, case):
    j.sort_orders_the_rendered_list(offline_flow, case)


@allure.feature("Cart")
@pytest.mark.parametrize("order", j.ORDERS, ids=j.ids(j.ORDERS))
def test_cart_survives_navigation_and_reload(offline_flow, order):
    j.cart_survives_navigation_and_reload(offline_flow, order)


@allure.feature("Cart")
@pytest.mark.smoke
def test_remove_from_catalogue_and_cart(offline_flow):
    j.remove_from_catalogue_and_cart(offline_flow)


@allure.feature("Checkout form")
@pytest.mark.parametrize("case", j.CHECKOUT_FORM_CASES, ids=j.ids(j.CHECKOUT_FORM_CASES))
def test_checkout_form_validation(offline_flow, case):
    j.checkout_form_validation(offline_flow, case)


@allure.feature("Order total")
@pytest.mark.parametrize("order", j.ORDERS, ids=j.ids(j.ORDERS))
def test_order_total_matches_the_catalogue(offline_flow, order):
    j.order_total_matches_the_catalogue(offline_flow, order)


@allure.feature("Personas")
@pytest.mark.parametrize("persona", j.PERSONAS, ids=j.ids(j.PERSONAS))
def test_persona_behaves_as_documented(offline_flow, persona):
    j.persona_behaves_as_documented(offline_flow, persona)
