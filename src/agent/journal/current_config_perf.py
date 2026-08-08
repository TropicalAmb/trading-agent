"""opt_v1+ actual A+/A vs B shadow — separate from all-time paper history."""

from __future__ import annotations

from typing import Any

from agent.journal.filter_calibration import _bucket_stats


def current_config_actual_performance(
    closed_trades: list[dict[str, Any]],
    shadow_trades: list[dict[str, Any]],
    *,
    min_version: str = "opt_v1",
) -> dict[str, Any]:
    def _is_current(t: dict[str, Any]) -> bool:
        v = str(t.get("config_version") or "")
        return bool(v) and (v == min_version or v.startswith("opt_v"))

    actual = [
        t
        for t in closed_trades
        if _is_current(t)
        and str(t.get("source", "")) != "demo"
        and str(t.get("exit_reason", ""))
        not in {"universe_prune", "corr_conflict_prune"}
        and str(t.get("execution_mode", "ACTUAL")).upper() != "SHADOW"
    ]
    a_plus = [
        t
        for t in actual
        if str(t.get("setup_tier") or t.get("tier") or "").upper() == "A+"
    ]
    a_only = [
        t for t in actual if str(t.get("setup_tier") or t.get("tier") or "").upper() == "A"
    ]
    shadow_b = [
        t
        for t in shadow_trades
        if _is_current(t)
        and str(t.get("setup_tier") or t.get("tier") or "B").upper() == "B"
        and str(t.get("status") or "CLOSED").upper() == "CLOSED"
    ]
    return {
        "config_version_floor": min_version,
        "A_PLUS_actual": _bucket_stats(a_plus),
        "A_actual": _bucket_stats(a_only),
        "B_shadow": _bucket_stats(shadow_b),
        "actual_trade_count": len(actual),
        "note": "CURRENT CONFIG ACTUAL PERFORMANCE — excludes legacy/pre-opt rows",
    }
