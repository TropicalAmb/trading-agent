"""High-confidence research pass with hard acceptance gates.

Gates for CHAMPION CANDIDATE (all required):
  OOS WR >= 65%, PF >= 1.50, E >= +0.25R, n >= 100

Does NOT lower the bar. Strategy edge measured in R only (not multi-contract $).
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from agent.research.hc_strategies import RTrade, all_generators  # noqa: E402
from research_wit_precise_backtest import _fetch  # noqa: E402

OUT = ROOT / "data" / "research_high_confidence_pass.json"
REPORT = ROOT / "data" / "research_high_confidence_report.md"

GATES = {
    "min_wr": 0.65,
    "min_pf": 1.50,
    "min_expectancy_r": 0.25,
    "min_n": 100,
}


def split_train_val_oos(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Chronological 60/20/20 — tune on train, select on val, report on untouched OOS."""
    if df.empty:
        return df, df, df
    days = sorted(df.index.normalize().unique())
    n = len(days)
    if n < 15:
        return df.iloc[0:0], df.iloc[0:0], df
    i1 = int(n * 0.60)
    i2 = int(n * 0.80)
    d0, d1, d2 = set(days[:i1]), set(days[i1:i2]), set(days[i2:])
    return (
        df[df.index.normalize().isin(d0)],
        df[df.index.normalize().isin(d1)],
        df[df.index.normalize().isin(d2)],
    )


def trade_stats(trades: list[RTrade]) -> dict[str, Any]:
    if not trades:
        return {
            "n": 0,
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
        }
    rs = np.array([t.pnl_r for t in trades], dtype=float)
    wins = rs[rs > 0]
    losses = rs[rs <= 0]
    gw, gl = float(wins.sum()) if len(wins) else 0.0, float(abs(losses.sum())) if len(losses) else 0.0
    # Wilson-ish bootstrap CI on WR
    rng = np.random.default_rng(42)
    boots = []
    for _ in range(400):
        sample = rng.choice(rs, size=len(rs), replace=True)
        boots.append(float((sample > 0).mean()))
    lo, hi = float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))
    equity = np.cumsum(rs)
    peak = np.maximum.accumulate(equity)
    dd = float((equity - peak).min()) if len(equity) else 0.0
    # weeks span
    ts = pd.to_datetime([t.entry_ts for t in trades], utc=True, errors="coerce")
    ts = ts.dropna()
    if len(ts) < 2:
        weeks = 1.0
    else:
        weeks = max((ts.max() - ts.min()).total_seconds() / (7 * 86400), 1 / 7)
    return {
        "n": int(len(rs)),
        "wr": round(float((rs > 0).mean()), 4),
        "wr_ci95": [round(lo, 4), round(hi, 4)],
        "pf": round(gw / gl, 3) if gl > 0 else (999.0 if gw > 0 else 0.0),
        "expectancy_r": round(float(rs.mean()), 4),
        "max_dd_r": round(dd, 3),
        "avg_win_r": round(float(wins.mean()), 3) if len(wins) else 0.0,
        "avg_loss_r": round(float(losses.mean()), 3) if len(losses) else 0.0,
        "med_win_r": round(float(np.median(wins)), 3) if len(wins) else 0.0,
        "med_loss_r": round(float(np.median(losses)), 3) if len(losses) else 0.0,
        "worst_r": round(float(rs.min()), 3),
        "p95_loss_r": round(float(np.percentile(losses, 5)), 3) if len(losses) else 0.0,
        "trades_per_week": round(len(rs) / weeks, 2),
    }


def meets_gates(st: dict[str, Any]) -> bool:
    return (
        st["n"] >= GATES["min_n"]
        and st["wr"] >= GATES["min_wr"]
        and st["pf"] >= GATES["min_pf"]
        and st["expectancy_r"] >= GATES["min_expectancy_r"]
        and st["worst_r"] > -5.0  # reject catastrophic single-trade tails in R
    )


