"""Complete VWAP+MSS deep research pass.

New holdout architecture (locked BEFORE tuning):
  - Newest ~20% of trading days = FINAL HOLDOUT (untouched until candidate selection)
  - Remaining DEV days: rolling walk-forward selection on train folds / val fold

Paper agent is NOT frozen by this script. Risk/qty untouched.
"""

from __future__ import annotations

import json
import sys
import time
from collections import defaultdict
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent.research.harness.datasets import SplitSpec, assign_period, fetch_yahoo, save_split_lock
from agent.research.harness.metrics import GATES, meets_gates, trade_stats
from agent.research.harness.monte_carlo import monte_carlo
from agent.research.harness.probability import calibrate_buckets
from agent.research.missed_moves import scan_missed_moves
from agent.research.vwap_mss_deep import (
    attach_fixed_r_pnls,
    event_to_trade,
    event_to_trade_fast,
    filter_events,
    scan_events,
    variant_specs,
)

OUT = ROOT / "data" / "vwap_mss_deep"
PRIMARY = {"NQ": "NQ=F", "MNQ": "MNQ=F", "ES": "ES=F", "MES": "MES=F"}
SECONDARY = {"GC": "GC=F", "MGC": "MGC=F", "CL": "CL=F", "MCL": "MCL=F"}
ALL = {**PRIMARY, **SECONDARY}


def freeze_new_holdout(df: pd.DataFrame, holdout_frac: float = 0.20) -> SplitSpec:
    """DEV = oldest (1-holdout); within DEV: 70% train / 30% val. Newest = final."""
    days = sorted(df.index.normalize().unique())
    n = len(days)
    if n < 25:
        raise ValueError(f"insufficient days: {n}")
    n_final = max(int(n * holdout_frac), 5)
    n_dev = n - n_final
    n_train = max(int(n_dev * 0.70), 8)
    n_val = n_dev - n_train
    train_days = days[:n_train]
    val_days = days[n_train:n_dev]
    final_days = days[n_dev:]
    return SplitSpec(
        train_end=str(train_days[-1]),
        val_end=str(val_days[-1]),
        final_start=str(final_days[0]),
        n_days_train=len(train_days),
        n_days_val=len(val_days),
        n_days_final=len(final_days),
    )


def prune_branch(st_train: dict, st_val: dict) -> bool:
    """True if branch should be pruned (bad on both train and val with sample)."""
    for st in (st_train, st_val):
        if st["n"] < 20:
            return False
    return (
        st_train["wr"] < 0.50
        and st_val["wr"] < 0.50
        and st_train["pf"] < 1.0
        and st_val["pf"] < 1.0
        and st_train["expectancy_r"] < 0
        and st_val["expectancy_r"] < 0
    )


def score_select(st: dict) -> float:
    """Composite for selection on VAL (not final). Prefer high WR with edge + sample."""
    if st["n"] < 15 or not st.get("anti_cheat_ok", False):
        return -999.0
    return (
        st["wr"] * 100
        + min(st["pf"], 3.0) * 8
        + st["expectancy_r"] * 40
        + min(st["n"], 80) * 0.05
        + min(st["trades_per_week"], 10) * 0.5
    )


def overext_bins(events_trades: list[tuple[Any, Any]]) -> dict[str, Any]:
    bins = [(0, 0.25), (0.25, 0.5), (0.5, 0.75), (0.75, 1.0), (1.0, 99)]
    out = {}
    for lo, hi in bins:
        name = f"{lo}-{hi}" if hi < 90 else ">1.00"
        rs = [t.pnl_r for e, t in events_trades if lo <= e.overext_vwap_atr < hi]
        out[name] = trade_stats(rs)
    return out


def ablation_table(base_st: dict, with_feat: dict[str, dict]) -> list[dict]:
    rows = []
    for feat, st in with_feat.items():
        rows.append(
            {
                "feature": feat,
                "wr_delta": round(st["wr"] - base_st["wr"], 4),
                "pf_delta": round(st["pf"] - base_st["pf"], 3),
                "expectancy_delta": round(st["expectancy_r"] - base_st["expectancy_r"], 4),
                "frequency_delta_tpw": round(st["trades_per_week"] - base_st["trades_per_week"], 2),
                "drawdown_delta": round(st["max_dd_r"] - base_st["max_dd_r"], 3),
                "n": st["n"],
                "wr": st["wr"],
                "pf": st["pf"],
                "expectancy_r": st["expectancy_r"],
            }
        )
    return rows


