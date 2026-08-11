"""A+ / A / B / C setup tiering from GLOBAL quality evidence (not strategy-local score alone)."""

from __future__ import annotations

from typing import Any

from agent.decision.setup import TradeSetup

LOCATION_STRATEGIES = {
    "liquidity_sweep",
    "sweep_retest",
    "breakout_retest",
    "opening_range",
    "vwap_acceptance",
    "vwap_mss",
    "vwap_orb",
    "liquidity_reversal",
    "vwap_reclaim",
    "cl_vwap_prox_momentum",
    "nq_ny_open_momentum",
}


def _agreeing(setup: TradeSetup) -> list[str]:
    meta = setup.metadata or {}
    names = list(meta.get("agreeing_engines") or [])
    if setup.strategy_name and setup.strategy_name not in names:
        names = [setup.strategy_name] + names
    seen: set[str] = set()
    out: list[str] = []
    for n in names:
        if n not in seen:
            seen.add(n)
            out.append(n)
    return out


def _has_engine_partner(setup: TradeSetup) -> bool:
    """True when another independent engine agrees on the same symbol/side."""
    return any(n != setup.strategy_name for n in _agreeing(setup))


def _structural_location(setup: TradeSetup, has_location: bool) -> bool:
    """Location from a location engine — not soft PDH/PDL proximity alone."""
    agreeing = _agreeing(setup)
    if setup.strategy_name in LOCATION_STRATEGIES:
        return True
    if any(n in LOCATION_STRATEGIES for n in agreeing):
        return True
    src = str((setup.metadata or {}).get("location_source") or "")
    if src in {"structural", "location_engine"}:
        return True
    if has_location and src and src != "soft_prior_day":
        return True
    return False


def assign_tier_from_global(
    setup: TradeSetup,
    cfg: dict[str, Any],
    *,
    global_score: float,
    families_positive: list[str] | tuple[str, ...],
    has_location: bool,
    hard_invalidations: list[str] | tuple[str, ...] = (),
    contradictions: list[str] | tuple[str, ...] = (),
) -> str:
    """Tier mapping using auditable global score + evidence requirements.

    Score alone cannot mint A+. Hard invalidations → C.
    Lone ema_pullback (no second engine) stays B/C — soft PDH/PDL does not unlock A.
    """
    tcfg = cfg.get("tiering", {})
    thr = tcfg.get("tier_thresholds") or {}
    ap_thr = float(thr.get("A_PLUS", tcfg.get("a_plus_min_confidence", 85)))
    a_thr = float(thr.get("A", tcfg.get("a_min_confidence", 72)))
    b_thr = float(thr.get("B", tcfg.get("b_min_confidence", 58)))
    ap_r = float(tcfg.get("a_plus_min_r", 1.4))
    a_r = float(tcfg.get("a_min_r", 1.2))

    if hard_invalidations:
        return "C"

    major = {c for c in contradictions if c in {"MTF_ALL_OPPOSE", "OVEREXTENDED"}}
    fams = [f for f in families_positive if f != "PRIMARY"]
    partner = _has_engine_partner(setup)
    # Soft near-PDH/PDL must not promote lone EMA into A/A+
    lone_ema = setup.strategy_name == "ema_pullback" and not partner
    structural_loc = _structural_location(setup, has_location)

    # A+
    if (
        global_score >= ap_thr
        and setup.expected_r >= ap_r
        and len(fams) >= 3
        and (structural_loc or has_location)
        and not major
        and not lone_ema
    ):
        return "A+"

    # A — non-EMA single engines can qualify; EMA needs a real partner engine
    if (
        global_score >= a_thr
        and setup.expected_r >= a_r
        and len(fams) >= 2
        and not major
        and not lone_ema
    ):
        return "A"

    if lone_ema:
        return "B" if global_score >= b_thr or setup.confidence_score >= 55 else "C"

    if global_score >= b_thr:
        return "B"
    return "C"


