"""Pytest fixtures & reporting hooks.

Fixture graph (all config-driven via ``Settings``):

    settings (session)
      └─ playwright (session)
           └─ browser (session)
                └─ context (function, tracing on)
                     └─ page (function)
                          └─ flow (function)  -> StoreFlow (page objects composed)

On failure a full-page screenshot and the Playwright trace are attached to
Allure; on success the trace is discarded to keep artifacts small.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Iterator
from pathlib import Path

import allure
import pytest
from playwright.sync_api import Browser, BrowserContext, Page, Playwright, sync_playwright

from qa_framework.config.settings import Settings
from qa_framework.core.browser_factory import BrowserFactory
from qa_framework.flows.store_flow import StoreFlow
from qa_framework.utils.attachments import Reporter
from qa_framework.utils.text import slugify


# --------------------------------------------------------------------------- #
# Outcome bookkeeping: make the test result visible to fixtures.
# --------------------------------------------------------------------------- #
@pytest.hookimpl(wrapper=True)
def pytest_runtest_makereport(item, call):
    rep = yield
    setattr(item, f"rep_{rep.when}", rep)
    return rep


def _failed(request: pytest.FixtureRequest) -> bool:
    setup = getattr(request.node, "rep_setup", None)
    call = getattr(request.node, "rep_call", None)
    return bool((setup and setup.failed) or (call and call.failed))


# --------------------------------------------------------------------------- #
# Live e2e is opt-in: it needs network access to the real site.
# --------------------------------------------------------------------------- #
def _e2e_enabled() -> bool:
    return os.getenv("QA_RUN_E2E", "").strip().lower() in {"1", "true", "yes", "on"}


def pytest_collection_modifyitems(config, items):
    if _e2e_enabled():
        return
    skip = pytest.mark.skip(reason="live e2e disabled; set QA_RUN_E2E=1 to run")
    for item in items:
        if "e2e" in item.keywords:
            item.add_marker(skip)


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="session")
def settings() -> Settings:
    return Settings.load()


@pytest.fixture(scope="session")
def playwright() -> Iterator[Playwright]:
    with sync_playwright() as pw:
        yield pw


@pytest.fixture(scope="session")
def browser(playwright: Playwright, settings: Settings) -> Iterator[Browser]:
    browser = BrowserFactory(settings).launch(playwright)
    yield browser
    browser.close()


@pytest.fixture
def context(
    browser: Browser, settings: Settings, request: pytest.FixtureRequest
) -> Iterator[BrowserContext]:
    context = BrowserFactory(settings).new_context(browser)
    context.tracing.start(screenshots=True, snapshots=True, sources=True)
    trace_path: Path | None = (
        settings.artifacts_dir / f"trace-{slugify(request.node.name, lower=False)}.zip"
    )
    try:
        yield context
    finally:
        try:
            context.tracing.stop(path=str(trace_path))
        except Exception:
            trace_path = None
        try:
            if trace_path and trace_path.exists():
                if _failed(request):
                    allure.attach.file(str(trace_path), name="playwright-trace", extension="zip")
                else:
                    trace_path.unlink()  # keep artifacts tidy on success
        finally:
            context.close()  # always release the context, even if attach/unlink fails


@pytest.fixture
def page(
    context: BrowserContext, request: pytest.FixtureRequest, settings: Settings
) -> Iterator[Page]:
    page = context.new_page()
    yield page
    if _failed(request):
        Reporter(settings.artifacts_dir).screenshot(
            page, f"FAILURE-{request.node.name}", full_page=True
        )
    page.close()


@pytest.fixture
def flow(page: Page, settings: Settings) -> StoreFlow:
    return StoreFlow(page, settings)


# --------------------------------------------------------------------------- #
# Allure environment metadata (shown on the report's "Environment" widget).
# --------------------------------------------------------------------------- #
def pytest_sessionfinish(session, exitstatus):
    try:
        s = Settings.load()
    except Exception:
        return
    # Anchor to the pytest rootdir so this works regardless of the CWD.
    allure_dir = Path(session.config.rootpath) / "reports" / "allure-results"
    if not allure_dir.exists():
        return
    (allure_dir / "environment.properties").write_text(
        "\n".join(
            [
                f"Profile={s.profile}",
                f"Browser={s.browser.name}",
                f"Headless={s.browser.headless}",
                f"BaseURL={s.base_url}",
                f"LiveE2E={_e2e_enabled()}",
                f"Python={sys.version.split()[0]}",
            ]
        ),
        encoding="utf-8",
    )