def missed_move_report(frames: dict[str, pd.DataFrame], trades_by_sym: dict[str, list]) -> dict[str, Any]:
    """Build candidate map from strategy entries, then scan large moves."""
    summary = {"by_symbol": {}, "totals": {}}
    tot = {"moves": 0, "captured": 0, "near_miss": 0, "missed": 0}
    # Primary symbols only for missed-move depth (independent; avoids 8x wall-clock)
    focus = [s for s in ("NQ", "ES", "GC", "CL") if s in frames]
    for sym in focus:
        df = frames[sym]
        if df is None or df.empty:
            continue
        print(f"  missed-move scan {sym}...", flush=True)
        # map bar ts -> candidates
        cmap: dict[str, list[dict]] = defaultdict(list)
        for t in trades_by_sym.get(sym, []):
            cmap[str(t.entry_ts)].append(
                {"tier": "A", "strategy": t.strategy, "direction": t.side, "symbol": sym}
            )
        # also mark near bars as near-miss (±2 bars)
        idx_map = {str(ts): i for i, ts in enumerate(df.index)}
        near_map: dict[str, list[dict]] = defaultdict(list)
        for ts, cands in list(cmap.items()):
            if ts not in idx_map:
                continue
            i = idx_map[ts]
            for k in range(max(0, i - 2), min(len(df), i + 3)):
                near_map[str(df.index[k])].extend(cands)

        moves = scan_missed_moves(
            df,
            symbol=sym,
            candidates_by_bar=dict(near_map),
            horizons=(3, 6, 12),
            atr_threshold=2.0,
            stride=2,
        )
        captured = near = missed = 0
        absent_notes = defaultdict(int)
        for m in moves:
            tot["moves"] += 1
            if m.had_a_or_better or m.had_any_candidate:
                # same bar or nearby
                if m.had_a_or_better:
                    captured += 1
                    tot["captured"] += 1
                else:
                    near += 1
                    tot["near_miss"] += 1
            else:
                missed += 1
                tot["missed"] += 1
                absent_notes["no_vwap_mss_signal"] += 1
        n = len(moves) or 1
        summary["by_symbol"][sym] = {
            "large_moves": len(moves),
            "captured": captured,
            "near_miss": near,
            "completely_missed": missed,
            "captured_pct": round(100 * captured / n, 1),
            "near_miss_pct": round(100 * near / n, 1),
            "missed_pct": round(100 * missed / n, 1),
            "absent_components": dict(absent_notes),
        }
    n = tot["moves"] or 1
    summary["totals"] = {
        **tot,
        "captured_pct": round(100 * tot["captured"] / n, 1),
        "near_miss_pct": round(100 * tot["near_miss"] / n, 1),
        "missed_pct": round(100 * tot["missed"] / n, 1),
    }
    return summary


def runtime_snapshot() -> dict[str, Any]:
    data = ROOT / "data"
    out: dict[str, Any] = {"config_version": None, "paper_agent_running": False}
    try:
        cfg = yaml.safe_load((ROOT / "config" / "settings.yaml").read_text(encoding="utf-8"))
        out["config_version"] = cfg.get("config_version")
        out["strategy_version"] = cfg.get("strategy_version")
        out["risk"] = {
            "max_risk_dollars_per_trade": (cfg.get("risk") or {}).get("max_risk_dollars_per_trade"),
            "max_account_risk_per_trade": (cfg.get("risk") or {}).get("max_account_risk_per_trade"),
            "risk_per_trade_pct": (cfg.get("risk") or {}).get("risk_per_trade_pct"),
        }
        out["quantity"] = cfg.get("quantity")
    except Exception as exc:
        out["config_error"] = str(exc)
    st_path = data / "supervisor_status.json"
    if st_path.exists():
        st = json.loads(st_path.read_text(encoding="utf-8"))
        out["supervisor"] = st
        out["paper_agent_running"] = st.get("state") == "running"
        out["supervisor_pid"] = st.get("supervisor_pid")
        out["agent_pid"] = st.get("agent_pid")
        out["latest_heartbeat_age_sec"] = st.get("heartbeat_age_sec")
    blot = data / "paper_trades.json"
    if blot.exists():
        try:
            b = json.loads(blot.read_text(encoding="utf-8"))
            out["blotter_heartbeat"] = (b.get("heartbeat") or {}).get("ts")
            trades = b.get("trades") or b.get("closed") or []
            if isinstance(trades, list) and trades:
                out["last_paper_trade"] = trades[-1]
            elif isinstance(b.get("open"), list) and b["open"]:
                out["last_paper_trade"] = b["open"][-1]
        except Exception:
            pass
    lev = data / "last_evaluation.json"
    if lev.exists():
        out["latest_paper_scan"] = datetime.fromtimestamp(lev.stat().st_mtime, tz=timezone.utc).isoformat()
    return out


