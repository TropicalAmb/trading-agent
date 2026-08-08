"""Quantity sizing — configurable, never hard-coded to 1 or forced-even."""

from __future__ import annotations

from typing import Any


def resolve_trade_quantity(
    cfg: dict[str, Any],
    *,
    symbol: str,
    strategy: str = "",
    agent_id: str = "agent_1",
    signal: Any = None,
) -> int:
    """Resolve contracts for a trade.

    Priority:
      1. signal.quantity if set
      2. quantity_by_symbol
      3. quantity_by_strategy
      4. quantity_by_agent_profile
      5. default_quantity (paper default: 1)
    """
    if signal is not None and getattr(signal, "quantity", None) is not None:
        qty = int(getattr(signal, "quantity"))
    else:
        q = cfg.get("quantity") or {}
        default = int(q.get("default_quantity", 1))
        by_sym = q.get("quantity_by_symbol") or {}
        by_strat = q.get("quantity_by_strategy") or {}
        by_agent = q.get("quantity_by_agent_profile") or {}
        qty = int(
            by_sym.get(symbol)
            or by_strat.get(strategy)
            or by_agent.get(agent_id)
            or default
        )
    qcfg = cfg.get("quantity") or {}
    max_q = int(qcfg.get("max_quantity", 25))
    # Do NOT force even sizes — scale-out only applies when qty >= 2
    return max(1, min(qty, max_q))
