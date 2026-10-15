"""Live login matrix (data/login_cases.yaml) and logout via the header menu.

Grew out of the login spec of the earlier playwright-pytest-swaglabs prototype;
the same data file also drives the offline integration suite.
"""

from __future__ import annotations

import allure
import pytest

from qa_framework.models import LoginCase
from qa_framework.pages import InventoryPage, LoginPage, Navbar

LOGIN_CASES = LoginCase.load_all("data/login_cases.yaml")

pytestmark = [pytest.mark.e2e, allure.epic("Demo store"), allure.feature("Login")]


@pytest.mark.parametrize("case", LOGIN_CASES, ids=[c.id for c in LOGIN_CASES])
def test_login(page, settings, case: LoginCase):
    login = LoginPage(page, settings).open_login()
    login.login(case.username, case.password)
    if case.should_succeed:
        assert InventoryPage(page, settings).wait_loaded().heading() == "Products"
    else:
        assert login.error_message() == case.expected_error


@pytest.mark.smoke
def test_logout_returns_to_login(flow, page, settings):
    flow.login()
    Navbar(page, settings).logout()
    assert LoginPage(page, settings).wait_for_any(LoginPage.USERNAME).is_visible()
    assert page.url.rstrip("/") == settings.base_url.rstrip("/")
