"""Standardized trade setup proposal (engines do not place orders)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


@dataclass
class TradeSetup:
    strategy_name: str
    symbol: str
    direction: str  # BUY | SELL
    setup_tier: str  # A+ | A | B | C
    confidence_score: int
    entry: float
    stop: float
    target: float
    expected_r: float
    market_timestamp: datetime
    received_timestamp: datetime
    reasons: list[str] = field(default_factory=list)
    invalidation_reason: Optional[str] = None
    session: Optional[str] = None
    agent_id: str = "agent_1"
    quantity: int = 1
    risk_dollars: float = 0.0
    reward_dollars: float = 0.0
    feed_source: str = "yahoo_delayed"
    is_realtime: bool = False
    estimated_delay_seconds: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def side(self) -> str:
        return self.direction
