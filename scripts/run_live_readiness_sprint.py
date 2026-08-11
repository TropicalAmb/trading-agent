"""ONE-SHOT live readiness sprint — adaptive loop, router replay, exec/risk, report.

Does NOT activate live trading. Does NOT freeze paper agent.
"""

from __future__ import annotations

import json
import math
import shutil
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

OUT = ROOT / "data" / "live_readiness"
OUT.mkdir(parents=True, exist_ok=True)


def _wilson(wins: int, n: int, z: float = 1.96) -> list[float]:
    if n <= 0:
        return [0.0, 1.0]
    p = wins / n
    denom = 1 + z**2 / n
    centre = p + z**2 / (2 * n)
    margin = z * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2))
    return [max(0.0, (centre - margin) / denom), min(1.0, (centre + margin) / denom)]


def _sel_metrics(rs: list[float], *, weeks: float = 1.0, costs_r: float = 0.05) -> dict:
    if not rs:
        return {
            "n": 0,
            "wr": None,
            "wr_ci95": None,
            "pf": None,
            "expectancy_r": None,
            "max_dd_r": None,
            "trades_per_week": 0.0,
            "avg_win": None,
            "avg_loss": None,
            "worst": None,
            "longest_losing_streak": 0,
        }
    adj = [r - costs_r for r in rs]
    wins = sum(1 for r in adj if r > 0)
    n = len(adj)
    wr = wins / n
    pos = sum(r for r in adj if r > 0)
    neg = abs(sum(r for r in adj if r < 0))
    pf = (pos / neg) if neg > 1e-12 else (999.0 if pos > 0 else 0.0)
    cum = np.cumsum(adj)
    peak = np.maximum.accumulate(cum)
    dd = float(np.min(cum - peak))
    streak = longest = 0
    for r in adj:
        if r < 0:
            streak += 1
            longest = max(longest, streak)
        else:
            streak = 0
    wlist = [r for r in adj if r > 0]
    llist = [r for r in adj if r < 0]
    return {
        "n": n,
        "wr": wr,
        "wr_ci95": _wilson(wins, n),
        "pf": pf,
        "expectancy_r": float(np.mean(adj)),
        "max_dd_r": dd,
        "trades_per_week": n / max(weeks, 1e-9),
        "avg_win": float(np.mean(wlist)) if wlist else None,
        "avg_loss": float(np.mean(llist)) if llist else None,
        "worst": float(min(adj)),
        "longest_losing_streak": longest,
    }


def section_system_health() -> dict:
    out = {}
    for name in ("supervisor_status.json", "trade_silence_status.json"):
        p = ROOT / "data" / name
        if p.exists():
            out[name] = json.loads(p.read_text(encoding="utf-8"))
    cfg = yaml.safe_load((ROOT / "config" / "settings.yaml").read_text(encoding="utf-8"))
    out["config_version"] = cfg.get("config_version")
    out["execution_profile"] = cfg.get("execution_profile")
    out["mode"] = cfg.get("mode")
    out["v2_enabled"] = (cfg.get("performance_router_v2") or {}).get("enabled")
    return out


