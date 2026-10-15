"""Login page (``/``).

Ported from the ``Login`` page object of the earlier playwright-pytest-swaglabs
prototype and moved onto ``BasePage`` (resilient locators, reporting).
"""

from __future__ import annotations

import allure

from qa_framework.pages.base_page import BasePage


class LoginPage(BasePage):
    PATH = "/"

    USERNAME = ('[data-test="username"]', "#user-name")
    PASSWORD = ('[data-test="password"]', "#password")
    SUBMIT = ('[data-test="login-button"]', "#login-button")
    ERROR = ('[data-test="error"]', ".error-message-container h3")

    @allure.step("Open the login page")
    def open_login(self) -> LoginPage:
        self.open()
        self.wait_for_any(self.USERNAME)
        return self

    @allure.step("Log in as '{username}'")
    def login(self, username: str, password: str) -> None:
        """Submit the form. Does not assert the outcome: callers check
        ``error_message()`` or the next page, so negative cases stay testable."""
        self.locator_any(self.USERNAME).first.fill(username)
        self.locator_any(self.PASSWORD).first.fill(password)
        self.locator_any(self.SUBMIT).first.click()

    def error_message(self) -> str:
        """The login error banner text, or ``""`` when no error is shown."""
        return self.first_text(self.ERROR)
