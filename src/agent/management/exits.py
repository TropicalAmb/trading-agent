from __future__ import annotations

import logging
import sqlite3
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Optional

from agent.models import (
    CreditSpreadCandidate,
    ExitReason,
    ExitSignal,
    OpenPosition,
    SpreadType,
)

logger = logging.getLogger(__name__)


class PositionBook:
    """SQLite-backed open position tracker (works for mock + paper)."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS positions (
                    id TEXT PRIMARY KEY,
                    underlying TEXT NOT NULL,
                    spread_type TEXT NOT NULL,
                    short_strike REAL NOT NULL,
                    long_strike REAL NOT NULL,
                    right TEXT NOT NULL,
                    expiry TEXT NOT NULL,
                    width REAL NOT NULL,
                    entry_credit REAL NOT NULL,
                    quantity INTEGER NOT NULL,
                    entry_spot REAL NOT NULL,
                    entry_ts TEXT NOT NULL,
                    status TEXT NOT NULL,
                    mark_debit REAL,
                    unrealized_pnl REAL DEFAULT 0
                )
                """
            )
            conn.commit()

    def open_from_candidate(
        self, candidate: CreditSpreadCandidate, *, entry_ts: datetime | None = None
    ) -> OpenPosition:
        pos = OpenPosition(
            id=str(uuid.uuid4())[:8],
            underlying=candidate.underlying,
            spread_type=candidate.spread_type,
            short_strike=candidate.short_leg.strike,
            long_strike=candidate.long_leg.strike,
            right=candidate.short_leg.right,
            expiry=candidate.short_leg.expiry,
            width=candidate.width,
            entry_credit=candidate.credit,
            quantity=candidate.contracts,
            entry_spot=candidate.spot,
            entry_ts=entry_ts or datetime.now(timezone.utc),
            status="open",
        )
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO positions (
                    id, underlying, spread_type, short_strike, long_strike, right,
                    expiry, width, entry_credit, quantity, entry_spot, entry_ts,
                    status, mark_debit, unrealized_pnl
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    pos.id,
                    pos.underlying,
                    pos.spread_type.value,
                    pos.short_strike,
                    pos.long_strike,
                    pos.right,
                    pos.expiry.isoformat(),
                    pos.width,
                    pos.entry_credit,
                    pos.quantity,
                    pos.entry_spot,
                    pos.entry_ts.isoformat(),
                    pos.status,
                    None,
                    0.0,
                ),
            )
            conn.commit()
        return pos

    def list_open(self) -> list[OpenPosition]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM positions WHERE status='open' ORDER BY entry_ts"
            ).fetchall()
        return [self._row_to_pos(r) for r in rows]

    def close(self, position_id: str, mark_debit: float, pnl: float) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE positions
                SET status='closed', mark_debit=?, unrealized_pnl=?
                WHERE id=?
                """,
                (mark_debit, pnl, position_id),
            )
            conn.commit()

    def update_mark(self, position_id: str, mark_debit: float, pnl: float) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE positions SET mark_debit=?, unrealized_pnl=? WHERE id=?",
                (mark_debit, pnl, position_id),
            )
            conn.commit()

    @staticmethod
    def _row_to_pos(r: sqlite3.Row) -> OpenPosition:
        return OpenPosition(
            id=r["id"],
            underlying=r["underlying"],
            spread_type=SpreadType(r["spread_type"]),
            short_strike=r["short_strike"],
            long_strike=r["long_strike"],
            right=r["right"],
            expiry=date.fromisoformat(r["expiry"]),
            width=r["width"],
            entry_credit=r["entry_credit"],
            quantity=r["quantity"],
            entry_spot=r["entry_spot"],
            entry_ts=datetime.fromisoformat(r["entry_ts"]),
            status=r["status"],
            mark_debit=r["mark_debit"],
            unrealized_pnl=r["unrealized_pnl"] or 0.0,
        )


def estimate_close_debit(
    pos: OpenPosition,
    spot: float,
    *,
    days_passed: int,
    entry_dte: int,
) -> float:
    """Approximate mark-to-close debit using intrinsic + decaying extrinsic.

    Conservative enough for management decisions / backtests without full OPRA.
    """
    width = pos.width
    if pos.spread_type == SpreadType.PUT_CREDIT:
        # Short put intrinsic if spot below short
        short_intr = max(0.0, pos.short_strike - spot)
        long_intr = max(0.0, pos.long_strike - spot)
    else:
        short_intr = max(0.0, spot - pos.short_strike)
        long_intr = max(0.0, spot - pos.long_strike)

    intrinsic_spread = max(0.0, min(width, short_intr - long_intr))
    # Remaining extrinsic roughly scales with sqrt time remaining
    rem = max(0.0, entry_dte - days_passed)
    time_frac = (rem / entry_dte) ** 0.5 if entry_dte > 0 else 0.0
    # Extrinsic left on the short-long package ~ portion of original credit
    # when still OTM; when tested, intrinsic dominates
    extrinsic = max(0.0, pos.entry_credit * time_frac * 0.85)
    if intrinsic_spread > 0:
        extrinsic *= 0.35
    debit = min(width, intrinsic_spread + extrinsic)
    # Never mark below a tiny residual while open with time left
    if rem > 0 and intrinsic_spread == 0:
        debit = max(debit, pos.entry_credit * 0.15 * time_frac)
    return round(min(width, max(0.05, debit)), 4)


def evaluate_exits(
    positions: list[OpenPosition],
    spots: dict[str, float],
    cfg: dict[str, Any],
    *,
    today: date | None = None,
) -> list[ExitSignal]:
    """Classic short-premium management: 50% profit, 2x stop, time exit."""
    mgmt = cfg.get("management", {})
    profit_frac = float(mgmt.get("profit_take_frac_of_credit", 0.50))
    stop_mult = float(mgmt.get("stop_loss_mult_of_credit", 2.0))
    time_exit_dte = int(mgmt.get("time_exit_dte", 21))
    force_close_dte = int(mgmt.get("force_close_dte", 7))

    today = today or date.today()
    signals: list[ExitSignal] = []

    for pos in positions:
        spot = spots.get(pos.underlying)
        if spot is None:
            continue
        dte = (pos.expiry - today).days
        entry_dte = max(1, (pos.expiry - pos.entry_ts.date()).days)
        days_passed = max(0, entry_dte - dte)
        mark = estimate_close_debit(
            pos, spot, days_passed=days_passed, entry_dte=entry_dte
        )
        pnl_per = pos.entry_credit - mark
        pnl = pnl_per * 100 * pos.quantity

        # Profit target: buy back at <= (1 - profit_frac) * credit
        target_debit = pos.entry_credit * (1.0 - profit_frac)
        if mark <= target_debit + 1e-9:
            signals.append(
                ExitSignal(
                    position_id=pos.id,
                    reason=ExitReason.PROFIT_TARGET,
                    mark_debit=mark,
                    pnl=pnl,
                    detail=f"mark {mark:.2f} <= target {target_debit:.2f}",
                )
            )
            continue

        # Stop: debit >= stop_mult * credit.
        # Assume a working stop fills near stop_debit (not full gap-to-max-loss),
        # which is the intended managed-trade behavior intraday.
        stop_debit = min(pos.width, pos.entry_credit * stop_mult)
        if mark >= stop_debit - 1e-9:
            fill = stop_debit
            stop_pnl = (pos.entry_credit - fill) * 100 * pos.quantity
            signals.append(
                ExitSignal(
                    position_id=pos.id,
                    reason=ExitReason.STOP_LOSS,
                    mark_debit=fill,
                    pnl=stop_pnl,
                    detail=f"mark {mark:.2f} >= stop {stop_debit:.2f}; fill@{fill:.2f}",
                )
            )
            continue

        if dte <= force_close_dte:
            signals.append(
                ExitSignal(
                    position_id=pos.id,
                    reason=ExitReason.EXPIRY_RISK,
                    mark_debit=mark,
                    pnl=pnl,
                    detail=f"dte {dte} <= force_close {force_close_dte}",
                )
            )
            continue

        if dte <= time_exit_dte and pnl_per >= 0:
            signals.append(
                ExitSignal(
                    position_id=pos.id,
                    reason=ExitReason.TIME_EXIT,
                    mark_debit=mark,
                    pnl=pnl,
                    detail=f"dte {dte} <= time_exit {time_exit_dte} with non-negative pnl",
                )
            )
            continue

    return signals
