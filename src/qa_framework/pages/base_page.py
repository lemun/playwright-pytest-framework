"""BasePage: shared behaviour for every page object.

Design notes
------------
* **Inheritance:** every concrete page extends ``BasePage`` and inherits
  navigation, waiting, resilient-locator and reporting helpers (DRY / OOP).
* **Resilient locators:** ``locator_any`` / ``wait_for_any`` accept an *ordered*
  list of candidate selectors and resolve to whichever the current build of the
  app renders. Pages list the stable ``data-test`` hook first and a class-based
  fallback second, so a renamed test id degrades to the fallback instead of
  breaking the suite.
* **SRP:** page objects expose intent ("login", "add to cart") and delegate
  reporting to ``Reporter`` and configuration to ``Settings``.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Literal

from playwright.sync_api import Locator, Page

from qa_framework.config.settings import Settings
from qa_framework.utils.attachments import Reporter
from qa_framework.utils.logger import get_logger

WaitState = Literal["attached", "detached", "hidden", "visible"]


class BasePage:
    #: App path of the page (relative to ``settings.base_url``); ``None`` when the
    #: page is only reached by interaction.
    PATH: str | None = None

    def __init__(self, page: Page, settings: Settings, reporter: Reporter | None = None):
        self.page = page
        self.settings = settings
        self.log = get_logger(self.__class__.__name__)
        # Pages composed by a flow share one Reporter; standalone pages fall back
        # to their own.
        self.reporter = reporter or Reporter(settings.artifacts_dir)

    # ------------------------------------------------------------------ #
    # Navigation
    # ------------------------------------------------------------------ #
    def open(self, path_or_url: str | None = None) -> None:
        target = path_or_url if path_or_url is not None else self.PATH
        if target is None:
            raise ValueError(f"{type(self).__name__} has no PATH; pass a path or URL")
        url = target if "://" in target else self.settings.url(target)
        self.log.info("navigate -> %s", url)
        self.page.goto(url, wait_until="domcontentloaded")

    # ------------------------------------------------------------------ #
    # Resilient locators
    # ------------------------------------------------------------------ #
    def locator_any(self, selectors: Sequence[str], root: Locator | None = None) -> Locator:
        """Return a Locator for the first candidate selector that matches now.

        Falls back to the first selector (so a subsequent action surfaces a
        clear, single-selector error) when none currently match.
        """
        base: Page | Locator = root if root is not None else self.page
        for sel in selectors:
            loc = base.locator(sel)
            if loc.count() > 0:
                return loc
        return base.locator(selectors[0])

    def wait_for_any(
        self,
        selectors: Sequence[str],
        *,
        state: WaitState = "visible",
        timeout: int | None = None,
    ) -> Locator:
        """Wait until *any* candidate selector reaches ``state``; return its group.

        Combines the candidates into one wait: an XPath union (``|``) when the
        selectors are XPath, else a CSS selector list (``,``).
        """
        if all(sel.startswith("xpath=") for sel in selectors):
            combined = "xpath=" + " | ".join(sel.removeprefix("xpath=") for sel in selectors)
        else:
            combined = ", ".join(selectors)
        self.page.locator(combined).first.wait_for(
            state=state, timeout=timeout or self.settings.timeouts.default_ms
        )
        return self.locator_any(selectors)

    def any_of(self, selectors: Sequence[str]) -> Locator:
        """Elements matching *any* candidate CSS selector (a CSS selector list).

        Unlike ``locator_any`` this does not pick one selector up front, so it
        is safe to use inside ``filter(has=...)``, where Playwright needs a
        selector relative to the outer element rather than a page-rooted chain.
        """
        return self.page.locator(", ".join(selectors))

    @staticmethod
    def safe_text(locator: Locator, timeout: int = 2000) -> str:
        try:
            return (locator.inner_text(timeout=timeout) or "").strip()
        except Exception:
            return ""

    def first_text(self, selectors: Sequence[str], root: Locator | None = None) -> str:
        """First non-empty inner_text across an ordered selector chain."""
        base: Page | Locator = root if root is not None else self.page
        for sel in selectors:
            loc = base.locator(sel)
            if loc.count():
                text = self.safe_text(loc.first)
                if text:
                    return text
        return ""

    # ------------------------------------------------------------------ #
    # Reporting
    # ------------------------------------------------------------------ #
    def screenshot(self, name: str, full_page: bool = False) -> Path | None:
        return self.reporter.screenshot(self.page, name, full_page=full_page)

    def attach_text(self, content: str, name: str) -> None:
        self.reporter.attach_text(content, name)
