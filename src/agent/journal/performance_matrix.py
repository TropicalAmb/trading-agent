"""Strategy × regime × session performance matrix (analytics only)."""

from __future__ import annotations

from collections import defaultdict
from typing import Any


def _key(t: dict[str, Any]) -> tuple:
    strat = str(t.get("strategy_name") or t.get("strategy") or "unknown")
    regime = str(t.get("regime") or "UNKNOWN")
    # Group legacy pre-opt rows so the dashboard stays readable
    if strat.lower() == "unknown" and regime.upper() == "UNKNOWN":
        strat = "LEGACY_UNKNOWN"
        regime = "LEGACY_UNKNOWN"
    return (
        strat,
        regime,
        str(t.get("session") or "other").lower().split()[0],
        str(t.get("symbol") or ""),
        str(t.get("side") or t.get("direction") or ""),
        str(t.get("setup_tier") or t.get("tier") or ""),
    )


def build_performance_matrix(trades: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[tuple, dict[str, Any]] = {}
    for t in trades:
        if str(t.get("execution_mode", "ACTUAL")).upper() == "SHADOW":
            continue
        if str(t.get("source", "")) == "demo":
            continue
        if str(t.get("exit_reason", "")) in {"universe_prune", "corr_conflict_prune"}:
            continue
        k = _key(t)
        b = buckets.setdefault(
            k,
            {
                "strategy": k[0],
                "regime": k[1],
                "session": k[2],
                "symbol": k[3],
                "direction": k[4],
                "tier": k[5],
                "trade_count": 0,
                "wins": 0,
                "losses": 0,
                "net_pnl": 0.0,
                "gross_win": 0.0,
                "gross_loss": 0.0,
                "r_sum": 0.0,
                "mae": [],
                "mfe": [],
            },
        )
        pnl = float(t.get("pnl_dollars") or 0.0)
        b["trade_count"] += 1
        b["net_pnl"] += pnl
        if pnl > 0:
            b["wins"] += 1
            b["gross_win"] += pnl
        elif pnl < 0:
            b["losses"] += 1
            b["gross_loss"] += abs(pnl)
        r = t.get("r_achieved")
        if r is not None:
            b["r_sum"] += float(r)
        if t.get("mae_pts") is not None:
            b["mae"].append(float(t["mae_pts"]))
        if t.get("mfe_pts") is not None:
            b["mfe"].append(float(t["mfe_pts"]))

    out: list[dict[str, Any]] = []
    for b in buckets.values():
        n = b["trade_count"]
        wins = b["wins"]
        losses = b["losses"]
        gw, gl = b["gross_win"], b["gross_loss"]
        mae = sorted(b["mae"])
        mfe = sorted(b["mfe"])
        out.append(
            {
                "strategy": b["strategy"],
                "regime": b["regime"],
                "session": b["session"],
                "symbol": b["symbol"],
                "direction": b["direction"],
                "tier": b["tier"],
                "trade_count": n,
                "wins": wins,
                "losses": losses,
                "net_pnl": round(b["net_pnl"], 2),
                "win_rate": round(wins / max(wins + losses, 1), 3),
                "profit_factor": round(gw / gl, 3) if gl > 0 else (999.0 if gw > 0 else 0.0),
                "expectancy": round(b["net_pnl"] / max(n, 1), 2),
                "average_r": round(b["r_sum"] / max(n, 1), 3),
                "average_winner": round(gw / max(wins, 1), 2) if wins else 0.0,
                "average_loser": round(-gl / max(losses, 1), 2) if losses else 0.0,
                "median_mae": mae[len(mae) // 2] if mae else None,
                "median_mfe": mfe[len(mfe) // 2] if mfe else None,
            }
        )
    out.sort(key=lambda r: (r["strategy"], r["regime"], r["session"]))
    return out
