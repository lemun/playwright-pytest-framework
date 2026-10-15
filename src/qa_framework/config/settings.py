"""Typed, layered configuration.

Resolution order (lowest -> highest precedence):

    config.yaml base values
        -> profile overrides   (profiles.<QA_PROFILE>, deep-merged)
            -> environment variables / .env

Everything the framework needs at runtime is funnelled through the immutable
``Settings`` object, so tests and page objects never read ``os.environ`` or YAML
directly. That keeps configuration in one place (SRP) and makes the suite
data-driven across environments and profiles.
"""

from __future__ import annotations

import copy
import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

from qa_framework.paths import PROJECT_ROOT

DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "config.yaml"

_TRUE_STRINGS = {"1", "true", "yes", "on"}
_FALSE_STRINGS = {"0", "false", "no", "off", ""}


def _as_bool(value: Any, *, field: str = "value") -> bool:
    """Strict boolean coercion. Raises on a typo so e.g. QA_HEADLESS=ture
    fails loudly instead of silently launching in the wrong mode."""
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in _TRUE_STRINGS:
        return True
    if text in _FALSE_STRINGS:
        return False
    raise ValueError(f"{field} must be a boolean (true/false), got {value!r}")


def _as_int(value: Any, *, field: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field} must be an integer, got {value!r}") from None


def _as_rate(value: Any) -> Decimal:
    """A rate in [0, 1) as an exact Decimal (via ``str`` so 0.08 stays 0.08)."""
    try:
        rate = Decimal(str(value))
    except InvalidOperation:
        raise ValueError(f"store.tax_rate must be a number, got {value!r}") from None
    if not Decimal(0) <= rate < Decimal(1):
        raise ValueError(f"store.tax_rate must be in [0, 1), got {value!r}")
    return rate


def _deep_merge(base: Mapping[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    """Recursively merge ``override`` onto a copy of ``base``."""
    merged = copy.deepcopy(dict(base))
    for key, value in (override or {}).items():
        if isinstance(value, Mapping) and isinstance(merged.get(key), Mapping):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


# --------------------------------------------------------------------------- #
# Strongly-typed configuration sections
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Viewport:
    width: int = 1440
    height: int = 900


@dataclass(frozen=True)
class BrowserConfig:
    name: str = "chromium"
    headless: bool = True
    slow_mo_ms: int = 0
    viewport: Viewport = field(default_factory=Viewport)
    locale: str = "en-US"
    timezone: str = "UTC"


@dataclass(frozen=True)
class Timeouts:
    default_ms: int = 10000
    navigation_ms: int = 30000


@dataclass(frozen=True)
class StoreConfig:
    #: Sales tax the store adds at checkout; the order-total check uses it.
    tax_rate: Decimal = Decimal("0.08")


@dataclass(frozen=True)
class AuthConfig:
    username: str = ""
    password: str = field(default="", repr=False)  # never echoed in logs/reprs


@dataclass(frozen=True)
class CheckoutInfo:
    first_name: str = "Test"
    last_name: str = "Buyer"
    postal_code: str = "10001"


@dataclass(frozen=True)
class Settings:
    base_url: str
    browser: BrowserConfig
    timeouts: Timeouts
    store: StoreConfig
    auth: AuthConfig
    checkout: CheckoutInfo
    artifacts_dir: Path
    profile: str

    def url(self, path: str = "/") -> str:
        """Absolute URL for an app path, e.g. ``settings.url("/cart.html")``."""
        return self.base_url.rstrip("/") + "/" + path.lstrip("/")

    # ------------------------------------------------------------------ #
    # Factory
    # ------------------------------------------------------------------ #
    @classmethod
    def load(cls, config_path: Path | None = None, profile: str | None = None) -> Settings:
        load_dotenv(PROJECT_ROOT / ".env", override=False)

        config_path = Path(config_path or DEFAULT_CONFIG_PATH)
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}

        profile = profile or os.getenv("QA_PROFILE") or "local"
        profiles = raw.pop("profiles", {}) or {}
        if profile not in profiles:
            raise ValueError(f"Unknown profile '{profile}'. Available: {sorted(profiles)}")
        cfg = _deep_merge(raw, profiles[profile] or {})

        browser_raw = cfg.get("browser", {})
        viewport_raw = browser_raw.get("viewport", {})
        timeouts_raw = cfg.get("timeouts", {})
        store_raw = cfg.get("store", {})
        auth_raw = cfg.get("auth", {})
        checkout_raw = cfg.get("checkout", {})

        # ---- env overrides (highest precedence) ----
        browser = BrowserConfig(
            name=os.getenv("QA_BROWSER", browser_raw.get("name", "chromium")),
            headless=_as_bool(
                os.getenv("QA_HEADLESS", browser_raw.get("headless", True)),
                field="QA_HEADLESS",
            ),
            slow_mo_ms=_as_int(
                os.getenv("QA_SLOWMO_MS", browser_raw.get("slow_mo_ms", 0)),
                field="QA_SLOWMO_MS",
            ),
            viewport=Viewport(
                width=_as_int(viewport_raw.get("width", 1440), field="viewport.width"),
                height=_as_int(viewport_raw.get("height", 900), field="viewport.height"),
            ),
            locale=os.getenv("QA_LOCALE", browser_raw.get("locale", "en-US")),
            timezone=os.getenv("QA_TIMEZONE", browser_raw.get("timezone", "UTC")),
        )

        timeouts = Timeouts(
            default_ms=_as_int(
                os.getenv("QA_TIMEOUT_DEFAULT_MS", timeouts_raw.get("default_ms", 10000)),
                field="QA_TIMEOUT_DEFAULT_MS",
            ),
            navigation_ms=_as_int(
                os.getenv("QA_TIMEOUT_NAV_MS", timeouts_raw.get("navigation_ms", 30000)),
                field="QA_TIMEOUT_NAV_MS",
            ),
        )

        store = StoreConfig(tax_rate=_as_rate(store_raw.get("tax_rate", "0.08")))

        auth = AuthConfig(
            username=os.getenv("QA_USERNAME") or str(auth_raw.get("username", "")),
            password=os.getenv("QA_PASSWORD") or str(auth_raw.get("password", "")),
        )

        checkout = CheckoutInfo(
            first_name=str(checkout_raw.get("first_name", "Test")),
            last_name=str(checkout_raw.get("last_name", "Buyer")),
            postal_code=str(checkout_raw.get("postal_code", "10001")),
        )

        artifacts_dir = PROJECT_ROOT / cfg.get("artifacts", {}).get("dir", "reports/artifacts")
        artifacts_dir.mkdir(parents=True, exist_ok=True)

        return cls(
            base_url=os.getenv("QA_BASE_URL", cfg.get("base_url", "https://www.saucedemo.com")),
            browser=browser,
            timeouts=timeouts,
            store=store,
            auth=auth,
            checkout=checkout,
            artifacts_dir=artifacts_dir,
            profile=profile,
        )
