"""Scalp-first growth plan: quick trades until profits unlock swing holds."""

from __future__ import annotations

from typing import Any


def current_trade_mode(cfg: dict[str, Any], realized_pnl: float) -> str:
    plan = cfg.get("growth_plan", {})
    unlock = float(plan.get("swing_unlock_realized_pnl", 2000))
    force = str(plan.get("force_mode", "") or "").lower()
    if force in {"scalp", "active", "swing"}:
        return force
    if realized_pnl >= unlock:
        return "swing"
    return str(plan.get("default_mode", "active")).lower()


def apply_trade_mode(cfg: dict[str, Any], realized_pnl: float = 0.0) -> str:
    """Mutate strategy/execution/schedule params for active vs swing. Returns mode name."""
    mode = current_trade_mode(cfg, realized_pnl)
    plan = cfg.get("growth_plan", {})
    preset = dict(plan.get(mode) or {})
    if not preset:
        return mode

    # Schedule hold time
    cfg.setdefault("schedule", {})
    if "max_hold_minutes" in preset:
        cfg["schedule"]["max_hold_minutes"] = preset["max_hold_minutes"]
    if "time_stop_only_if_losing" in preset:
        cfg["schedule"]["time_stop_only_if_losing"] = bool(
            preset["time_stop_only_if_losing"]
        )

    # Strategy dollar / R targets for all engines
    for key in ("confluence", "vwap_acceptance", "vwap_orb", "sweep_retest"):
        block = cfg.setdefault(key, {})
        for field in (
            "target_dollars",
            "target_r_multiple",
            "min_reward_dollars",
            "max_risk_dollars",
            "min_confidence",
        ):
            if field in preset:
                block[field] = preset[field]

    # Execution style
    exe = cfg.setdefault("execution", {})
    if "scale_out" in preset:
        exe["scale_out"] = {**exe.get("scale_out", {}), **preset["scale_out"]}
    if "profit_protection" in preset:
        exe["profit_protection"] = {
            **exe.get("profit_protection", {}),
            **preset["profit_protection"],
        }

    cfg["_active_trade_mode"] = mode
    return mode