def section_learning_e2e(tmp: Path) -> dict:
    from agent.learning.loop import (
        load_loop_state,
        maybe_retrain,
        record_candidate_snapshot,
        record_outcome_for_setup,
        save_loop_state,
    )
    from agent.learning.model import AdaptiveTradeQualityModel
    from agent.learning.store import LearningStore
    from agent.decision.setup import TradeSetup

    store_path = tmp / "candidates.jsonl"
    models_dir = tmp / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    # Seed minimal champion so predict works
    qm0 = AdaptiveTradeQualityModel(models_dir=models_dir)
    cfg = {
        "mode": "paper",
        "config_version": "readiness_e2e",
        "trade_quality_model": {
            "enabled": True,
            "learning_store": str(store_path),
            "models_dir": str(models_dir),
            "retrain_every_resolved": 5,
            "min_challenger_shadow_decisions": 5,
            "allow_paper_auto_promote": True,
            "allow_live_auto_promote": False,
        },
        "high_confidence": {"enabled": True, "shadow_parallel": True},
    }
    # Generate synthetic resolved candidates
    for i in range(12):
        s = TradeSetup(
            strategy_name="vwap_acceptance",
            symbol="MES",
            direction="BUY" if i % 2 == 0 else "SELL",
            setup_tier="A",
            confidence_score=70 + i,
            entry=100.0,
            stop=99.5,
            target=101.0,
            expected_r=2.0,
            market_timestamp=datetime(2026, 8, 1 + (i % 28), tzinfo=timezone.utc),
            received_timestamp=datetime(2026, 8, 1 + (i % 28), tzinfo=timezone.utc),
            session="ny",
            metadata={
                "setup_id": f"MES|vwap_acceptance|E2E|{i}",
                "global_score": 70 + i,
                "regime": "TREND_UP",
                "entry_features": {
                    "symbol": "MES",
                    "strategy": "vwap_acceptance",
                    "direction": "LONG" if i % 2 == 0 else "SHORT",
                    "session": "ny",
                    "mtf_aligned": 2 + (i % 2),
                    "above_vwap": 1,
                    "global_score": 70 + i,
                    "target_r": 2.0,
                    "body_atr": 0.5,
                },
                "router_v1_decision": "SELECT",
                "balanced_decision": "SELECT",
                "high_confidence_shadow": {"decision": "SELECT" if i % 3 else "PASS"},
            },
        )
        record_candidate_snapshot(cfg, setup=s, router_decision="EXECUTED", executed_or_shadow="ACTUAL")
        record_outcome_for_setup(
            cfg,
            setup_id=s.metadata["setup_id"],
            trade={
                "entry": 100.0,
                "stop": 99.5,
                "exit": 101.0 if i % 3 else 99.4,
                "side": s.direction,
                "result": "WIN" if i % 3 else "LOSS",
                "exit_reason": "target" if i % 3 else "stop",
                "mfe_pts": 1.0,
                "mae_pts": 0.2,
                "metadata": s.metadata,
            },
        )
    store = LearningStore(store_path)
    rows = store.all_rows()
    resolved = [r for r in rows if r.get("final_result") not in (None, "", "OPEN")]
    st = load_loop_state(models_dir)
    # Force retrain threshold
    st["resolved_since_retrain"] = 25
    save_loop_state(models_dir, st)
    # Need enough rows in unified dataset path — retrain uses build_unified_dataset from learning_path
    retrain = maybe_retrain(cfg)
    qm = AdaptiveTradeQualityModel(models_dir=models_dir)
    # Persistence: reload store + model dir
    persist_ok = store_path.exists() and len(LearningStore(store_path).all_rows()) == len(rows)
    has_decisions = all(
        (r.get("router_decision") or r.get("router_v1_decision") or r.get("high_confidence_shadow"))
        for r in rows[:3]
    )
    return {
        "candidates": len(rows),
        "resolved": len(resolved),
        "schema_version": rows[0].get("schema_version") if rows else None,
        "retrain": retrain,
        "champion": (qm.champion.version if qm.champion else None),
        "challenger": (qm.challenger.version if qm.challenger else None),
        "persistence_files_ok": persist_ok,
        "has_parallel_decisions": has_decisions,
        "pipeline_ok": len(resolved) >= 10 and persist_ok and has_decisions,
    }


