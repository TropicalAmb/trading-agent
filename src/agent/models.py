from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


class SpreadType(str, Enum):
    PUT_CREDIT = "put_credit"
    CALL_CREDIT = "call_credit"


class Side(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class DecisionAction(str, Enum):
    PASS = "pass"
    TRADE = "trade"


class OptionLeg(BaseModel):
    symbol: str
    expiry: date
    strike: float
    right: str  # C or P
    action: Side
    quantity: int = 1

    @field_validator("right")
    @classmethod
    def normalize_right(cls, v: str) -> str:
        v = v.upper()
        if v not in {"C", "P", "CALL", "PUT"}:
            raise ValueError("right must be C/P")
        return "C" if v.startswith("C") else "P"


class CreditSpreadCandidate(BaseModel):
    """A defined-risk vertical credit spread produced by the rule scanner."""

    underlying: str
    spread_type: SpreadType
    short_leg: OptionLeg
    long_leg: OptionLeg
    width: float
    credit: float
    max_loss: float
    dte: int
    spot: float
    iv_rank: Optional[float] = None
    trend_ok: bool = True
    score: float = 0.0
    rationale_tags: list[str] = Field(default_factory=list)
    quote_ts: Optional[datetime] = None

    @property
    def contracts(self) -> int:
        return abs(self.short_leg.quantity)

    def with_quantity(self, qty: int) -> "CreditSpreadCandidate":
        data = self.model_dump()
        data["short_leg"]["quantity"] = qty
        data["long_leg"]["quantity"] = qty
        data["max_loss"] = max(0.0, (self.width - self.credit) * 100 * qty)
        return CreditSpreadCandidate.model_validate(data)


class AccountSnapshot(BaseModel):
    equity: float
    cash: float
    buying_power: float
    open_positions: int = 0
    open_underlyings: list[str] = Field(default_factory=list)
    realized_pnl_today: float = 0.0
    unrealized_pnl: float = 0.0
    healthy: bool = True
    notes: list[str] = Field(default_factory=list)


class AdvisorDecision(BaseModel):
    action: DecisionAction
    candidate_index: Optional[int] = None
    rationale: str = ""
    raw: dict[str, Any] = Field(default_factory=dict)


class RiskVerdict(BaseModel):
    approved: bool
    reasons: list[str] = Field(default_factory=list)
    sized_candidate: Optional[CreditSpreadCandidate] = None
    kill_switch: bool = False
    halt_trading: bool = False


class OrderResult(BaseModel):
    dry_run: bool
    submitted: bool
    order_id: Optional[str] = None
    status: str = ""
    detail: str = ""
    candidate: Optional[CreditSpreadCandidate] = None


class JournalEvent(BaseModel):
    ts: datetime
    event_type: str
    payload: dict[str, Any] = Field(default_factory=dict)


class OpenPosition(BaseModel):
    """Tracked credit-spread position for management / exits."""

    id: str
    underlying: str
    spread_type: SpreadType
    short_strike: float
    long_strike: float
    right: str
    expiry: date
    width: float
    entry_credit: float
    quantity: int
    entry_spot: float
    entry_ts: datetime
    status: str = "open"  # open | closed
    mark_debit: Optional[float] = None  # cost to close (debit)
    unrealized_pnl: float = 0.0


class ExitReason(str, Enum):
    PROFIT_TARGET = "profit_target"
    STOP_LOSS = "stop_loss"
    TIME_EXIT = "time_exit"
    EXPIRY_RISK = "expiry_risk"


class ExitSignal(BaseModel):
    position_id: str
    reason: ExitReason
    mark_debit: float
    pnl: float
    detail: str = ""
