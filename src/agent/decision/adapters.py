"""Shared adapters between TradeSetup and legacy SweepSignal-shaped objects."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from agent.decision.setup import TradeSetup
from agent.strategy.sweep_retest import SweepSignal


def setup_to_signal(setup: TradeSetup) -> SweepSignal:
    """Legacy executor/risk expect SweepSignal; attach qty + tier metadata."""
    # Engines historically report per-contract dollars; blotter multiplies by qty.
    # TradeSetup stores position-level dollars — convert back to per-contract.
    q = max(1, int(setup.quantity))
    risk_pc = float(setup.risk_dollars) / q
    reward_pc = float(setup.reward_dollars) / q
    ts = setup.market_timestamp
    if isinstance(ts, datetime) and ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    sig = SweepSignal(
        symbol=setup.symbol,
        side=setup.direction,
        entry=float(setup.entry),
        stop=float(setup.stop),
        target=float(setup.target),
        confidence=int(setup.confidence_score),
        reason=(
            f"tier={setup.setup_tier} | {setup.strategy_name} | "
            + "; ".join(setup.reasons)
        ),
        pdh=float(setup.metadata.get("pdh") or setup.entry),
        pdl=float(setup.metadata.get("pdl") or setup.entry),
        ts=ts or datetime.now(timezone.utc),
        risk_dollars=risk_pc,
        reward_dollars=reward_pc,
    )
    # Duck-typed extras for executor / journal
    setattr(sig, "quantity", q)
    setattr(sig, "setup_tier", setup.setup_tier)
    setattr(sig, "strategy_name", setup.strategy_name)
    setattr(sig, "agent_id", setup.agent_id)
    setattr(sig, "market_timestamp", setup.market_timestamp)
    setattr(sig, "received_timestamp", setup.received_timestamp)
    setattr(sig, "feed_source", setup.feed_source)
    setattr(sig, "estimated_delay_seconds", setup.estimated_delay_seconds)
    setattr(sig, "is_realtime", setup.is_realtime)
    setattr(sig, "metadata", dict(setup.metadata or {}))
    setattr(sig, "global_score", (setup.metadata or {}).get("global_score"))
    setattr(sig, "setup_id", (setup.metadata or {}).get("setup_id"))
    return sig


def resolve_quantity(cfg: dict[str, Any], *, symbol: str, strategy: str, agent_id: str) -> int:
    from agent.execution.sizing import resolve_trade_quantity

    return resolve_trade_quantity(
        cfg, symbol=symbol, strategy=strategy, agent_id=agent_id
    )