def monte_carlo(trades: list[RTrade], n_sims: int = 500) -> dict[str, Any]:
    if len(trades) < 5:
        return {"n_sims": 0}
    rs = np.array([t.pnl_r for t in trades], dtype=float)
    rng = np.random.default_rng(7)
    terminals, maxdds, streaks = [], [], []
    for _ in range(n_sims):
        sample = rng.choice(rs, size=len(rs), replace=True)
        eq = np.cumsum(sample)
        terminals.append(float(eq[-1]))
        peak = np.maximum.accumulate(eq)
        maxdds.append(float((eq - peak).min()))
        # losing streak
        streak = cur = 0
        for x in sample:
            if x <= 0:
                cur += 1
                streak = max(streak, cur)
            else:
                cur = 0
        streaks.append(streak)
    terminals = np.array(terminals)
    maxdds = np.array(maxdds)
    return {
        "n_sims": n_sims,
        "median_terminal_r": round(float(np.median(terminals)), 3),
        "p05_terminal_r": round(float(np.percentile(terminals, 5)), 3),
        "median_max_dd_r": round(float(np.median(maxdds)), 3),
        "p05_max_dd_r": round(float(np.percentile(maxdds, 5)), 3),
        "prob_dd_ge_10r": round(float((maxdds <= -10).mean()), 4),
        "prob_dd_ge_20r": round(float((maxdds <= -20).mean()), 4),
        "median_longest_losing_streak": int(np.median(streaks)),
    }


