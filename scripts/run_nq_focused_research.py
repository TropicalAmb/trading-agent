"""NQ-focused research pass — prove ONE high-quality NQ strategy family.

Does NOT change paper execution, risk, universe, or live activation.
Primary data: Kaggle NQ 1m. Databento used for cross-check / finalists when keyed.
"""

from __future__ import annotations

import json
import os
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
load_dotenv(ROOT / ".env")

from agent.data.cross_check import cross_check_ohlcv, fetch_databento_overlap_sample
from agent.data.data_quality import audit_nq_1m, audit_to_markdown
from agent.data.databento_historical import DatabentoHistoricalProvider
from agent.data.kaggle_nq import load_nq_1m_csv, resample_ohlcv
from agent.research.harness.metrics import trade_stats
from agent.research.hc_strategies import (
    gen_ema_pullback,
    gen_pdh_pdl_sweep,
    gen_vwap_reclaim,
)
from agent.research.harness.strategy_registry import gen_breakout_retest
from agent.research.nq_context_entry import (
    CONFIRMATIONS,
    EXIT_RS,
    SESSION_WINDOWS,
    TRIGGERS,
    build_context_5m,
    filter_by_days,
    generate_candidates,
    realize_trades,
    rolling_walk_forward_splits,
    stats_for,
)

OUT = ROOT / "data" / "nq_focused_research"


def _score_cell(st: dict[str, Any]) -> float:
    """Train/val selection score: prefer accuracy with healthy PF/E (not engineered 70%)."""
    n = int(st.get("n") or 0)
    if n < 15:
        return -1e9
    wr = float(st.get("wr") or 0)
    pf = float(st.get("pf") or 0)
    e = float(st.get("expectancy_r") or 0)
    dd = abs(float(st.get("max_dd_r") or 0))
    if e <= 0 or pf < 1.0:
        return -1e6 + wr
    # balanced score
    return wr * 100 + min(pf, 3.0) * 8 + e * 40 - min(dd, 20) * 0.5 + min(n, 200) * 0.05


def _fmt_stats(st: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "n",
        "wr",
        "pf",
        "expectancy_r",
        "max_dd_r",
        "avg_win_r",
        "avg_loss_r",
        "worst_r",
        "trades_per_week",
        "long_n",
        "short_n",
        "long_wr",
        "short_wr",
        "anti_cheat_ok",
    ]
    return {k: st.get(k) for k in keys if k in st}


def complex_bot_trades(df5: pd.DataFrame) -> list[dict[str, Any]]:
    """Existing complex generators on same 5m NQ frame (research comparison only)."""
    gens = [
        ("complex_ema_pullback_1.5", lambda d: gen_ema_pullback(d, "NQ", target_r=1.5)),
        ("complex_vwap_reclaim_1.5", lambda d: gen_vwap_reclaim(d, "NQ", target_r=1.5)),
        ("complex_pdh_pdl_1.5", lambda d: gen_pdh_pdl_sweep(d, "NQ", target_r=1.5, with_mss=True)),
        ("complex_breakout_retest_1.5", lambda d: gen_breakout_retest(d, "NQ", target_r=1.5)),
    ]
    rows = []
    for name, fn in gens:
        try:
            trades = fn(df5)
        except Exception as exc:
            rows.append({"name": name, "error": str(exc), "n": 0})
            continue
        # restrict to NY morning-ish for fairer compare
        kept = []
        for t in trades:
            ts = pd.Timestamp(t.entry_ts)
            if ts.tzinfo is None:
                # assume ET like frame
                m = ts.hour * 60 + ts.minute
            else:
                te = ts.tz_convert("America/New_York")
                m = te.hour * 60 + te.minute
            if 8 * 60 + 30 <= m < 11 * 60 + 30:
                kept.append(t)
        st = trade_stats([t.pnl_r for t in kept], [t.entry_ts for t in kept])
        rows.append({"name": name, "stats": _fmt_stats(st), "n_raw": len(trades), "n_ny_am": len(kept)})
    return rows


