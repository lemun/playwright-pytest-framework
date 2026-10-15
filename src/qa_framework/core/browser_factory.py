"""Creates browsers/contexts entirely from ``Settings``.

Centralising launch/context creation keeps every cross-cutting concern
(browser engine, headless, slow-mo, viewport, locale, timezone, timeouts) in one
place and driven by configuration rather than scattered across fixtures.
"""

from __future__ import annotations

from playwright.sync_api import Browser, BrowserContext, BrowserType, Playwright

from qa_framework.config.settings import Settings

_ENGINES = ("chromium", "firefox", "webkit")


class BrowserFactory:
    def __init__(self, settings: Settings):
        self.settings = settings

    def browser_type(self, playwright: Playwright) -> BrowserType:
        name = self.settings.browser.name
        if name not in _ENGINES:
            raise ValueError(f"Unsupported browser '{name}'. Use one of {_ENGINES}.")
        engine: BrowserType = getattr(playwright, name)
        return engine

    def launch(self, playwright: Playwright) -> Browser:
        return self.browser_type(playwright).launch(
            headless=self.settings.browser.headless,
            slow_mo=self.settings.browser.slow_mo_ms,
        )

    def new_context(self, browser: Browser) -> BrowserContext:
        b = self.settings.browser
        context = browser.new_context(
            viewport={"width": b.viewport.width, "height": b.viewport.height},
            locale=b.locale,
            timezone_id=b.timezone,
        )
        context.set_default_timeout(self.settings.timeouts.default_ms)
        context.set_default_navigation_timeout(self.settings.timeouts.navigation_ms)
        return context
