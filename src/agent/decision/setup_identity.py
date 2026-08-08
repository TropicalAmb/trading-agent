"""Persistent setup identity — suppress re-entry from the same structural setup."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def structural_setup_key(
    *,
    symbol: str,
    strategy: str,
    direction: str,
    level: float | None = None,
    entry: float | None = None,
) -> str:
    """Bar-independent structural identity (same pullback zone across 5m bars)."""
    lvl = round(float(level if level is not None else entry or 0.0), 1)
    return f"{symbol.upper()}|{strategy}|{direction.upper()}|l{lvl}"


def setup_fingerprint(
    *,
    symbol: str,
    strategy: str,
    direction: str,
    market_bar_ts: datetime | str,
    entry: float,
    level: float | None = None,
) -> str:
    """Identity for a setup instance (not wall-clock scan time)."""
    if isinstance(market_bar_ts, datetime):
        bar = market_bar_ts.replace(tzinfo=None).isoformat(timespec="minutes")
    else:
        bar = str(market_bar_ts)[:16]
    # Round entry/level so tiny noise doesn't create a "new" setup
    e = round(float(entry), 1)
    lvl = round(float(level if level is not None else entry), 1)
    return f"{symbol.upper()}|{strategy}|{direction.upper()}|{bar}|e{e}|l{lvl}"


class SetupIdentityStore:
    def __init__(self, path: str | Path = "data/setup_identities.json"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._data: dict[str, Any] = {"traded": {}, "seen": {}}
        self._load()

    def _load(self) -> None:
        if self.path.exists():
            try:
                self._data = json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:
                self._data = {"traded": {}, "seen": {}}

    def _save(self) -> None:
        self.path.write_text(json.dumps(self._data, indent=2), encoding="utf-8")

    def already_traded(self, fp: str) -> bool:
        return fp in (self._data.get("traded") or {})

    def mark_traded(self, fp: str, meta: dict[str, Any] | None = None) -> None:
        self._data.setdefault("traded", {})[fp] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            **(meta or {}),
        }
        # Keep last 2000
        traded = self._data["traded"]
        if len(traded) > 2000:
            keys = sorted(traded.keys(), key=lambda k: traded[k].get("ts", ""))[-2000:]
            self._data["traded"] = {k: traded[k] for k in keys}
        self._save()

    def mark_seen(self, fp: str) -> None:
        self._data.setdefault("seen", {})[fp] = datetime.now(timezone.utc).isoformat()
        self._save()

    def already_seen(self, fp: str, *, max_age_seconds: float = 10800.0) -> bool:
        """True if structural key was seen recently (default 3h cooldown)."""
        raw = (self._data.get("seen") or {}).get(fp)
        if not raw:
            return False
        try:
            ts = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            age = (datetime.now(timezone.utc) - ts).total_seconds()
            if age > float(max_age_seconds):
                self.clear_seen(fp)
                return False
            return True
        except Exception:
            return True

    def clear_seen(self, fp: str) -> None:
        seen = self._data.setdefault("seen", {})
        if fp in seen:
            del seen[fp]
            self._save()
