"""Fixtures for the offline integration layer: the real page objects and flow,
pointed at the in-process fake store instead of the live site."""

from __future__ import annotations

from dataclasses import replace

import pytest
from fake_store import BASE_URL, FakeStore
from playwright.sync_api import BrowserContext, Page

from qa_framework.config.settings import Settings
from qa_framework.flows.store_flow import StoreFlow


@pytest.fixture
def store(context: BrowserContext) -> FakeStore:
    fake = FakeStore()
    fake.install(context)
    return fake


@pytest.fixture
def offline_settings(settings: Settings) -> Settings:
    return replace(settings, base_url=BASE_URL)


@pytest.fixture
def offline_flow(page: Page, offline_settings: Settings, store: FakeStore) -> StoreFlow:
    return StoreFlow(page, offline_settings)
