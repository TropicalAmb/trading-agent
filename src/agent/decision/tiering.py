"""A+ / A / B / C setup tiering from GLOBAL quality evidence (not strategy-local score alone)."""

from __future__ import annotations

from typing import Any

from agent.decision.setup import TradeSetup

LOCATION_STRATEGIES = {
    "liquidity_sweep",
    "sweep_retest",
    "breakout_retest",
    "opening_range",
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
    Lone mediocre EMA without location remains B.
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
    agreeing = _agreeing(setup)
    lone_ema = (
        setup.strategy_name == "ema_pullback"
        and len(agreeing) < 2
        and not has_location
    )

    # A+
    if (
        global_score >= ap_thr
        and setup.expected_r >= ap_r
        and len(fams) >= 3
        and has_location
        and not major
        and not lone_ema
    ):
        return "A+"

    # A — valid single excellent strategy can qualify without second engine
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

    lone_ema = (
        strategy_name == "ema_pullback"
        and agreeing_engines < 2
        and not has_location
    )
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
        return assign_tier_from_global(
            setup,
            cfg,
            global_score=float(meta.get("global_score") or 0),
            families_positive=list(meta.get("families_positive") or []),
            has_location=bool(meta.get("has_location")),
            hard_invalidations=list(meta.get("hard_invalidations") or []),
            contradictions=list(meta.get("contradictions") or []),
        )
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


def can_execute(setup: TradeSetup, cfg: dict[str, Any]) -> bool:
    minimum = str(cfg.get("tiering", {}).get("minimum_trade_tier", "A")).upper()
    allowed = {
        "A+": {"A+"},
        "A": {"A+", "A"},
        "B": {"A+", "A", "B"},
        "C": {"A+", "A", "B", "C"},
    }.get(minimum, {"A+", "A"})
    if (setup.metadata or {}).get("hard_invalidations"):
        return False
    if (setup.metadata or {}).get("execution_mode") == "SHADOW":
        return False
    return setup.setup_tier in allowed


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
