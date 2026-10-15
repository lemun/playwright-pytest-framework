"""Data-driven input loader — JSON / YAML / CSV behind one API.

    DataLoader.load("data/orders.json")   # -> list[dict]
    DataLoader.load("data/orders.yaml")
    DataLoader.load("data/orders.csv")

Format is inferred from the file extension, so test data can be swapped without
touching code (e.g. ``QA_ORDERS=data/orders.yaml``).
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import yaml

from qa_framework.paths import PROJECT_ROOT


class DataLoader:
    """Stateless loader; resolves relative paths against the project root."""

    @staticmethod
    def _resolve(path: str | Path) -> Path:
        p = Path(path)
        return p if p.is_absolute() else (PROJECT_ROOT / p)

    @classmethod
    def load(cls, path: str | Path) -> Any:
        resolved = cls._resolve(path)
        if not resolved.exists():
            raise FileNotFoundError(f"Data file not found: {resolved}")

        suffix = resolved.suffix.lower()
        text = resolved.read_text(encoding="utf-8")

        if suffix == ".json":
            return json.loads(text)
        if suffix in {".yaml", ".yml"}:
            return yaml.safe_load(text)
        if suffix == ".csv":
            return cls._load_csv(resolved)
        raise ValueError(f"Unsupported data format '{suffix}' for {resolved}")

    @staticmethod
    def _load_csv(path: Path) -> list[dict[str, str]]:
        with path.open(newline="", encoding="utf-8") as fh:
            return [dict(row) for row in csv.DictReader(fh)]
