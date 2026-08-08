"""Post-trade diagnostics for objective strategy improvement."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class PostTradeDiagnostics:
    def __init__(self, path: str | Path = "data/post_trade_diagnostics.jsonl"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def record_close(self, trade: dict[str, Any], *, bars_after: dict[str, float] | None = None) -> dict[str, Any]:
        entry = float(trade.get("entry") or 0)
        stop = float(trade.get("stop") or trade.get("initial_stop") or 0)
        target = float(trade.get("target") or 0)
        exit_px = float(trade.get("exit") or 0)
        side = str(trade.get("side", "BUY")).upper()
        risk_pts = abs(entry - stop) or 1e-9
        if side == "BUY":
            r_achieved = (exit_px - entry) / risk_pts
            mae = float(trade.get("mae_pts") or 0)
            mfe = float(trade.get("mfe_pts") or trade.get("peak_favorable_pts") or 0)
        else:
            r_achieved = (entry - exit_px) / risk_pts
            mae = float(trade.get("mae_pts") or 0)
            mfe = float(trade.get("mfe_pts") or trade.get("peak_favorable_pts") or 0)

        row = {
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "trade_id": trade.get("id"),
            "symbol": trade.get("symbol"),
            "side": side,
            "strategy": trade.get("strategy_name"),
            "setup_tier": trade.get("setup_tier"),
            "global_score": trade.get("confidence"),
            "strategy_local_score": trade.get("strategy_local_score"),
            "confirmations": trade.get("confirmations") or trade.get("reason"),
            "contradictions": trade.get("contradictions"),
            "entry_market_timestamp": trade.get("market_timestamp") or trade.get("opened_at"),
            "received_at": trade.get("received_at"),
            "data_delay_seconds": trade.get("estimated_delay_seconds"),
            "feed_source": trade.get("feed_source"),
            "session": trade.get("session"),
            "agent_id": trade.get("agent_id"),
            "qty": trade.get("qty_original") or trade.get("qty"),
            "entry": entry,
            "exit": exit_px,
            "stop": stop,
            "target": target,
            "pnl_dollars": trade.get("pnl_dollars"),
            "r_achieved": round(r_achieved, 3),
            "mae_pts": mae,
            "mfe_pts": mfe,
            "exit_reason": trade.get("exit_reason"),
            "stop_touched_before_target": trade.get("exit_reason") in {
                "stop",
                "STOP",
                "stop_hit",
            },
            "market_move_after_entry": bars_after or {},
        }
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, default=str) + "\n")
        return row


class HypotheticalBTracker:
    """Journal B setups and later compare expectancy vs A+/A."""

    def __init__(self, path: str | Path = "data/hypothetical_b_setups.jsonl"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, setup_row: dict[str, Any]) -> None:
        row = {
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            **setup_row,
            "executed": False,
            "hypothetical": True,
        }
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, default=str) + "\n")
