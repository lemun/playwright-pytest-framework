"""Live user journeys on saucedemo.com, Sauce Labs' public practice store.

The journeys live in ``tests/journeys.py`` and also run offline against the
fake store. Opt-in: these run only with QA_RUN_E2E=1 (see conftest).
"""

from __future__ import annotations

import allure
import journeys as j
import pytest

pytestmark = [pytest.mark.e2e, allure.epic("Demo store")]


@allure.feature("Catalogue sorting")
@pytest.mark.parametrize("case", j.SORT_OPTIONS, ids=j.ids(j.SORT_OPTIONS))
def test_sort_orders_the_rendered_list(flow, case):
    j.sort_orders_the_rendered_list(flow, case)


@allure.feature("Cart")
@pytest.mark.parametrize("order", j.ORDERS, ids=j.ids(j.ORDERS))
def test_cart_survives_navigation_and_reload(flow, order):
    j.cart_survives_navigation_and_reload(flow, order)


@allure.feature("Cart")
@pytest.mark.smoke
def test_remove_from_catalogue_and_cart(flow):
    j.remove_from_catalogue_and_cart(flow)


@allure.feature("Checkout form")
@pytest.mark.parametrize("case", j.CHECKOUT_FORM_CASES, ids=j.ids(j.CHECKOUT_FORM_CASES))
def test_checkout_form_validation(flow, case):
    j.checkout_form_validation(flow, case)


@allure.feature("Order total")
@pytest.mark.parametrize("order", j.ORDERS, ids=j.ids(j.ORDERS))
def test_order_total_matches_the_catalogue(flow, order):
    j.order_total_matches_the_catalogue(flow, order)


@allure.feature("Personas")
@pytest.mark.parametrize("persona", j.PERSONAS, ids=j.ids(j.PERSONAS))
def test_persona_behaves_as_documented(flow, persona):
    j.persona_behaves_as_documented(flow, persona)
