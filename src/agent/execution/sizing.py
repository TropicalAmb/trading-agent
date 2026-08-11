"""Quantity sizing — configurable, never hard-coded to 1 or forced-even."""

from __future__ import annotations

from typing import Any

from agent.execution.risk_budget import effective_max_risk_dollars


def resolve_trade_quantity(
    cfg: dict[str, Any],
    *,
    symbol: str,
    strategy: str = "",
    agent_id: str = "agent_1",
    signal: Any = None,
    tier: str | None = None,
) -> int:
    """Resolve desired contracts for a trade (before risk fit).

    Priority:
      1. signal.quantity if set
      2. quantity_by_tier (A+ / A) when tier provided
      3. quantity_by_symbol
      4. quantity_by_strategy
      5. quantity_by_agent_profile
      6. default_quantity
    """
    q = cfg.get("quantity") or {}
    max_q = int(q.get("max_quantity", 25))
    if signal is not None and getattr(signal, "quantity", None) is not None:
        qty = int(getattr(signal, "quantity"))
    else:
        default = int(q.get("default_quantity", 1))
        by_tier = q.get("quantity_by_tier") or {}
        by_sym = q.get("quantity_by_symbol") or {}
        by_strat = q.get("quantity_by_strategy") or {}
        by_agent = q.get("quantity_by_agent_profile") or {}
        tier_key = str(tier or "").upper()
        qty = int(
            (by_tier.get(tier_key) if tier_key else None)
            or by_sym.get(symbol)
            or by_strat.get(strategy)
            or by_agent.get(agent_id)
            or default
        )
    return max(1, min(qty, max_q))


def fit_quantity_to_risk(
    *,
    desired_qty: int,
    entry: float,
    stop: float,
    point_value: float,
    hard_cap_dollars: float,
    max_quantity: int = 25,
) -> int:
    """Largest qty ≤ desired that keeps |entry-stop|*pv*qty ≤ hard_cap.

    hard_cap_dollars must be > 0. If <= 0 is passed, treat as misconfig and
    force a conservative $250 floor (never unlimited).
    """
    desired = max(1, min(int(desired_qty), int(max_quantity)))
    cap = float(hard_cap_dollars)
    if cap <= 0:
        cap = 250.0
    risk_pts = abs(float(entry) - float(stop))
    if risk_pts <= 1e-12 or point_value <= 0:
        return 0
    per_contract = risk_pts * float(point_value)
    if per_contract <= 0:
        return 0
    max_affordable = int(cap // per_contract)
    if max_affordable < 1:
        return 0  # cannot take even 1 under hard cap → caller may SHADOW / micro
    return max(1, min(desired, max_affordable))


def hard_cap_from_cfg(cfg: dict[str, Any], *, equity: float | None = None) -> float:
    return effective_max_risk_dollars(cfg, equity=equity)
