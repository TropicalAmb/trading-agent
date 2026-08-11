from __future__ import annotations

import logging
from typing import Any

from agent.execution.order_state import OrderState
from agent.execution.sizing import (
    fit_quantity_to_risk,
    hard_cap_from_cfg,
    resolve_trade_quantity,
)
from agent.paper.blotter import PaperBlotter
from agent.schedule.sessions import active_session_name
from agent.strategy.sweep_retest import SweepSignal

logger = logging.getLogger(__name__)

# Default tick sizes (points) for paper slippage — contract multipliers stay in instruments.point_value
_DEFAULT_TICKS = {
    "MES": 0.25,
    "MNQ": 0.25,
    "MGC": 0.1,
    "MYM": 1.0,
    "M2K": 0.1,
    "MCL": 0.01,
    "ES": 0.25,
    "NQ": 0.25,
    "CL": 0.01,
    "GC": 0.1,
}


def apply_paper_friction(
    cfg: dict[str, Any],
    *,
    symbol: str,
    side: str,
    entry: float,
    stop: float,
    target: float,
) -> tuple[float, float, float, str]:
    """Slippage never improves fill. Returns entry, stop, target, note."""
    pe = cfg.get("paper_execution") or {}
    tick = float(
        (cfg.get("instruments", {}).get(symbol) or {}).get("tick_size")
        or _DEFAULT_TICKS.get(symbol.upper(), 0.25)
    )
    e_slip = int(pe.get("slippage_ticks_entry", 1)) * tick
    s_slip = int(pe.get("slippage_ticks_stop", 1)) * tick
    t_slip = int(pe.get("slippage_ticks_target", 0)) * tick
    note = "FILL_MODEL_LIMITATION: delayed bar approximation"
    if side.upper() == "BUY":
        # Entry no better (higher), stop no better (lower), target no better (lower)
        entry2 = entry + e_slip
        stop2 = stop - s_slip
        target2 = target - t_slip
    else:
        entry2 = entry - e_slip
        stop2 = stop + s_slip
        target2 = target + t_slip
    return float(entry2), float(stop2), float(target2), note