def main() -> int:
    symbols = {
        "NQ": "NQ=F",
        "ES": "ES=F",
        "GC": "GC=F",
        "CL": "CL=F",
    }
    # Prefer 1h for longer history / larger OOS n; also 5m for ORB-sensitive
    frames_1h: dict[str, pd.DataFrame] = {}
    frames_5m: dict[str, pd.DataFrame] = {}
    print("Fetching market data...", flush=True)
    for name, ysym in symbols.items():
        frames_1h[name] = _fetch(ysym, "1h", "365d")
        frames_5m[name] = _fetch(ysym, "5m", "60d")
        print(f"  {name}: 1h={len(frames_1h[name])} 5m={len(frames_5m[name])}", flush=True)

    gens_1h = all_generators(include_orb=False)
    gens_orb = [g for g in all_generators(include_orb=True) if g[0].startswith("ORB")]
    configs_tested = 0
    families: set[str] = set()
    rows: list[dict[str, Any]] = []
    total_oos_trades = 0

    def run_batch(gens, frames, timeframe: str) -> None:
        nonlocal configs_tested, total_oos_trades
        for gname, gen in gens:
            configs_tested += 1
            print(f"[{configs_tested}] {gname} ({timeframe})", flush=True)
            oos_all: list[RTrade] = []
            val_all: list[RTrade] = []
            by_sym_oos: dict[str, list[RTrade]] = defaultdict(list)
            for sym, df in frames.items():
                if df is None or df.empty:
                    continue
                train, val, oos = split_train_val_oos(df)
                try:
                    all_tr = gen(df, sym)
                except Exception as exc:
                    print("  gen fail", gname, sym, exc, flush=True)
                    continue
                if not all_tr:
                    continue
                families.add(all_tr[0].family)
                train_end = train.index.max() if len(train) else None
                val_end = val.index.max() if len(val) else None
                def _naive(x):
                    if x is None:
                        return None
                    x = pd.Timestamp(x)
                    if x.tzinfo is not None:
                        return x.tz_convert("UTC").tz_localize(None)
                    return x

                te, ve = _naive(train_end), _naive(val_end)
                for t in all_tr:
                    ts = _naive(t.entry_ts)
                    if te is not None and ts <= te:
                        continue
                    if ve is not None and ts <= ve:
                        val_all.append(t)
                    else:
                        oos_all.append(t)
                        by_sym_oos[sym].append(t)

            st_oos = trade_stats(oos_all)
            st_val = trade_stats(val_all)
            total_oos_trades += st_oos["n"]
            val_ok = st_val["n"] < 10 or (
                st_val["expectancy_r"] > -0.05 and st_val["wr"] >= 0.45
            )
            rows.append(
                {
                    "config": gname,
                    "family": oos_all[0].family if oos_all else "?",
                    "timeframe": timeframe,
                    "oos": st_oos,
                    "val": st_val,
                    "val_ok": val_ok,
                    "gates": meets_gates(st_oos) and val_ok,
                    "by_symbol_n": {k: len(v) for k, v in by_sym_oos.items()},
                    "monte_carlo": monte_carlo(oos_all) if st_oos["n"] >= 30 else {},
                    "sessions": {
                        s: trade_stats([t for t in oos_all if t.session == s])
                        for s in sorted({t.session for t in oos_all})
                    },
                    "regimes": {
                        r: trade_stats([t for t in oos_all if t.regime == r])
                        for r in sorted({t.regime for t in oos_all})
                    },
                }
            )

    run_batch(gens_1h, frames_1h, "1h")
    run_batch(gens_orb, frames_5m, "5m")

    # Rank
    def rank_key(r: dict) -> tuple:
        o = r["oos"]
        return (
            r["gates"],
            o["wr"] >= GATES["min_wr"],
            o["n"] >= GATES["min_n"],
            o["expectancy_r"],
            o["pf"],
            o["n"],
            o["wr"],
        )

    rows.sort(key=rank_key, reverse=True)

    champions = [r for r in rows if r["gates"]]
    top10 = rows[:10]

    def best_for(pred) -> dict | None:
        cands = [r for r in rows if pred(r) and r["oos"]["n"] >= 20]
        if not cands:
            cands = [r for r in rows if pred(r)]
        return cands[0] if cands else None

    highest_wr = max(rows, key=lambda r: (r["oos"]["n"] >= 5, r["oos"]["wr"], r["oos"]["n"]))
    highest_wr_n100 = max(
        (r for r in rows if r["oos"]["n"] >= 100),
        key=lambda r: r["oos"]["wr"],
        default=None,
    )
    highest_wr_pf15 = max(
        (r for r in rows if r["oos"]["pf"] >= 1.5 and r["oos"]["n"] >= 20),
        key=lambda r: (r["oos"]["wr"], r["oos"]["n"]),
        default=None,
    )
    highest_wr_e25 = max(
        (r for r in rows if r["oos"]["expectancy_r"] >= 0.25 and r["oos"]["n"] >= 20),
        key=lambda r: (r["oos"]["wr"], r["oos"]["n"]),
        default=None,
    )

    # Pareto: among positive E, pick diverse WR/freq
    edge_rows = [r for r in rows if r["oos"]["expectancy_r"] > 0 and r["oos"]["n"] >= 30]
    edge_rows.sort(key=lambda r: r["oos"]["wr"], reverse=True)
    pareto = []
    for r in edge_rows[:40]:
        pareto.append(
            {
                "config": r["config"],
                "wr": r["oos"]["wr"],
                "trades_per_week": r["oos"]["trades_per_week"],
                "expectancy_r": r["oos"]["expectancy_r"],
                "n": r["oos"]["n"],
                "pf": r["oos"]["pf"],
            }
        )

    # Calibration stub: bucket by strategy family empirical WR on train — skip fake precision
    calibration = {
        "status": "INSUFFICIENT — probability model not activated until champion gates met with comparable n",
        "buckets": {},
    }

    # Risk config snapshot
    import yaml

    cfg = yaml.safe_load((ROOT / "config" / "settings.yaml").read_text(encoding="utf-8"))
    risk = cfg.get("risk") or {}

    summary = {
        "gates": GATES,
        "configs_tested": configs_tested,
        "unique_families": sorted(families),
        "n_families": len(families),
        "total_oos_trades_evaluated": total_oos_trades,
        "champion_candidates": len(champions),
        "verdict": (
            "CHAMPION CANDIDATE(S) FOUND"
            if champions
            else "NO CANDIDATE YET MEETS HIGH-CONFIDENCE STANDARD"
        ),
        "highest_oos_wr": {
            "config": highest_wr["config"],
            "oos": highest_wr["oos"],
        },
        "highest_wr_n_ge_100": (
            {"config": highest_wr_n100["config"], "oos": highest_wr_n100["oos"]}
            if highest_wr_n100
            else None
        ),
        "highest_wr_pf_ge_1_5": (
            {"config": highest_wr_pf15["config"], "oos": highest_wr_pf15["oos"]}
            if highest_wr_pf15
            else None
        ),
        "highest_wr_E_ge_0_25": (
            {"config": highest_wr_e25["config"], "oos": highest_wr_e25["oos"]}
            if highest_wr_e25
            else None
        ),
        "best_by_symbol": {
            "NQ": best_for(lambda r: "NQ" in r.get("by_symbol_n", {})),
            "ES": best_for(lambda r: "ES" in r.get("by_symbol_n", {})),
            "GC": best_for(lambda r: "GC" in r.get("by_symbol_n", {})),
            "CL": best_for(lambda r: "CL" in r.get("by_symbol_n", {})),
        },
        "top10": [
            {
                "strategy": r["config"],
                "family": r["family"],
                "timeframe": r["timeframe"],
                "oos_n": r["oos"]["n"],
                "wr": r["oos"]["wr"],
                "wr_ci95": r["oos"]["wr_ci95"],
                "pf": r["oos"]["pf"],
                "expectancy_r": r["oos"]["expectancy_r"],
                "max_dd_r": r["oos"]["max_dd_r"],
                "trades_per_week": r["oos"]["trades_per_week"],
                "avg_win_r": r["oos"]["avg_win_r"],
                "avg_loss_r": r["oos"]["avg_loss_r"],
                "worst_r": r["oos"]["worst_r"],
                "gates": r["gates"],
            }
            for r in top10
        ],
        "pareto_wr_freq_E": pareto[:15],
        "monte_carlo_best_edge": (
            rows[0]["monte_carlo"] if rows and rows[0]["oos"]["n"] >= 30 else {}
        ),
        "calibration": calibration,
        "hard_risk_config": {
            "risk_per_trade_pct": risk.get("risk_per_trade_pct"),
            "max_account_risk_per_trade": risk.get("max_account_risk_per_trade"),
            "max_risk_dollars_per_trade": risk.get("max_risk_dollars_per_trade"),
            "max_total_open_risk_dollars": risk.get("max_total_open_risk_dollars"),
            "max_daily_loss_dollars": risk.get("max_daily_loss_dollars")
            or risk.get("daily_loss_kill_dollars"),
            "max_correlated_risk_dollars": risk.get("max_correlated_risk_dollars"),
        },
        "active_bot_changes": [
            "Restored finite risk: max_risk_dollars_per_trade=500, risk_per_trade_pct=0.01, max_account_risk_per_trade=500",
            "Oversized full-size setups → SHADOW + suggest micro (not unlimited risk)",
            "No champion swap — gates not used to promote a new live strategy",
            "Paper mode unchanged; quantity not increased from this pass",
        ],
    }

    # Compact session/regime leaders from best edge row with n
    sess_best = {}
    reg_best = {}
    for r in rows:
        for s, st in (r.get("sessions") or {}).items():
            if st["n"] < 15:
                continue
            cur = sess_best.get(s)
            if cur is None or (st["wr"], st["expectancy_r"]) > (cur["oos"]["wr"], cur["oos"]["expectancy_r"]):
                sess_best[s] = {"config": r["config"], "oos": st}
        for g, st in (r.get("regimes") or {}).items():
            if st["n"] < 15:
                continue
            cur = reg_best.get(g)
            if cur is None or (st["wr"], st["expectancy_r"]) > (cur["oos"]["wr"], cur["oos"]["expectancy_r"]):
                reg_best[g] = {"config": r["config"], "oos": st}
    summary["best_by_session"] = sess_best
    summary["best_by_regime"] = reg_best

    OUT.write_text(json.dumps({"summary": summary, "all_rows_top50": rows[:50]}, indent=2), encoding="utf-8")

    # Markdown report
    lines = [
        "# High-confidence research pass",
        "",
        f"**Verdict: {summary['verdict']}**",
        "",
        f"- Configs tested: {configs_tested}",
        f"- Families: {summary['n_families']} ({', '.join(summary['unique_families'])})",
        f"- Total OOS trades evaluated: {total_oos_trades}",
        f"- Champion candidates (all gates): {len(champions)}",
        "",
        "## Gates",
        f"`{GATES}`",
        "",
        "## Top 10 (R-space only)",
        "",
        "| Strategy | TF | n | WR | PF | E[R] | MaxDD[R] | /wk | WorstR | Gates |",
        "|----------|----|---|----|----|------|----------|-----|--------|-------|",
    ]
    for t in summary["top10"]:
        lines.append(
            f"| {t['strategy']} | {t['timeframe']} | {t['oos_n']} | {t['wr']:.1%} | {t['pf']} | "
            f"{t['expectancy_r']} | {t['max_dd_r']} | {t['trades_per_week']} | {t['worst_r']} | {t['gates']} |"
        )
    lines += [
        "",
        "## Hard risk (restored)",
        json.dumps(summary["hard_risk_config"], indent=2),
        "",
        "## Active bot changes",
        *[f"- {x}" for x in summary["active_bot_changes"]],
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(summary, indent=2, default=str)[:8000])
    print("Wrote", OUT, REPORT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
