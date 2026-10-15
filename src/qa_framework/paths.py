"""Canonical filesystem anchors, importable without pulling in config/settings.

Keeping ``PROJECT_ROOT`` here (rather than inside ``config.settings``) lets light
utilities such as the data loader resolve paths without taking a
``utils -> config`` dependency edge.
"""

from __future__ import annotations

from pathlib import Path

# This file is src/qa_framework/paths.py: parents[0]=src/qa_framework, parents[1]=src,
# parents[2]=the repo root.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
