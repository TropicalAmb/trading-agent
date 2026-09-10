"""Five-layer trade cascade — additive context, not a monster gate stack.

Layers:
1 FIT — strategy/market historical fit
2 THESIS — HTF directional context (4h/1h/15m)
3 LOCATION — VWAP/EMA/levels quality
4 TRIGGER — one clean entry trigger (strategy-defined)
5 RISK — existing hard risk remains outside; this layer only tags readiness
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional

import pandas as pd

from agent.decision.setup import TradeSetup
from agent.research.momentum_deep import build_feature_frame


@dataclass
class CascadeResult:
    fit: str = "NEUTRAL"  # FIT | NEUTRAL | POOR_FIT
    thesis: str = "MIXED"  # LONG_SUPPORT | SHORT_SUPPORT | MIXED
    location: str = "ACCEPTABLE_LOCATION"
    trigger: str = "NONE"  # MOMENTUM | PULLBACK | BREAKOUT_RETEST | REJECTION | NONE
    risk_ready: bool = True
    hard_reject: bool = False
    reject_reason: str = ""
    decision: str = "HOLD"  # EXECUTE_PAPER | SHADOW | REJECT
    layer_log: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _atr_pctile_bucket(pctile: float | None) -> str:
    if pctile is None or pctile != pctile:
        return "UNKNOWN"
    if pctile < 0.25:
        return "LOW"
    if pctile < 0.70:
        return "NORMAL"
    if pctile < 0.90:
        return "HIGH"
    return "EXTREME"


def layer1_fit(
    *,
    strategy: str,
    symbol: str,
    session: str,
    vol_regime: str,
    cfg: dict[str, Any],
    lifecycle_state: str = "ACTIVE",
) -> tuple[str, dict[str, Any]]:
    """POOR_FIT only when sample-adequate evidence says cell is bad or lifecycle paused."""
    lc = (cfg.get("strategy_lifecycle") or {}).get("cells") or {}
    # Prefer runtime lifecycle store values passed in
    if lifecycle_state in {"HARD_PAUSED", "SHADOW_ONLY"}:
        return "POOR_FIT", {"lifecycle": lifecycle_state}
    if lifecycle_state == "WATCH":
        return "NEUTRAL", {"lifecycle": lifecycle_state}

    # Config evidence table (from validation reports) — optional
    evidence = (cfg.get("strategy_fit_evidence") or {}).get(strategy) or {}
    sym_ev = evidence.get(symbol.upper()) or evidence.get("default") or {}
    sess_bad = {str(x).lower() for x in (sym_ev.get("poor_sessions") or [])}
    regime_bad = {str(x).upper() for x in (sym_ev.get("poor_vol_regimes") or [])}
    min_n = int(sym_ev.get("min_n_for_poor_fit", 30))
    n = int(sym_ev.get("n") or 0)
    if n >= min_n and session.lower() in sess_bad:
        return "POOR_FIT", {"reason": "session_poor_fit", "session": session}
    if n >= min_n and vol_regime.upper() in regime_bad:
        return "POOR_FIT", {"reason": "vol_regime_poor_fit", "regime": vol_regime}
    if bool(sym_ev.get("validated_positive")):
        return "FIT", {"evidence": True}
    return "NEUTRAL", {"evidence": bool(sym_ev)}


def layer2_thesis(row: pd.Series, side: str) -> tuple[str, dict[str, Any]]:
    want = 1 if side.upper() in {"BUY", "LONG"} else -1
    dirs = {
        "4h": int(row.get("dir_4h", 0)),
        "1h": int(row.get("dir_1h", 0)),
        "15m": int(row.get("dir_15m", 0)),
    }
    agree = sum(1 for v in dirs.values() if v == want)
    conflict = sum(1 for v in dirs.values() if v == -want)
    if agree >= 2 and conflict == 0:
        thesis = "LONG_SUPPORT" if want == 1 else "SHORT_SUPPORT"
    else:
        thesis = "MIXED"
    return thesis, {"dirs": dirs, "agree": agree, "conflict": conflict}


def layer3_location(row: pd.Series, side: str, *, strategy: str, cfg: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    abs_vwap = abs(float(row["close_vs_vwap"])) if pd.notna(row.get("close_vs_vwap")) else None
    abs_ema = abs(float(row["close_vs_ema20"])) if pd.notna(row.get("close_vs_ema20")) else None
    details = {"abs_vwap_atr": abs_vwap, "abs_ema20_atr": abs_ema}
    # Strategy-specific evidence: CL specialist rewards tight VWAP
    if strategy.startswith("cl_vwap_prox"):
        thr = float((cfg.get("cl_vwap_prox_momentum") or {}).get("max_abs_vwap_atr", 0.25))
        if abs_vwap is not None and abs_vwap <= thr:
            return "EXCELLENT_LOCATION", details
        if abs_vwap is not None and abs_vwap <= thr * 2:
            return "ACCEPTABLE_LOCATION", details
        return "POOR_LOCATION", details
    if strategy.startswith("nq_context_entry"):
        # Champion is EMA20 pullback zone + VWAP buffer — treat zone proximity as location
        zone = float((cfg.get("nq_context_entry") or {}).get("zone_atr", 0.30))
        if abs_ema is not None and abs_ema <= zone:
            return "EXCELLENT_LOCATION", details
        if abs_ema is not None and abs_ema <= zone * 2:
            return "ACCEPTABLE_LOCATION", details
        if abs_vwap is not None and abs_vwap <= 0.75:
            return "ACCEPTABLE_LOCATION", details
        return "POOR_LOCATION", details
    if strategy.startswith("vwap_rejection"):
        # Wick-reject closes back across VWAP — entry sits near VWAP by construction.
        if abs_vwap is not None and abs_vwap <= 0.35:
            return "EXCELLENT_LOCATION", details
        if abs_vwap is not None and abs_vwap <= 0.75:
            return "ACCEPTABLE_LOCATION", details
        if abs_vwap is not None and abs_vwap > 1.5:
            return "POOR_LOCATION", details
        return "ACCEPTABLE_LOCATION", details
    # Generic
    if abs_vwap is not None and abs_vwap <= 0.25:
        return "EXCELLENT_LOCATION", details
    if abs_vwap is not None and abs_vwap <= 0.75:
        return "ACCEPTABLE_LOCATION", details
    if abs_vwap is not None and abs_vwap > 1.5:
        return "POOR_LOCATION", details
    return "ACCEPTABLE_LOCATION", details


def layer4_trigger(row: pd.Series, side: str, *, strategy: str) -> tuple[str, dict[str, Any]]:
    if strategy.startswith("nq_context_entry"):
        return "PULLBACK", {"nq_context_entry": True}
    if strategy.startswith("vwap_rejection"):
        # Evaluator only fires on a validated VWAP wick-reject; the rejection
        # itself is the entry trigger (mirrors nq_context_entry trusting PULLBACK).
        return "REJECTION", {"vwap_rejection": True}
    if strategy.startswith("cl_vwap_prox") or strategy.startswith("nq_ny_open"):
        ok = (side == "BUY" and int(row.get("parity_mom_long", 0)) == 1) or (
            side == "SELL" and int(row.get("parity_mom_short", 0)) == 1
        )
        return ("MOMENTUM" if ok else "NONE"), {"parity_mom": ok}
    # Generic momentum / pullback hints from feature frame
    if side == "BUY" and int(row.get("mom_long", 0)) == 1:
        return "MOMENTUM", {}
    if side == "SELL" and int(row.get("mom_short", 0)) == 1:
        return "MOMENTUM", {}
    if int(row.get("pullback_recent", 0)) == 1:
        return "PULLBACK", {}
    if int(row.get("retest", 0)) == 1 or int(row.get("breakout", 0)) == 1:
        return "BREAKOUT_RETEST", {}
    return "NONE", {}


def evaluate_cascade(
    setup: TradeSetup,
    bars: Optional[pd.DataFrame],
    cfg: dict[str, Any],
    *,
    lifecycle_state: str = "ACTIVE",
) -> CascadeResult:
    side = setup.direction.upper()
    strategy = setup.strategy_name
    session = str(setup.session or "unknown")
    result = CascadeResult()
    row = None
    if bars is not None and len(bars) >= 50:
        try:
            frame = build_feature_frame(bars)
            row = frame.iloc[-1]
        except Exception as exc:
            result.details["feature_error"] = str(exc)

    vol_regime = "UNKNOWN"
    if row is not None:
        vol_regime = _atr_pctile_bucket(
            float(row["atr_pctile"]) if pd.notna(row.get("atr_pctile")) else None
        )

    fit, fit_d = layer1_fit(
        strategy=strategy,
        symbol=setup.symbol,
        session=session,
        vol_regime=vol_regime,
        cfg=cfg,
        lifecycle_state=lifecycle_state,
    )
    result.fit = fit
    result.details["fit"] = fit_d
    result.details["vol_regime"] = vol_regime

    if fit == "POOR_FIT" and lifecycle_state in {"HARD_PAUSED", "SHADOW_ONLY"}:
        result.hard_reject = True
        result.reject_reason = f"POOR_FIT:{lifecycle_state}"
    elif fit == "POOR_FIT" and bool((cfg.get("trade_cascade") or {}).get("hard_reject_poor_fit", True)):
        # Only hard-reject POOR_FIT when evidence-backed (lifecycle or fit table)
        if fit_d.get("lifecycle") or fit_d.get("reason"):
            result.hard_reject = True
            result.reject_reason = f"POOR_FIT:{fit_d.get('reason') or fit_d.get('lifecycle')}"

    if row is not None:
        thesis, td = layer2_thesis(row, side)
        loc, ld = layer3_location(row, side, strategy=strategy, cfg=cfg)
        trig, trd = layer4_trigger(row, side, strategy=strategy)
        result.thesis = thesis
        result.location = loc
        result.trigger = trig
        result.details["thesis"] = td
        result.details["location"] = ld
        result.details["trigger"] = trd
    else:
        # Features unavailable → unknown thesis (empty). Do NOT default MIXED:
        # require_non_mixed_thesis would hard-block every setup when the frame fails.
        result.thesis = ""
        result.location = "ACCEPTABLE_LOCATION"
        result.trigger = "NONE"
        result.details["thesis"] = {"dirs": {}, "agree": 0, "conflict": 0, "unknown": True}

    # Layer 5: risk readiness tag — hard risk dollars applied in pipeline sizing
    result.risk_ready = not bool((setup.metadata or {}).get("hard_invalidations"))
    result.details["layer5"] = "DEFER_TO_EXISTING_HARD_RISK"

    # Human-readable layer log (must be consumed by journal/dashboard)
    abs_vwap = (result.details.get("location") or {}).get("abs_vwap_atr")
    loc_note = f"{result.location}"
    if abs_vwap is not None:
        loc_note += f" — VWAP distance {abs_vwap:.2f} ATR"
    result.layer_log = [
        f"FIT: {result.fit}",
        f"THESIS: {result.thesis}",
        f"LOCATION: {loc_note}",
        f"TRIGGER: {result.trigger}",
        f"RISK: {'READY' if result.risk_ready else 'BLOCKED'} (hard cap enforced in sizing)",
    ]
    if result.hard_reject:
        result.decision = "REJECT"
        result.layer_log.append(f"Decision: REJECT — {result.reject_reason}")
    elif lifecycle_state in {"SHADOW_ONLY", "HARD_PAUSED"}:
        result.decision = "SHADOW"
        result.layer_log.append(f"Decision: SHADOW — lifecycle={lifecycle_state}")
    elif result.trigger == "NONE":
        result.decision = "REJECT"
        result.layer_log.append("Decision: REJECT — no trigger")
    elif result.fit == "POOR_FIT":
        result.decision = "SHADOW"
        result.layer_log.append("Decision: SHADOW — POOR_FIT")
    else:
        result.decision = "EXECUTE_PAPER"
        result.layer_log.append("Decision: EXECUTE_PAPER (pending hard risk/qty)")
    return result


def attach_cascade_to_setup(
    setup: TradeSetup,
    bars: Optional[pd.DataFrame],
    cfg: dict[str, Any],
    *,
    lifecycle_state: str = "ACTIVE",
) -> TradeSetup:
    cas = evaluate_cascade(setup, bars, cfg, lifecycle_state=lifecycle_state)
    meta = dict(setup.metadata or {})
    meta["cascade"] = cas.to_dict()
    meta["cascade_log"] = list(cas.layer_log)
    meta["cascade_decision"] = cas.decision
    meta["vol_regime"] = cas.details.get("vol_regime")
    if cas.hard_reject or cas.decision == "REJECT":
        hard = list(meta.get("hard_invalidations") or [])
        hard.append(cas.reject_reason or "CASCADE_REJECT")
        meta["hard_invalidations"] = hard
    if cas.decision == "SHADOW" or lifecycle_state in {"SHADOW_ONLY", "HARD_PAUSED"}:
        meta["execution_mode"] = "SHADOW"
        meta["cell_health"] = lifecycle_state if lifecycle_state != "ACTIVE" else "SHADOW_ONLY"
    setup.metadata = meta
    return setup


def format_cascade_summary(setup: TradeSetup) -> str:
    meta = setup.metadata or {}
    lines = list(meta.get("cascade_log") or [])
    risk = meta.get("risk_cap_dollars")
    qty = setup.quantity
    sym = setup.symbol
    if risk is not None:
        lines.append(
            f"RISK DETAIL: {sym} qty={qty} risk=${setup.risk_dollars:.0f} cap=${float(risk):.0f}"
        )
    if meta.get("remapped_from"):
        lines.append(f"CONTRACT: remapped {meta.get('remapped_from')} → {sym} (risk fit)")
    lines.append(f"Decision: {meta.get('cascade_decision') or 'HOLD'}")
    return " | ".join(lines)
