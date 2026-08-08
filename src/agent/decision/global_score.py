"""Auditable global trade score with independent evidence families."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from agent.context.market_context import MarketContext
from agent.context.regime import MarketRegime, regime_weight
from agent.decision.setup import TradeSetup

# Independent families — do not double-count within a family
EVIDENCE_FAMILIES = (
    "MTF",
    "VWAP",
    "EMA_TREND",
    "LOCATION",
    "CANDLE_CONFIRMATION",
    "REGIME",
    "RISK_REWARD",
    "VOLATILITY",
    "OTHER_ENGINE",
    "PORTFOLIO",
    "PRIMARY",
)

HARD_INVALIDATIONS = {
    "DATA_STALE",
    "NO_STOP",
    "INVALID_STOP",
    "RISK_LIMIT",
    "INVALID_RR",
    "DUPLICATE_SETUP",
    "BROKER_NOT_HEALTHY",
    "MARKET_CLOSED",
    "INVALID_CONTRACT_DATA",
    "POSITION_CONFLICT",
}


@dataclass(frozen=True)
class ScoreComponent:
    name: str
    points: float
    reason: str
    family: str


@dataclass(frozen=True)
class GlobalScore:
    score: float
    components: tuple[ScoreComponent, ...]
    contradictions: tuple[str, ...]
    hard_invalidations: tuple[str, ...]
    families_positive: tuple[str, ...]
    has_location: bool


def _side_sign(direction: str) -> int:
    return 1 if str(direction).upper() in {"BUY", "LONG"} else -1


def np_clip(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def score_setup(
    setup: TradeSetup,
    ctx: MarketContext,
    cfg: dict[str, Any],
    *,
    hard_invalidations: list[str] | None = None,
    portfolio_penalty: float = 0.0,
    portfolio_reason: str = "",
) -> GlobalScore:
    """Weighted evidence score. Hard invalidations always block execution upstream."""
    gcfg = cfg.get("global_scoring", {})
    # Recalibrated: primary alone must not mint high scores (was 45 → B@90+)
    base = float(gcfg.get("primary_setup_base_points", gcfg.get("valid_setup_base", 32)))
    max_regime_pts = float(gcfg.get("max_regime_points", 8))

    comps: list[ScoreComponent] = []
    contradictions: list[str] = []
    hard = list(hard_invalidations or [])
    if setup.invalidation_reason:
        hard.append(str(setup.invalidation_reason))

    if setup.stop is None or float(setup.stop) <= 0:
        hard.append("NO_STOP")
    if setup.direction.upper() == "BUY" and not (setup.stop < setup.entry < setup.target):
        hard.append("INVALID_STOP")
    if setup.direction.upper() == "SELL" and not (setup.target < setup.entry < setup.stop):
        hard.append("INVALID_STOP")
    min_r = float(cfg.get("tiering", {}).get("a_min_r", 1.2)) * 0.5
    if setup.expected_r < min_r:
        hard.append("INVALID_RR")

    comps.append(
        ScoreComponent("PRIMARY", base, f"valid {setup.strategy_name} setup", "PRIMARY")
    )

    sign = _side_sign(setup.direction)
    aligned = 0
    opposed = 0
    for d in (ctx.direction_15m, ctx.direction_1h, ctx.direction_4h):
        if d == 0:
            continue
        if d == sign:
            aligned += 1
        else:
            opposed += 1
    if aligned == 3:
        comps.append(ScoreComponent("MTF", 15, "all three MTF candles aligned", "MTF"))
    elif aligned == 2:
        comps.append(ScoreComponent("MTF", 10, "two of three MTF candles aligned", "MTF"))
    if opposed == 3:
        comps.append(ScoreComponent("MTF", -15, "all three MTF candles oppose", "MTF"))
        contradictions.append("MTF_ALL_OPPOSE")
    elif opposed == 2:
        comps.append(ScoreComponent("MTF", -10, "two of three MTF candles oppose", "MTF"))
        contradictions.append("MTF_MAJORITY_OPPOSE")

    if sign > 0 and ctx.above_vwap:
        comps.append(ScoreComponent("VWAP", 10, "VWAP supports long", "VWAP"))
    elif sign < 0 and ctx.below_vwap:
        comps.append(ScoreComponent("VWAP", 10, "VWAP supports short", "VWAP"))
    elif sign > 0 and ctx.below_vwap:
        comps.append(ScoreComponent("VWAP", -10, "VWAP materially opposes long", "VWAP"))
        contradictions.append("VWAP_OPPOSE")
    elif sign < 0 and ctx.above_vwap:
        comps.append(ScoreComponent("VWAP", -10, "VWAP materially opposes short", "VWAP"))
        contradictions.append("VWAP_OPPOSE")

    # EMA structure — reduced from +10 so it cannot inflate lone EMA toward A+
    if sign > 0 and ctx.ema_bull:
        comps.append(ScoreComponent("EMA_TREND", 8, "EMA20/50 structure bullish", "EMA_TREND"))
    elif sign < 0 and ctx.ema_bear:
        comps.append(ScoreComponent("EMA_TREND", 8, "EMA20/50 structure bearish", "EMA_TREND"))
    elif sign > 0 and ctx.ema_bear:
        comps.append(ScoreComponent("EMA_TREND", -8, "EMA structure opposes long", "EMA_TREND"))
        contradictions.append("EMA_OPPOSE")
    elif sign < 0 and ctx.ema_bull:
        comps.append(ScoreComponent("EMA_TREND", -8, "EMA structure opposes short", "EMA_TREND"))
        contradictions.append("EMA_OPPOSE")

    has_location = False
    loc_strats = {"liquidity_sweep", "sweep_retest", "breakout_retest", "opening_range"}
    loc_quality = str((setup.metadata or {}).get("location_quality") or "")
    if setup.strategy_name in loc_strats or (setup.metadata or {}).get("has_location"):
        has_location = True
        pts = 15 if loc_quality == "exceptional" else 10
        comps.append(
            ScoreComponent(
                "LOCATION",
                pts,
                f"structural location ({setup.strategy_name})",
                "LOCATION",
            )
        )
    elif (sign > 0 and ctx.near_pdl) or (sign < 0 and ctx.near_pdh):
        has_location = True
        comps.append(ScoreComponent("LOCATION", 10, "near prior-day extreme", "LOCATION"))

    if sign > 0 and ctx.momentum_up:
        comps.append(ScoreComponent("CANDLE", 8, "strong bullish confirmation", "CANDLE_CONFIRMATION"))
    elif sign < 0 and ctx.momentum_down:
        comps.append(ScoreComponent("CANDLE", 8, "strong bearish confirmation", "CANDLE_CONFIRMATION"))
    elif sign > 0 and ctx.direction_15m >= 0 and not ctx.momentum_down:
        comps.append(ScoreComponent("CANDLE", 4, "acceptable bullish confirmation", "CANDLE_CONFIRMATION"))
    elif sign < 0 and ctx.direction_15m <= 0 and not ctx.momentum_up:
        comps.append(ScoreComponent("CANDLE", 4, "acceptable bearish confirmation", "CANDLE_CONFIRMATION"))
    else:
        comps.append(
            ScoreComponent("CANDLE", -8, "weak candle confirmation", "CANDLE_CONFIRMATION")
        )

    w = regime_weight(cfg, setup.strategy_name, ctx.regime)
    regime_pts = float(np_clip((w - 1.0) * 40.0, -max_regime_pts, max_regime_pts))
    if abs(regime_pts) >= 0.5:
        comps.append(
            ScoreComponent(
                "REGIME",
                regime_pts,
                f"regime {ctx.regime.value} weight={w:.2f}",
                "REGIME",
            )
        )
        if regime_pts <= -6:
            contradictions.append("REGIME_UNFAVORABLE")

    if setup.expected_r >= 2.0:
        comps.append(ScoreComponent("RR", 10, f"R={setup.expected_r:.2f} >= 2.0", "RISK_REWARD"))
    elif setup.expected_r >= 1.5:
        comps.append(ScoreComponent("RR", 5, f"R={setup.expected_r:.2f} >= 1.5", "RISK_REWARD"))

    if sign > 0 and ctx.overextended_long:
        comps.append(ScoreComponent("EXT", -12, "overextended long", "VOLATILITY"))
        contradictions.append("OVEREXTENDED")
        setup.metadata = dict(setup.metadata or {})
        setup.metadata["overextended"] = True
    elif sign < 0 and ctx.overextended_short:
        comps.append(ScoreComponent("EXT", -12, "overextended short", "VOLATILITY"))
        contradictions.append("OVEREXTENDED")
        setup.metadata = dict(setup.metadata or {})
        setup.metadata["overextended"] = True
    elif not (ctx.overextended_long or ctx.overextended_short):
        comps.append(
            ScoreComponent("ENTRY_Q", 6, "entry not overextended", "VOLATILITY")
        )

    agreeing = list((setup.metadata or {}).get("agreeing_engines") or [])
    others = [n for n in agreeing if n != setup.strategy_name]
    if others:
        comps.append(
            ScoreComponent(
                "OTHER_ENGINE",
                8,
                f"agreement with {','.join(others)}",
                "OTHER_ENGINE",
            )
        )

    if portfolio_penalty:
        comps.append(
            ScoreComponent(
                "PORTFOLIO",
                -abs(portfolio_penalty),
                portfolio_reason or "correlated exposure",
                "PORTFOLIO",
            )
        )

    by_fam: dict[str, ScoreComponent] = {}
    for c in comps:
        prev = by_fam.get(c.family)
        if prev is None or abs(c.points) > abs(prev.points):
            by_fam[c.family] = c
    final_comps = tuple(by_fam.values())
    raw = sum(c.points for c in final_comps)
    score = float(max(0.0, min(100.0, raw)))

    pos_fams = tuple(
        sorted({c.family for c in final_comps if c.points > 0 and c.family != "PRIMARY"})
    )

    return GlobalScore(
        score=round(score, 2),
        components=final_comps,
        contradictions=tuple(contradictions),
        hard_invalidations=tuple(dict.fromkeys(hard)),
        families_positive=pos_fams,
        has_location=has_location,
    )


def format_score_breakdown(gs: GlobalScore) -> str:
    lines = [f"GLOBAL SCORE {gs.score:.0f}"]
    for c in sorted(gs.components, key=lambda z: -z.points):
        sign = "+" if c.points >= 0 else ""
        lines.append(f"{sign}{c.points:.0f} {c.reason}")
    if gs.contradictions:
        lines.append("contradictions: " + ", ".join(gs.contradictions))
    if gs.hard_invalidations:
        lines.append("HARD: " + ", ".join(gs.hard_invalidations))
    return "\n".join(lines)
