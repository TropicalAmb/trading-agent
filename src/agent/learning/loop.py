"""Operational learning loop — append snapshots, scheduled retrain, promotion."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from agent.learning.model import (
    AdaptiveTradeQualityModel,
    ModelBundle,
    calibration_bins,
    is_calibrated_enough,
    train_baseline_models,
    train_nonlinear_models,
)
from agent.learning.store import LearningStore


def _state_path(models_dir: Path) -> Path:
    return models_dir / "loop_state.json"


def load_loop_state(models_dir: str | Path) -> dict[str, Any]:
    p = _state_path(Path(models_dir))
    if not p.exists():
        return {"resolved_since_retrain": 0, "last_retrain_at": None}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {"resolved_since_retrain": 0, "last_retrain_at": None}


def save_loop_state(models_dir: str | Path, state: dict[str, Any]) -> None:
    p = _state_path(Path(models_dir))
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state, indent=2), encoding="utf-8")


def record_candidate_snapshot(
    cfg: dict[str, Any],
    *,
    setup: Any = None,
    row: dict[str, Any] | None = None,
    router_decision: str = "",
    executed_or_shadow: str = "SHADOW",
) -> Optional[dict[str, Any]]:
    tcfg = cfg.get("trade_quality_model") or {}
    if not bool(tcfg.get("enabled", True)):
        return None
    store = LearningStore(tcfg.get("learning_store", "data/learning/candidates.jsonl"))
    qm = AdaptiveTradeQualityModel(models_dir=tcfg.get("models_dir", "data/learning/models"))
    if setup is not None:
        meta = setup.metadata or {}
        feats = dict(meta.get("entry_features") or {})
        champ = qm.predict_row(feats, which="champion")
        chall = qm.predict_row(feats, which="challenger")
        payload = {
            "setup_id": meta.get("setup_id"),
            "timestamp": str(setup.market_timestamp),
            "market_timestamp": str(setup.market_timestamp),
            "symbol": setup.symbol,
            "strategy": setup.strategy_name,
            "session": setup.session,
            "regime": meta.get("regime"),
            "direction": setup.direction,
            "features": feats,
            "global_score": meta.get("global_score"),
            "local_score": meta.get("strategy_local_score"),
            "tier": setup.setup_tier,
            "champion_probability": champ.predicted_win_probability,
            "challenger_probability": chall.predicted_win_probability,
            "champion_model_version": champ.model_version,
            "challenger_model_version": chall.model_version,
            "router_decision": router_decision,
            "executed_or_shadow": executed_or_shadow,
            "entry": setup.entry,
            "stop": setup.stop,
            "target": setup.target,
            "final_result": "OPEN",
            "config_version": meta.get("config_version") or cfg.get("config_version"),
        }
        payload.update(feats)
        return store.append(payload)
    if row is not None:
        feats = dict(row.get("entry_features") or row.get("features") or {})
        champ = qm.predict_row({**row, **feats}, which="champion")
        chall = qm.predict_row({**row, **feats}, which="challenger")
        payload = {
            **row,
            "features": feats,
            "champion_probability": champ.predicted_win_probability,
            "challenger_probability": chall.predicted_win_probability,
            "champion_model_version": champ.model_version,
            "challenger_model_version": chall.model_version,
            "router_decision": router_decision or row.get("router_decision") or "",
            "executed_or_shadow": executed_or_shadow,
            "final_result": row.get("final_result") or "OPEN",
        }
        return store.append(payload)
    return None


def record_outcome_for_setup(
    cfg: dict[str, Any],
    *,
    setup_id: str | None,
    trade: dict[str, Any],
) -> bool:
    tcfg = cfg.get("trade_quality_model") or {}
    if not bool(tcfg.get("enabled", True)):
        return False
    store = LearningStore(tcfg.get("learning_store", "data/learning/candidates.jsonl"))
    meta = trade.get("metadata") if isinstance(trade.get("metadata"), dict) else {}
    sid = str(
        setup_id
        or trade.get("setup_id")
        or meta.get("setup_id")
        or ""
    )
    open_row = store.find_open_by_setup(sid) if sid else None
    # Fallback: match open candidate by symbol+strategy+entry time when setup_id missing
    if open_row is None:
        try:
            sym = str(trade.get("symbol") or "").upper()
            strat = str(trade.get("strategy_name") or trade.get("strategy") or "")
            ts = str(trade.get("market_timestamp") or trade.get("opened_at") or "")
            for row in store.all_rows():
                if str(row.get("final_result") or "OPEN") not in {"OPEN", ""}:
                    continue
                if str(row.get("symbol") or "").upper() != sym:
                    continue
                if strat and str(row.get("strategy") or "") != strat:
                    continue
                if ts and str(row.get("market_timestamp") or row.get("timestamp") or "")[:16] == ts[:16]:
                    open_row = row
                    sid = str(row.get("setup_id") or sid)
                    break
        except Exception:
            pass
    r = trade.get("r_achieved")
    if r is None:
        try:
            entry, stop, exit_px = float(trade["entry"]), float(trade["stop"]), float(trade["exit"])
            risk = abs(entry - stop)
            side = str(trade.get("side") or trade.get("direction") or "").upper()
            if risk > 0:
                r = (exit_px - entry) / risk if side in {"BUY", "LONG"} else (entry - exit_px) / risk
        except Exception:
            r = None
    # 1R hit before stop: MFE >= risk distance
    plus_1r = 0
    try:
        risk_pts = abs(float(trade["entry"]) - float(trade["stop"]))
        mfe = float(trade.get("mfe_pts") or trade.get("mfe") or 0)
        if risk_pts > 0 and mfe >= risk_pts * 0.99:
            plus_1r = 1
    except Exception:
        plus_1r = 1 if (r or 0) >= 1.0 else 0
    outcome = {
        "final_result": trade.get("result") or ("WIN" if (r or 0) > 0 else "LOSS"),
        "realized_r": r,
        "mfe_r": trade.get("mfe_r"),
        "mae_r": trade.get("mae_r"),
        "mfe_pts": trade.get("mfe_pts") or trade.get("mfe"),
        "mae_pts": trade.get("mae_pts") or trade.get("mae"),
        "win": 1 if (r or 0) > 0 else 0,
        "exit_reason": trade.get("exit_reason"),
        "target_before_stop": 1 if "target" in str(trade.get("exit_reason") or "").lower() else 0,
        "plus_1r_before_stop": plus_1r,
        "entry_features": trade.get("entry_features") or meta.get("entry_features"),
        "high_confidence_shadow": meta.get("high_confidence_shadow"),
    }
    ok = False
    if open_row:
        ok = store.update_outcome(str(open_row["candidate_id"]), outcome)
    else:
        store.append({**trade, **outcome, "setup_id": sid, "final_result": outcome["final_result"]})
        ok = True
    if ok:
        models_dir = tcfg.get("models_dir", "data/learning/models")
        st = load_loop_state(models_dir)
        st["resolved_since_retrain"] = int(st.get("resolved_since_retrain") or 0) + 1
        save_loop_state(models_dir, st)
        maybe_retrain(cfg)
    return ok


def maybe_retrain(cfg: dict[str, Any]) -> dict[str, Any]:
    """Retrain challenger when enough new outcomes accumulate (not every trade)."""
    tcfg = cfg.get("trade_quality_model") or {}
    models_dir = Path(tcfg.get("models_dir", "data/learning/models"))
    every = int(tcfg.get("retrain_every_resolved", 25))
    st = load_loop_state(models_dir)
    if int(st.get("resolved_since_retrain") or 0) < every:
        return {"retrained": False, "reason": "threshold_not_met", "count": st.get("resolved_since_retrain")}

    from agent.learning.dataset import build_unified_dataset, time_splits

    df, _audit = build_unified_dataset(
        learning_path=tcfg.get("learning_store", "data/learning/candidates.jsonl"),
        backfill_bars=False,
    )
    if len(df) < 40:
        return {"retrained": False, "reason": "insufficient_rows", "n": len(df)}
    splits = time_splits(df)
    base = train_baseline_models(splits["train"], splits["val"], target="win")
    nonlin = train_nonlinear_models(splits["train"], splits["val"], target="win")
    if not base.get("ok"):
        return {"retrained": False, "reason": base.get("reason")}

    # Pick best val brier among logistic_l2 and GB if available
    candidates = []
    for name, block in (base.get("models") or {}).items():
        b = (block.get("val") or {}).get("brier")
        if b is not None:
            candidates.append((b, name, "baseline", base["estimators"].get(name), block))
    if nonlin.get("ok"):
        for name, block in (nonlin.get("models") or {}).items():
            b = (block.get("val") or {}).get("brier")
            if b is not None:
                candidates.append((b, name, "nonlinear", nonlin["estimators"].get(name), block))
    if not candidates:
        return {"retrained": False, "reason": "no_scored_models"}
    candidates.sort(key=lambda x: x[0])
    brier, name, family, est, block = candidates[0]

    # Calibration on val
    import numpy as np
    import pandas as pd
    from agent.learning.dataset import numeric_matrix

    va = splits["val"]
    y_col = "win"
    Xva, names = numeric_matrix(va)
    # realign
    Xtr, tr_names = numeric_matrix(splits["train"])
    Xva_df = pd.DataFrame(Xva, columns=names)
    for c in tr_names:
        if c not in Xva_df.columns:
            Xva_df[c] = 0.0
    Xva = Xva_df[tr_names].to_numpy(dtype=float)
    yva = va[y_col].astype(int).to_numpy()
    proba = est.predict_proba(Xva)[:, 1]
    bins = calibration_bins(yva, proba)
    calibrated = is_calibrated_enough(bins, min_bin_n=max(5, len(va) // 12))

    qm = AdaptiveTradeQualityModel(models_dir=models_dir)
    version = f"trade_quality_challenger_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}"
    prior_wr = float(splits["train"]["win"].mean()) if len(splits["train"]) else 0.5
    prior_e = float(pd.to_numeric(splits["train"]["realized_r"], errors="coerce").mean() or 0)
    bundle = ModelBundle(
        version=version,
        kind=name,
        feature_names=list(tr_names),
        coefficients=(block.get("coefficients") if "coefficients" in block else None),
        importances=(block.get("importances") if "importances" in block else None),
        intercept=block.get("intercept"),
        calibrated=calibrated,
        brier_score=float(brier),
        train_n=len(splits["train"]),
        val_n=len(splits["val"]),
        created_at=datetime.now(timezone.utc).isoformat(),
        prior_win_rate=prior_wr,
        prior_expectancy_r=prior_e,
    )
    qm.save_bundle(qm.challenger_name, bundle, estimator=est)

    # Promotion check vs champion — PAPER only, never LIVE
    promoted = False
    allow_paper = bool(tcfg.get("allow_paper_auto_promote", True))
    allow_live = bool(tcfg.get("allow_live_auto_promote", False))
    mode = str(cfg.get("mode") or "paper").lower()
    if allow_live:
        # Hard refuse — live auto-promotion is never permitted by policy
        allow_live = False
    champ = qm.champion
    min_shadow = int(tcfg.get("min_challenger_shadow_decisions", 100))
    can_promote = allow_paper and mode == "paper" and not allow_live
    if can_promote and champ is None and calibrated and len(df) >= min_shadow:
        qm.promote_challenger_to_champion(new_version=version.replace("challenger", "champion"))
        promoted = True
    elif can_promote and champ is not None and calibrated:
        champ_brier = champ.brier_score if champ.brier_score is not None else 1.0
        if float(brier) < float(champ_brier) - 1e-6 and len(df) >= min_shadow:
            qm.promote_challenger_to_champion(new_version=version.replace("challenger", "v"))
            promoted = True

    st["resolved_since_retrain"] = 0
    st["last_retrain_at"] = datetime.now(timezone.utc).isoformat()
    st["last_challenger"] = version
    st["last_promoted"] = promoted
    save_loop_state(models_dir, st)
    return {
        "retrained": True,
        "challenger": version,
        "brier": brier,
        "calibrated": calibrated,
        "promoted": promoted,
        "bins": bins,
        "family": family,
        "model": name,
    }
