"""Header bar shared by every signed-in page: burger menu + cart link/badge.

Ported from the ``Navbar`` page object of the earlier playwright-pytest-swaglabs
prototype. It is a *component* rather than a page: it has no URL of its own and
is composed into the flow alongside the pages.
"""

from __future__ import annotations

import allure

from qa_framework.pages.base_page import BasePage


class Navbar(BasePage):
    CART_LINK = ('[data-test="shopping-cart-link"]', ".shopping_cart_link")
    CART_BADGE = ('[data-test="shopping-cart-badge"]', ".shopping_cart_badge")
    MENU_BUTTON = ("#react-burger-menu-btn", 'button:has-text("Open Menu")')
    LOGOUT = ('[data-test="logout-sidebar-link"]', "#logout_sidebar_link")
    RESET = ('[data-test="reset-sidebar-link"]', "#reset_sidebar_link")

    def cart_count(self) -> int:
        """Number shown on the cart badge; 0 when the badge is absent."""
        text = self.first_text(self.CART_BADGE)
        return int(text) if text.isdigit() else 0

    @allure.step("Open the cart from the header")
    def open_cart(self) -> None:
        self.locator_any(self.CART_LINK).first.click()

    def open_menu(self) -> None:
        self.locator_any(self.MENU_BUTTON).first.click()

    @allure.step("Log out")
    def logout(self) -> None:
        self.open_menu()
        self.locator_any(self.LOGOUT).first.click()

    @allure.step("Reset app state")
    def reset_app_state(self) -> None:
        self.open_menu()
        self.locator_any(self.RESET).first.click()
