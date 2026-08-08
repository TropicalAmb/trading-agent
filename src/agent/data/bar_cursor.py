"""Persist last processed market bar per symbol — prevents delayed-bar re-trades."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional


class BarCursorStore:
    def __init__(self, path: str | Path = "data/bar_cursors.json"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._state: dict[str, str] = {}
        self._load()

    def _load(self) -> None:
        if self.path.exists():
            try:
                self._state = json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:
                self._state = {}

    def _save(self) -> None:
        self.path.write_text(json.dumps(self._state, indent=2), encoding="utf-8")

    def get(self, symbol: str) -> Optional[datetime]:
        raw = self._state.get(symbol.upper())
        if not raw:
            return None
        try:
            return datetime.fromisoformat(raw)
        except ValueError:
            return None

    def set(self, symbol: str, market_ts: datetime) -> None:
        self._state[symbol.upper()] = market_ts.isoformat()
        self._save()

    def already_processed(self, symbol: str, market_ts: datetime) -> bool:
        last = self.get(symbol)
        if last is None:
            return False
        # Compare naive timestamps
        a = last.replace(tzinfo=None) if last.tzinfo else last
        b = market_ts.replace(tzinfo=None) if market_ts.tzinfo else market_ts
        return a >= b
