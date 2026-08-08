"""Per-strategy / session circuit breakers — never kill the whole agent."""

from __future__ import annotations

import json
import time
from enum import Enum
from pathlib import Path
from typing import Any


class StrategyHealth(str, Enum):
    ACTIVE = "ACTIVE"
    WATCH = "WATCH"
    PAUSED_TEMP = "PAUSED_TEMP"


class CircuitBreakerStore:
    def __init__(self, path: str | Path = "data/circuit_breakers.json"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._state: dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        if self.path.exists():
            try:
                self._state = json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:
                self._state = {}

    def _save(self) -> None:
        self.path.write_text(json.dumps(self._state, indent=2), encoding="utf-8")

    def _key(self, strategy: str, session: str) -> str:
        return f"{strategy}|{str(session).lower()}"

    def status(self, strategy: str, session: str, cfg: dict[str, Any]) -> StrategyHealth:
        cb = cfg.get("circuit_breakers") or {}
        pause_m = float(cb.get("pause_minutes", 60))
        k = self._key(strategy, session)
        row = self._state.get(k) or {}
        # Expire pause
        if row.get("state") == StrategyHealth.PAUSED_TEMP.value:
            until = float(row.get("pause_until") or 0)
            if time.time() >= until:
                row["state"] = StrategyHealth.ACTIVE.value
                row["loss_streak"] = 0
                self._state[k] = row
                self._save()
            else:
                return StrategyHealth.PAUSED_TEMP
        st = str(row.get("state") or StrategyHealth.ACTIVE.value)
        try:
            return StrategyHealth(st)
        except Exception:
            return StrategyHealth.ACTIVE

    def record_close(
        self, strategy: str, session: str, pnl: float, cfg: dict[str, Any]
    ) -> StrategyHealth:
        cb = cfg.get("circuit_breakers") or {}
        watch_n = int(cb.get("consecutive_losses_watch", 3))
        pause_n = int(cb.get("consecutive_losses_pause", 5))
        pause_m = float(cb.get("pause_minutes", 60))
        k = self._key(strategy, session)
        row = self._state.get(k) or {
            "state": StrategyHealth.ACTIVE.value,
            "loss_streak": 0,
            "trades": 0,
        }
        row["trades"] = int(row.get("trades") or 0) + 1
        if pnl < 0:
            row["loss_streak"] = int(row.get("loss_streak") or 0) + 1
        else:
            row["loss_streak"] = 0
        streak = int(row["loss_streak"])
        if streak >= pause_n:
            row["state"] = StrategyHealth.PAUSED_TEMP.value
            row["pause_until"] = time.time() + pause_m * 60.0
        elif streak >= watch_n:
            row["state"] = StrategyHealth.WATCH.value
        else:
            row["state"] = StrategyHealth.ACTIVE.value
        self._state[k] = row
        self._save()
        return self.status(strategy, session, cfg)

    def snapshot(self) -> list[dict[str, Any]]:
        out = []
        for k, v in self._state.items():
            strat, sess = k.split("|", 1)
            out.append(
                {
                    "strategy": strat,
                    "session": sess,
                    "state": v.get("state"),
                    "loss_streak": v.get("loss_streak", 0),
                    "trades": v.get("trades", 0),
                }
            )
        return out
