"""Active-market opportunity rates — exclude weekend/maintenance closed periods."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


CLOSED_REASONS = {
    "MARKET_CLOSED",
    "WEEKEND_GAP",
    "MAINTENANCE_BREAK",
    "weekend gap",
    "weekend (Saturday)",
    "CME exchange closed",
}


def is_closed_session_reason(reason: str | None) -> bool:
    if not reason:
        return False
    r = str(reason)
    rl = r.lower()
    if "weekend" in rl or "maintenance" in rl or "exchange closed" in rl:
        return True
    for token in CLOSED_REASONS:
        if token.lower() in rl:
            return True
    return False


def _bump(d: dict[str, Any], *keys: str, n: int = 1) -> None:
    cur = d
    for k in keys[:-1]:
        cur = cur.setdefault(k, {})
    last = keys[-1]
    cur[last] = int(cur.get(last, 0)) + n


def accumulate_cycle(
    store: dict[str, Any],
    *,
    session_reason: str,
    bars_processed: int,
    candidates: list[dict[str, Any]],
    executions: int,
    active: bool,
) -> dict[str, Any]:
    """Mutate and return store. Closed-session cycles do not inflate rate denominators."""
    store.setdefault("all_cycles", 0)
    store["all_cycles"] = int(store["all_cycles"]) + 1
    if not active or is_closed_session_reason(session_reason):
        store.setdefault("closed_session_cycles", 0)
        store["closed_session_cycles"] = int(store["closed_session_cycles"]) + 1
        return store

    store.setdefault("active_market_cycles", 0)
    store["active_market_cycles"] = int(store["active_market_cycles"]) + 1
    store.setdefault("market_bars_processed", 0)
    store["market_bars_processed"] = int(store["market_bars_processed"]) + int(
        bars_processed
    )
    store.setdefault("strategy_candidates", 0)
    store["strategy_candidates"] = int(store["strategy_candidates"]) + len(candidates)
    store.setdefault("actual_executions", 0)
    store["actual_executions"] = int(store["actual_executions"]) + int(executions)

    tiers = Counter(str(c.get("tier") or "").upper() for c in candidates)
    for t in ("A+", "A", "B", "C"):
        store.setdefault("tier_counts", {})
        store["tier_counts"][t] = int(store["tier_counts"].get(t, 0)) + int(tiers.get(t, 0))

    by = store.setdefault("by", {"strategy": {}, "symbol": {}, "session": {}, "regime": {}})
    for c in candidates:
        strat = str(c.get("strategy") or "unknown")
        sym = str(c.get("symbol") or "?")
        sess = str(c.get("session") or "unknown").split()[0].lower()
        regime = str(c.get("regime") or "UNKNOWN")
        tier = str(c.get("tier") or "").upper()
        for dim, key in (
            ("strategy", strat),
            ("symbol", sym),
            ("session", sess),
            ("regime", regime),
        ):
            bucket = by[dim].setdefault(key, {"candidates": 0, "A+": 0, "A": 0, "B": 0, "C": 0})
            bucket["candidates"] += 1
            if tier in bucket:
                bucket[tier] += 1
    return store


def rates(store: dict[str, Any]) -> dict[str, Any]:
    bars = max(int(store.get("market_bars_processed") or 0), 0)
    cands = int(store.get("strategy_candidates") or 0)
    tiers = store.get("tier_counts") or {}
    a_or_better = int(tiers.get("A+", 0)) + int(tiers.get("A", 0))
    execs = int(store.get("actual_executions") or 0)
    per100 = lambda n: round(100.0 * n / bars, 3) if bars else None
    flag = None
    if bars >= 200 and a_or_better == 0:
        flag = "LOW_A_TIER_FREQUENCY_REVIEW"
    return {
        "market_bars_processed": bars,
        "strategy_candidates": cands,
        "A+": int(tiers.get("A+", 0)),
        "A": int(tiers.get("A", 0)),
        "B": int(tiers.get("B", 0)),
        "C": int(tiers.get("C", 0)),
        "actual_executions": execs,
        "candidates_per_100_bars": per100(cands),
        "a_or_better_per_100_bars": per100(a_or_better),
        "executions_per_100_bars": per100(execs),
        "active_market_cycles": int(store.get("active_market_cycles") or 0),
        "closed_session_cycles_excluded": int(store.get("closed_session_cycles") or 0),
        "frequency_flag": flag,
        "by": store.get("by") or {},
    }


class OpportunityStatsStore:
    def __init__(self, path: str | Path = "data/opportunity_stats.json"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._data: dict[str, Any] = {}
        if self.path.exists():
            try:
                self._data = json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:
                self._data = {}

    def record_cycle(self, **kwargs: Any) -> dict[str, Any]:
        accumulate_cycle(self._data, **kwargs)
        self.path.write_text(json.dumps(self._data, indent=2), encoding="utf-8")
        return rates(self._data)

    def summary(self) -> dict[str, Any]:
        return rates(self._data)
