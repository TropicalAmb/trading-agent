"""Learning-store schema versioning (backward-compatible)."""

from __future__ import annotations

from typing import Any

SCHEMA_VERSION = 2

# Fields treated as PRE-ENTRY only (never overwrite from post-trade path leakage)
PRE_ENTRY_KEYS = frozenset(
    {
        "candidate_id",
        "setup_id",
        "timestamp",
        "market_timestamp",
        "symbol",
        "strategy",
        "direction",
        "session",
        "regime",
        "dir_15m",
        "dir_1h",
        "dir_4h",
        "mtf_aligned",
        "above_vwap",
        "below_vwap",
        "vwap_dist_atr",
        "vwap_slope",
        "ema_bull",
        "ema_bear",
        "ema20_above_ema50",
        "price_vs_ema20_atr",
        "price_vs_ema50_atr",
        "near_pdh",
        "near_pdl",
        "near_session_high",
        "near_session_low",
        "sweep_type",
        "liquidity_level",
        "sweep_magnitude_atr",
        "reclaim_quality",
        "mss",
        "break_of_structure",
        "fvg",
        "displacement",
        "body_atr",
        "upper_wick_atr",
        "lower_wick_atr",
        "close_location",
        "engulfing",
        "rejection",
        "atr",
        "atr_pctile",
        "volatility_regime",
        "pullback_depth_atr",
        "overextended",
        "entry",
        "stop",
        "target",
        "target_r",
        "agreeing_n",
        "global_score",
        "local_score",
        "tier",
        "tier_rank",
        "features",
        "entry_features",
        "config_version",
        "schema_version",
    }
)

OUTCOME_KEYS = frozenset(
    {
        "final_result",
        "realized_r",
        "win",
        "mfe_r",
        "mae_r",
        "mfe_pts",
        "mae_pts",
        "exit_reason",
        "target_before_stop",
        "plus_1r_before_stop",
        "outcome_updated_at",
    }
)

DECISION_KEYS = frozenset(
    {
        "router_v1_decision",
        "balanced_decision",
        "high_confidence_decision",
        "high_confidence_shadow",
        "router_decision",
        "executed_or_shadow",
        "model_version",
        "router_version",
        "champion_probability",
        "challenger_probability",
        "champion_model_version",
        "challenger_model_version",
        "quality_predictions",
    }
)


def stamp_schema(row: dict[str, Any]) -> dict[str, Any]:
    out = dict(row)
    out.setdefault("schema_version", SCHEMA_VERSION)
    return out


def strip_post_entry_leakage(row: dict[str, Any]) -> dict[str, Any]:
    """Ensure predictive feature blob excludes outcome fields."""
    out = dict(row)
    feats = dict(out.get("features") or out.get("entry_features") or {})
    for k in list(feats.keys()):
        if k in OUTCOME_KEYS or k in {"exit", "closed_at", "pnl", "pnl_dollars"}:
            feats.pop(k, None)
    out["features"] = feats
    if "entry_features" in out:
        out["entry_features"] = dict(feats)
    return stamp_schema(out)