def assign_tier(
    confidence: int,
    *,
    expected_r: float,
    reason_count: int,
    cfg: dict[str, Any],
    strategy_name: str = "",
    agreeing_engines: int = 1,
    has_location: bool = False,
    has_contradiction: bool = False,
    overextended: bool = False,
) -> str:
    """Legacy helper kept for older tests — maps to same philosophy."""
    tcfg = cfg.get("tiering", {})
    thr = tcfg.get("tier_thresholds") or {}
    ap_min = int(thr.get("A_PLUS", tcfg.get("a_plus_min_confidence", 85)))
    a_min = int(thr.get("A", tcfg.get("a_min_confidence", 72)))
    b_min = int(thr.get("B", tcfg.get("b_min_confidence", 58)))
    ap_r = float(tcfg.get("a_plus_min_r", 1.4))
    a_r = float(tcfg.get("a_min_r", 1.2))

    if has_contradiction or overextended:
        if confidence >= b_min:
            return "B"
        return "C"

    # Soft location alone must not unlock A for EMA — need a second engine
    lone_ema = strategy_name == "ema_pullback" and agreeing_engines < 2
    if lone_ema:
        if confidence >= b_min and expected_r >= 1.0:
            return "B"
        return "C"

    if (
        confidence >= ap_min
        and expected_r >= ap_r
        and reason_count >= 3
        and (agreeing_engines >= 2 or has_location)
    ):
        return "A+"

    if confidence >= a_min and expected_r >= a_r:
        if agreeing_engines >= 2 or has_location or reason_count >= 2:
            return "A"
        return "B"

    if confidence >= b_min:
        return "B"
    return "C"


def assign_tier_for_setup(setup: TradeSetup, cfg: dict[str, Any]) -> str:
    meta = setup.metadata or {}
    if "global_score" in meta:
        tier = assign_tier_from_global(
            setup,
            cfg,
            global_score=float(meta.get("global_score") or 0),
            families_positive=list(meta.get("families_positive") or []),
            has_location=bool(meta.get("has_location")),
            hard_invalidations=list(meta.get("hard_invalidations") or []),
            contradictions=list(meta.get("contradictions") or []),
        )
    else:
        tier = None
    # Validated paper specialists: floor to A when cascade trigger+location OK
    paper_specs = {str(x) for x in (cfg.get("paper_specialist_engines") or [])}
    if setup.strategy_name in paper_specs and not meta.get("hard_invalidations"):
        cas = meta.get("cascade") or {}
        trig_ok = str(cas.get("trigger") or "") in {"MOMENTUM", "PULLBACK", "BREAKOUT_RETEST"}
        loc_ok = str(cas.get("location") or "") in {
            "EXCELLENT_LOCATION",
            "ACCEPTABLE_LOCATION",
        }
        if trig_ok and loc_ok and (tier is None or tier_rank(tier) < tier_rank("A")):
            meta["tier_floor"] = "paper_specialist_v1"
            setup.metadata = meta
            return "A"
    if tier is not None:
        return tier
    agreeing = _agreeing(setup)
    # Fall back: count distinct families from reasons without inflation
    fam_hints = []
    for r in setup.reasons or []:
        fam_hints.append(str(r))
    has_location = any(n in LOCATION_STRATEGIES for n in agreeing) or bool(
        meta.get("has_location")
    )
    return assign_tier(
        setup.confidence_score,
        expected_r=setup.expected_r,
        reason_count=len(set(fam_hints)),
        cfg=cfg,
        strategy_name=setup.strategy_name,
        agreeing_engines=len(agreeing),
        has_location=has_location,
        has_contradiction=bool(meta.get("has_contradiction")),
        overextended=bool(meta.get("overextended")),
    )


def tier_rank(tier: str) -> int:
    return {"A+": 4, "A": 3, "B": 2, "C": 1}.get(tier, 0)