def write_report(payload: dict[str, Any], path: Path) -> None:
    r = payload
    lines = [
        "# VWAP + MSS Deep Research Report",
        "",
        f"Generated: {r.get('generated_at')}",
        "",
        "## A. RUNTIME",
        "```json",
        json.dumps(r.get("runtime", {}), indent=2),
        "```",
        "",
        "## B. RESEARCH SCALE",
        "```json",
        json.dumps(r.get("scale", {}), indent=2),
        "```",
        "",
        "## Q. FINAL VERDICT",
        f"**{r.get('verdict')}**",
        "",
        r.get("verdict_reason", ""),
        "",
        "## C. VWAP+MSS RESULTS",
        "### Baseline (DEV val)",
        "```json",
        json.dumps(r.get("baseline", {}), indent=2),
        "```",
        "### Best high-WR (selected on VAL, FINAL metrics)",
        "```json",
        json.dumps(r.get("best_high_wr", {}), indent=2),
        "```",
        "### Best balanced",
        "```json",
        json.dumps(r.get("best_balanced", {}), indent=2),
        "```",
        "### Best high-expectancy",
        "```json",
        json.dumps(r.get("best_high_exp", {}), indent=2),
        "```",
        "",
        "## D–G. BY MARKET (FINAL holdout for top candidates)",
        "```json",
        json.dumps(r.get("by_market", {}), indent=2),
        "```",
        "",
        "## H. SESSION",
        "```json",
        json.dumps(r.get("by_session", {}), indent=2),
        "```",
        "",
        "## I. NY OPEN DEEP DIVE",
        "```json",
        json.dumps(r.get("ny_open", {}), indent=2),
        "```",
        "",
        "## London",
        "```json",
        json.dumps(r.get("london", {}), indent=2),
        "```",
        "",
        "## Asia",
        "```json",
        json.dumps(r.get("asia", {}), indent=2),
        "```",
        "",
        "## J. FEATURE ABLATION (VAL)",
        "```json",
        json.dumps(r.get("ablation", {}), indent=2),
        "```",
        "",
        "## K. ENTRY TIMING",
        "```json",
        json.dumps(r.get("entry_timing", {}), indent=2),
        "```",
        "",
        "## L. EXIT COMPARISON",
        "```json",
        json.dumps(r.get("exit_comparison", {}), indent=2),
        "```",
        "",
        "## M. MONTE CARLO",
        "```json",
        json.dumps(r.get("monte_carlo", {}), indent=2),
        "```",
        "",
        "## N. MISSED-MOVE ANALYSIS",
        "```json",
        json.dumps(r.get("missed_moves", {}), indent=2),
        "```",
        "",
        "## O. FREQUENCY / ACCURACY PARETO",
        "```json",
        json.dumps(r.get("pareto", {}), indent=2),
        "```",
        "",
        "## P. PROBABILITY CALIBRATION",
        "```json",
        json.dumps(r.get("calibration", {}), indent=2),
        "```",
        "",
        "## Overextension bins",
        "```json",
        json.dumps(r.get("overextension", {}), indent=2),
        "```",
        "",
        "## R. PAPER CHANGES",
        "```json",
        json.dumps(r.get("paper_changes", []), indent=2),
        "```",
        "",
        "## Split lock",
        "```json",
        json.dumps(r.get("split_lock", {}), indent=2),
        "```",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    runtime = runtime_snapshot()
    print("RUNTIME:", json.dumps({k: runtime.get(k) for k in ("paper_agent_running", "agent_pid", "supervisor_pid", "config_version")}, indent=2), flush=True)

    # --- Load expanded history ---
    frames_1h: dict[str, pd.DataFrame] = {}
    frames_5m: dict[str, pd.DataFrame] = {}
    splits: dict[str, SplitSpec] = {}
    print("Loading expanded history...", flush=True)
    for name, ysym in ALL.items():
        # Yahoo: 1h up to ~730d; 5m ~60d
        df1 = fetch_yahoo(ysym, "1h", "730d")
        if df1.empty:
            df1 = fetch_yahoo(ysym, "1h", "365d")
        df5 = fetch_yahoo(ysym, "5m", "60d")
        frames_1h[name] = df1
        frames_5m[name] = df5
        print(f"  {name}: 1h={len(df1)} 5m={len(df5)}", flush=True)
        if len(df1) > 100:
            splits[name] = freeze_new_holdout(df1)

    # Lock splits BEFORE any tuning
    split_lock = {
        "locked_at": datetime.now(timezone.utc).isoformat(),
        "rule": "NEW holdout: newest 20% days FINAL; DEV=70/30 train/val of remaining. Prior research final OOS contaminated — not reused.",
        "splits_1h": {k: asdict(v) for k, v in splits.items()},
        "gates": GATES,
        "symbols_primary": list(PRIMARY),
        "symbols_secondary": list(SECONDARY),
    }
    save_split_lock(OUT / "split_lock.json", split_lock)
    print("Split lock written (before tuning).", flush=True)

    # --- Scan events once per symbol (1h primary research TF for sample size) ---
    events_by_sym: dict[str, list] = {}
    for name, df in frames_1h.items():
        if df is None or df.empty or name not in splits:
            continue
        print(f"Scanning events {name}...", flush=True)
        evs = scan_events(df, name)
        print(f"  events={len(evs)}; precomputing exits...", flush=True)
        attach_fixed_r_pnls(df, evs)
        events_by_sym[name] = evs
        print(f"  exits ready", flush=True)

    specs = variant_specs()
    print(f"Variant specs: {len(specs)}", flush=True)

    # Evaluate each spec on train/val only
    results: list[dict[str, Any]] = []
    pruned = 0
    for i, spec in enumerate(specs, 1):
        if i % 40 == 0 or i == 1:
            print(f"[{i}/{len(specs)}] {spec['id']}", flush=True)
        by = {"train": [], "val": [], "final": []}
        by_sym_final: dict[str, list] = defaultdict(list)
        filt_keys = {
            k: v
            for k, v in spec.items()
            if k
            not in (
                "id",
                "group",
                "target_r",
                "entry_mode",
                "mss_mode",
                "vwap_mode",
            )
        }
        for sym, events in events_by_sym.items():
            df = frames_1h[sym]
            split = splits[sym]
            evs = filter_events(
                events,
                mss_mode=spec["mss_mode"],
                vwap_mode=spec["vwap_mode"],
                **filt_keys,
            )
            # de-dupe by entry_ts+side
            seen = set()
            entry_mode = spec.get("entry_mode", "signal_close")
            tr_r = float(spec["target_r"])
            for ev in evs:
                key = (ev.entry_ts, ev.side)
                if key in seen:
                    continue
                seen.add(key)
                if entry_mode == "signal_close":
                    tr = event_to_trade_fast(ev, target_r=tr_r, config_id=spec["id"])
                else:
                    tr = event_to_trade(
                        df,
                        ev,
                        target_r=tr_r,
                        config_id=spec["id"],
                        entry_mode=entry_mode,
                    )
                if tr is None:
                    continue
                period = assign_period(tr.entry_ts, split)
                by[period].append((ev, tr))
                if period == "final":
                    by_sym_final[sym].append(tr)

        st_tr = trade_stats([t.pnl_r for _, t in by["train"]], [t.entry_ts for _, t in by["train"]])
        st_va = trade_stats([t.pnl_r for _, t in by["val"]], [t.entry_ts for _, t in by["val"]])
        if prune_branch(st_tr, st_va):
            pruned += 1
            continue
        results.append(
            {
                "config": spec["id"],
                "spec": spec,
                "train": st_tr,
                "val": st_va,
                "select_score": score_select(st_va if st_va["n"] >= 15 else st_tr),
                "by_period_trades": by,
                "by_sym_final": dict(by_sym_final),
            }
        )

    print(f"Kept {len(results)} configs after prune ({pruned} pruned)", flush=True)
    results.sort(key=lambda x: x["select_score"], reverse=True)
    print("Selecting finalists on VAL...", flush=True)

    # Pick finalists from VAL scores only
    def pick(pred):
        for r in results:
            if pred(r):
                return r
        return results[0] if results else None

    best_wr = pick(lambda r: r["val"]["n"] >= 20 and r["val"]["wr"] >= 0.55)
    best_bal = pick(
        lambda r: r["val"]["n"] >= 25
        and r["val"]["wr"] >= 0.55
        and r["val"]["expectancy_r"] >= 0.15
        and r["val"]["trades_per_week"] >= 1.0
    )
    eligible_exp = [x for x in results if x["val"]["n"] >= 20]
    best_exp = max(eligible_exp, key=lambda r: r["val"]["expectancy_r"]) if eligible_exp else None
    # fallbacks
    if best_wr is None and results:
        best_wr = max(results, key=lambda r: (r["val"]["wr"], r["val"]["n"]))
    if best_bal is None and results:
        best_bal = max(results, key=lambda r: r["select_score"])
    if best_exp is None and results:
        best_exp = max(results, key=lambda r: (r["val"]["expectancy_r"], r["val"]["n"]))
    print(
        f"Finalists: wr={best_wr['config'] if best_wr else None} "
        f"bal={best_bal['config'] if best_bal else None} "
        f"exp={best_exp['config'] if best_exp else None}",
        flush=True,
    )

    _finalize_cache: dict[str, dict] = {}

    def finalize(row: dict | None, *, with_mc: bool = False) -> dict:
        if not row:
            return {}
        ck = row["config"] + ("|mc" if with_mc else "")
        if ck in _finalize_cache:
            return _finalize_cache[ck]
        trades = [t for _, t in row["by_period_trades"]["final"]]
        st = trade_stats([t.pnl_r for t in trades], [t.entry_ts for t in trades])
        mc = (
            monte_carlo([t.pnl_r for t in trades], n_sims=10000)
            if with_mc and st["n"] >= 15
            else ({"n_sims": 0, "status": "DEFERRED"} if not with_mc else {"n_sims": 0, "status": "INSUFFICIENT"})
        )
        by_sym = {
            sym: trade_stats([t.pnl_r for t in ts], [t.entry_ts for t in ts])
            for sym, ts in row["by_sym_final"].items()
        }
        sessions = defaultdict(list)
        for t in trades:
            sessions[t.session].append(t)
        by_sess = {s: trade_stats([t.pnl_r for t in ts], [t.entry_ts for t in ts]) for s, ts in sessions.items()}
        out = {
            "config": row["config"],
            "spec": row["spec"],
            "train": row["train"],
            "val": row["val"],
            "final": st,
            "gates_met": meets_gates(st),
            "monte_carlo": mc,
            "by_symbol": by_sym,
            "by_session": by_sess,
            "final_trades_n": st["n"],
        }
        _finalize_cache[ck] = out
        return out

    print("FINAL holdout + Monte Carlo (10k) on finalists...", flush=True)
    fin_wr = finalize(best_wr, with_mc=True)
    print("  high_wr final n=", fin_wr.get("final_trades_n"), flush=True)
    fin_bal = finalize(best_bal, with_mc=True)
    print("  balanced final n=", fin_bal.get("final_trades_n"), flush=True)
    fin_exp = finalize(best_exp, with_mc=True)
    print("  high_exp final n=", fin_exp.get("final_trades_n"), flush=True)

    # Baseline reference: base_mC_reclaim_R1.25
    baseline_row = next((r for r in results if r["config"] == "base_mC_reclaim_R1.25"), None)
    if baseline_row is None and results:
        baseline_row = next((r for r in results if r["config"].startswith("base_mC_reclaim")), results[0])
    baseline = {
        "config": baseline_row["config"] if baseline_row else None,
        "train": baseline_row["train"] if baseline_row else {},
        "val": baseline_row["val"] if baseline_row else {},
        "final": finalize(baseline_row).get("final") if baseline_row else {},
    }

    # Ablation on VAL using fixed mss/vwap/R
    abl_base = next((r for r in results if r["config"] == "base_mC_reclaim_R1.25"), baseline_row)
    abl_feats = {}
    if abl_base:
        base_val = abl_base["val"]
        for feat, cid_prefix in [
            ("liq_sweep", "v1_liq_mC_reclaim_R1.25"),
            ("pdh_pdl", "v2_pdh_mC_reclaim_R1.25"),
            ("sess_sweep", "v3_sess_mC_reclaim_R1.25"),
            ("fvg", "v4_fvg_mC_reclaim_R1.25"),
            ("fvg_retest", "v5_fvg_rt_mC_reclaim_R1.25"),
            ("displacement", "v6_disp_mC_reclaim_R1.25"),
            ("mtf1", "v7_mtf15_mC_reclaim_R1.25"),
            ("mtf2", "v8_mtf2_mC_reclaim_R1.25"),
            ("mtf3", "v9_mtf3_mC_reclaim_R1.25"),
            ("rejection", "v10_reject_mC_reclaim_R1.25"),
            ("engulfing", "v11_engulf_mC_reclaim_R1.25"),
            ("overext_cap", "v12_nochase_mC_reclaim_R1.25"),
            ("liq+fvg", "v13_liq_fvg_mC_reclaim_R1.25"),
            ("mtf+fvg", "v15_mtf_fvg_mC_reclaim_R1.25"),
            ("mtf+liq", "v16_mtf_liq_mC_reclaim_R1.25"),
            ("ema_align", "v17_ema_mC_reclaim_R1.25"),
            ("quality_stack", "v20_quality_mC_reclaim_R1.25"),
        ]:
            row = next((r for r in results if r["config"] == cid_prefix), None)
            if row:
                abl_feats[feat] = row["val"]
        # leave-one-out style: quality without fvg ≈ mtf+disp+nochase
        ablation = {"base": base_val, "deltas": ablation_table(base_val, abl_feats)}
    else:
        ablation = {}

    # Entry timing comparison (VAL)
    entry_timing = {}
    for r in results:
        if r["spec"].get("group") == "entry_timing" or str(r["config"]).startswith("entry_"):
            entry_timing[r["config"]] = {
                "val": r["val"],
                "entry_mode": r["spec"].get("entry_mode"),
            }

    # Exit comparison: same events base_mC_reclaim across R
    exit_comparison = {}
    for tr in (1.0, 1.25, 1.5, 1.75, 2.0, 2.5):
        # synthesize from events if not in grid
        cid = f"base_mC_reclaim_R{tr}"
        row = next((r for r in results if r["config"] == cid), None)
        if row:
            exit_comparison[f"{tr}R"] = {"val": row["val"], "final": finalize(row).get("final")}
        else:
            # compute quickly on all primary
            by = {"train": [], "val": [], "final": []}
            for sym, events in events_by_sym.items():
                if sym not in PRIMARY:
                    continue
                df = frames_1h[sym]
                split = splits[sym]
                evs = filter_events(events, mss_mode="C", vwap_mode="reclaim")
                seen = set()
                for ev in evs:
                    key = (ev.entry_ts, ev.side)
                    if key in seen:
                        continue
                    seen.add(key)
                    t = event_to_trade(df, ev, target_r=tr, config_id=cid)
                    if t:
                        by[assign_period(t.entry_ts, split)].append(t)
            exit_comparison[f"{tr}R"] = {
                "val": trade_stats([t.pnl_r for t in by["val"]], [t.entry_ts for t in by["val"]]),
                "final": trade_stats([t.pnl_r for t in by["final"]], [t.entry_ts for t in by["final"]]),
            }

    # NY open deep dive — select window on VAL, then FINAL once
    ny_rows = [r for r in results if str(r["config"]).startswith("ny_")]
    ny_by_win: dict[str, list] = defaultdict(list)
    for r in ny_rows:
        win = r["spec"].get("ny_window", "?")
        ny_by_win[win].append(r)
    ny_selected = {}
    for win, rows in ny_by_win.items():
        best = max(rows, key=lambda x: score_select(x["val"]))
        ny_selected[win] = {
            "selected_on_val": best["config"],
            "val": best["val"],
            "final": finalize(best).get("final"),
            "by_symbol_final": finalize(best).get("by_symbol"),
        }
    # pick best window by VAL only
    if ny_selected:
        best_ny_win = max(ny_selected.items(), key=lambda kv: score_select(kv[1]["val"]))[0]
        ny_open = {"selected_window_on_val": best_ny_win, "windows": ny_selected}
    else:
        ny_open = {"selected_window_on_val": None, "windows": {}}

    lon_rows = [r for r in results if str(r["config"]).startswith("lon_")]
    london = {}
    # VAL ranking only; FINAL once for best London window
    for r in lon_rows:
        london[r["config"]] = {"val": r["val"]}
    if lon_rows:
        best_lon = max(lon_rows, key=lambda x: score_select(x["val"]))
        london["SELECTED_FINAL"] = {
            "config": best_lon["config"],
            "val": best_lon["val"],
            "final": finalize(best_lon).get("final"),
            "by_symbol": finalize(best_lon).get("by_symbol"),
        }

    # Asia sufficiency
    asia_trades = []
    for r in (best_bal, best_wr):
        if not r:
            continue
        for _, t in r["by_period_trades"]["final"]:
            if t.session == "ASIA":
                asia_trades.append(t)
        break
    asia_st = trade_stats([t.pnl_r for t in asia_trades], [t.entry_ts for t in asia_trades])
    asia = {
        "status": "INSUFFICIENT DATA" if asia_st["n"] < 30 else "OK",
        "final_metrics": asia_st,
        "note": "Asia remains in scope; report insufficient when n<30.",
    }

    # Missed moves using balanced finalist train+val+final signals as candidate map
    mm_trades: dict[str, list] = defaultdict(list)
    src = best_bal or best_wr
    if src:
        for period in ("train", "val", "final"):
            for _, t in src["by_period_trades"][period]:
                mm_trades[t.symbol].append(t)
    print("Missed-move analysis...", flush=True)
    missed = missed_move_report(frames_1h, dict(mm_trades))
    print("  missed-move totals:", missed.get("totals"), flush=True)

    # Overextension bins on baseline val trades
    overext = {}
    if baseline_row:
        overext = overext_bins(baseline_row["by_period_trades"]["val"])

    # Pareto frontier from VAL
    pareto = []
    for r in results:
        st = r["val"]
        if st["n"] < 15:
            continue
        pareto.append(
            {
                "config": r["config"],
                "wr": st["wr"],
                "expectancy_r": st["expectancy_r"],
                "pf": st["pf"],
                "trades_per_week": st["trades_per_week"],
                "n": st["n"],
                "max_dd_r": st["max_dd_r"],
            }
        )
    # non-dominated: maximize wr, expectancy, frequency
    frontier = []
    for p in pareto:
        dominated = False
        for q in pareto:
            if (
                q["wr"] >= p["wr"]
                and q["expectancy_r"] >= p["expectancy_r"]
                and q["trades_per_week"] >= p["trades_per_week"]
                and (q["wr"] > p["wr"] or q["expectancy_r"] > p["expectancy_r"] or q["trades_per_week"] > p["trades_per_week"])
            ):
                dominated = True
                break
        if not dominated:
            frontier.append(p)
    frontier = sorted(frontier, key=lambda x: (-x["wr"], -x["expectancy_r"]))[:25]

    # Probability calibration from train empirical WR by (session, mtf proxy via config group)
    cal_pred = []
    cal_out = []
    if best_bal:
        # build train WR by session as crude model; apply to val
        train_by_sess = defaultdict(list)
        for _, t in best_bal["by_period_trades"]["train"]:
            train_by_sess[t.session].append(1 if t.pnl_r > 0 else 0)
        sess_wr = {s: (sum(v) / len(v) if len(v) >= 10 else None) for s, v in train_by_sess.items()}
        for _, t in best_bal["by_period_trades"]["val"]:
            p = sess_wr.get(t.session)
            if p is None:
                continue
            cal_pred.append(p)
            cal_out.append(1 if t.pnl_r > 0 else 0)
    if len(cal_pred) >= 40:
        calibration = calibrate_buckets(cal_pred, cal_out, min_n=15)
        # Brier
        brier = float(np.mean([(p - o) ** 2 for p, o in zip(cal_pred, cal_out)]))
        calibration["brier"] = round(brier, 4)
        calibration["n"] = len(cal_pred)
        calibration["status"] = "OK"
    else:
        calibration = {"status": "INSUFFICIENT", "n": len(cal_pred)}

    # By market full metrics for finalists
    by_market = {
        "high_wr": fin_wr.get("by_symbol", {}),
        "balanced": fin_bal.get("by_symbol", {}),
        "high_exp": fin_exp.get("by_symbol", {}),
    }

    # Verdict
    candidates_ok = []
    for label, fin in (("high_wr", fin_wr), ("balanced", fin_bal), ("high_exp", fin_exp)):
        st = fin.get("final") or {}
        if st and meets_gates(st):
            candidates_ok.append((label, fin))
    # also check n>=100 prefer 200, wr>=0.65
    if candidates_ok:
        verdict = "HIGH-CONFIDENCE CANDIDATE FOUND"
        verdict_reason = f"Gates met on FINAL holdout: {[c[0] for c in candidates_ok]}"
    else:
        verdict = "NO ROBUST >=65% CANDIDATE YET"
        # closest
        closest = None
        for fin in (fin_wr, fin_bal, fin_exp):
            st = fin.get("final") or {}
            if not st or st.get("n", 0) < 10:
                continue
            if closest is None or st.get("wr", 0) > closest.get("wr", 0):
                closest = {**st, "config": fin.get("config")}
        verdict_reason = (
            f"No FINAL holdout config met WR>=65%, PF>=1.5, E>=0.25R, n>=100, anti-cheat. "
            f"Closest FINAL: {closest}"
        )

    # Paper changes: none unless we promote — evaluate if balanced VAL clearly beats live heuristics
    paper_changes: list[dict] = []
    # Authorization: only if FINAL meets most gates with n>=80 and WR>=0.62 — still document; user said promote when clearly superior
    promote = False
    promo_fin = fin_bal or fin_wr
    if promo_fin and promo_fin.get("final"):
        st = promo_fin["final"]
        if (
            st.get("n", 0) >= 100
            and st.get("wr", 0) >= 0.65
            and st.get("pf", 0) >= 1.5
            and st.get("expectancy_r", 0) >= 0.25
            and st.get("anti_cheat_ok", False)
        ):
            promote = True
    if promote:
        paper_changes.append(
            {
                "action": "AUTHORIZED_BUT_DEFERRED_TO_EXPLICIT_VERSION_BUMP",
                "reason": "FINAL gates met — implement vwap_mss_v1 in separate change with tests",
                "config": promo_fin.get("config"),
                "final": promo_fin.get("final"),
            }
        )
    else:
        paper_changes.append(
            {
                "action": "NONE",
                "reason": "No FINAL holdout candidate cleared promotion gates; paper agent unchanged (still opt_v1).",
            }
        )

    total_bars = sum(len(df) for df in frames_1h.values()) + sum(len(df) for df in frames_5m.values())
    scale = {
        "historical_range_1h": {
            sym: {
                "start": str(df.index.min()) if len(df) else None,
                "end": str(df.index.max()) if len(df) else None,
                "bars": len(df),
            }
            for sym, df in frames_1h.items()
        },
        "bars_total_approx": total_bars,
        "strategy_variants_specified": len(specs),
        "configs_evaluated_after_prune": len(results),
        "configs_pruned": pruned,
        "train_trades_sum": sum(r["train"]["n"] for r in results),
        "val_trades_sum": sum(r["val"]["n"] for r in results),
        "final_oos_top": {
            "high_wr": fin_wr.get("final_trades_n"),
            "balanced": fin_bal.get("final_trades_n"),
            "high_exp": fin_exp.get("final_trades_n"),
        },
        "elapsed_sec": round(time.time() - t0, 1),
    }

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "runtime": runtime,
        "scale": scale,
        "split_lock": split_lock,
        "baseline": baseline,
        "best_high_wr": fin_wr,
        "best_balanced": fin_bal,
        "best_high_exp": fin_exp,
        "by_market": by_market,
        "by_session": {
            "high_wr": fin_wr.get("by_session"),
            "balanced": fin_bal.get("by_session"),
        },
        "ny_open": ny_open,
        "london": london,
        "asia": asia,
        "ablation": ablation,
        "entry_timing": entry_timing,
        "exit_comparison": exit_comparison,
        "monte_carlo": {
            "high_wr": fin_wr.get("monte_carlo"),
            "balanced": fin_bal.get("monte_carlo"),
            "high_exp": fin_exp.get("monte_carlo"),
        },
        "missed_moves": missed,
        "pareto": frontier,
        "calibration": calibration,
        "overextension": overext,
        "verdict": verdict,
        "verdict_reason": verdict_reason,
        "paper_changes": paper_changes,
        "top20_val": [
            {"config": r["config"], "val": r["val"], "score": r["select_score"]}
            for r in results[:20]
        ],
    }

    (OUT / "vwap_mss_deep_results.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    write_report(payload, OUT / "VWAP_MSS_DEEP_REPORT.md")
    print("\n==== VERDICT ====", flush=True)
    print(verdict, flush=True)
    print(verdict_reason, flush=True)
    print("Report:", OUT / "VWAP_MSS_DEEP_REPORT.md", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
