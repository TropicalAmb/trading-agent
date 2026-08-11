"""Contextual strategy-cell health (not global strategy bans)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agent.learning.shrink import shrink_expectancy, shrink_rate


def cell_key(strategy: str, symbol: str, session: str, regime: str, direction: str) -> str:
    return "|".join(
        [
            str(strategy or "unknown"),
            str(symbol or "").upper(),
            str(session or "unknown").lower().split()[0],
            str(regime or "UNKNOWN").upper(),
            str(direction or "UNKNOWN").upper(),
        ]
    )


def evaluate_cell_health(
    rs: list[float],
    *,
    min_n: int = 30,
    global_wr: float = 0.5,
    global_e: float = 0.0,
) -> dict[str, Any]:
    n = len(rs)
    if n < min_n:
        return {
            "state": "ACTIVE",
            "reason": f"insufficient_sample n={n}",
            "n": n,
            "shrunk_wr": None,
            "expectancy_r": None,
        }
    wins = sum(1 for r in rs if r > 0)
    shr = shrink_rate(wins, n, prior_mean=global_wr, prior_strength=20.0)
    e = shrink_expectancy(rs, prior_mean=global_e, prior_strength=20.0)
    # Recent vs long-term drift
    recent = rs[-max(10, n // 5) :]
    recent_e = sum(recent) / len(recent)
    drift = recent_e - e
    state = "ACTIVE"
    reason = "ok"
    if e < -0.05 and shr.shrunk < 0.48:
        state = "SHADOW_ONLY"
        reason = "sustained_negative_expectancy"
    elif e < 0 or shr.shrunk < 0.50:
        state = "DOWNWEIGHTED"
        reason = "weak_expectancy_or_wr"
    if drift < -0.25 and len(recent) >= 15 and e > 0:
        state = "DOWNWEIGHTED"
        reason = "PERFORMANCE_DRIFT"
    return {
        "state": state,
        "reason": reason,
        "n": n,
        "raw_wr": wins / n,
        "shrunk_wr": shr.shrunk,
        "expectancy_r": e,
        "recent_expectancy_r": recent_e,
        "drift": drift,
    }


class StrategyHealthStore:
    def __init__(self, path: str | Path = "data/learning/strategy_cell_health.json"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._state: dict[str, Any] = {}
        self.load()

    def load(self) -> None:
        if self.path.exists():
            try:
                self._state = json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:
                self._state = {}
        self._state.setdefault("cells", {})

    def save(self) -> None:
        self.path.write_text(json.dumps(self._state, indent=2), encoding="utf-8")

    def get(self, key: str) -> str:
        cell = (self._state.get("cells") or {}).get(key) or {}
        return str(cell.get("state") or "ACTIVE")

    def update(self, key: str, state: str, *, note: str = "") -> None:
        cells = self._state.setdefault("cells", {})
        prev = dict(cells.get(key) or {})
        prev["state"] = str(state)
        if note:
            prev["note"] = note
        cells[key] = prev
        self.save()

    def update_from_router_cells(self, cells: dict[tuple, list[float]], *, min_n: int = 30) -> dict[str, Any]:
        # cells keys from StrategyPerformanceRouter are ("strategy,symbol,...", v1, v2, ...)
        all_r: list[float] = []
        for rs in cells.values():
            all_r.extend(rs)
        g_wr = (sum(1 for r in all_r if r > 0) / len(all_r)) if all_r else 0.5
        g_e = (sum(all_r) / len(all_r)) if all_r else 0.0
        updated = {}
        for full, rs in cells.items():
            # Only exact 5-dim cells
            if not full or not str(full[0]).startswith("strategy,symbol,session,regime,direction"):
                continue
            if len(full) < 6:
                continue
            key = cell_key(full[1], full[2], full[3], full[4], full[5])
            verdict = evaluate_cell_health(rs, min_n=min_n, global_wr=g_wr, global_e=g_e)
            self._state["cells"][key] = verdict
            updated[key] = verdict
        self.save()
        return updated