def execution_reject_reason(setup: TradeSetup, cfg: dict[str, Any]) -> str | None:
    """Stable reject code if setup cannot paper-execute; None if it can.

    Used for ledger/ops so A/A+ quality filters never vanish silently.
    """
    minimum = str(cfg.get("tiering", {}).get("minimum_trade_tier", "A")).upper()
    allowed = {
        "A+": {"A+"},
        "A": {"A+", "A"},
        "B": {"A+", "A", "B"},
        "C": {"A+", "A", "B", "C"},
    }.get(minimum, {"A+", "A"})
    meta = setup.metadata or {}
    if meta.get("hard_invalidations"):
        return f"HARD_INVALIDATION:{','.join(str(x) for x in meta.get('hard_invalidations') or [])}"
    if meta.get("execution_mode") == "SHADOW":
        return "EXECUTION_MODE_SHADOW"
    research_only = {str(x) for x in (cfg.get("research_only_engines") or [])}
    if setup.strategy_name in research_only or meta.get("research_only"):
        return f"RESEARCH_ONLY:{setup.strategy_name}"
    health = str(
        meta.get("cell_health")
        or (meta.get("router_evidence") or {}).get("cell_health")
        or "ACTIVE"
    )
    if health in {"SHADOW_ONLY", "PAUSED_FOR_REVIEW", "HARD_PAUSED"}:
        return f"CELL_HEALTH:{health}"
    life = str(meta.get("lifecycle_state") or "ACTIVE")
    if life in {"SHADOW_ONLY", "HARD_PAUSED"}:
        return f"LIFECYCLE:{life}"
    profile = str(cfg.get("execution_profile") or "balanced").lower()
    if profile == "high_confidence":
        hq = cfg.get("high_confidence") or {}
        ev = meta.get("router_evidence") or {}
        if bool(hq.get("enabled", True)) and bool(ev.get("model_calibrated")):
            p = ev.get("model_probability")
            thr = float(hq.get("min_predicted_probability", 0.65))
            if p is None or float(p) < thr:
                return "HIGH_CONFIDENCE_PROB"
            if float(ev.get("expectancy_r") or 0) < float(hq.get("min_expectancy_r", 0.0)):
                return "HIGH_CONFIDENCE_EXPECTANCY"
            if float(ev.get("profit_factor") or 0) < float(hq.get("min_profit_factor", 1.2)):
                return "HIGH_CONFIDENCE_PF"
            if int(ev.get("sample_count") or 0) < int(hq.get("min_sample", 30)):
                return "HIGH_CONFIDENCE_N"
    if setup.setup_tier not in allowed:
        return f"TIER:{setup.setup_tier}"

    eq = cfg.get("execution_quality") or {}
    if bool(eq.get("enabled", False)) and setup.strategy_name != "x":
        paper_specs = {str(x) for x in (cfg.get("paper_specialist_engines") or [])}
        is_specialist = setup.strategy_name in paper_specs
        min_r = float(eq.get("min_expected_r", 0) or 0)
        if min_r > 0 and float(setup.expected_r or 0) < min_r:
            return f"EXECUTION_QUALITY:R<{min_r}"
        min_reward = float(eq.get("min_reward_dollars", 0) or 0)
        if min_reward > 0 and float(setup.reward_dollars or 0) < min_reward:
            return (
                f"EXECUTION_QUALITY:reward ${float(setup.reward_dollars or 0):.0f}"
                f" < min ${min_reward:.0f}"
            )
        cas = meta.get("cascade") or {}
        if bool(eq.get("reject_poor_cascade_location", False)):
            if str(cas.get("location") or "") == "POOR_LOCATION":
                return "EXECUTION_QUALITY:POOR_LOCATION"
        if bool(eq.get("require_non_mixed_thesis", False)) and not is_specialist:
            # Location engines may paper with imperfect MTF (IRL: factors disagree).
            # Cascade thesis stays journaled for research; do not hard-kill good location A's.
            allow_mixed_loc = bool(eq.get("location_may_trade_mixed_thesis", True))
            if not (
                allow_mixed_loc and setup.strategy_name in LOCATION_STRATEGIES
            ):
                thesis = str(cas.get("thesis") or "")
                side = str(setup.direction or "").upper()
                want = "LONG_SUPPORT" if side in {"BUY", "LONG"} else "SHORT_SUPPORT"
                # Missing/unknown cascade thesis must NOT block (features unavailable ≠ MIXED)
                if thesis and thesis not in {want, ""}:
                    if thesis == "MIXED" or (
                        thesis in {"LONG_SUPPORT", "SHORT_SUPPORT"} and thesis != want
                    ):
                        return f"EXECUTION_QUALITY:thesis_{thesis}"
        min_agree = int(eq.get("min_agreeing_engines", 0) or 0)
        if (
            min_agree >= 2
            and not is_specialist
            and setup.strategy_name not in LOCATION_STRATEGIES
        ):
            if len(_agreeing(setup)) < min_agree:
                return f"EXECUTION_QUALITY:agreeing<{min_agree}"
        if bool(eq.get("ema_pullback_requires_partner", True)):
            if setup.strategy_name == "ema_pullback" and not _has_engine_partner(setup):
                return "EXECUTION_QUALITY:ema_needs_partner"
    return None


def can_execute(setup: TradeSetup, cfg: dict[str, Any]) -> bool:
    return execution_reject_reason(setup, cfg) is None


def is_executable_tier(tier: str, cfg: dict[str, Any]) -> bool:
    from datetime import datetime, timezone

    dummy = TradeSetup(
        strategy_name="x",
        symbol="MES",
        direction="BUY",
        setup_tier=str(tier).upper(),
        confidence_score=0,
        entry=1.0,
        stop=0.5,
        target=2.0,
        expected_r=1.0,
        market_timestamp=datetime.now(timezone.utc),
        received_timestamp=datetime.now(timezone.utc),
    )
    return can_execute(dummy, cfg)