class DirectionalExecutor:
    """Places bracket orders (entry + stop + target) via paper adapter or broker.

    Paper execution is architecturally identical to live — only the adapter differs.
    Quantity comes from config (default_quantity), never hard-coded.
    """

    def __init__(self, broker, cfg: dict[str, Any], blotter: PaperBlotter | None = None):
        self.broker = broker
        self.cfg = cfg
        self.blotter = blotter or PaperBlotter(
            cfg.get("paper", {}).get("json_path", "data/paper_trades.json"),
            cfg.get("paper", {}).get("html_path", "data/paper_trading_view.html"),
            float(cfg.get("paper", {}).get("starting_equity", 50_000)),
        )

    def _size_qty(self, signal: SweepSignal) -> int:
        desired = resolve_trade_quantity(
            self.cfg,
            symbol=str(signal.symbol),
            strategy=str(getattr(signal, "strategy_name", "") or ""),
            agent_id=str(getattr(signal, "agent_id", self.cfg.get("agent_id", "agent_1"))),
            signal=signal,
            tier=str(getattr(signal, "setup_tier", "") or "") or None,
        )
        meta = self.cfg.get("instruments", {}).get(str(signal.symbol), {}) or {}
        pv = float(meta.get("point_value", 5.0))
        hard = hard_cap_from_cfg(self.cfg)
        max_q = int((self.cfg.get("quantity") or {}).get("max_quantity", 25))
        return fit_quantity_to_risk(
            desired_qty=desired,
            entry=float(signal.entry),
            stop=float(signal.stop),
            point_value=pv,
            hard_cap_dollars=hard,
            max_quantity=max_q,
        )

    def execute(self, signal: SweepSignal, *, source: str = "agent") -> dict[str, Any]:
        dry_run = bool(self.cfg.get("execution", {}).get("dry_run", True))
        mode = str(self.cfg.get("mode", "paper")).lower()
        # Hard invariant: paper mode must never hit live broker order path
        if mode == "paper":
            dry_run = True
        qty = self._size_qty(signal)
        detail = {
            "symbol": signal.symbol,
            "side": signal.side,
            "entry": signal.entry,
            "stop": signal.stop,
            "target": signal.target,
            "qty": qty,
            "confidence": signal.confidence,
            "risk_dollars": signal.risk_dollars,
            "reward_dollars": signal.reward_dollars,
            "reason": signal.reason,
            "setup_tier": getattr(signal, "setup_tier", None),
            "strategy_name": getattr(signal, "strategy_name", None),
            "agent_id": getattr(signal, "agent_id", self.cfg.get("agent_id", "agent_1")),
            "market_timestamp": str(getattr(signal, "market_timestamp", "") or ""),
            "received_timestamp": str(getattr(signal, "received_timestamp", "") or ""),
        }
        if qty < 1:
            logger.warning(
                "Directional REJECT %s %s — cannot size under risk hard cap",
                signal.side,
                signal.symbol,
            )
            return {
                "ok": False,
                "status": "REJECTED",
                "reason": "RISK_LIMIT qty=0 after fit",
                "detail": detail,
            }
        logger.info(
            "Directional %s %s qty=%s conf=%s tier=%s dry_run=%s risk=$%.0f target=$%.0f",
            signal.side,
            signal.symbol,
            qty,
            getattr(signal, "confidence", "?"),
            getattr(signal, "setup_tier", "?"),
            dry_run,
            signal.risk_dollars * max(qty, 1),
            signal.reward_dollars * max(qty, 1),
        )

        # Global kill switch — no new orders when armed
        try:
            from agent.execution.kill_switch import kill_switch_from_cfg

            ks = kill_switch_from_cfg(self.cfg)
            reject = ks.reject_new_orders_reason()
            if reject:
                logger.warning("KILL_SWITCH blocked order %s %s", signal.symbol, reject)
                return {
                    "dry_run": dry_run,
                    "submitted": False,
                    "order_id": None,
                    "status": "REJECTED",
                    "order_state": OrderState.REJECTED.value,
                    "reason": reject,
                }
        except Exception:
            pass

        if dry_run or not hasattr(self.broker, "place_bracket_order"):
            meta = self.cfg.get("instruments", {}).get(signal.symbol, {})
            entry, stop, target, fill_note = apply_paper_friction(
                self.cfg,
                symbol=str(signal.symbol),
                side=str(signal.side),
                entry=float(signal.entry),
                stop=float(signal.stop),
                target=float(signal.target),
            )
            # Order state machine: paper jumps CREATED → FILLED (deterministic)
            _ = OrderState.CREATED
            sig_meta = getattr(signal, "metadata", None) or {}
            paper = self.blotter.record_paper_fill(
                symbol=signal.symbol,
                side=signal.side,
                entry=entry,
                stop=stop,
                target=target,
                qty=qty,
                source=source,
                reason=str(getattr(signal, "reason", "") or "") + f" | {fill_note}",
                confidence=float(getattr(signal, "confidence", 0) or 0),
                risk_dollars=float(getattr(signal, "risk_dollars", 0) or 0),
                reward_dollars=float(getattr(signal, "reward_dollars", 0) or 0),
                status=OrderState.FILLED.value,
                session=active_session_name(self.cfg) or "unknown",
                point_value=float(meta.get("point_value", 5.0)),
                setup_tier=str(getattr(signal, "setup_tier", "") or ""),
                strategy_name=str(getattr(signal, "strategy_name", "") or ""),
                agent_id=str(
                    getattr(signal, "agent_id", self.cfg.get("agent_id", "agent_1"))
                ),
                market_timestamp=str(getattr(signal, "market_timestamp", "") or ""),
                received_timestamp=str(getattr(signal, "received_timestamp", "") or ""),
                feed_source=str(getattr(signal, "feed_source", "yahoo_delayed") or ""),
                config_version=str(
                    sig_meta.get("config_version") or self.cfg.get("config_version") or ""
                ),
                strategy_version=str(
                    sig_meta.get("strategy_version")
                    or self.cfg.get("strategy_version")
                    or ""
                ),
                metadata=dict(sig_meta),
            )
            return {
                "dry_run": True,
                "submitted": True,
                "order_id": paper["id"],
                "status": "PAPER_FILL",
                "order_state": OrderState.FILLED.value,
                "fill_model": fill_note,
                "detail": detail,
                "paper_view": "data/paper_trading_view.html",
            }
        # Live path: submit ≠ fill — adapter must progress OrderState asynchronously
        return self.broker.place_bracket_order(signal, qty=qty, dry_run=dry_run)
