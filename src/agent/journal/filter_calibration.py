"""Filter-calibration advisory — never auto-changes thresholds."""

from __future__ import annotations

from typing import Any


def _bucket_stats(trades: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(trades)
    if n == 0:
        return {
            "count": 0,
            "net_pnl": 0.0,
            "wins": 0,
            "losses": 0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "expectancy": 0.0,
            "average_r": 0.0,
        }
    pnls = [float(t.get("pnl_dollars") or 0) for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    gw = sum(wins)
    gl = abs(sum(losses))
    rs = [float(t["r_achieved"]) for t in trades if t.get("r_achieved") is not None]
    return {
        "count": n,
        "net_pnl": round(sum(pnls), 2),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": round(len(wins) / max(len(wins) + len(losses), 1), 3),
        "profit_factor": round(gw / gl, 3) if gl > 0 else (999.0 if gw > 0 else 0.0),
        "expectancy": round(sum(pnls) / n, 2),
        "average_r": round(sum(rs) / len(rs), 3) if rs else 0.0,
    }


def build_filter_calibration(
    *,
    actual_trades: list[dict[str, Any]],
    shadow_trades: list[dict[str, Any]],
    min_b_sample: int = 30,
) -> dict[str, Any]:
    a_plus = [
        t
        for t in actual_trades
        if str(t.get("setup_tier") or t.get("tier") or "").upper() == "A+"
        and str(t.get("execution_mode", "ACTUAL")).upper() != "SHADOW"
    ]
    a = [
        t
        for t in actual_trades
        if str(t.get("setup_tier") or t.get("tier") or "").upper() == "A"
        and str(t.get("execution_mode", "ACTUAL")).upper() != "SHADOW"
    ]
    b_shadow = [
        t
        for t in shadow_trades
        if str(t.get("tier") or t.get("setup_tier") or "").upper() == "B"
        and str(t.get("status") or "").upper() == "CLOSED"
    ]
    c_shadow = [
        t
        for t in shadow_trades
        if str(t.get("tier") or t.get("setup_tier") or "").upper() == "C"
        and str(t.get("status") or "").upper() == "CLOSED"
    ]

    a_stats = _bucket_stats(a)
    ap_stats = _bucket_stats(a_plus)
    b_stats = _bucket_stats(b_shadow)
    c_stats = _bucket_stats(c_shadow)

    if b_stats["count"] < min_b_sample:
        assessment = "INSUFFICIENT_DATA"
        note = f"B shadow closed={b_stats['count']} < min {min_b_sample}"
    elif b_stats["expectancy"] <= 0:
        assessment = "FILTER_APPEARS_USEFUL"
        note = "B shadow expectancy ≤ 0 — keeping A minimum looks helpful"
    elif b_stats["expectancy"] > 0 and b_stats["profit_factor"] > 1.2:
        assessment = "REVIEW_THRESHOLD"
        note = "B shadow positive with PF>1.2 — review only, do not auto-change"
    else:
        assessment = "REVIEW_THRESHOLD"
        note = "B shadow mixed — keep thresholds"

    if (
        b_stats["count"] >= min_b_sample
        and a_stats["count"] >= min_b_sample
        and b_stats["expectancy"] > a_stats["expectancy"] * 1.25
        and b_stats["profit_factor"] > a_stats["profit_factor"]
    ):
        assessment = "POSSIBLE_OVERFILTERING"
        note = "B expectancy strongly exceeds A over sufficient sample — advisory only"

    return {
        "A_PLUS_actual": ap_stats,
        "A_actual": a_stats,
        "B_shadow": b_stats,
        "C_shadow": c_stats,
        "FILTER_ASSESSMENT": assessment,
        "note": note,
        "min_b_sample": min_b_sample,
    }


def performance_by_config_version(trades: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[str, list[dict[str, Any]]] = {}
    for t in trades:
        if str(t.get("execution_mode", "ACTUAL")).upper() == "SHADOW":
            continue
        if str(t.get("source", "")) == "demo":
            continue
        if str(t.get("exit_reason", "")) in {"universe_prune", "corr_conflict_prune"}:
            continue
        ver = str(t.get("config_version") or "LEGACY_UNKNOWN")
        buckets.setdefault(ver, []).append(t)
    out = []
    for ver, rows in sorted(buckets.items()):
        s = _bucket_stats(rows)
        s["config_version"] = ver
        out.append(s)
    return out