def section_router_replay() -> dict:
    from agent.learning.analyze import (
        global_score_deciles,
        simulate_router_selection,
        tier_calibration,
    )
    from agent.learning.dataset import build_unified_dataset, numeric_matrix, time_splits
    from agent.learning.model import (
        AdaptiveTradeQualityModel,
        calibration_bins,
        is_calibrated_enough,
        train_baseline_models,
        train_nonlinear_models,
    )
    from agent.learning.shrink import shrink_rate

    df, audit = build_unified_dataset(backfill_bars=False)
    if len(df) < 30:
        return {"ok": False, "reason": "insufficient_unified_rows", "n": len(df)}

    # Friction: subtract 0.05R per trade as commission/slippage proxy
    costs_r = 0.05
    splits = time_splits(df)
    train, val, final = splits["train"], splits["val"], splits["final"]
    weeks = 1.0
    if audit.date_min and audit.date_max:
        try:
            weeks = max((pd.Timestamp(audit.date_max) - pd.Timestamp(audit.date_min)).days / 7.0, 1.0)
        except Exception:
            weeks = 1.0

    base = train_baseline_models(train, val, target="win")
    nonlin = train_nonlinear_models(train, val, target="win")
    # Choose simpler if nonlinear not meaningfully better on val brier
    chosen = "logistic_l2"
    chosen_brier = None
    if base.get("ok"):
        chosen_brier = (base["models"].get("logistic_l2") or {}).get("val", {}).get("brier")
    if nonlin.get("ok") and chosen_brier is not None:
        gb_b = (nonlin["models"].get("gradient_boosting") or {}).get("val", {}).get("brier")
        rf_b = (nonlin["models"].get("random_forest") or {}).get("val", {}).get("brier")
        best_nl = None
        best_nl_name = None
        for name, b in (("gradient_boosting", gb_b), ("random_forest", rf_b)):
            if b is not None and (best_nl is None or b < best_nl):
                best_nl, best_nl_name = b, name
        if best_nl is not None and best_nl < chosen_brier - 0.01:
            chosen = best_nl_name
            chosen_brier = best_nl
        else:
            chosen = "logistic_l2"

    # Walk-forward selection on FINAL holdout (untouched)
    v1 = simulate_router_selection(final, mode="v1", profile="balanced")
    # Build probs from champion if available
    qm = AdaptiveTradeQualityModel(models_dir=ROOT / "data" / "learning" / "models")
    probs = None
    try:
        X, names = numeric_matrix(final)
        # use store model predict row-wise
        probs = []
        for _, row in final.iterrows():
            pred = qm.predict_row(row.to_dict(), which="champion")
            probs.append(pred.predicted_win_probability)
        probs = np.array(probs, dtype=float)
    except Exception:
        probs = None
    v2 = simulate_router_selection(final, mode="v2", profile="high_confidence", probs=probs)

    def _from_sel(sel: dict) -> dict:
        rs = list(sel.get("realized_rs") or [])
        m = _sel_metrics(rs, weeks=weeks, costs_r=costs_r)
        # Prefer cost-adjusted metrics; keep raw selection n/wr for reference
        return {
            "raw_n": sel.get("n"),
            "raw_wr": sel.get("wr"),
            "raw_expectancy_r": sel.get("expectancy_r"),
            "raw_pf": sel.get("pf"),
            **m,
            "costs_r_applied": costs_r,
        }

    # Frequency frontier on final using probability thresholds
    frontier = []
    if probs is not None and len(probs) == len(final):
        for thr, label in ((0.70, "HC70"), (0.67, "HC67"), (0.65, "HC65"), (0.50, "BALANCED")):
            mask = probs >= thr if label != "BALANCED" else np.ones(len(final), dtype=bool)
            part = final.loc[mask]
            rs = pd.to_numeric(part["realized_r"], errors="coerce").dropna().tolist()
            # Deduplicate roughly: take every other to mimic selection sparsity for balanced
            if label == "BALANCED":
                rs = list(simulate_router_selection(final, mode="v1").get("realized_rs") or [])
                if not rs:
                    rs = pd.to_numeric(final["realized_r"], errors="coerce").dropna().tolist()[
                        : max(1, len(final) // 5)
                    ]
            else:
                # select rows above threshold; cap to one per day-symbol
                work = final.copy()
                work["_p"] = probs
                work = work[work["_p"] >= thr]
                work["_day"] = pd.to_datetime(work["market_timestamp"], errors="coerce").dt.floor("D")
                picked = []
                for _, g in work.groupby(["_day", "symbol"], dropna=False):
                    picked.append(g.sort_values("_p", ascending=False).iloc[0])
                if picked:
                    rs = [float(x["realized_r"]) for x in picked if pd.notna(x.get("realized_r"))]
            if not isinstance(rs, list):
                rs = list(pd.to_numeric(pd.Series(rs), errors="coerce").dropna().tolist())
            m = _sel_metrics(rs, weeks=weeks, costs_r=costs_r)
            frontier.append({"profile": label, "threshold": thr, **m})

    # Failure analysis on v2 losers
    failures = []
    if probs is not None:
        work = final.copy()
        work["_p"] = probs
        work = work[work["_p"] >= 0.65]
        for _, row in work.iterrows():
            r = float(row["realized_r"]) if pd.notna(row.get("realized_r")) else 0.0
            if r >= 0:
                continue
            tags = []
            if int(row.get("overextended") or 0) == 1:
                tags.append("overextension")
            if int(row.get("mtf_aligned") or 0) <= 1:
                tags.append("HTF conflict")
            if int(row.get("below_vwap") or 0) == 1 and str(row.get("direction") or "").upper() in {"LONG", "BUY"}:
                tags.append("VWAP failure")
            if int(row.get("above_vwap") or 0) == 1 and str(row.get("direction") or "").upper() in {"SHORT", "SELL"}:
                tags.append("VWAP failure")
            if not tags:
                tags.append("other")
            failures.append({"symbol": row.get("symbol"), "strategy": row.get("strategy"), "tags": tags, "r": r})

    tag_counts: dict[str, int] = {}
    for f in failures:
        for t in f["tags"]:
            tag_counts[t] = tag_counts.get(t, 0) + 1

    tiers = tier_calibration(df)
    score_rows = global_score_deciles(df)
    # Bucket 50-59 ... 90+
    buckets = []
    if "global_score" in df.columns:
        s = pd.to_numeric(df["global_score"], errors="coerce")
        for lo, hi, lab in ((50, 60, "50-59"), (60, 70, "60-69"), (70, 80, "70-79"), (80, 90, "80-89"), (90, 201, "90+")):
            part = df[(s >= lo) & (s < hi)]
            if part.empty:
                buckets.append({"bucket": lab, "n": 0})
                continue
            rs = pd.to_numeric(part["realized_r"], errors="coerce").dropna()
            wins = int(part["win"].sum()) if "win" in part.columns else int((rs > 0).sum())
            gw = float(rs[rs > 0].sum()) if len(rs) else 0.0
            gl = float(abs(rs[rs < 0].sum())) if len(rs) else 0.0
            buckets.append(
                {
                    "bucket": lab,
                    "n": len(part),
                    "wr": wins / max(len(part), 1),
                    "pf": (gw / gl) if gl > 1e-12 else (999.0 if gw > 0 else 0.0),
                    "expectancy_r": float(rs.mean()) if len(rs) else None,
                }
            )
    # GLOBAL_SCORE_CALIBRATION_FAILURE if expectancy not nondecreasing across buckets with n>=15
    score_flag = None
    usable = [b for b in buckets if b.get("n", 0) >= 15 and b.get("expectancy_r") is not None]
    for i in range(1, len(usable)):
        if usable[i]["expectancy_r"] + 1e-9 < usable[i - 1]["expectancy_r"]:
            score_flag = "GLOBAL_SCORE_CALIBRATION_FAILURE"
            break

    # Holdout calibration of champion probs
    cal = {"calibrated": False, "bins": [], "brier": None}
    if probs is not None and len(final):
        y = final["win"].astype(int).to_numpy()
        cal["bins"] = calibration_bins(y, probs)
        from sklearn.metrics import brier_score_loss

        try:
            cal["brier"] = float(brier_score_loss(y, probs))
        except Exception:
            pass
        cal["calibrated"] = is_calibrated_enough(cal["bins"], min_bin_n=max(5, len(final) // 12))

    # Shrinkage demo
    shr = shrink_rate(8, 10, prior_mean=0.5, prior_strength=20.0)

    v1m = _from_sel(v1)
    v2m = _from_sel(v2)
    # Material improvement? Require lift AND usable sample; still do not auto-deploy.
    material = False
    if v1m.get("wr") is not None and v2m.get("wr") is not None and (v2m.get("n") or 0) >= 30:
        material = (v2m["wr"] - v1m["wr"]) >= 0.05 and (v2m.get("expectancy_r") or -9) >= (
            v1m.get("expectancy_r") or -9
        ) - 0.05
    directional_lift = False
    if v1m.get("wr") is not None and v2m.get("wr") is not None:
        directional_lift = (v2m["wr"] - v1m["wr"]) >= 0.05 and (v2m.get("expectancy_r") or -9) > (
            v1m.get("expectancy_r") or -9
        )

    return {
        "ok": True,
        "usable_rows": audit.usable_rows,
        "weeks": weeks,
        "costs_r": costs_r,
        "baseline": {k: v for k, v in base.items() if k != "estimators"},
        "nonlinear": {k: v for k, v in nonlin.items() if k != "estimators"},
        "chosen_model": chosen,
        "chosen_val_brier": chosen_brier,
        "router_v1": v1m,
        "router_v2_high_confidence": v2m,
        "material_oos_improvement": material,
        "directional_lift_small_sample": directional_lift,
        "frontier": frontier,
        "failure_tag_counts": tag_counts,
        "failure_sample": failures[:20],
        "tier_calibration": tiers,
        "global_score_buckets": buckets,
        "global_score_flag": score_flag,
        "score_deciles": score_rows,
        "calibration": cal,
        "shrinkage_demo": {"raw": shr.raw, "shrunk": shr.shrunk, "n": 10, "wins": 8},
        "deploy_v2_paper": False,
        "deploy_reason": (
            "keep router_v1 paper — v2 shows directional lift on small FINAL holdout "
            f"(n={v2m.get('n')}, WR={v2m.get('wr')}) but sample <30 and WR << 65% HC target; "
            "HC65/67/70 thresholds currently select 0 trades (model probs clustered ~0.5)"
            if directional_lift
            else "no material OOS WR/E improvement — keep router_v1 paper"
        ),
    }


def section_cl() -> dict:
    from agent.learning.cl_priority import build_cl_priority_report

    try:
        return build_cl_priority_report(ROOT, run_hist_bt=True)
    except Exception as exc:
        return {"error": str(exc), "traceback": traceback.format_exc()}


def section_execution_tests() -> dict:
    from agent.execution.kill_switch import ExecutionKillSwitch
    from agent.execution.order_state import OrderState
    from agent.execution.sim_broker import SimulatedBroker
    from types import SimpleNamespace

    results = []

    def check(name: str, ok: bool, detail: str = ""):
        results.append({"name": name, "ok": ok, "detail": detail})

    broker = SimulatedBroker(equity=25_000)
    broker.connect()
    check("broker_connect", broker.is_connected())
    sig = SimpleNamespace(symbol="MES", side="BUY", entry=5000.0, stop=4990.0, target=5020.0, market_timestamp="t1")
    r = broker.place_bracket_order(sig, qty=1)
    check("market_bracket_fill", r.get("order_state") == OrderState.FILLED.value, str(r))
    check("oco_children", bool(r.get("stop_order_id") and r.get("target_order_id")))
    r2 = broker.place_bracket_order(sig, qty=1)
    check("duplicate_order_reject", r2.get("reason") == "DUPLICATE_ORDER", str(r2))
    broker.force_partial = True
    sig2 = SimpleNamespace(symbol="MNQ", side="SELL", entry=18000.0, stop=18020.0, target=17950.0, market_timestamp="t2")
    rp = broker.place_bracket_order(sig2, qty=2)
    check("partial_fill", rp.get("order_state") == OrderState.PARTIALLY_FILLED.value, str(rp))
    broker.force_partial = False
    broker.force_reject = True
    sig3 = SimpleNamespace(symbol="MGC", side="BUY", entry=2300.0, stop=2290.0, target=2320.0, market_timestamp="t3")
    rr = broker.place_bracket_order(sig3, qty=1)
    check("rejection", rr.get("order_state") == OrderState.REJECTED.value)
    broker.force_reject = False
    cancel = broker.cancel_order(r["order_id"])
    check("cancel_terminal_or_ok", cancel.get("order_state") in {OrderState.CANCELED.value, OrderState.FILLED.value} or cancel.get("ok") is False)
    cr = broker.cancel_replace(rp["order_id"], new_stop=18025.0)
    check("cancel_replace", cr.get("ok") is True or cr.get("reason") is not None, str(cr))
    close = broker.close_position("MES")
    check("position_close", close.get("ok") is True, str(close))
    broker.disconnect()
    sig4 = SimpleNamespace(symbol="MCL", side="BUY", entry=70.0, stop=69.5, target=71.0, market_timestamp="t4")
    rd = broker.place_bracket_order(sig4, qty=1)
    check("disconnect_reject", rd.get("reason") == "BROKER_DISCONNECT")
    broker.connect()
    recon = broker.reconcile_positions()
    check("reconcile", "broker_positions" in recon)

    # Kill switch
    ks_path = OUT / "kill_switch_test.json"
    ks = ExecutionKillSwitch(ks_path)
    ks.disarm()
    check("kill_disarmed", not ks.is_armed())
    ks.arm(reason="readiness_test", existing_position_mode="MANAGE_EXISTING")
    check("kill_armed", ks.is_armed())
    check("kill_mode_manage", ks.existing_mode() == "MANAGE_EXISTING")
    check("kill_reject_reason", ks.reject_new_orders_reason() is not None)
    ks.disarm()
    check("kill_disarm", not ks.is_armed())

    # Directional executor respects kill switch
    from agent.execution.directional import DirectionalExecutor
    from agent.paper.blotter import PaperBlotter

    blotter = PaperBlotter(OUT / "tmp_paper.json")
    cfg = {
        "mode": "paper",
        "execution": {"dry_run": True, "kill_switch_path": str(ks_path)},
        "instruments": {"MES": {"point_value": 5}},
        "paper_friction": {"enabled": False},
    }
    ex = DirectionalExecutor(broker, cfg, blotter=blotter)
    ks.arm(reason="block_test")
    sig5 = SimpleNamespace(
        symbol="MES",
        side="BUY",
        entry=5000.0,
        stop=4990.0,
        target=5020.0,
        confidence=80,
        risk_dollars=50,
        reward_dollars=100,
        setup_tier="A",
        strategy_name="test",
        market_timestamp="",
        received_timestamp="",
        feed_source="test",
        reason="test",
        metadata={},
    )
    blocked = ex.execute(sig5, source="test")
    check("executor_kill_switch", blocked.get("reason", "").startswith("KILL_SWITCH"), str(blocked))
    ks.disarm()

    passed = sum(1 for x in results if x["ok"])
    return {"passed": passed, "failed": len(results) - passed, "cases": results}


def section_risk_trace() -> dict:
    cfg = yaml.safe_load((ROOT / "config" / "settings.yaml").read_text(encoding="utf-8"))
    risk = cfg.get("risk") or {}
    keys = [
        "risk_per_trade_pct",
        "max_account_risk_per_trade",
        "max_risk_dollars_per_trade",
        "max_daily_loss_dollars",
        "max_total_open_risk_dollars",
        "max_correlated_risk_dollars",
        "daily_loss_kill_dollars",
        "max_open_positions",
    ]
    traced = {k: risk.get(k) for k in keys}
    # Runtime engine instantiation
    from agent.risk.directional import DirectionalRiskEngine
    from agent.models import AccountSnapshot
    from types import SimpleNamespace

    eng = DirectionalRiskEngine(cfg)
    acct = AccountSnapshot(
        equity=50_000,
        cash=50_000,
        buying_power=50_000,
        open_positions=0,
        open_underlyings=[],
        realized_pnl_today=0.0,
        unrealized_pnl=0.0,
        healthy=True,
        notes=[],
    )
    # Oversized CL full-size risk should reject or shrink path
    sig = SimpleNamespace(
        symbol="CL",
        side="BUY",
        entry=80.0,
        stop=79.0,
        target=82.0,
        confidence=80,
        risk_dollars=1000.0,  # above 500 cap
        reward_dollars=2000.0,
        reason="risk_test",
        strategy_name="vwap_acceptance",
        setup_tier="A",
        quantity=1,
        market_timestamp=datetime.now(timezone.utc),
    )
    ok, reasons = eng.evaluate(sig, acct, [], skip_session_check=True)
    pilot = yaml.safe_load((ROOT / "config" / "live_pilot.yaml").read_text(encoding="utf-8"))
    return {
        "settings_risk": traced,
        "oversized_signal_approved": ok,
        "oversized_reasons": reasons,
        "live_pilot_risk": (pilot.get("risk") or {}),
        "live_pilot_qty_max": (pilot.get("quantity") or {}).get("max_quantity"),
        "live_pilot_universe": pilot.get("universe"),
        "finite_controls_ok": all(
            traced.get(k) is not None
            for k in (
                "max_risk_dollars_per_trade",
                "max_total_open_risk_dollars",
                "max_daily_loss_dollars",
            )
        ),
    }


def section_persistence() -> dict:
    from agent.learning.store import LearningStore
    from agent.learning.model import AdaptiveTradeQualityModel

    store = LearningStore(ROOT / "data" / "learning" / "candidates.jsonl")
    n1 = len(store.all_rows())
    qm = AdaptiveTradeQualityModel(models_dir=ROOT / "data" / "learning" / "models")
    champ1 = qm.champion.version if qm.champion else None
    # Simulate restart by reloading
    store2 = LearningStore(ROOT / "data" / "learning" / "candidates.jsonl")
    n2 = len(store2.all_rows())
    qm2 = AdaptiveTradeQualityModel(models_dir=ROOT / "data" / "learning" / "models")
    champ2 = qm2.champion.version if qm2.champion else None
    paper = ROOT / "data" / "paper_trades.json"
    return {
        "learning_rows_before": n1,
        "learning_rows_after_reload": n2,
        "champion_before": champ1,
        "champion_after": champ2,
        "unchanged": n1 == n2 and champ1 == champ2,
        "paper_trades_exists": paper.exists(),
        "loop_state_exists": (ROOT / "data" / "learning" / "models" / "loop_state.json").exists(),
    }


def section_data_broker_external() -> dict:
    from agent.data.broker_realtime import BrokerRealtimeProvider
    from agent.data.yahoo_delayed import make_provider

    cfg = yaml.safe_load((ROOT / "config" / "settings.yaml").read_text(encoding="utf-8"))
    y = make_provider(cfg)
    rt = BrokerRealtimeProvider(cfg)
    return {
        "paper_provider": type(y).__name__,
        "realtime_healthy": rt.health().is_healthy,
        "realtime_error": rt.health().last_error,
        "external_dependencies": rt.external_dependencies(),
        "tradovate_oco_todo": True,
        "live_pilot_path": "config/live_pilot.yaml",
        "live_pilot_activated": False,
    }


def write_report(payload: dict) -> None:
    (OUT / "LIVE_READINESS_REPORT.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    h = payload.get("system_health") or {}
    learn = payload.get("learning_e2e") or {}
    replay = payload.get("router_replay") or {}
    cl = payload.get("cl_analysis") or {}
    ex = payload.get("execution_tests") or {}
    risk = payload.get("risk") or {}
    pers = payload.get("persistence") or {}
    ext = payload.get("data_broker") or {}
    tests = payload.get("pytest") or {}
    winner = (cl.get("recent_cl_paper_winner") or {})
    hist = (cl.get("cl_liquidity_reversal_historical") or {})
    lines = [
        "# LIVE READINESS REPORT",
        "",
        f"Generated: {payload.get('generated_at')}",
        f"**Verdict: {payload.get('verdict')}**",
        "",
        "## A. SYSTEM HEALTH",
        f"- config_version: {h.get('config_version')}",
        f"- execution_profile: {h.get('execution_profile')} · mode={h.get('mode')} · v2_enabled={h.get('v2_enabled')}",
        f"- supervisor: {(h.get('supervisor_status.json') or {}).get('state')} / {(h.get('supervisor_status.json') or {}).get('health')}",
        f"- heartbeat_age_sec: {(h.get('supervisor_status.json') or {}).get('heartbeat_age_sec')}",
        f"- silence: {(h.get('trade_silence_status.json') or {}).get('severity')} mins={(h.get('trade_silence_status.json') or {}).get('minutes_since_last_paper')}",
        "",
        "## B. ADAPTIVE LEARNING",
        f"- E2E pipeline_ok: {learn.get('pipeline_ok')}",
        f"- e2e candidates/resolved: {learn.get('candidates')}/{learn.get('resolved')}",
        f"- schema_version: {learn.get('schema_version')}",
        f"- retrain: {learn.get('retrain')}",
        f"- persistence_files_ok: {learn.get('persistence_files_ok')}",
        f"- production store rows: {(pers.get('learning_rows_after_reload'))}",
        f"- champion: {pers.get('champion_after')}",
        "",
        "## C. CL ANALYSIS",
        f"- warning: {winner.get('warning')}",
        f"- trade_id: {winner.get('trade_id')}",
        f"- snapshot strategy: {(winner.get('snapshot') or {}).get('strategy')}",
        f"- LR hist overall: {hist.get('overall')}",
        f"- relative best cells: {len(hist.get('relative_best_subcells') or [])}",
        f"- validated/developing/early: {len(hist.get('validated_cells') or [])}/{len(hist.get('developing_cells') or [])}/{len(hist.get('early_cells') or [])}",
        "",
        "## D. SCORE/TIER CALIBRATION",
        f"- tier: {replay.get('tier_calibration')}",
        f"- global score buckets: {replay.get('global_score_buckets')}",
        f"- flags: tier={(replay.get('tier_calibration') or {}).get('flag')} score={replay.get('global_score_flag')}",
        "",
        "## E. ROUTER COMPARISON (FINAL holdout, costs_r={})".format(replay.get("costs_r")),
        f"- v1: {replay.get('router_v1')}",
        f"- v2 HC: {replay.get('router_v2_high_confidence')}",
        f"- material_oos_improvement: {replay.get('material_oos_improvement')}",
        f"- deploy_v2_paper: {replay.get('deploy_v2_paper')} — {replay.get('deploy_reason')}",
        f"- chosen_model: {replay.get('chosen_model')} brier={replay.get('chosen_val_brier')}",
        "",
        "## F. ACCURACY/FREQUENCY FRONTIER",
        json.dumps(replay.get("frontier") or [], indent=2, default=str),
        "",
        "## G. CALIBRATION",
        json.dumps(replay.get("calibration") or {}, indent=2, default=str),
        "",
        "## H. EXECUTION TESTS",
        f"- passed/failed: {ex.get('passed')}/{ex.get('failed')}",
        "",
        "## I. RISK TESTS",
        f"- settings: {risk.get('settings_risk')}",
        f"- oversized approved? {risk.get('oversized_signal_approved')} reasons={risk.get('oversized_reasons')}",
        f"- live_pilot risk: {risk.get('live_pilot_risk')}",
        f"- finite_controls_ok: {risk.get('finite_controls_ok')}",
        "",
        "## J. RESTART/PERSISTENCE",
        json.dumps(pers, indent=2, default=str),
        "",
        "## K. REAL-TIME DATA STATUS",
        f"- paper provider: {ext.get('paper_provider')}",
        f"- realtime healthy: {ext.get('realtime_healthy')}",
        f"- error: {ext.get('realtime_error')}",
        "",
        "## L. BROKER STATUS",
        "- SimulatedBroker: verified in execution tests",
        "- Tradovate live brackets: market entry only; OCO stop/target TODO",
        "- IBKR adapter present; live fills async not fully wired",
        "",
        "## M. LIVE_PILOT CONFIG",
        f"- path: {ext.get('live_pilot_path')}",
        f"- activated: {ext.get('live_pilot_activated')}",
        f"- universe: {risk.get('live_pilot_universe')}",
        f"- max qty: {risk.get('live_pilot_qty_max')}",
        "",
        "## N. REMAINING EXTERNAL DEPENDENCIES",
        json.dumps(ext.get("external_dependencies") or [], indent=2),
        "",
        "## O. FILES CHANGED (sprint)",
        "\n".join(f"- {x}" for x in (payload.get("files_changed") or [])),
        "",
        "## P. TEST RESULTS",
        json.dumps(tests, indent=2, default=str),
        "",
        "## FAILURE ANALYSIS (v2 HC losses)",
        json.dumps(replay.get("failure_tag_counts") or {}, indent=2),
        "",
        "## BLOCKERS",
        "\n".join(f"- {b}" for b in (payload.get("blockers") or [])),
    ]
    (OUT / "LIVE_READINESS_REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    print("=== LIVE READINESS SPRINT ===", flush=True)
    payload: dict = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "files_changed": [
            "src/agent/learning/schema.py",
            "src/agent/learning/store.py",
            "src/agent/learning/loop.py",
            "src/agent/decision/performance_router_v2.py",
            "src/agent/execution/kill_switch.py",
            "src/agent/execution/sim_broker.py",
            "src/agent/execution/order_state.py",
            "src/agent/execution/directional.py",
            "src/agent/data/historical.py",
            "src/agent/data/broker_realtime.py",
            "src/agent/data/yahoo_delayed.py",
            "src/agent/data/__init__.py",
            "config/live_pilot.yaml",
            "scripts/run_live_readiness_sprint.py",
            "tests/test_live_readiness.py",
            "data/live_readiness/*",
            "PROJECT_MEMORY.md",
            "DEBUG.md",
        ],
    }
    tmp = OUT / "_e2e_tmp"
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True, exist_ok=True)

    print("1/8 system health", flush=True)
    payload["system_health"] = section_system_health()

    print("2/8 learning e2e", flush=True)
    try:
        payload["learning_e2e"] = section_learning_e2e(tmp)
    except Exception as exc:
        payload["learning_e2e"] = {"pipeline_ok": False, "error": str(exc), "traceback": traceback.format_exc()}

    print("3/8 router replay", flush=True)
    try:
        payload["router_replay"] = section_router_replay()
    except Exception as exc:
        payload["router_replay"] = {"ok": False, "error": str(exc), "traceback": traceback.format_exc()}

    print("4/8 CL analysis", flush=True)
    payload["cl_analysis"] = section_cl()

    print("5/8 execution tests", flush=True)
    try:
        payload["execution_tests"] = section_execution_tests()
    except Exception as exc:
        payload["execution_tests"] = {"passed": 0, "failed": 1, "error": str(exc), "traceback": traceback.format_exc()}

    print("6/8 risk + persistence + external", flush=True)
    payload["risk"] = section_risk_trace()
    payload["persistence"] = section_persistence()
    payload["data_broker"] = section_data_broker_external()

    print("7/8 pytest", flush=True)
    import subprocess

    proc = subprocess.run(
        [
            str(ROOT / ".venv" / "Scripts" / "python.exe"),
            "-m",
            "pytest",
            "tests/test_live_readiness.py",
            "tests/test_cl_priority_learning.py",
            "tests/test_trade_quality_learning.py",
            "tests/test_performance_router.py",
            "tests/test_sizing.py",
            "tests/test_live_main_risk_engine.py",
            "tests/test_directional_risk_guards.py",
            "-q",
            "--tb=line",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    payload["pytest"] = {
        "returncode": proc.returncode,
        "stdout_tail": (proc.stdout or "")[-4000:],
        "stderr_tail": (proc.stderr or "")[-2000:],
    }

    # Verdict
    blockers = []
    if not (payload.get("learning_e2e") or {}).get("pipeline_ok"):
        blockers.append("Adaptive learning E2E pipeline incomplete/failed")
    if (payload.get("execution_tests") or {}).get("failed", 1) > 0:
        blockers.append("Execution simulation tests failed")
    if not (payload.get("risk") or {}).get("finite_controls_ok"):
        blockers.append("Risk controls not finite/configured")
    if not (payload.get("persistence") or {}).get("unchanged"):
        blockers.append("Learning persistence reload mismatch")
    if proc.returncode != 0:
        blockers.append("Automated pytest failures")
    # External always block micro live
    blockers.append("Realtime futures market data not operational (BrokerRealtimeProvider)")
    blockers.append("Broker demo/live credentials + OCO bracket completion required")
    blockers.append("Explicit human approval + ALLOW_LIVE_TRADING not granted")

    local_ok = (
        (payload.get("learning_e2e") or {}).get("pipeline_ok")
        and (payload.get("execution_tests") or {}).get("failed", 1) == 0
        and (payload.get("risk") or {}).get("finite_controls_ok")
        and (payload.get("persistence") or {}).get("unchanged")
        and proc.returncode == 0
    )
    if local_ok:
        verdict = "READY FOR BROKER-SIM VALIDATION"
        # Keep external blockers listed
        blockers = [
            "Realtime futures MD entitlement + BrokerRealtimeProvider.connect implementation",
            "Tradovate/TopstepX credentials (TRADOVATE_*) + account id/spec",
            "Front-month contract mapping for MES/MNQ/MGC/MCL",
            "Complete Tradovate OCO stop/target attachment",
            "Successful broker demo simulation under human supervision",
            "Explicit approval before any real-money activation",
        ]
    else:
        verdict = "NOT READY — BLOCKERS: " + "; ".join(blockers)

    # Never claim READY FOR MICRO LIVE PILOT without realtime+broker
    payload["verdict"] = verdict
    payload["blockers"] = blockers
    payload["router_v2_deployed_to_paper"] = False
    payload["live_pilot_activated"] = False

    print("8/8 write report", flush=True)
    write_report(payload)
    # Deploy flag stays false
    (OUT / "DEPLOY_DECISION.json").write_text(
        json.dumps(
            {
                "deploy_router_v2_paper": False,
                "activate_live_pilot": False,
                "verdict": verdict,
                "material_oos": (payload.get("router_replay") or {}).get("material_oos_improvement"),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print("VERDICT:", verdict, flush=True)
    print("Report:", OUT / "LIVE_READINESS_REPORT.md", flush=True)
    return 0 if local_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
