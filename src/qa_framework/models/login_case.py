"""Data-driven login case: who logs in, and what the store should answer."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class LoginCase:
    id: str
    username: str
    password: str = field(repr=False)
    #: Expected error banner text; empty means the login must succeed.
    expected_error: str = ""

    @property
    def should_succeed(self) -> bool:
        return not self.expected_error

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> LoginCase:
        try:
            return cls(
                id=str(raw["id"]),
                username=str(raw.get("username") or ""),
                password=str(raw.get("password") or ""),
                expected_error=str(raw.get("expected_error") or ""),
            )
        except KeyError as exc:
            raise ValueError(f"Login case missing required key {exc} in {raw!r}") from exc

    @classmethod
    def load_all(cls, path: str | Path) -> list[LoginCase]:
        from qa_framework.utils.data_loader import DataLoader

        return [cls.from_dict(row) for row in DataLoader.load(path)]
