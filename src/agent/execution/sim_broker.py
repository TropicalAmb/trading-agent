"""Deterministic broker simulation for execution readiness (not live capital)."""

from __future__ import annotations

import itertools
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from agent.execution.order_state import OrderState
from agent.models import AccountSnapshot

logger = logging.getLogger(__name__)


@dataclass
class SimOrder:
    order_id: str
    symbol: str
    side: str
    qty: int
    order_type: str
    state: OrderState
    entry: float | None = None
    stop: float | None = None
    target: float | None = None
    filled_qty: int = 0
    avg_fill: float | None = None
    parent_id: str | None = None
    oco_group: str | None = None
    reject_reason: str | None = None
    events: list[dict[str, Any]] = field(default_factory=list)

    def log(self, event: str, **kw: Any) -> None:
        self.events.append(
            {"ts": datetime.now(timezone.utc).isoformat(), "event": event, "state": self.state.value, **kw}
        )


class SimulatedBroker:
    """Full order-state machine for integration tests + broker-sim validation."""

    def __init__(self, *, equity: float = 25_000.0, connected: bool = True):
        self.equity = float(equity)
        self._connected = connected
        self._ids = itertools.count(1)
        self.orders: dict[str, SimOrder] = {}
        self.positions: dict[str, dict[str, Any]] = {}
        self.events: list[dict[str, Any]] = []
        self.force_reject = False
        self.force_partial = False
        self.duplicate_guard: set[str] = set()

    def connect(self) -> None:
        self._connected = True
        self._evt("CONNECT")

    def disconnect(self) -> None:
        self._connected = False
        self._evt("DISCONNECT")

    def is_connected(self) -> bool:
        return self._connected

    def _evt(self, event: str, **kw: Any) -> None:
        self.events.append({"ts": datetime.now(timezone.utc).isoformat(), "event": event, **kw})

    def get_account_snapshot(self) -> AccountSnapshot:
        return AccountSnapshot(
            equity=self.equity,
            cash=self.equity,
            buying_power=self.equity,
            open_positions=len(self.positions),
            open_underlyings=list(self.positions.keys()),
            realized_pnl_today=0.0,
            unrealized_pnl=0.0,
            healthy=self._connected,
            notes=["sim_broker"],
        )

    def _new_id(self) -> str:
        return f"SIM-{next(self._ids):05d}"

    def place_bracket_order(self, signal: Any, *, qty: int = 1, dry_run: bool = False) -> dict[str, Any]:
        if dry_run:
            return {"dry_run": True, "submitted": False, "status": "DRY_RUN", "order_state": OrderState.CREATED.value}
        if not self._connected:
            self._evt("REJECT", reason="BROKER_DISCONNECT")
            return {
                "dry_run": False,
                "submitted": False,
                "status": "REJECTED",
                "order_state": OrderState.REJECTED.value,
                "reason": "BROKER_DISCONNECT",
            }
        dup_key = f"{getattr(signal,'symbol', '')}|{getattr(signal,'side','')}|{getattr(signal,'entry', '')}|{getattr(signal,'market_timestamp','')}"
        if dup_key in self.duplicate_guard:
            self._evt("REJECT", reason="DUPLICATE_ORDER", key=dup_key)
            return {
                "dry_run": False,
                "submitted": False,
                "status": "REJECTED",
                "order_state": OrderState.REJECTED.value,
                "reason": "DUPLICATE_ORDER",
            }
        oid = self._new_id()
        order = SimOrder(
            order_id=oid,
            symbol=str(signal.symbol).upper(),
            side=str(signal.side).upper(),
            qty=int(qty),
            order_type="BRACKET",
            state=OrderState.CREATED,
            entry=float(signal.entry),
            stop=float(signal.stop),
            target=float(signal.target),
            oco_group=f"OCO-{oid}",
        )
        order.log("CREATED")
        order.state = OrderState.SUBMITTED
        order.log("SUBMITTED")
        order.state = OrderState.ACKNOWLEDGED
        order.log("ACKNOWLEDGED")
        self.orders[oid] = order
        self.duplicate_guard.add(dup_key)

        if self.force_reject:
            order.state = OrderState.REJECTED
            order.reject_reason = "FORCED_REJECT"
            order.log("REJECTED", reason="FORCED_REJECT")
            return {
                "dry_run": False,
                "submitted": True,
                "order_id": oid,
                "status": "REJECTED",
                "order_state": order.state.value,
                "reason": order.reject_reason,
            }

        fill_qty = max(1, qty // 2) if self.force_partial and qty > 1 else qty
        order.filled_qty = fill_qty
        order.avg_fill = float(signal.entry)
        if fill_qty < qty:
            order.state = OrderState.PARTIALLY_FILLED
            order.log("PARTIAL_FILL", filled=fill_qty)
        else:
            order.state = OrderState.FILLED
            order.log("FILLED", filled=fill_qty)
            self.positions[order.symbol] = {
                "symbol": order.symbol,
                "side": order.side,
                "qty": fill_qty,
                "entry": order.avg_fill,
                "stop": order.stop,
                "target": order.target,
                "order_id": oid,
            }
        # Attach protective OCO children (simulated)
        stop_id = self._new_id()
        tgt_id = self._new_id()
        for child_id, kind, px in ((stop_id, "STOP", order.stop), (tgt_id, "TARGET", order.target)):
            child = SimOrder(
                order_id=child_id,
                symbol=order.symbol,
                side="SELL" if order.side == "BUY" else "BUY",
                qty=fill_qty,
                order_type=kind,
                state=OrderState.ACKNOWLEDGED,
                entry=px,
                parent_id=oid,
                oco_group=order.oco_group,
            )
            child.log("OCO_CHILD", kind=kind)
            self.orders[child_id] = child
        return {
            "dry_run": False,
            "submitted": True,
            "order_id": oid,
            "status": order.state.value,
            "order_state": order.state.value,
            "filled_qty": fill_qty,
            "stop_order_id": stop_id,
            "target_order_id": tgt_id,
            "oco_group": order.oco_group,
        }

    def cancel_order(self, order_id: str) -> dict[str, Any]:
        o = self.orders.get(order_id)
        if o is None:
            self._evt("CANCEL_FAIL", reason="UNKNOWN_ORDER", order_id=order_id)
            return {"ok": False, "reason": "UNKNOWN_ORDER", "order_state": OrderState.REJECTED.value}
        if o.state in {OrderState.FILLED, OrderState.CANCELED, OrderState.CLOSED}:
            return {"ok": False, "reason": f"TERMINAL:{o.state.value}", "order_state": o.state.value}
        o.state = OrderState.CANCEL_PENDING
        o.log("CANCEL_PENDING")
        o.state = OrderState.CANCELED
        o.log("CANCELED")
        return {"ok": True, "order_id": order_id, "order_state": o.state.value}

    def cancel_replace(self, order_id: str, *, new_stop: float | None = None, new_target: float | None = None) -> dict[str, Any]:
        o = self.orders.get(order_id)
        if o is None:
            return {"ok": False, "reason": "UNKNOWN_ORDER"}
        cancel = self.cancel_order(order_id)
        if not cancel.get("ok"):
            return cancel
        # Create replacement working order
        rid = self._new_id()
        repl = SimOrder(
            order_id=rid,
            symbol=o.symbol,
            side=o.side,
            qty=o.qty,
            order_type=o.order_type,
            state=OrderState.ACKNOWLEDGED,
            entry=o.entry,
            stop=new_stop if new_stop is not None else o.stop,
            target=new_target if new_target is not None else o.target,
            parent_id=o.parent_id,
            oco_group=o.oco_group,
        )
        repl.log("CANCEL_REPLACE", replaced=order_id)
        self.orders[rid] = repl
        return {"ok": True, "order_id": rid, "replaced": order_id, "order_state": repl.state.value}

    def close_position(self, symbol: str) -> dict[str, Any]:
        pos = self.positions.pop(symbol.upper(), None)
        if pos is None:
            self._evt("CLOSE_FAIL", reason="NO_POSITION", symbol=symbol)
            return {"ok": False, "reason": "NO_POSITION"}
        oid = self._new_id()
        o = SimOrder(
            order_id=oid,
            symbol=symbol.upper(),
            side="SELL" if pos["side"] == "BUY" else "BUY",
            qty=int(pos["qty"]),
            order_type="MARKET",
            state=OrderState.FILLED,
            entry=float(pos["entry"]),
            filled_qty=int(pos["qty"]),
            avg_fill=float(pos["entry"]),
        )
        o.log("FLAT")
        o.state = OrderState.CLOSED
        o.log("CLOSED")
        self.orders[oid] = o
        # Cancel remaining OCO children
        for child in self.orders.values():
            if child.oco_group and child.parent_id == pos.get("order_id") and child.state not in {
                OrderState.FILLED,
                OrderState.CANCELED,
                OrderState.CLOSED,
            }:
                child.state = OrderState.CANCELED
                child.log("OCO_CANCEL_ON_FLAT")
        return {"ok": True, "order_id": oid, "order_state": OrderState.CLOSED.value}

    def reconcile_positions(self) -> dict[str, Any]:
        """Internal vs broker position reconciliation snapshot."""
        return {
            "broker_positions": dict(self.positions),
            "open_working_orders": [
                o.order_id
                for o in self.orders.values()
                if o.state
                in {
                    OrderState.SUBMITTED,
                    OrderState.ACKNOWLEDGED,
                    OrderState.PARTIALLY_FILLED,
                    OrderState.CANCEL_PENDING,
                }
            ],
            "connected": self._connected,
        }
