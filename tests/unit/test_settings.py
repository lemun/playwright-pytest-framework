"""Unit tests for the layered configuration loader."""

from __future__ import annotations

import allure
import pytest

from qa_framework.config.settings import Settings

# Config-default tests must read the YAML/profile values, not ambient env
# overrides (e.g. a QA_HEADLESS exported for a headed local run).
_ENV_OVERRIDES = (
    "QA_HEADLESS",
    "QA_BROWSER",
    "QA_BASE_URL",
    "QA_PROFILE",
    "QA_USERNAME",
    "QA_PASSWORD",
    "QA_TIMEOUT_NAV_MS",
)


@pytest.fixture
def clean_env(monkeypatch):
    for name in _ENV_OVERRIDES:
        monkeypatch.delenv(name, raising=False)


@allure.feature("Configuration · profiles & env")
@pytest.mark.smoke
def test_default_local_profile(clean_env):
    s = Settings.load(profile="local")
    assert s.profile == "local"
    assert s.base_url == "https://www.saucedemo.com"
    assert s.browser.name == "chromium"
    assert s.browser.headless is True
    assert s.auth.username == "standard_user"


def test_ci_profile_overrides_base(clean_env):
    local, ci = Settings.load(profile="local"), Settings.load(profile="ci")
    assert ci.timeouts.navigation_ms > local.timeouts.navigation_ms
    assert ci.browser == local.browser  # only timeouts differ


def test_unknown_profile_raises():
    with pytest.raises(ValueError, match="Unknown profile"):
        Settings.load(profile="does-not-exist")


def test_env_overrides_take_precedence(clean_env, monkeypatch):
    monkeypatch.setenv("QA_HEADLESS", "false")
    monkeypatch.setenv("QA_BROWSER", "firefox")
    monkeypatch.setenv("QA_USERNAME", "visual_user")
    monkeypatch.setenv("QA_BASE_URL", "https://staging.example.test/")
    s = Settings.load(profile="local")
    assert s.browser.headless is False
    assert s.browser.name == "firefox"
    assert s.auth.username == "visual_user"
    assert s.url("/cart.html") == "https://staging.example.test/cart.html"


@pytest.mark.parametrize(("name", "value"), [("QA_HEADLESS", "ture"), ("QA_TIMEOUT_NAV_MS", "x")])
def test_typos_in_env_fail_loudly(clean_env, monkeypatch, name, value):
    monkeypatch.setenv(name, value)
    with pytest.raises(ValueError, match=name):
        Settings.load(profile="local")


def test_password_is_not_in_repr(clean_env):
    assert "secret_sauce" not in repr(Settings.load(profile="local"))


def test_store_tax_rate_is_exact(clean_env):
    assert str(Settings.load(profile="local").store.tax_rate) == "0.08"


@pytest.mark.parametrize("value", ["eight", "1.5", "-0.1"])
def test_invalid_tax_rate_fails_loudly(clean_env, tmp_path, value):
    config = tmp_path / "config.yaml"
    config.write_text(f'store:\n  tax_rate: "{value}"\nprofiles:\n  local: {{}}\n')
    with pytest.raises(ValueError, match="tax_rate"):
        Settings.load(config_path=config, profile="local")