def router_v2_lift(trades_oos: list, *, label: str = "simple") -> dict[str, Any]:
    """Apply existing quality model as subset filter when available; else context heuristic."""
    if not trades_oos:
        return {"status": "no_trades", "label": label}
    base = stats_for(trades_oos) if hasattr(trades_oos[0], "pnl_r") else trade_stats(
        [t["pnl_r"] for t in trades_oos], [t.get("entry_ts") for t in trades_oos]
    )

    # Heuristic adaptive subset: HTF aligned + VWAP side (proxy for router context learning)
    selected = []
    for t in trades_oos:
        ctx = getattr(t, "context", None) or {}
        side = getattr(t, "side", None)
        if not ctx:
            selected.append(t)
            continue
        aligned = float(ctx.get("ema_aligned") or 0) > 0.5
        vwap_ok = float(ctx.get("above_vwap") or 0) > 0.5 if side == "BUY" else float(ctx.get("above_vwap") or 0) < 0.5
        d1h = float(ctx.get("dir_1h") or 0)
        side_ok = (side == "BUY" and d1h >= 0) or (side == "SELL" and d1h <= 0)
        if aligned and vwap_ok and side_ok:
            selected.append(t)

    model_status = "heuristic_context_proxy"
    try:
        from agent.learning.model import TradeQualityModel

        model_path = ROOT / "data" / "learning" / "models" / "trade_quality_champion.json"
        if model_path.exists():
            model_status = "champion_present_not_feature_aligned_used_heuristic"
    except Exception:
        pass

    sel_st = stats_for(selected) if selected and hasattr(selected[0], "pnl_r") else _fmt_stats(
        trade_stats([], [])
    )
    return {
        "status": model_status,
        "base": _fmt_stats(base if isinstance(base, dict) else stats_for(trades_oos)),
        "selected": _fmt_stats(sel_st if isinstance(sel_st, dict) else sel_st),
        "selected_n": len(selected),
        "base_n": len(trades_oos),
        "note": (
            "router_v2 paper enable stays false. This pass measures whether context "
            "subsetting lifts simple NQ_CONTEXT_ENTRY OOS — not inventing new ML."
        ),
    }


