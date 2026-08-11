"""Standardized R-space metrics + acceptance gates + anti-cheat checks."""

from __future__ import annotations

from typing import Any, Sequence

import numpy as np
import pandas as pd

# Research aspirational accuracy target (track WR; do not block paper on this alone)
GATES = {
    "min_wr": 0.65,
    "min_pf": 1.50,
    "min_expectancy_r": 0.25,
    "min_n": 100,
    "max_worst_loss_r": -5.0,  # reject catastrophic single-trade tails
    "min_med_win_over_med_loss": 0.35,  # reject tiny-target / huge-stop games
}

# Soft paper-promotion bar (edge-first). WR is a metric, not a hard blocker.
PAPER_GATES = {
    "min_wr": 0.0,  # tracked only
    "min_pf": 1.20,
    "min_expectancy_r": 0.0,  # must be > 0 via meets_paper_gates
    "min_n": 30,
    "max_worst_loss_r": -5.0,
    "min_med_win_over_med_loss": 0.35,
}


def trade_stats(pnl_r: Sequence[float], entry_ts: Sequence[str] | None = None) -> dict[str, Any]:
    if not len(pnl_r):
        return {
            "n": 0,
            "wins": 0,
            "losses": 0,
            "wr": 0.0,
            "wr_ci95": [0.0, 0.0],
            "pf": 0.0,
            "expectancy_r": 0.0,
            "max_dd_r": 0.0,
            "avg_win_r": 0.0,
            "avg_loss_r": 0.0,
            "med_win_r": 0.0,
            "med_loss_r": 0.0,
            "worst_r": 0.0,
            "p95_loss_r": 0.0,
            "trades_per_week": 0.0,
            "longest_losing_streak": 0,
            "anti_cheat_ok": True,
            "anti_cheat_reasons": [],
        }
    rs = np.asarray(list(pnl_r), dtype=float)
    wins = rs[rs > 0]
    losses = rs[rs <= 0]
    gw = float(wins.sum()) if len(wins) else 0.0
    gl = float(abs(losses.sum())) if len(losses) else 0.0
    rng = np.random.default_rng(42)
    boots = [float((rng.choice(rs, size=len(rs), replace=True) > 0).mean()) for _ in range(400)]
    lo, hi = float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))
    equity = np.cumsum(rs)
    peak = np.maximum.accumulate(equity)
    dd = float((equity - peak).min())
    streak = cur = 0
    for x in rs:
        if x <= 0:
            cur += 1
            streak = max(streak, cur)
        else:
            cur = 0
    weeks = 1.0
    if entry_ts:
        ts = pd.to_datetime(list(entry_ts), utc=True, errors="coerce").dropna()
        if len(ts) >= 2:
            weeks = max((ts.max() - ts.min()).total_seconds() / (7 * 86400), 1 / 7)
    med_w = float(np.median(wins)) if len(wins) else 0.0
    med_l = float(abs(np.median(losses))) if len(losses) else 0.0
    reasons: list[str] = []
    if len(wins) and len(losses) and med_l > 0 and (med_w / med_l) < GATES["min_med_win_over_med_loss"]:
        reasons.append("tiny_target_or_huge_stop")
    if float(rs.min()) <= GATES["max_worst_loss_r"]:
        reasons.append("catastrophic_tail")
    return {
        "n": int(len(rs)),
        "wins": int(len(wins)),
        "losses": int(len(losses)),
        "wr": round(float((rs > 0).mean()), 4),
        "wr_ci95": [round(lo, 4), round(hi, 4)],
        "pf": round(gw / gl, 3) if gl > 0 else (999.0 if gw > 0 else 0.0),
        "expectancy_r": round(float(rs.mean()), 4),
        "max_dd_r": round(dd, 3),
        "avg_win_r": round(float(wins.mean()), 3) if len(wins) else 0.0,
        "avg_loss_r": round(float(losses.mean()), 3) if len(losses) else 0.0,
        "med_win_r": round(med_w, 3),
        "med_loss_r": round(float(np.median(losses)), 3) if len(losses) else 0.0,
        "worst_r": round(float(rs.min()), 3),
        "p95_loss_r": round(float(np.percentile(losses, 5)), 3) if len(losses) else 0.0,
        "trades_per_week": round(len(rs) / weeks, 2),
        "longest_losing_streak": int(streak),
        "anti_cheat_ok": len(reasons) == 0,
        "anti_cheat_reasons": reasons,
    }


def meets_gates(st: dict[str, Any]) -> bool:
    """Hard research accuracy gates (≥65% WR aspirational)."""
    return (
        st.get("n", 0) >= GATES["min_n"]
        and st.get("wr", 0) >= GATES["min_wr"]
        and st.get("pf", 0) >= GATES["min_pf"]
        and st.get("expectancy_r", 0) >= GATES["min_expectancy_r"]
        and st.get("anti_cheat_ok", False)
        and st.get("worst_r", 0) > GATES["max_worst_loss_r"]
    )


def meets_paper_gates(st: dict[str, Any]) -> bool:
    """Soft paper-promotion: positive expectancy + PF + sample. WR not required."""
    return (
        st.get("n", 0) >= PAPER_GATES["min_n"]
        and st.get("pf", 0) >= PAPER_GATES["min_pf"]
        and st.get("expectancy_r", 0) > PAPER_GATES["min_expectancy_r"]
        and st.get("anti_cheat_ok", False)
        and st.get("worst_r", 0) > PAPER_GATES["max_worst_loss_r"]
    )
