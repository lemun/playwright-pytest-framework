"""Capture screenshots / text and route them to both Allure and the artifacts dir.

Keeping this in one place means page objects just call ``reporter.screenshot(...)``
without knowing how reporting is wired (SRP). Allure attachments degrade
gracefully: if Allure is not active the screenshot is still saved to disk.
"""

from __future__ import annotations

import time
from pathlib import Path

import allure
from playwright.sync_api import Page

from qa_framework.utils.text import slugify


class Reporter:
    """Binds reporting to a target directory; one instance per test run/page."""

    def __init__(self, artifacts_dir: Path):
        self.artifacts_dir = Path(artifacts_dir)
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)

    def screenshot(self, page: Page, name: str, full_page: bool = False) -> Path | None:
        """Take a screenshot, attach it to Allure, and save a PNG to disk."""
        try:
            data = page.screenshot(full_page=full_page)
        except Exception:  # a closed/crashed page must never fail the test here
            return None

        allure.attach(data, name=name, attachment_type=allure.attachment_type.PNG)

        path = self.artifacts_dir / f"{int(time.time() * 1000)}-{slugify(name)}.png"
        path.write_bytes(data)
        return path

    def attach_text(self, content: str, name: str) -> None:
        allure.attach(content, name=name, attachment_type=allure.attachment_type.TEXT)