def run(*, quick: bool = False) -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    report: dict[str, Any] = {
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "family": "NQ_CONTEXT_ENTRY",
        "quick": quick,
    }

    print("Loading Kaggle NQ 1m...", flush=True)
    df_1m = load_nq_1m_csv()
    if quick:
        # last ~90 calendar days for smoke
        cut = df_1m.index.max() - pd.Timedelta(days=90)
        df_1m = df_1m.loc[df_1m.index >= cut]
        print(f"QUICK mode: {len(df_1m)} bars from {df_1m.index.min()}", flush=True)

    quality = audit_nq_1m(df_1m)
    (OUT / "DATA_QUALITY_REPORT.md").write_text(audit_to_markdown(quality), encoding="utf-8")
    (OUT / "data_quality.json").write_text(json.dumps(quality, indent=2, default=str), encoding="utf-8")
    report["data"] = quality
    print(f"Data rows={quality['rows']} ok={quality['ok']} warnings={quality['warnings']}", flush=True)

    # Databento cross-check (optional)
    db_cmp: dict[str, Any] = {"status": "SKIPPED_NO_API_KEY"}
    key = (os.getenv("DATABENTO_API_KEY") or "").strip()
    if key:
        try:
            prov = DatabentoHistoricalProvider(api_key=key)
            sample = fetch_databento_overlap_sample(prov, df_1m, symbol="NQ", days=3)
            if sample is not None and not sample.empty:
                db_cmp = cross_check_ohlcv(df_1m, sample)
                db_cmp["status"] = "COMPARED"
            else:
                db_cmp = {"status": "FETCH_EMPTY"}
        except Exception as exc:
            db_cmp = {"status": "ERROR", "error": str(exc)}
    else:
        db_cmp = {
            "status": "SKIPPED_NO_API_KEY",
            "recommendation": "Add DATABENTO_API_KEY to .env for overlap QA + finalist validation",
        }
    report["databento_cross_check"] = db_cmp
    (OUT / "databento_cross_check.json").write_text(json.dumps(db_cmp, indent=2, default=str), encoding="utf-8")

    print("Building 5m context...", flush=True)
    df5 = build_context_5m(df_1m, use_4h=False)
    splits = rolling_walk_forward_splits(df5.index, n_folds=4 if not quick else 3, holdout_frac=0.20)
    report["splits"] = {
        "n_folds": len(splits["folds"]),
        "n_research_days": splits["n_research_days"],
        "n_holdout_days": splits["n_holdout_days"],
    }

    # Grid search — window/confirm/exit selected on train+val only
    cells: list[dict[str, Any]] = []
    confirmations = CONFIRMATIONS if not quick else ("signal_close", "rejection_wick", "next_bar")
    exits: list[Any] = list(EXIT_RS) + ["structural"]
    if quick:
        exits = [1.0, 1.5, 2.0, "structural"]

    for trigger in TRIGGERS:
        for window in SESSION_WINDOWS:
            for conf in confirmations:
                print(f"Candidates {trigger} {window} {conf}...", flush=True)
                cands = generate_candidates(df5, trigger=trigger, window=window, confirmation=conf)
                if not cands:
                    continue
                for ex in exits:
                    trades = realize_trades(cands, df_1m, target_r=ex)
                    # aggregate train/val across folds
                    train_all = []
                    val_all = []
                    for fold in splits["folds"]:
                        train_all.extend(filter_by_days(trades, fold["train_days"]))
                        val_all.extend(filter_by_days(trades, fold["val_days"]))
                    # de-dup by entry_ts (overlapping expanding folds)
                    def _dedupe(ts_list):
                        seen = set()
                        out = []
                        for t in ts_list:
                            k = (t.entry_ts, t.trigger, t.confirmation, t.exit_style, t.side)
                            if k in seen:
                                continue
                            seen.add(k)
                            out.append(t)
                        return out

                    train_u, val_u = _dedupe(train_all), _dedupe(val_all)
                    hold = filter_by_days(trades, splits["holdout_days"])
                    st_train, st_val = stats_for(train_u), stats_for(val_u)
                    # selection metric: prefer val; if thin use train
                    select_st = st_val if st_val["n"] >= 20 else st_train
                    cells.append(
                        {
                            "trigger": trigger,
                            "window": window,
                            "confirmation": conf,
                            "exit": ex if not isinstance(ex, float) else f"{ex}R",
                            "target_r": ex,
                            "train": _fmt_stats(st_train),
                            "val": _fmt_stats(st_val),
                            "holdout": _fmt_stats(stats_for(hold)),
                            "select_score": _score_cell(select_st),
                            "select_n": int(select_st["n"]),
                            "_holdout_trades": [t.to_dict() for t in hold],
                            "all_research_trades_n": len(train_u) + len(val_u),
                        }
                    )

    cells_sorted = sorted(cells, key=lambda x: x["select_score"], reverse=True)
    report["cells_tried"] = len(cells_sorted)

    # Best configs by objective (selection on train/val only)
    def pick(pred, key):
        pool = [c for c in cells_sorted if pred(c)]
        if not pool:
            return None
        if key == "wr":
            return max(pool, key=lambda c: (c["val"]["wr"] if c["val"]["n"] >= 20 else c["train"]["wr"], c["select_score"]))
        if key == "expectancy":
            return max(
                pool,
                key=lambda c: (
                    c["val"]["expectancy_r"] if c["val"]["n"] >= 20 else c["train"]["expectancy_r"],
                    c["select_score"],
                ),
            )
        return pool[0]

    serious = [c for c in cells_sorted if c["select_n"] >= 40]
    promising40 = serious[:15]
    best_acc = pick(lambda c: c["select_n"] >= 40, "wr")
    best_bal = pick(lambda c: c["select_n"] >= 40 and (c["val"].get("pf") or 0) >= 1.1, "bal")
    best_e = pick(lambda c: c["select_n"] >= 40, "expectancy")

    # Per-trigger holdout for best balanced window chosen on train/val
    # Choose one operating window from best_bal or best_acc
    chosen_window = None
    if best_bal:
        chosen_window = best_bal["window"]
    elif best_acc:
        chosen_window = best_acc["window"]
    else:
        chosen_window = "0930_1100"

    trigger_holdout = {}
    combined_hold = []
    for trigger in TRIGGERS:
        # best cell for this trigger under chosen window by select_score
        pool = [c for c in cells_sorted if c["trigger"] == trigger and c["window"] == chosen_window]
        if not pool:
            pool = [c for c in cells_sorted if c["trigger"] == trigger]
        if not pool:
            trigger_holdout[trigger] = {"n": 0}
            continue
        top = pool[0]
        th = top["holdout"]
        trigger_holdout[trigger] = {
            **th,
            "config": {
                "window": top["window"],
                "confirmation": top["confirmation"],
                "exit": top["exit"],
            },
            "train_val_select": {"train": top["train"], "val": top["val"]},
        }
        hdicts = top.get("_holdout_trades") or []
        combined_hold.extend(hdicts)
        print(
            f"  holdout {trigger}: n={th.get('n')} attached={len(hdicts)} "
            f"cfg={top['confirmation']}/{top['exit']}",
            flush=True,
        )

    # Combined unique by entry
    seen = set()
    comb_trades = []
    for td in combined_hold:
        k = (td["entry_ts"], td["trigger"], td["side"])
        if k in seen:
            continue
        seen.add(k)
        comb_trades.append(td)
    comb_st = trade_stats([t["pnl_r"] for t in comb_trades], [t["entry_ts"] for t in comb_trades])

    # WR vs R curve for best_bal config family
    wr_vs_r = []
    if best_bal:
        for ex in EXIT_RS:
            pool = [
                c
                for c in cells_sorted
                if c["trigger"] == best_bal["trigger"]
                and c["window"] == best_bal["window"]
                and c["confirmation"] == best_bal["confirmation"]
                and c["exit"] == f"{ex}R"
            ]
            if pool:
                wr_vs_r.append({"target_r": ex, "val": pool[0]["val"], "holdout": pool[0]["holdout"]})

    print("Complex bot comparison...", flush=True)
    complex_rows = complex_bot_trades(df5)
    # holdout slice for complex
    hold_days = splits["holdout_days"]
    complex_holdout = []
    for row in complex_rows:
        if "stats" not in row:
            continue
        # re-run not stored — report full-sample NY AM as proxy + note
        complex_holdout.append(row)

    # Router lift on combined holdout trades reconstructed as objects-like
    class _T:
        def __init__(self, d):
            self.pnl_r = d["pnl_r"]
            self.entry_ts = d["entry_ts"]
            self.side = d["side"]
            self.context = d.get("context") or {}
            self.session_window = d.get("session_window")
            self.trigger = d.get("trigger")

    lift = router_v2_lift([_T(t) for t in comb_trades])

    # Databento finalist validation
    finalist_db: dict[str, Any] = {"status": "SKIPPED_NO_API_KEY"}
    finalists = [x for x in (best_acc, best_bal, best_e) if x]
    if key and finalists:
        try:
            prov = DatabentoHistoricalProvider(api_key=key)
            # last 10 holdout days only (cost control)
            hold_sorted = sorted(hold_days)
            sample_days = hold_sorted[-10:] if len(hold_sorted) > 10 else hold_sorted
            if sample_days:
                start = sample_days[0]
                end = sample_days[-1] + pd.Timedelta(days=1)
                db_1m = prov.fetch_ohlcv_df("NQ", start=start.to_pydatetime(), end=end.to_pydatetime(), schema="ohlcv-1m")
                db5 = build_context_5m(db_1m)
                db_results = []
                for cell in finalists[:2]:
                    cands = generate_candidates(
                        db5,
                        trigger=cell["trigger"],
                        window=cell["window"],
                        confirmation=cell["confirmation"],
                    )
                    tr = realize_trades(cands, db_1m, target_r=cell["target_r"])
                    db_results.append(
                        {
                            "config": {
                                "trigger": cell["trigger"],
                                "window": cell["window"],
                                "confirmation": cell["confirmation"],
                                "exit": cell["exit"],
                            },
                            "stats": _fmt_stats(stats_for(tr)),
                        }
                    )
                finalist_db = {"status": "VALIDATED", "results": db_results, "bars": len(db_1m)}
        except Exception as exc:
            finalist_db = {"status": "ERROR", "error": str(exc), "trace": traceback.format_exc()[-500:]}

    # Verdict
    def _good(st: dict | None) -> bool:
        if not st:
            return False
        n = int(st.get("n") or 0)
        wr = float(st.get("wr") or 0)
        pf = float(st.get("pf") or 0)
        e = float(st.get("expectancy_r") or 0)
        return n >= 100 and wr >= 0.65 and pf >= 1.2 and e > 0

    hold_ref = (best_bal or best_acc or {}).get("holdout") if (best_bal or best_acc) else None
    verdict = (
        "NQ STRATEGY READY FOR DEMO"
        if _good(hold_ref) or _good(comb_st)
        else "NQ STRATEGY NOT YET GOOD ENOUGH"
    )
    if hold_ref and int(hold_ref.get("n") or 0) < 40 and int(comb_st.get("n") or 0) < 40:
        verdict = "NQ STRATEGY NOT YET GOOD ENOUGH"

    report.update(
        {
            "chosen_operating_window": chosen_window,
            "window_selection_note": "Selected from train/validation only; holdout unused for window pick.",
            "trigger_holdout": trigger_holdout,
            "combined_holdout": _fmt_stats(comb_st),
            "best_high_accuracy": _cell_summary(best_acc),
            "best_balanced": _cell_summary(best_bal),
            "best_expectancy": _cell_summary(best_e),
            "promising_40plus": [_cell_summary(c) for c in promising40],
            "wr_vs_r": wr_vs_r,
            "complex_bot_comparison": complex_holdout,
            "router_v2_lift": lift,
            "databento_finalist_validation": finalist_db,
            "verdict": verdict,
            "finished_utc": datetime.now(timezone.utc).isoformat(),
        }
    )

    slim_cells = []
    for c in cells_sorted[:200]:
        slim = {k: v for k, v in c.items() if not k.startswith("_")}
        slim_cells.append(slim)
    report["top_cells"] = slim_cells[:50]

    (OUT / "nq_focused_research.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    md = render_markdown(report)
    (OUT / "NQ_FOCUSED_RESEARCH_REPORT.md").write_text(md, encoding="utf-8")
    print("VERDICT:", verdict, flush=True)
    print("Report:", OUT / "NQ_FOCUSED_RESEARCH_REPORT.md", flush=True)
    return report


def _cell_summary(cell: dict | None) -> dict | None:
    if not cell:
        return None
    return {
        "trigger": cell["trigger"],
        "window": cell["window"],
        "confirmation": cell["confirmation"],
        "exit": cell["exit"],
        "select_score": cell["select_score"],
        "train": cell["train"],
        "val": cell["val"],
        "holdout": cell["holdout"],
    }


def render_markdown(r: dict[str, Any]) -> str:
    d = r.get("data") or {}
    lines = [
        "# NQ Focused Research Report",
        "",
        f"**Verdict:** `{r.get('verdict')}`",
        "",
        f"Finished UTC: `{r.get('finished_utc')}`",
        "",
        "## DATA",
        f"- Kaggle rows / range: `{d.get('rows')}` / `{d.get('start')}` → `{d.get('end')}`",
        f"- Quality ok: `{d.get('ok')}`",
        f"- Issues: `{d.get('issues')}`",
        f"- Warnings: `{d.get('warnings')}`",
        f"- Databento comparison: `{json.dumps(r.get('databento_cross_check'), default=str)[:500]}`",
        "",
        f"Operating window (train/val only): `{r.get('chosen_operating_window')}`",
        "",
        "## PULLBACK",
        f"```\n{json.dumps(r.get('trigger_holdout', {}).get('PULLBACK'), indent=2, default=str)}\n```",
        "",
        "## LIQUIDITY",
        f"```\n{json.dumps(r.get('trigger_holdout', {}).get('LIQUIDITY'), indent=2, default=str)}\n```",
        "",
        "## BREAKOUT RETEST",
        f"```\n{json.dumps(r.get('trigger_holdout', {}).get('BREAKOUT_RETEST'), indent=2, default=str)}\n```",
        "",
        "## COMBINED",
        f"```\n{json.dumps(r.get('combined_holdout'), indent=2, default=str)}\n```",
        "",
        "## BEST HIGH-ACCURACY CONFIG",
        f"```\n{json.dumps(r.get('best_high_accuracy'), indent=2, default=str)}\n```",
        "",
        "## BEST BALANCED CONFIG",
        f"```\n{json.dumps(r.get('best_balanced'), indent=2, default=str)}\n```",
        "",
        "## BEST EXPECTANCY CONFIG",
        f"```\n{json.dumps(r.get('best_expectancy'), indent=2, default=str)}\n```",
        "",
        "## WR vs R TARGET",
        f"```\n{json.dumps(r.get('wr_vs_r'), indent=2, default=str)}\n```",
        "",
        "## CURRENT COMPLEX BOT COMPARISON",
        f"```\n{json.dumps(r.get('complex_bot_comparison'), indent=2, default=str)}\n```",
        "",
        "## ROUTER_V2 LIFT",
        f"```\n{json.dumps(r.get('router_v2_lift'), indent=2, default=str)}\n```",
        "",
        "## FINAL DATABENTO VALIDATION",
        f"```\n{json.dumps(r.get('databento_finalist_validation'), indent=2, default=str)}\n```",
        "",
        "## Notes",
        "- Yahoo was not used as the primary research feed.",
        "- Global score was not used as an entry gate for NQ_CONTEXT_ENTRY.",
        "- Paper agent / backend infrastructure unchanged; live not activated.",
        "- Prefer 100+ untouched OOS trades before demo claims; 40+ listed under promising cells.",
        "- Structural exits can print high WR with sub-1R average winners — treat WR-vs-R matrix as the decision surface.",
        "- Kaggle file has exactly 1,048,575 rows (Excel max) — possible truncation at Dec 2025; Databento required for finalist truth.",
        "- Databento cross-check/finalists skipped until `DATABENTO_API_KEY` is set in local `.env`.",
        "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    quick = "--quick" in sys.argv
    run(quick=quick)
