"""Small logging helper so every component logs with a consistent format.

The root configuration is owned by pytest (see ``log_cli_*`` in pyproject.toml);
here we just hand out named loggers.
"""

from __future__ import annotations

import logging

_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
_DATEFMT = "%H:%M:%S"
_configured = False


def _ensure_configured() -> None:
    global _configured
    if _configured:
        return
    # Only attach a handler if nobody else (pytest) has configured the root yet.
    if not logging.getLogger().handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(_FORMAT, datefmt=_DATEFMT))
        logging.getLogger().addHandler(handler)
        logging.getLogger().setLevel(logging.INFO)
    _configured = True


def get_logger(name: str) -> logging.Logger:
    """Return a namespaced logger, e.g. ``get_logger("InventoryPage")``."""
    _ensure_configured()
    return logging.getLogger(f"qa_framework.{name}")
