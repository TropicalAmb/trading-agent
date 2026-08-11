"""CL priority learning cell pass — analyze winner, LR cells, write report.

Does NOT promote liquidity_reversal or change paper risk/qty/universe.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent.learning.cl_priority import build_cl_priority_report
from agent.learning.analyze import global_score_deciles, tier_calibration
from agent.learning.dataset import build_unified_dataset
from agent.learning.health import StrategyHealthStore, cell_key  # noqa: F401

OUT = ROOT / "data" / "cl_priority_learning"


def _md(report: dict) -> str:
    w = report.get("recent_cl_paper_winner") or {}
    snap = w.get("snapshot") or {}
    hist = report.get("cl_liquidity_reversal_historical") or {}
    cmp_ = hist.get("winner_vs_loser") or {}
    lines = [
        "# CL Priority Learning Report",
        "",
        f"Generated: {report.get('generated_at')}",
        "",
        "## Policy",
        "- Do **not** promote from one paper trade",
        "- Keep multi-strategy mix / router_v1 paper path",
        "- CL `liquidity_reversal` = priority **learning/shadow** cell only",
        "",
        "## Why the recent CL winner won (non-causal)",
        "",
        f"**Warning:** {w.get('warning')}",
        "",
        f"- trade_id: `{w.get('trade_id')}`",
        f"- strategy: `{snap.get('strategy')}`",
        f"- direction: `{snap.get('direction')}` session=`{snap.get('session')}`",
        f"- global_score/tier: `{snap.get('global_score')}` / `{snap.get('tier')}`",
        f"- MTF: 15m={snap.get('dir_15m')} 1h={snap.get('dir_1h')} 4h={snap.get('dir_4h')} aligned={snap.get('mtf_aligned')}",
        f"- VWAP above={snap.get('above_vwap')} dist_atr={snap.get('vwap_dist_atr')}",
        f"- agreeing: {snap.get('agreeing_engines')}",
        f"- result R={snap.get('realized_r')} MFE={snap.get('mfe_pts')} MAE={snap.get('mae_pts')} pnl={snap.get('pnl_dollars')}",
        f"- features_source: {snap.get('features_source')}",
        "",
        "### Anecdotal traits (single trade)",
    ]
    for a in w.get("anecdotal_traits") or []:
        lines.append(f"- {a}")
    lines += ["", "### Statistical candidates (CL LR historical win vs loss)", ""]
    for u in w.get("statistically_useful_traits") or []:
        lines.append(
            f"- {u.get('trait')}: winners={u.get('winners')} losers={u.get('losers')} delta={u.get('delta')}"
        )
    lines += [
        "",
        "## CL liquidity_reversal winner vs loser (historical)",
        f"- n_wins={cmp_.get('n_wins')} n_losses={cmp_.get('n_losses')}",
        f"- winners: {json.dumps(cmp_.get('winners') or {}, default=str)}",
        f"- losers: {json.dumps(cmp_.get('losers') or {}, default=str)}",
        "",
        "## Strongest subcells (vs ~49.1% OOS WR ref / PF≥1.2 / E>0)",
        "",
    ]
    strong = hist.get("stronger_than_global_ref") or []
    if not strong:
        lines.append("_None met WR≥49.1% with PF≥1.2 and E>0 in this hist BT._")
    for c in strong[:20]:
        lines.append(
            f"- [{c.get('category')}] {c.get('dimension')}={c.get('value')}: "
            f"n={c.get('n')} WR={c.get('wr')} shrunk={c.get('shrunk_wr')} "
            f"PF={c.get('pf')} E={c.get('expectancy_r')} DD={c.get('max_dd_r')}"
        )
    lines += ["", "## Relative-best subcells (diagnostic; may be below OOS ref)", ""]
    for c in (hist.get("relative_best_subcells") or [])[:12]:
        lines.append(
            f"- [{c.get('category')}] {c.get('dimension')}={c.get('value')}: "
            f"n={c.get('n')} WR={c.get('wr'):.1%} shrunk={c.get('shrunk_wr'):.1%} "
            f"PF={c.get('pf'):.2f} E={c.get('expectancy_r'):+.3f}R DD={c.get('max_dd_r')}"
        )
    lines += [
        "",
        f"### VALIDATED (n>=100): {len(hist.get('validated_cells') or [])}",
        f"### DEVELOPING (n>=40): {len(hist.get('developing_cells') or [])}",
        f"### EARLY (n>=20): {len(hist.get('early_cells') or [])} — do not control paper",
        "",
        f"Overall historical: {hist.get('overall')}",
        "",
        f"Learning store CL rows: {(report.get('learning_store') or {}).get('cl_rows')}",
    ]
    return "\n".join(lines)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    print("Building CL priority report (includes historical LR backtest)...", flush=True)
    report = build_cl_priority_report(ROOT, run_hist_bt=True)

    # Global score / tier calibration on unified dataset (all strategies)
    df, audit = build_unified_dataset(backfill_bars=False)
    if len(df):
        report["global_score_calibration"] = global_score_deciles(df)
        report["tier_calibration"] = tier_calibration(df)
    else:
        report["global_score_calibration"] = {"flag": "NO_DATA"}
        report["tier_calibration"] = {"flag": "NO_DATA"}

    # Explicit priority note — do NOT globally SHADOW_ONLY the strategy
    (OUT / "PRIORITY_CELL.json").write_text(
        json.dumps(
            {
                "cell": "CL|liquidity_reversal",
                "mode": "PRIORITY_SHADOW_LEARNING",
                "do_not_globally_promote": True,
                "engine_status": "research_only (existing)",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    # Seed insufficient-data health for CL LR cells without flipping healthy cells
    hs = StrategyHealthStore(str(ROOT / "data" / "learning" / "strategy_cell_health.json"))
    for sess in ("asia", "london", "ny"):
        for regime in ("TREND_UP", "TREND_DOWN", "RANGE"):
            for d in ("BUY", "SELL"):
                key = cell_key("liquidity_reversal", "CL", sess, regime, d)
                if hs.get(key) in {"ACTIVE", "INSUFFICIENT_DATA"} or not hs.get(key):
                    hs.update(key, "INSUFFICIENT_DATA", note="priority_learning_seed")

    (OUT / "CL_PRIORITY_LEARNING_REPORT.json").write_text(
        json.dumps(report, indent=2, default=str), encoding="utf-8"
    )
    (OUT / "CL_PRIORITY_LEARNING_REPORT.md").write_text(_md(report), encoding="utf-8")
    print("Wrote", OUT / "CL_PRIORITY_LEARNING_REPORT.md", flush=True)
    snap = (report.get("recent_cl_paper_winner") or {}).get("snapshot") or {}
    print(
        "Winner:",
        (report.get("recent_cl_paper_winner") or {}).get("trade_id"),
        snap.get("strategy"),
        snap.get("session"),
        "pnl=",
        snap.get("pnl_dollars"),
        flush=True,
    )
    hist = report.get("cl_liquidity_reversal_historical") or {}
    print("LR hist n=", (hist.get("overall") or {}).get("n"), "strong cells=", len(hist.get("stronger_than_global_ref") or []), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
