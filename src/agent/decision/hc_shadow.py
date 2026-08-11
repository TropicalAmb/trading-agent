"""High-confidence shadow parallel path — never changes paper execution while v2 is off."""

from __future__ import annotations

from typing import Any, Optional


def _hc_gates_ok(ev: dict[str, Any], hq: dict[str, Any]) -> tuple[bool, str]:
    if not bool(hq.get("enabled", True)):
        return False, "HC_DISABLED"
    n = int(ev.get("sample_count") or 0)
    if n < int(hq.get("min_sample", 30)):
        return False, "HIGH_CONFIDENCE_N"
    if float(ev.get("expectancy_r") or 0) < float(hq.get("min_expectancy_r", 0.0)):
        return False, "HIGH_CONFIDENCE_EXPECTANCY"
    pf = float(ev.get("profit_factor") or 0)
    if pf < float(hq.get("min_profit_factor", 1.2)):
        return False, "HIGH_CONFIDENCE_PF"
    p = ev.get("model_probability")
    thr = float(hq.get("min_predicted_probability", 0.65))
    # Prefer calibrated model; fall back to shrunk WR when model absent
    if p is not None and bool(ev.get("model_calibrated")):
        if float(p) < thr:
            return False, "HIGH_CONFIDENCE_PROB"
    else:
        wr = float(ev.get("shrunk_win_rate") or ev.get("win_rate") or 0)
        if wr < thr:
            return False, "HIGH_CONFIDENCE_SHRUNK_WR"
    return True, "SELECT"


def attach_model_evidence_shadow(
    setups: list[Any],
    cfg: dict[str, Any],
) -> None:
    """Attach router_v2-style evidence for learning/dashboard without enabling v2 ranking."""
    tcfg = cfg.get("trade_quality_model") or {}
    v2cfg = cfg.get("performance_router_v2") or {}
    # If v2 ranking already attached evidence, skip re-attach
    if bool(v2cfg.get("enabled", False)):
        return
    if not bool(tcfg.get("enabled", True)):
        return
    if not bool((cfg.get("high_confidence") or {}).get("attach_shadow_evidence", True)):
        return
    try:
        from agent.decision.performance_router_v2 import router_v2_from_cfg
        from agent.learning.model import AdaptiveTradeQualityModel
    except Exception:
        return
    qm = AdaptiveTradeQualityModel(
        models_dir=tcfg.get("models_dir", "data/learning/models"),
        champion_name=str(tcfg.get("champion_name") or "trade_quality_champion"),
        challenger_name=str(tcfg.get("challenger_name") or "trade_quality_challenger"),
    )
    router = router_v2_from_cfg(cfg, quality_model=qm)
    for s in setups:
        try:
            router.attach_v2(s, cfg)
            meta = dict(s.metadata or {})
            meta["router_version"] = "v1+shadow_v2_evidence"
            # Also store challenger + multi-head predictions
            feats = dict(meta.get("entry_features") or {})
            champ = qm.predict_row(feats, which="champion")
            chall = qm.predict_row(feats, which="challenger")
            meta["quality_predictions"] = {
                "champion": champ.to_dict(),
                "challenger": chall.to_dict(),
                "p_win": champ.predicted_win_probability,
                "p_1r": feats.get("p_1r_pred") or champ.predicted_win_probability,
                "expected_r": champ.expected_r,
            }
            s.metadata = meta
        except Exception:
            continue


def attach_high_confidence_shadow_decisions(
    setups: list[Any],
    cfg: dict[str, Any],
    *,
    router_v1_selected_ids: Optional[set[str]] = None,
) -> None:
    """For every candidate, record balanced vs high_confidence_shadow decisions."""
    hq = cfg.get("high_confidence") or {}
    if not bool(hq.get("shadow_parallel", True)):
        return
    selected = router_v1_selected_ids or set()
    for s in setups:
        meta = dict(s.metadata or {})
        sid = str(meta.get("setup_id") or "")
        ev = dict(meta.get("router_evidence") or {})
        ok, reason = _hc_gates_ok(ev, hq)
        tier = str(getattr(s, "setup_tier", "") or "").upper()
        paperable_tier = tier in {"A", "A+"}
        # HC shadow still requires A/A+ tier eligibility (hard gate)
        if not paperable_tier:
            ok, reason = False, f"TIER:{tier or 'none'}"
        decision = "SELECT" if ok else "PASS"
        meta["router_v1_decision"] = "SELECT" if sid in selected else "PASS"
        meta["balanced_decision"] = meta["router_v1_decision"]
        meta["high_confidence_shadow"] = {
            "decision": decision,
            "reason": reason,
            "model_probability": ev.get("model_probability"),
            "shrunk_win_rate": ev.get("shrunk_win_rate") or ev.get("win_rate"),
            "raw_win_rate": ev.get("raw_win_rate"),
            "sample_count": ev.get("sample_count"),
            "expectancy_r": ev.get("expectancy_r"),
            "profit_factor": ev.get("profit_factor"),
            "evidence_level": ev.get("evidence_level"),
            "model_version": ev.get("model_version"),
        }
        meta["high_confidence_decision"] = decision
        s.metadata = meta
