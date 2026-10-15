"""Small text helpers shared across reporting code."""

from __future__ import annotations

import re


def slugify(text: str, *, lower: bool = True) -> str:
    """Filesystem/report-safe slug.

    Collapses any run of non-alphanumerics to a single ``-`` and trims the ends.
    ``lower`` (default) lowercases first — pass ``lower=False`` to preserve case
    (e.g. when slugging a test node name). Empty input yields ``"shot"``.
    """
    s = text.lower() if lower else text
    return re.sub(r"[^A-Za-z0-9]+", "-", s).strip("-") or "shot"
