from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional
from zoneinfo import ZoneInfo

from agent.models import (
    AccountSnapshot,
    CreditSpreadCandidate,
    RiskVerdict,
    SpreadType,
)

logger = logging.getLogger(__name__)


class RiskEngine:
    """Hard veto layer. Claude cannot bypass these checks."""

    def __init__(self, cfg: dict[str, Any]):
        self.cfg = cfg
        self._halted = False
        self._halt_reason: Optional[str] = None

    @property
    def halted(self) -> bool:
        return self._halted

    def reset_halt(self) -> None:
        self._halted = False
        self._halt_reason = None

    def check_session(self, now: datetime | None = None) -> list[str]:
        sched = self.cfg.get("schedule", {})
        tz_name = sched.get("timezone", "America/New_York")
        tz = ZoneInfo(tz_name)
        now = now or datetime.now(tz)
        if now.tzinfo is None:
            now = now.replace(tzinfo=tz)
        else:
            now = now.astimezone(tz)

        # Weekday Mon-Fri
        if now.weekday() >= 5:
            return ["outside RTH: weekend"]

        start = sched.get("entry_start", "09:45")
        end = sched.get("entry_end", "15:30")
        sh, sm = map(int, start.split(":"))
        eh, em = map(int, end.split(":"))
        minutes = now.hour * 60 + now.minute
        if minutes < sh * 60 + sm or minutes > eh * 60 + em:
            return [f"outside RTH entry window {start}-{end} {tz_name}"]
        return []

    def evaluate(
        self,
        candidate: CreditSpreadCandidate | None,
        account: AccountSnapshot,
        *,
        now: datetime | None = None,
        skip_session_check: bool = False,
    ) -> RiskVerdict:
        risk = self.cfg.get("risk", {})
        reasons: list[str] = []

        if self._halted:
            return RiskVerdict(
                approved=False,
                reasons=[f"trading halted: {self._halt_reason}"],
                kill_switch=True,
                halt_trading=True,
            )

        # Daily kill switch
        kill_pct = float(risk.get("daily_loss_kill_pct", 0.03))
        if account.equity > 0:
            day_pnl = account.realized_pnl_today + min(0.0, account.unrealized_pnl)
            # Conservative: if realized today is deeply negative vs equity
            loss_pct = -min(0.0, account.realized_pnl_today) / account.equity
            if loss_pct >= kill_pct:
                self._halted = True
                self._halt_reason = f"daily loss {loss_pct:.2%} >= {kill_pct:.2%}"
                return RiskVerdict(
                    approved=False,
                    reasons=[self._halt_reason],
                    kill_switch=True,
                    halt_trading=True,
                )

        if not account.healthy:
            reasons.append("account/broker unhealthy")

        if not skip_session_check:
            reasons.extend(self.check_session(now))

        if candidate is None:
            reasons.append("no candidate")
            return RiskVerdict(approved=False, reasons=reasons)

        # Defined risk: both legs required, opposite actions, same right/expiry
        if risk.get("require_both_legs", True):
            if candidate.short_leg is None or candidate.long_leg is None:
                reasons.append("missing leg — not defined risk")
            elif candidate.short_leg.action.value != "SELL":
                reasons.append("short leg must be SELL")
            elif candidate.long_leg.action.value != "BUY":
                reasons.append("long leg must be BUY (hedge)")
            elif candidate.short_leg.right != candidate.long_leg.right:
                reasons.append("legs must be same option right")
            elif candidate.short_leg.expiry != candidate.long_leg.expiry:
                reasons.append("legs must share expiry")

        if risk.get("require_defined_risk", True):
            if candidate.width <= 0 or candidate.max_loss <= 0:
                reasons.append("invalid width/max_loss — not defined risk")
            # Naked short would have no long protection: long strike must be further OTM
            if candidate.spread_type == SpreadType.PUT_CREDIT:
                if candidate.long_leg.strike >= candidate.short_leg.strike:
                    reasons.append("put credit long strike must be below short strike")
            elif candidate.spread_type == SpreadType.CALL_CREDIT:
                if candidate.long_leg.strike <= candidate.short_leg.strike:
                    reasons.append("call credit long strike must be above short strike")

        # Stale quotes
        if risk.get("halt_on_stale_data", True) and candidate.quote_ts is not None:
            max_age = int(risk.get("max_quote_age_sec", 120))
            ts = candidate.quote_ts
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            age = (datetime.now(timezone.utc) - ts.astimezone(timezone.utc)).total_seconds()
            if age > max_age:
                reasons.append(f"stale quote age {age:.0f}s > {max_age}s")

        # Position limits
        max_open = int(risk.get("max_open_positions", 3))
        if account.open_positions >= max_open:
            reasons.append(f"max open positions reached ({max_open})")

        if candidate.underlying in account.open_underlyings:
            reasons.append(f"already have position in {candidate.underlying}")

        # Correlated index book
        index_syms = set(risk.get("index_symbols", ["SPY", "QQQ", "IWM"]))
        max_idx = int(risk.get("max_correlated_index_positions", 1))
        if candidate.underlying in index_syms:
            open_idx = sum(1 for u in account.open_underlyings if u in index_syms)
            if open_idx >= max_idx:
                reasons.append("max correlated index positions reached")

        # Sizing
        max_contracts = int(risk.get("max_contracts_per_trade", 1))
        qty = min(max_contracts, candidate.contracts or 1)
        if qty < 1:
            reasons.append("quantity < 1")

        sized = candidate.with_quantity(qty)
        max_loss_pct = float(risk.get("max_loss_pct_of_equity_per_trade", 0.02))
        if account.equity > 0:
            loss_frac = sized.max_loss / account.equity
            if loss_frac > max_loss_pct + 1e-12:
                reasons.append(
                    f"max loss ${sized.max_loss:.0f} ({loss_frac:.2%}) exceeds "
                    f"{max_loss_pct:.2%} of equity"
                )

        # Cap contracts further if needed
        if account.equity > 0 and sized.max_loss > account.equity * max_loss_pct:
            # try reduce to 1 already — still fail
            reasons.append("cannot size within max loss budget")

        approved = len(reasons) == 0
        if not approved:
            logger.info("Risk rejected: %s", "; ".join(reasons))
        return RiskVerdict(
            approved=approved,
            reasons=reasons,
            sized_candidate=sized if approved else sized,
            kill_switch=False,
            halt_trading=False,
        )
