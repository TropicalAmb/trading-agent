"""Full trade-quality learning pass: dataset → models → cells → v1 vs v2 OOS."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent.learning.analyze import (
    feature_lift_table,
    global_score_deciles,
    high_accuracy_cells,
    interaction_table,
    simulate_router_selection,
    tier_calibration,
)
from agent.learning.dataset import build_unified_dataset, numeric_matrix, time_splits
from agent.learning.health import StrategyHealthStore
from agent.learning.model import (
    AdaptiveTradeQualityModel,
    ModelBundle,
    calibration_bins,
    is_calibrated_enough,
    train_baseline_models,
    train_nonlinear_models,
)
from agent.learning.shrink import shrink_rate
from agent.decision.performance_router import router_from_cfg
from agent.research.harness.datasets import fetch_yahoo
from agent.research.missed_moves import scan_missed_moves

OUT = ROOT / "data" / "trade_quality_learning"
YAHOO = {"NQ": "NQ=F", "ES": "ES=F", "GC": "GC=F", "CL": "CL=F", "MNQ": "MNQ=F", "MES": "MES=F", "MYM": "YM=F", "MGC": "MGC=F", "MCL": "MCL=F", "M2K": "M2K=F"}


def _discovery_hypotheses(lifts: dict, interactions: list) -> list[dict]:
    hyps = []
    for w in (lifts.get("winner_features") or [])[:5]:
        if w.get("lift_pp", 0) >= 5 and w.get("n", 0) >= 12:
            hyps.append(
                {
                    "name": f"discovery_{w['feature']}".replace(" ", "_")[:80],
                    "mode": "SHADOW_ONLY",
                    "rule": w["feature"],
                    "evidence_lift_pp": w["lift_pp"],
                    "n": w["n"],
                    "status": "HYPOTHESIS",
                }
            )
    for it in interactions[:5]:
        if it.get("lift_pp", 0) >= 6 and it.get("n", 0) >= 15:
            hyps.append(
                {
                    "name": f"discovery_{it['interaction']}_{it['values']}"[:80],
                    "mode": "SHADOW_ONLY",
                    "rule": str(it),
                    "evidence_lift_pp": it["lift_pp"],
                    "n": it["n"],
                    "status": "HYPOTHESIS",
                }
            )
    return hyps


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    print("Building unified dataset + optional bar backfill...", flush=True)
    # Light backfill for top symbols present in data
    raw_df, audit0 = build_unified_dataset(backfill_bars=False)
    symbols = sorted(set(raw_df["symbol"].astype(str)) & set(YAHOO)) if len(raw_df) else []
    cache = {}
    for sym in symbols[:8]:
        print(f"  bars {sym}", flush=True)
        try:
            cache[sym] = fetch_yahoo(YAHOO[sym], "5m", "60d")
        except Exception as exc:
            print(f"  skip bars {sym}: {exc}", flush=True)
    df, audit = build_unified_dataset(backfill_bars=True, bar_cache=cache)
    (OUT / "dataset_audit.json").write_text(json.dumps(audit.to_dict(), indent=2), encoding="utf-8")
    df.to_csv(OUT / "unified_candidates.csv", index=False)
    print(f"usable_rows={audit.usable_rows} range={audit.date_min} -> {audit.date_max}", flush=True)

    splits = time_splits(df)
    for k, v in splits.items():
        print(f"  split {k}: n={len(v)}", flush=True)

    # Baselines
    print("Training baselines...", flush=True)
    base = train_baseline_models(splits["train"], splits["val"], target="win")
    nonlin = train_nonlinear_models(splits["train"], splits["val"], target="win")
    (OUT / "baseline_models.json").write_text(
        json.dumps({k: v for k, v in base.items() if k != "estimators"}, indent=2, default=str),
        encoding="utf-8",
    )
    (OUT / "nonlinear_models.json").write_text(
        json.dumps({k: v for k, v in nonlin.items() if k != "estimators"}, indent=2, default=str),
        encoding="utf-8",
    )

    # Pick champion candidate from val brier
    pick = None
    est = None
    feat_names = []
    if base.get("ok"):
        for name, block in base["models"].items():
            b = (block.get("val") or {}).get("brier")
            if b is None:
                continue
            if pick is None or b < pick[0]:
                pick = (b, name, block)
                est = base["estimators"].get(name)
                feat_names = base.get("feature_names") or []
    if nonlin.get("ok"):
        for name, block in nonlin["models"].items():
            b = (block.get("val") or {}).get("brier")
            if b is None:
                continue
            if pick is None or b < pick[0]:
                pick = (b, name, block)
                est = nonlin["estimators"].get(name)
                feat_names = nonlin.get("feature_names") or []

    final = splits["final"]
    cal_report = {"calibrated": False, "bins": [], "brier_final": None}
    probs_final = None
    if est is not None and len(final):
        Xf, names = numeric_matrix(final)
        Xf_df = pd.DataFrame(Xf, columns=names)
        for c in feat_names:
            if c not in Xf_df.columns:
                Xf_df[c] = 0.0
        Xf = Xf_df[feat_names].to_numpy(dtype=float) if feat_names else Xf
        yf = final["win"].astype(int).to_numpy()
        probs_final = est.predict_proba(Xf)[:, 1]
        from sklearn.metrics import brier_score_loss

        cal_report["brier_final"] = float(brier_score_loss(yf, probs_final)) if len(np.unique(yf)) > 1 else None
        cal_report["bins"] = calibration_bins(yf, probs_final)
        cal_report["calibrated"] = is_calibrated_enough(
            cal_report["bins"], min_bin_n=max(4, len(final) // 10)
        )
        print(
            f"FINAL brier={cal_report['brier_final']} calibrated={cal_report['calibrated']}",
            flush=True,
        )

    # Persist model as challenger (and champion if none / calibrated)
    qm = AdaptiveTradeQualityModel(models_dir=OUT / "models")
    if est is not None and pick is not None:
        prior_wr = float(splits["train"]["win"].mean()) if len(splits["train"]) else 0.5
        prior_e = float(pd.to_numeric(splits["train"]["realized_r"], errors="coerce").mean() or 0)
        bundle = ModelBundle(
            version=f"trade_quality_v1_{datetime.now(timezone.utc).strftime('%Y%m%d')}",
            kind=pick[1],
            feature_names=list(feat_names),
            coefficients=pick[2].get("coefficients"),
            importances=pick[2].get("importances"),
            intercept=pick[2].get("intercept"),
            calibrated=bool(cal_report["calibrated"]),
            brier_score=float(pick[0]),
            train_n=len(splits["train"]),
            val_n=len(splits["val"]),
            created_at=datetime.now(timezone.utc).isoformat(),
            prior_win_rate=prior_wr,
            prior_expectancy_r=prior_e,
        )
        qm.save_bundle(qm.challenger_name, bundle, estimator=est)
        # Seed paper models dir too
        paper_qm = AdaptiveTradeQualityModel(models_dir=ROOT / "data" / "learning" / "models")
        paper_qm.save_bundle(paper_qm.challenger_name, bundle, estimator=est)
        if paper_qm.champion is None:
            paper_qm.promote_challenger_to_champion(new_version=bundle.version)
            print("Seeded paper champion model", bundle.version, flush=True)

    lifts = feature_lift_table(df, target="win")
    interactions = interaction_table(df, target="win", min_n=12)
    cells = high_accuracy_cells(df)
    tiers = tier_calibration(df)
    score_dec = global_score_deciles(df)

    # Shrinkage demo on strategy global cells
    shrink_rows = []
    for strat, part in df.groupby("strategy"):
        n = len(part)
        wins = int(part["win"].sum())
        shr = shrink_rate(wins, n, prior_mean=float(df["win"].mean()), prior_strength=20.0)
        shrink_rows.append(
            {
                "strategy": strat,
                "n": n,
                "raw_wr": shr.raw,
                "shrunk_wr": shr.shrunk,
                "prior": shr.prior_mean,
            }
        )

    # Router v1 vs v2 selection on FINAL
    v1_sel = simulate_router_selection(final, mode="v1")
    v2_sel = simulate_router_selection(
        final, mode="v2", profile="high_confidence", probs=probs_final if probs_final is not None and len(probs_final) == len(final) else None
    )
    v2_bal = simulate_router_selection(
        final, mode="v2", profile="balanced", probs=probs_final if probs_final is not None and len(probs_final) == len(final) else None
    )

    # Material improvement?
    def _score(s):
        if not s or not s.get("n"):
            return -999
        return float(s.get("expectancy_r") or 0) + 0.5 * float(s.get("wr") or 0)

    improve = _score(v2_sel) > _score(v1_sel) + 0.02 and (v2_sel.get("n") or 0) >= 8
    improve_bal = _score(v2_bal) > _score(v1_sel) + 0.02 and (v2_bal.get("n") or 0) >= 8
    deploy_v2 = bool((improve or improve_bal) and cal_report.get("calibrated"))

    # Missed-move archetypes (sample)
    archetypes = []
    for sym in list(cache.keys())[:3]:
        dfc = cache[sym]
        if dfc is None or len(dfc) < 100:
            continue
        mm = scan_missed_moves(dfc, symbol=sym, candidates_by_bar={}, stride=6)
        # Pre-move feature clusters via simple rules on bars before move index
        from agent.context.market_context import build_market_context
        from agent.context.regime import MarketRegimeClassifier

        counts = {"mtf_trend_compression": 0, "vwap_hold_pullback": 0, "sweep_like_wick": 0, "other": 0}
        for m in mm[:80]:
            try:
                ts = pd.Timestamp(m.bar_ts)
                hist = dfc.loc[:ts].iloc[:-1]
                if len(hist) < 50:
                    counts["other"] += 1
                    continue
                ctx = build_market_context(hist, regime_result=MarketRegimeClassifier().classify(hist))
                last = hist.iloc[-1]
                rng = float(last["high"] - last["low"]) or 1e-9
                wick = max(float(last["high"] - max(last["close"], last["open"])), float(min(last["close"], last["open"]) - last["low"]))
                if abs(ctx.direction_1h) + abs(ctx.direction_4h) >= 2 and float(ctx.regime_confidence) > 0.4:
                    counts["mtf_trend_compression"] += 1
                elif (ctx.above_vwap or ctx.below_vwap) and not (ctx.overextended_long or ctx.overextended_short):
                    counts["vwap_hold_pullback"] += 1
                elif wick / rng > 0.45:
                    counts["sweep_like_wick"] += 1
                else:
                    counts["other"] += 1
            except Exception:
                counts["other"] += 1
        archetypes.append({"symbol": sym, "missed_sample": min(80, len(mm)), "clusters": counts})

    hyps = _discovery_hypotheses(lifts, interactions)
    (OUT / "discovery_hypotheses.json").write_text(json.dumps(hyps, indent=2), encoding="utf-8")
    # Shadow-only discovery patterns (never auto-execute)
    discovery_shadows = []
    for h in hyps:
        name = str(h.get("name") or "unnamed")
        if not name.startswith("DISCOVERY_SHADOW_"):
            name = f"DISCOVERY_SHADOW_{name}"
        discovery_shadows.append(
            {
                **h,
                "name": name,
                "mode": "SHADOW_ONLY",
                "status": "HYPOTHESIS",
                "auto_execute": False,
            }
        )
    disc_dir = ROOT / "data" / "learning" / "discovery_shadows"
    disc_dir.mkdir(parents=True, exist_ok=True)
    (disc_dir / "DISCOVERY_SHADOW_REGISTRY.json").write_text(
        json.dumps(
            {
                "generated": datetime.now(timezone.utc).isoformat(),
                "patterns": discovery_shadows,
                "note": "Shadow until validated OOS — do not wire into paper execution",
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    # Health update from router cells
    try:
        r = router_from_cfg(
            {
                "performance_router": {
                    "enabled": True,
                    "trade_paths": ["data/paper_trades.json"],
                    "shadow_path": "data/shadow_trades.json",
                    "include_shadow": True,
                    "min_sample": 30,
                }
            }
        )
        hs = StrategyHealthStore(ROOT / "data" / "learning" / "strategy_cell_health.json")
        updated = hs.update_from_router_cells(r._cells, min_n=30)
    except Exception as exc:
        updated = {"error": str(exc)}

    # Expected frequency proxy
    weeks = 1.0
    if audit.date_min and audit.date_max:
        try:
            weeks = max((pd.Timestamp(audit.date_max) - pd.Timestamp(audit.date_min)).days / 7.0, 1.0)
        except Exception:
            weeks = 1.0
    tpw = len(df) / weeks

    report = {
        "generated": datetime.now(timezone.utc).isoformat(),
        "usable_rows": audit.usable_rows,
        "date_range": [audit.date_min, audit.date_max],
        "audit": audit.to_dict(),
        "baseline": {k: v for k, v in base.items() if k != "estimators"},
        "nonlinear": {k: v for k, v in nonlin.items() if k != "estimators"},
        "calibration": cal_report,
        "winner_features": lifts.get("winner_features"),
        "loser_features": lifts.get("loser_features"),
        "interactions": interactions[:25],
        "high_accuracy_cells_n100": cells.get("strong"),
        "promising_cells_n40": cells.get("promising"),
        "shrinkage": shrink_rows,
        "tier_calibration": tiers,
        "global_score_deciles": score_dec,
        "missed_move_archetypes": archetypes,
        "discovery_hypotheses": hyps,
        "router_v1_final_selection": v1_sel,
        "router_v2_high_confidence_final_selection": v2_sel,
        "router_v2_balanced_final_selection": v2_bal,
        "deploy_router_v2": deploy_v2,
        "deploy_reason": (
            "OOS selection improved AND calibration ok"
            if deploy_v2
            else "no material OOS improvement and/or calibration insufficient — keep v1"
        ),
        "expected_trades_per_week_proxy": tpw,
        "cell_health_updates": len(updated) if isinstance(updated, dict) else 0,
    }
    (OUT / "TRADE_QUALITY_LEARNING_REPORT.json").write_text(
        json.dumps(report, indent=2, default=str), encoding="utf-8"
    )

    # Markdown
    lines = [
        "# Trade Quality Learning Report",
        "",
        f"Generated: {report['generated']}",
        "",
        f"**Usable rows:** {audit.usable_rows}",
        f"**Date range:** {audit.date_min} → {audit.date_max}",
        f"**Sources:** {audit.sources}",
        f"**Duplicates removed:** {audit.duplicate_setup_ids}",
        f"**Legacy excluded:** {len(audit.legacy_excluded)}",
        "",
        "## Class balance",
        str(audit.class_balance),
        "",
        "## Baseline / nonlinear (val)",
        "",
    ]
    if base.get("ok"):
        for name, block in base["models"].items():
            lines.append(f"- {name}: val brier={(block.get('val') or {}).get('brier')} auc={(block.get('val') or {}).get('auc')}")
    if nonlin.get("ok"):
        for name, block in nonlin["models"].items():
            lines.append(f"- {name}: val brier={(block.get('val') or {}).get('brier')} auc={(block.get('val') or {}).get('auc')}")
    lines += [
        "",
        f"## FINAL holdout calibration: calibrated={cal_report['calibrated']} brier={cal_report['brier_final']}",
        "",
        "### Reliability bins",
    ]
    for b in cal_report.get("bins") or []:
        lines.append(f"- {b}")
    lines += ["", "## Top winner features"]
    for w in (lifts.get("winner_features") or [])[:10]:
        lines.append(f"- {w['feature']}: {w['lift_pp']:+.1f}pp (n={w['n']}, WR={w['wr']:.1%})")
    lines += ["", "## Top loser features"]
    for w in (lifts.get("loser_features") or [])[:10]:
        lines.append(f"- {w['feature']}: {w['lift_pp']:+.1f}pp (n={w['n']}, WR={w['wr']:.1%})")
    lines += ["", "## Tier calibration", str(tiers), "", "## Router v1 vs v2 (FINAL selection proxy)"]
    lines.append(f"- v1: {v1_sel}")
    lines.append(f"- v2 balanced: {v2_bal}")
    lines.append(f"- v2 high_confidence: {v2_sel}")
    lines.append(f"- **Deploy router_v2?** {deploy_v2} — {report['deploy_reason']}")
    lines += ["", "## High-accuracy cells (≥100)", str(cells.get("strong")), "", "## Promising (≥40)", str(cells.get("promising"))]
    lines += ["", "## Missed-move archetypes", str(archetypes), "", "## Discovery hypotheses", str(hyps)]
    (OUT / "TRADE_QUALITY_LEARNING_REPORT.md").write_text("\n".join(lines), encoding="utf-8")

    # Deploy decision for settings
    deploy_flag = OUT / "DEPLOY_ROUTER_V2.json"
    deploy_flag.write_text(json.dumps({"deploy": deploy_v2, "reason": report["deploy_reason"]}, indent=2), encoding="utf-8")
    print("Report:", OUT / "TRADE_QUALITY_LEARNING_REPORT.md")
    print("DEPLOY_V2:", deploy_v2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
