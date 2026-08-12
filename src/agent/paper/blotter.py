"""Local paper-trading blotter with full trade lifecycle for learning."""

from __future__ import annotations

import csv
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_JSON = Path("data/paper_trades.json")
DEFAULT_HTML = Path("data/paper_trading_view.html")
DEFAULT_CSV = Path("data/trade_journal.csv")


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _hold_minutes(opened: str | None, closed: str | None) -> float | None:
    a = _parse_ts(opened)
    b = _parse_ts(closed)
    if not a or not b:
        return None
    return round((b - a).total_seconds() / 60.0, 2)


def _money(side: str, entry: float, other: float, qty: int, point_value: float) -> float:
    """Dollar move from entry to another price for 1+ contracts."""
    if side.upper() == "BUY":
        pts = float(other) - float(entry)
    else:
        pts = float(entry) - float(other)
    return round(pts * float(point_value) * int(qty), 2)


def _fmt_money(value: float | None) -> str:
    if value is None:
        return "—"
    sign = "+" if value > 0 else ""
    return f"{sign}${value:,.2f}"


class PaperBlotter:
    def __init__(
        self,
        json_path: str | Path = DEFAULT_JSON,
        html_path: str | Path = DEFAULT_HTML,
        starting_equity: float = 50_000.0,
        csv_path: str | Path = DEFAULT_CSV,
    ):
        self.json_path = Path(json_path)
        self.html_path = Path(html_path)
        self.csv_path = Path(csv_path)
        self.json_path.parent.mkdir(parents=True, exist_ok=True)
        self.starting_equity = starting_equity
        self._state = self._load()

    def _load(self) -> dict[str, Any]:
        if self.json_path.exists():
            try:
                state = json.loads(self.json_path.read_text(encoding="utf-8"))
                return self._migrate(state)
            except json.JSONDecodeError:
                logger.warning("Corrupt paper blotter; starting fresh")
        return {
            "starting_equity": self.starting_equity,
            "realized_pnl": 0.0,
            "trades": [],
            "open_positions": [],
            "closed_trades": [],
        }

    def _migrate(self, state: dict[str, Any]) -> dict[str, Any]:
        """Repair older demo blotter rows so manage/close works."""
        state.setdefault("realized_pnl", 0.0)
        state.setdefault("closed_trades", [])
        state.setdefault("open_positions", [])
        state.setdefault("trades", [])
        by_id = {t.get("id"): t for t in state["trades"] if t.get("id")}
        for t in state["trades"]:
            if t.get("status") in {"PAPER_FILL", "DRY_RUN"}:
                t["status"] = "OPEN"
            t.setdefault("opened_at", t.get("ts"))
            t.setdefault("point_value", 5.0 if t.get("symbol") == "MES" else 2.0)
            t.setdefault("session", "unknown")
        for p in state["open_positions"]:
            p.setdefault("point_value", 5.0 if p.get("symbol") == "MES" else 2.0)
            p.setdefault("session", "unknown")
            tid = p.get("trade_id")
            if tid and tid in by_id:
                by_id[tid]["status"] = "OPEN"
                by_id[tid].setdefault("opened_at", p.get("opened_at") or by_id[tid].get("ts"))
                by_id[tid].setdefault("point_value", p.get("point_value", 5.0))
        return state

    def _save(self) -> None:
        self.json_path.write_text(
            json.dumps(self._state, indent=2, default=str), encoding="utf-8"
        )
        self._export_csv()
        self.render_html()

    def _export_csv(self) -> None:
        closed = self._state.get("closed_trades", [])
        self.csv_path.parent.mkdir(parents=True, exist_ok=True)
        fields = [
            "id",
            "symbol",
            "side",
            "session",
            "opened_at",
            "closed_at",
            "hold_minutes",
            "entry",
            "exit",
            "stop",
            "target",
            "qty",
            "pnl_dollars",
            "exit_reason",
            "confidence",
            "source",
            "reason",
            "result",
        ]
        with self.csv_path.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
            w.writeheader()
            for t in closed:
                w.writerow(t)
            for t in self._state.get("trades", []):
                if t.get("status") == "OPEN":
                    w.writerow(
                        {
                            **t,
                            "opened_at": t.get("opened_at") or t.get("ts"),
                            "closed_at": "",
                            "hold_minutes": "",
                            "exit": "",
                            "pnl_dollars": "",
                            "exit_reason": "OPEN",
                            "result": "OPEN",
                        }
                    )

    def record_paper_fill(
        self,
        *,
        symbol: str,
        side: str,
        entry: float,
        stop: float,
        target: float,
        qty: int = 1,
        source: str = "agent",
        reason: str = "",
        confidence: float | None = None,
        risk_dollars: float | None = None,
        reward_dollars: float | None = None,
        tv_price: float | None = None,
        status: str = "OPEN",
        session: str | None = None,
        point_value: float = 5.0,
        setup_tier: str = "",
        strategy_name: str = "",
        agent_id: str = "agent_1",
        market_timestamp: str = "",
        received_timestamp: str = "",
        feed_source: str = "yahoo_delayed",
        config_version: str = "",
        strategy_version: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        # Prefer market bar time for journal honesty on delayed feeds
        opened_at = market_timestamp or now
        # Replace any open on same symbol
        self._state["open_positions"] = [
            p for p in self._state.get("open_positions", []) if p.get("symbol") != symbol.upper()
        ]
        trade_id = f"PAPER-{len(self._state.get('trades', [])) + len(self._state.get('closed_trades', [])) + 1:05d}"
        risk_pts = abs(float(entry) - float(stop))
        # TP1 default = 1R (same distance as stop, in profit direction)
        if side.upper() == "BUY":
            tp1 = float(entry) + risk_pts
        else:
            tp1 = float(entry) - risk_pts
        meta = dict(metadata or {})
        # Compact learning payload — entry-time only (no post-entry leakage)
        learn_meta = {
            "setup_id": meta.get("setup_id"),
            "structural_key": meta.get("structural_key"),
            "regime": meta.get("regime"),
            "global_score": meta.get("global_score"),
            "strategy_local_score": meta.get("strategy_local_score"),
            "entry_features": meta.get("entry_features"),
            "router_evidence": meta.get("router_evidence"),
            "agreeing_engines": meta.get("agreeing_engines"),
            "cascade": meta.get("cascade"),
            "high_confidence_shadow": meta.get("high_confidence_shadow"),
            "quality_predictions": meta.get("quality_predictions"),
            "config_version": config_version or meta.get("config_version"),
        }
        trade = {
            "id": trade_id,
            "ts": now,
            "opened_at": opened_at,
            "received_at": received_timestamp or now,
            "market_timestamp": market_timestamp or opened_at,
            "closed_at": None,
            "hold_minutes": None,
            "symbol": symbol.upper(),
            "side": side.upper(),
            "qty": qty,
            "qty_original": qty,
            "entry": float(entry),
            "exit": None,
            "stop": float(stop),
            "target": float(target),
            "tp1": tp1,
            "tp1_done": False,
            "status": "OPEN",
            "source": source,
            "reason": reason,
            "confidence": confidence,
            "setup_tier": setup_tier,
            "strategy_name": strategy_name,
            "agent_id": agent_id,
            "feed_source": feed_source,
            "config_version": config_version or "",
            "strategy_version": strategy_version or "",
            "risk_dollars": risk_dollars,
            "reward_dollars": reward_dollars,
            "tv_price": tv_price,
            "session": session or "unknown",
            "point_value": float(point_value),
            "pnl_dollars": None,
            "partial_pnl_dollars": 0.0,
            "exit_reason": None,
            "result": "OPEN",
            "venue": "LOCAL_PAPER",
            "setup_id": meta.get("setup_id"),
            "metadata": learn_meta,
            "entry_features": meta.get("entry_features"),
        }
        self._state.setdefault("trades", []).insert(0, trade)
        # signal risk/reward are per 1 contract; scale to position size
        if risk_dollars is not None:
            risk_d = float(risk_dollars) * qty
        else:
            risk_d = abs(_money(side, entry, stop, qty, float(point_value)))
        if reward_dollars is not None:
            reward_d = float(reward_dollars) * qty
        else:
            reward_d = abs(_money(side, entry, target, qty, float(point_value)))
        trade["risk_dollars"] = risk_d
        trade["reward_dollars"] = reward_d
        self._state["open_positions"].append(
            {
                "symbol": trade["symbol"],
                "side": trade["side"],
                "qty": qty,
                "qty_original": qty,
                "entry": trade["entry"],
                "stop": trade["stop"],
                "target": trade["target"],
                "tp1": tp1,
                "tp1_done": False,
                "initial_stop": float(stop),
                "peak_favorable_pts": 0.0,
                "mae_pts": 0.0,
                "mfe_pts": 0.0,
                "opened_at": trade["opened_at"],
                "market_timestamp": trade.get("market_timestamp"),
                "received_at": trade.get("received_at"),
                "trade_id": trade["id"],
                "session": trade["session"],
                "point_value": trade["point_value"],
                "risk_dollars": risk_d,
                "reward_dollars": reward_d,
                "partial_pnl_dollars": 0.0,
                "setup_tier": setup_tier,
                "strategy_name": strategy_name,
                "agent_id": agent_id,
                "feed_source": feed_source,
                "setup_id": meta.get("setup_id"),
                "metadata": learn_meta,
            }
        )
        trade["initial_stop"] = float(stop)
        self._save()
        logger.info(
            "OPEN %s %s qty=%s @ %.2f stop=%.2f tp1=%.2f target=%.2f session=%s id=%s",
            trade["side"],
            trade["symbol"],
            qty,
            trade["entry"],
            trade["stop"],
            tp1,
            trade["target"],
            trade["session"],
            trade["id"],
        )
        return trade

    def close_trade(
        self,
        trade_id: str,
        *,
        exit_price: float,
        exit_reason: str,
    ) -> dict[str, Any] | None:
        trade = next((t for t in self._state.get("trades", []) if t.get("id") == trade_id), None)
        if trade is None:
            return None
        if trade.get("status") not in {"OPEN", "PAPER_FILL", "DRY_RUN"}:
            return trade

        now = datetime.now(timezone.utc).isoformat()
        side = trade["side"]
        entry = float(trade["entry"])
        qty = int(trade.get("qty", 1))
        pv = float(trade.get("point_value", 5.0))
        if side == "BUY":
            pnl = (float(exit_price) - entry) * pv * qty
        else:
            pnl = (entry - float(exit_price)) * pv * qty
        partial = float(trade.get("partial_pnl_dollars") or 0.0)
        total_pnl = round(pnl + partial, 2)

        trade["closed_at"] = now
        trade["exit"] = float(exit_price)
        trade["exit_reason"] = exit_reason
        trade["pnl_dollars"] = total_pnl
        trade["hold_minutes"] = _hold_minutes(trade.get("opened_at"), now)
        trade["status"] = "CLOSED"
        trade["result"] = "WIN" if total_pnl > 0 else ("LOSS" if total_pnl < 0 else "BE")

        # Capture excursion stats before removing open row
        pos = next(
            (
                p
                for p in self._state.get("open_positions", [])
                if p.get("trade_id") == trade_id
            ),
            None,
        )
        if pos is not None:
            trade["mae_pts"] = float(pos.get("mae_pts") or trade.get("mae_pts") or 0)
            trade["mfe_pts"] = float(
                pos.get("mfe_pts")
                or pos.get("peak_favorable_pts")
                or trade.get("peak_favorable_pts")
                or 0
            )

        self._state["open_positions"] = [
            p for p in self._state.get("open_positions", []) if p.get("trade_id") != trade_id
        ]
        self._state.setdefault("closed_trades", []).insert(0, dict(trade))
        self._state["realized_pnl"] = round(
            float(self._state.get("realized_pnl", 0.0)) + pnl, 2
        )
        self._save()
        try:
            from agent.journal.diagnostics import PostTradeDiagnostics

            PostTradeDiagnostics().record_close(trade)
        except Exception:
            logger.exception("post-trade diagnostics failed")
        logger.info(
            "CLOSE %s %s exit=%.2f pnl=$%.2f (incl partial $%.2f) hold=%.1f min reason=%s id=%s",
            trade["side"],
            trade["symbol"],
            exit_price,
            trade["pnl_dollars"],
            partial,
            trade["hold_minutes"] or 0,
            exit_reason,
            trade_id,
        )
        return trade

    def take_partial(
        self,
        trade_id: str,
        *,
        exit_price: float,
        close_qty: int,
        move_stop_to_be: bool = True,
    ) -> dict[str, Any] | None:
        """Bank part of the position (TP1); leave the runner open."""
        trade = next((t for t in self._state.get("trades", []) if t.get("id") == trade_id), None)
        pos = next(
            (p for p in self._state.get("open_positions", []) if p.get("trade_id") == trade_id),
            None,
        )
        if trade is None or pos is None:
            return None
        qty = int(pos.get("qty", 1))
        close_qty = min(max(1, close_qty), qty - 1) if qty > 1 else 0
        if close_qty <= 0:
            return None

        side = trade["side"]
        entry = float(trade["entry"])
        pv = float(trade.get("point_value", 5.0))
        partial_pnl = _money(side, entry, exit_price, close_qty, pv)
        remaining = qty - close_qty

        trade["qty"] = remaining
        trade["tp1_done"] = True
        trade["partial_pnl_dollars"] = round(
            float(trade.get("partial_pnl_dollars") or 0.0) + partial_pnl, 2
        )
        pos["qty"] = remaining
        pos["tp1_done"] = True
        pos["partial_pnl_dollars"] = trade["partial_pnl_dollars"]
        # Remaining risk/reward for open qty
        pos["risk_dollars"] = abs(
            _money(side, entry, float(pos["stop"]), remaining, pv)
        )
        pos["reward_dollars"] = abs(
            _money(side, entry, float(pos["target"]), remaining, pv)
        )
        if move_stop_to_be:
            pos["stop"] = entry
            trade["stop"] = entry
            pos["risk_dollars"] = 0.0

        self._state["realized_pnl"] = round(
            float(self._state.get("realized_pnl", 0.0)) + partial_pnl, 2
        )
        # Journal a partial close row for the learning CSV
        partial_row = {
            **dict(trade),
            "id": f"{trade_id}-TP1",
            "qty": close_qty,
            "exit": float(exit_price),
            "closed_at": datetime.now(timezone.utc).isoformat(),
            "status": "PARTIAL",
            "exit_reason": "tp1",
            "pnl_dollars": partial_pnl,
            "result": "WIN" if partial_pnl > 0 else ("LOSS" if partial_pnl < 0 else "BE"),
            "hold_minutes": _hold_minutes(
                trade.get("opened_at"), datetime.now(timezone.utc).isoformat()
            ),
        }
        self._state.setdefault("closed_trades", []).insert(0, partial_row)
        self._save()
        logger.info(
            "TP1 PARTIAL %s %s closed %s/%s @ %.2f pnl=$%.2f runner=%s stop_be=%s id=%s",
            side,
            trade["symbol"],
            close_qty,
            qty,
            exit_price,
            partial_pnl,
            remaining,
            move_stop_to_be,
            trade_id,
        )
        return partial_row

    def _apply_profit_protection(
        self,
        pos: dict[str, Any],
        trade: dict[str, Any] | None,
        px: float,
        prot: dict[str, Any],
    ) -> bool:
        """Tighten stops so winners don't become full losers. Returns True if stop moved."""
        if not prot.get("enabled", False):
            return False
        side = str(pos["side"])
        entry = float(pos["entry"])
        stop = float(pos["stop"])
        target = float(pos["target"])
        initial_stop = float(
            pos.get("initial_stop")
            or (trade or {}).get("initial_stop")
            or stop
        )
        risk_pts = abs(entry - initial_stop)
        if risk_pts <= 0:
            return False

        if side == "BUY":
            fav = px - entry
        else:
            fav = entry - px
        peak = max(float(pos.get("peak_favorable_pts") or 0.0), fav)
        pos["peak_favorable_pts"] = peak
        if trade is not None:
            trade["peak_favorable_pts"] = peak
            trade.setdefault("initial_stop", initial_stop)
        pos.setdefault("initial_stop", initial_stop)

        new_stop = stop
        be_at = float(prot.get("move_be_at_r", 0.75))
        if fav >= be_at * risk_pts:
            # Breakeven (tiny buffer toward profit so fees/noise don't stop out instantly)
            be = entry
            if side == "BUY":
                new_stop = max(new_stop, be)
            else:
                new_stop = min(new_stop, be)

        # Near target: lock a chunk of the open profit
        dist_target = abs(target - entry)
        if dist_target > 0:
            progress = fav / dist_target
            near = float(prot.get("near_target_frac", 0.70))
            lock_frac = float(prot.get("lock_profit_frac", 0.50))
            if progress >= near:
                if side == "BUY":
                    lock_px = entry + dist_target * lock_frac
                    new_stop = max(new_stop, lock_px)
                else:
                    lock_px = entry - dist_target * lock_frac
                    new_stop = min(new_stop, lock_px)

        # Trail from peak after +1R
        trail_after = float(prot.get("trail_after_r", 1.0))
        giveback = float(prot.get("trail_giveback_r", 0.40))
        if peak >= trail_after * risk_pts:
            locked_fav = peak - giveback * risk_pts
            if locked_fav > 0:
                if side == "BUY":
                    new_stop = max(new_stop, entry + locked_fav)
                else:
                    new_stop = min(new_stop, entry - locked_fav)

        if new_stop == stop:
            return False
        # Only tighten (never widen)
        if side == "BUY" and new_stop <= stop:
            return False
        if side == "SELL" and new_stop >= stop:
            return False
        pos["stop"] = float(new_stop)
        if trade is not None:
            trade["stop"] = float(new_stop)
        pv = float(pos.get("point_value") or 5.0)
        qty = int(pos.get("qty") or 1)
        pos["risk_dollars"] = abs(_money(side, entry, new_stop, qty, pv))
        logger.info(
            "PROTECT %s %s stop %.2f -> %.2f (mark=%.2f peak_fav=%.2f)",
            side,
            pos.get("symbol"),
            stop,
            new_stop,
            px,
            peak,
        )
        return True

    def manage_open(
        self,
        prices: dict[str, float],
        *,
        max_hold_minutes: float | None = None,
        scale_out: dict[str, Any] | None = None,
        profit_protection: dict[str, Any] | None = None,
        time_stop_only_if_losing: bool = True,
    ) -> list[dict[str, Any]]:
        """Hit TP1 (partial), stop, target, or time stop. Returns closed/partial events."""
        closed: list[dict[str, Any]] = []
        scale = scale_out or {}
        scale_on = bool(scale.get("enabled", False))
        move_be = bool(scale.get("move_stop_to_breakeven", True))
        prot = profit_protection or {}
        dirty = False

        for pos in list(self._state.get("open_positions", [])):
            sym = pos["symbol"]
            px = prices.get(sym)
            if px is None:
                continue
            side = pos["side"]
            entry = float(pos["entry"])
            target = float(pos["target"])
            # Track MAE / MFE every mark for post-trade diagnostics
            if side == "BUY":
                fav = float(px) - entry
                adv = entry - float(px)
            else:
                fav = entry - float(px)
                adv = float(px) - entry
            pos["mfe_pts"] = max(float(pos.get("mfe_pts") or 0.0), max(0.0, fav))
            pos["mae_pts"] = max(float(pos.get("mae_pts") or 0.0), max(0.0, adv))
            pos["peak_favorable_pts"] = max(
                float(pos.get("peak_favorable_pts") or 0.0), max(0.0, fav)
            )
            trade_row = next(
                (
                    t
                    for t in self._state.get("trades", [])
                    if t.get("id") == pos.get("trade_id")
                ),
                None,
            )
            if trade_row is not None:
                trade_row["mfe_pts"] = pos["mfe_pts"]
                trade_row["mae_pts"] = pos["mae_pts"]
                trade_row["peak_favorable_pts"] = pos["peak_favorable_pts"]
            target = float(pos["target"])
            qty = int(pos.get("qty", 1))
            pv = float(pos.get("point_value") or 5.0)
            trade = next(
                (t for t in self._state.get("trades", []) if t.get("id") == pos.get("trade_id")),
                None,
            )
            if self._apply_profit_protection(pos, trade, float(px), prot):
                dirty = True
            stop = float(pos["stop"])

            if pos.get("tp1") is not None:
                tp1 = float(pos["tp1"])
            elif trade and trade.get("tp1") is not None:
                tp1 = float(trade["tp1"])
            elif side == "BUY":
                tp1 = entry + (target - entry) * 0.5
            else:
                tp1 = entry - (entry - target) * 0.5

            reason = None
            # Stop / target first (full close)
            if side == "BUY":
                if px <= stop:
                    reason = "stop"
                elif px >= target:
                    reason = "target"
            else:
                if px >= stop:
                    reason = "stop"
                elif px <= target:
                    reason = "target"

            # Partial TP1: bank half, keep runner
            if (
                reason is None
                and scale_on
                and not pos.get("tp1_done")
                and qty >= 2
            ):
                hit_tp1 = (side == "BUY" and px >= tp1) or (side == "SELL" and px <= tp1)
                if hit_tp1:
                    close_qty = qty // 2
                    partial = self.take_partial(
                        pos["trade_id"],
                        exit_price=float(px),
                        close_qty=close_qty,
                        move_stop_to_be=move_be,
                    )
                    if partial:
                        closed.append(partial)
                    continue

            # Time stop: only cut losers by default — winners can run to target/trail.
            # Hold clock must use wall/received time, NOT market bar `opened_at`.
            # Yahoo delayed bars are wall-clock-past; treating them as UTC made
            # brand-new fills look like they already held 2–4h → instant time_stop.
            if reason is None and max_hold_minutes:
                opened = _parse_ts(
                    pos.get("received_at") or pos.get("ts") or pos.get("opened_at")
                )
                if opened:
                    held = (datetime.now(timezone.utc) - opened).total_seconds() / 60.0
                    if held >= max_hold_minutes:
                        u_pnl = _money(side, entry, float(px), qty, pv)
                        if (not time_stop_only_if_losing) or u_pnl < 0:
                            reason = "time_stop"
            if reason:
                t = self.close_trade(pos["trade_id"], exit_price=float(px), exit_reason=reason)
                if t:
                    closed.append(t)
        if dirty and not closed:
            self._save()
        return closed

    def recent_trades(self, limit: int = 50) -> list[dict[str, Any]]:
        return list(self._state.get("trades", [])[:limit])

    def open_positions(self) -> list[dict[str, Any]]:
        return list(self._state.get("open_positions", []))

    def realized_pnl(self) -> float:
        return float(self._state.get("realized_pnl", 0.0) or 0.0)

    def session_pnl(self) -> dict[str, dict[str, float | int]]:
        """Realized P&L and trade counts by session bucket (asia/london/ny/other)."""
        buckets = ("asia", "london", "ny", "other")
        out: dict[str, dict[str, float | int]] = {
            k: {"pnl": 0.0, "trades": 0, "wins": 0, "losses": 0} for k in buckets
        }
        for t in self._state.get("closed_trades", []):
            # Skip bookkeeping flat closes that aren't real strategy outcomes
            if str(t.get("exit_reason", "")) in {
                "universe_prune",
                "corr_conflict_prune",
            }:
                continue
            if str(t.get("source", "")) == "demo":
                continue
            raw = str(t.get("session") or "other").lower()
            if raw.startswith("asia"):
                key = "asia"
            elif raw.startswith("london"):
                key = "london"
            elif raw.startswith("ny"):
                key = "ny"
            else:
                key = "other"
            pnl = float(t.get("pnl_dollars") or 0.0)
            out[key]["pnl"] = float(out[key]["pnl"]) + pnl
            out[key]["trades"] = int(out[key]["trades"]) + 1
            if pnl > 0:
                out[key]["wins"] = int(out[key]["wins"]) + 1
            elif pnl < 0:
                out[key]["losses"] = int(out[key]["losses"]) + 1
        for k in out:
            out[k]["pnl"] = round(float(out[k]["pnl"]), 2)
        return out

    def daily_session_pnl(self) -> dict[str, dict[str, dict[str, float | int]]]:
        """Realized P&L segmented by calendar day (ET) and session.

        Returns: { '2026-08-06': { 'asia': {...}, 'london': {...}, 'ny': {...}, 'total': {...} } }
        """
        from zoneinfo import ZoneInfo

        et = ZoneInfo("America/New_York")
        days: dict[str, dict[str, dict[str, float | int]]] = {}

        def _bucket() -> dict[str, float | int]:
            return {"pnl": 0.0, "trades": 0, "wins": 0, "losses": 0}

        for t in self._state.get("closed_trades", []):
            if str(t.get("exit_reason", "")) in {
                "universe_prune",
                "corr_conflict_prune",
            }:
                continue
            if str(t.get("source", "")) == "demo":
                continue
            # Prefer market/opened time for strategy analysis on delayed feeds
            raw_ts = t.get("market_timestamp") or t.get("opened_at") or t.get("closed_at")
            dt = _parse_ts(str(raw_ts) if raw_ts else None)
            if dt is None:
                day = "unknown"
            else:
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                day = dt.astimezone(et).date().isoformat()
            raw = str(t.get("session") or "other").lower()
            if raw.startswith("asia"):
                sess = "asia"
            elif raw.startswith("london"):
                sess = "london"
            elif raw.startswith("ny"):
                sess = "ny"
            else:
                sess = "other"
            days.setdefault(
                day,
                {
                    "asia": _bucket(),
                    "london": _bucket(),
                    "ny": _bucket(),
                    "other": _bucket(),
                    "total": _bucket(),
                },
            )
            pnl = float(t.get("pnl_dollars") or 0.0)
            for key in (sess, "total"):
                days[day][key]["pnl"] = float(days[day][key]["pnl"]) + pnl
                days[day][key]["trades"] = int(days[day][key]["trades"]) + 1
                if pnl > 0:
                    days[day][key]["wins"] = int(days[day][key]["wins"]) + 1
                elif pnl < 0:
                    days[day][key]["losses"] = int(days[day][key]["losses"]) + 1
        for day in days:
            for k in days[day]:
                days[day][k]["pnl"] = round(float(days[day][k]["pnl"]), 2)
        return dict(sorted(days.items(), reverse=True))

    def open_risk_dollars(self) -> float:
        total = 0.0
        for p in self._state.get("open_positions", []):
            if p.get("risk_dollars") is not None:
                total += float(p["risk_dollars"])
                continue
            side = str(p.get("side", "BUY"))
            entry = float(p.get("entry") or 0)
            stop = float(p.get("stop") or 0)
            qty = int(p.get("qty") or 1)
            pv = float(p.get("point_value") or 5.0)
            total += abs(_money(side, entry, stop, qty, pv))
        return round(total, 2)

    def heartbeat(
        self,
        *,
        session: str,
        prices: dict[str, float],
        decision: str,
        signals_found: int = 0,
        agent_running: bool = True,
        engine_votes: dict[str, list[str]] | None = None,
        symbol_reports: dict[str, Any] | None = None,
        feed_meta: dict[str, Any] | None = None,
        candidates: list[dict[str, Any]] | None = None,
        last_evaluated_candidates: list[dict[str, Any]] | None = None,
    ) -> None:
        """Rewrite the HTML every cycle so the browser page proves the agent is alive."""
        now = datetime.now(timezone.utc).isoformat()
        fm = dict(feed_meta or {})
        if not fm.get("config_version"):
            try:
                from agent.config import load_settings

                root = self.json_path.resolve().parent.parent
                fm["config_version"] = load_settings(root / "config" / "settings.yaml").get(
                    "config_version"
                )
            except Exception:
                pass
        cands = list(candidates or [])
        last_cands = list(
            last_evaluated_candidates
            if last_evaluated_candidates is not None
            else (self._state.get("heartbeat") or {}).get("last_evaluated_candidates")
            or cands
        )
        # signals_found = executable A+/A count from caller.
        self._state["heartbeat"] = {
            "ts": now,
            "session": session,
            "prices": {k: round(float(v), 2) for k, v in prices.items()},
            "decision": decision,
            "status_detail": fm.get("status_detail"),
            "scan_state": fm.get("scan_state"),
            "signals_found": signals_found,
            "agent_running": agent_running,
            "open_count": len(self._state.get("open_positions", [])),
            "engine_votes": engine_votes or {},
            "symbol_reports": symbol_reports or {},
            "candidates": cands,
            "last_evaluated_candidates": last_cands,
            "feed_source": fm.get("source", "yahoo_delayed"),
            "is_realtime": bool(fm.get("is_realtime", False)),
            "estimated_delay_seconds": fm.get("estimated_delay_seconds"),
            "expected_delay_seconds": fm.get("expected_delay_seconds"),
            "stale_threshold_seconds": fm.get("stale_threshold_seconds"),
            "last_market_bar": fm.get("last_market_bar"),
            "last_evaluated_market_bar": fm.get("last_evaluated_market_bar"),
            "bar_interval": fm.get("bar_interval") or fm.get("bar_interval_label"),
            "bar_interval_seconds": fm.get("bar_interval_seconds"),
            "scheduler_interval_minutes": fm.get("scheduler_interval_minutes"),
            "last_fetch_attempt": fm.get("last_fetch_attempt"),
            "last_successful_fetch": fm.get("last_successful_fetch"),
            "execution_decisions": fm.get("execution_decisions") or [],
            "feed_meta": fm,
            "config_version": fm.get("config_version")
            or (self._state.get("heartbeat") or {}).get("config_version"),
        }
        hist = list(self._state.get("scan_history", []))
        hist.insert(
            0,
            {
                "ts": now,
                "session": session,
                "decision": decision,
                "signals_found": signals_found,
                "prices": {k: round(float(v), 2) for k, v in prices.items()},
                "votes": engine_votes or {},
                "symbol_reports": symbol_reports or {},
                "candidates": cands,
                "last_evaluated_candidates": last_cands,
                "feed": fm,
            },
        )
        self._state["scan_history"] = hist[:40]
        # Autonomous silence / blocker diagnostic (non-fatal)
        try:
            from agent.ops.trade_silence import run_trade_silence_watch
            from agent.config import load_settings

            root = self.json_path.resolve().parent.parent
            cfg = load_settings(root / "config" / "settings.yaml")
            report = run_trade_silence_watch(root, cfg)
            self._state["heartbeat"]["trade_silence"] = {
                "severity": report.severity,
                "summary": report.summary,
                "minutes_since_last_paper": report.minutes_since_last_paper,
                "blocker_codes": list(report.blocker_codes),
                "recommended_action": report.recommended_action,
                "shadow_open": report.shadow_open,
                "recent_rejects": report.recent_rejects,
                "top_reject_reasons": list(report.top_reject_reasons)[:5],
            }
        except Exception:
            pass
        self._save()

    def render_html(self) -> Path:
        trades = self._state.get("trades", [])
        opens = self._state.get("open_positions", [])
        closed = self._state.get("closed_trades", [])
        hb = self._state.get("heartbeat") or {}
        equity = float(self._state.get("starting_equity", self.starting_equity))
        realized = float(self._state.get("realized_pnl", 0.0))
        price_bits = ", ".join(
            f"{k} {v}" for k, v in list((hb.get("prices") or {}).items())[:8]
        ) or "waiting for first scan..."
        hb_ts = hb.get("ts") or "not yet — start the agent"
        decision = hb.get("decision") or "—"
        session = hb.get("session") or "—"
        sigs = hb.get("signals_found", "—")

        # Supervisor health (background always-on process)
        sup_note = ""
        hb_age = None
        try:
            if hb_ts and hb_ts != "not yet — start the agent":
                ht = datetime.fromisoformat(str(hb_ts).replace("Z", "+00:00"))
                if ht.tzinfo is None:
                    ht = ht.replace(tzinfo=timezone.utc)
                hb_age = (datetime.now(timezone.utc) - ht).total_seconds()
        except Exception:
            hb_age = None
        obs = {}
        try:
            from agent.config import load_settings

            obs = (load_settings().get("observability") or {})
        except Exception:
            obs = {}
        warn_s = float(obs.get("scheduler_warning_seconds", 90))
        stuck_s = float(obs.get("scheduler_stuck_seconds", 150))
        if hb_age is None:
            alive = "NO / STALE — click Start Trading Agent"
            agent_health = "UNKNOWN"
            run_banner_class = "unknown"
            run_banner_title = "NOT RUNNING"
            run_banner_plain = "No heartbeat yet. Start the Trading Agent to begin scanning."
            run_banner_sub = "If you already started it, wait ~1 minute for the first scan cycle."
        elif hb_age > stuck_s:
            mins = hb_age / 60.0
            hours = hb_age / 3600.0
            age_txt = f"{hours:.1f}h" if hours >= 2 else f"{mins:.0f}m"
            alive = f"STUCK — no scheduler heartbeat {hb_age:.0f}s ago"
            agent_health = "STUCK"
            run_banner_class = "bad"
            run_banner_title = "NOT ACTIVELY RUNNING (STUCK)"
            run_banner_plain = (
                f"Last scan heartbeat was {age_txt} ago. The agent is not ticking the 1-minute loop."
            )
            run_banner_sub = (
                "Supervisor may still show 'running' while recovering. Prefer Start Trading Agent / "
                "wait for auto-restart. Fresh heartbeat should land within ~1–2 minutes if healthy."
            )
        elif hb_age > warn_s:
            alive = f"DEGRADED — scheduler heartbeat {hb_age:.0f}s ago"
            agent_health = "DEGRADED"
            run_banner_class = "warn"
            run_banner_title = "RUNNING — SLOW / DEGRADED"
            run_banner_plain = (
                f"Heartbeat is {hb_age:.0f}s old (warn>{warn_s:.0f}s). Still alive, but lagging."
            )
            run_banner_sub = (
                "If this persists past ~2.5 minutes it becomes STUCK and the supervisor should restart."
            )
        else:
            alive = f"RUNNING — scheduler tick {hb_age:.0f}s ago"
            agent_health = "RUNNING"
            run_banner_class = "ok"
            run_banner_title = "ACTIVELY RUNNING"
            run_banner_plain = (
                f"Scan loop is live — last heartbeat {hb_age:.0f}s ago (expect refresh every ~60s)."
            )
            # Clarify idle-but-alive vs trading
            ss = str(hb.get("scan_state") or "")
            if "NO_NEW" in ss or "WAITING" in ss.upper():
                run_banner_sub = (
                    "Actively scanning, but no new completed market bar this tick "
                    "(normal between 5m bars). Not the same as stopped."
                )
            elif int(hb.get("signals_found") or 0) > 0:
                run_banner_sub = (
                    f"Actively scanning with {hb.get('signals_found')} executable setup(s) this cycle."
                )
            else:
                run_banner_sub = (
                    "Actively scanning. Zero executable setups this cycle is OK when quality gates pass nothing."
                )

        sup = {}
        try:
            cand = self.json_path.parent / "supervisor_status.json"
            if cand.exists():
                sup = json.loads(cand.read_text(encoding="utf-8"))
                st = sup.get("state", "?")
                expl = sup.get("last_exit_explain")
                rc = sup.get("restart_count", 0)
                rr = sup.get("restart_reason") or "—"
                lrt = sup.get("last_restart_timestamp") or "—"
                if expl:
                    sup_note = (
                        f"Supervisor: {st} · pid {sup.get('supervisor_pid', '?')} · "
                        f"agent_pid {sup.get('agent_pid', '?')} · restarts={rc} · "
                        f"last_restart={lrt} · reason={rr} · last exit: {expl}"
                    )
                else:
                    sup_note = (
                        f"Supervisor: {st} · pid {sup.get('supervisor_pid', '?')} · "
                        f"agent_pid {sup.get('agent_pid', '?')} · restarts={rc} · "
                        f"last_restart={lrt} · reason={rr}"
                    )
        except Exception:
            sup_note = ""

        silence_html = ""
        try:
            sil = hb.get("trade_silence") or {}
            if not sil:
                sil_path = self.json_path.parent / "trade_silence_status.json"
                if sil_path.exists():
                    sil = json.loads(sil_path.read_text(encoding="utf-8"))
            sev = str(sil.get("severity") or "OK").upper()
            blockers_list = [str(x) for x in (sil.get("blocker_codes") or [])]
            # Healthy selective quiet is informational only — do not scare with a banner
            # Suppress only non-fault states; PIPELINE_DROUGHT / CODE_BUG / etc. show
            actionable = [
                b
                for b in blockers_list
                if b
                not in {
                    "HEALTHY_SELECTIVE_QUIET",
                    "MARKET_CLOSED",
                    "STOP_AGENT_SET",
                }
            ]
            show = sev in {"WARN", "ALERT"} and bool(actionable) and bool(sil.get("summary"))
            if show:
                color = {
                    "ALERT": "#f07178",
                    "WARN": "#e6c07b",
                }.get(sev, "var(--muted)")
                blockers = ", ".join(blockers_list) or "—"
                tops = sil.get("top_reject_reasons") or []
                top_s = "; ".join(f"{a}×{b}" for a, b in tops[:4]) or "—"
                silence_html = (
                    f"<div class='meta' style='border:1px solid {color};padding:8px;margin-top:8px;'>"
                    f"<b style='color:{color}'>TRADE SILENCE [{sev}]</b> — "
                    f"{sil.get('summary')}<br/>"
                    f"mins_since_paper={sil.get('minutes_since_last_paper')} · "
                    f"blockers={blockers} · shadows_open={sil.get('shadow_open')} · "
                    f"recent_rejects={sil.get('recent_rejects')}<br/>"
                    f"top_rejects: {top_s}<br/>"
                    f"action: {sil.get('recommended_action') or '—'}"
                    f"</div>"
                )
        except Exception:
            silence_html = ""

        def rows_closed() -> str:
            if not closed:
                return "<tr><td colspan='10'>No closed trades yet — open trades hit stop/target over time.</td></tr>"
            out = []
            for t in closed[:100]:
                pnl = t.get("pnl_dollars")
                pnl_s = f"${pnl:.2f}" if isinstance(pnl, (int, float)) else ""
                out.append(
                    "<tr>"
                    f"<td>{t.get('opened_at','')}</td>"
                    f"<td>{t.get('closed_at','')}</td>"
                    f"<td>{t.get('hold_minutes','')}</td>"
                    f"<td>{t.get('session','')}</td>"
                    f"<td><b>{t.get('side','')}</b> {t.get('symbol','')}</td>"
                    f"<td>{t.get('entry','')}</td>"
                    f"<td>{t.get('exit','')}</td>"
                    f"<td>{pnl_s}</td>"
                    f"<td>{t.get('result','')} / {t.get('exit_reason','')}</td>"
                    f"<td>{t.get('id','')}</td>"
                    "</tr>"
                )
            return "\n".join(out)

        def rows_open() -> str:
            if not opens:
                return (
                    "<tr><td colspan='13'>Flat — no open paper positions.</td></tr>"
                )
            prices = hb.get("prices") or {}
            out = []
            for p in opens:
                side = str(p.get("side", "BUY"))
                entry = float(p.get("entry") or 0)
                stop = float(p.get("stop") or 0)
                target = float(p.get("target") or 0)
                qty = int(p.get("qty") or 1)
                pv = float(p.get("point_value") or (5.0 if p.get("symbol") == "MES" else 2.0))
                risk_d = p.get("risk_dollars")
                if risk_d is None:
                    risk_d = abs(_money(side, entry, stop, qty, pv))
                reward_d = p.get("reward_dollars")
                if reward_d is None:
                    reward_d = abs(_money(side, entry, target, qty, pv))
                mark = prices.get(str(p.get("symbol")))
                u_pnl = _money(side, entry, mark, qty, pv) if mark is not None else None
                u_cls = "up" if (u_pnl or 0) > 0 else ("down" if (u_pnl or 0) < 0 else "")
                tp1 = p.get("tp1")
                tp1_s = f"{tp1}" if tp1 is not None else "—"
                if p.get("tp1_done"):
                    tp1_s = f"{tp1_s} done"
                runner = f"{qty}/{p.get('qty_original', qty)}"
                out.append(
                    "<tr>"
                    f"<td>{p.get('opened_at')}</td>"
                    f"<td>{p.get('session')}</td>"
                    f"<td>{p.get('symbol')}</td>"
                    f"<td><b>{side}</b></td>"
                    f"<td>{runner}</td>"
                    f"<td>{entry}</td>"
                    f"<td>{mark if mark is not None else '—'}</td>"
                    f"<td>{stop}</td>"
                    f"<td>{tp1_s}</td>"
                    f"<td>{target}</td>"
                    f"<td>${float(risk_d):,.2f}</td>"
                    f"<td>${float(reward_d):,.2f}</td>"
                    f"<td class='{u_cls}'>{_fmt_money(u_pnl)}</td>"
                    "</tr>"
                )
            return "\n".join(out)

        # Unrealized total across opens (for account card)
        prices = hb.get("prices") or {}
        unrealized_total = 0.0
        risk_total = 0.0
        for p in opens:
            side = str(p.get("side", "BUY"))
            entry = float(p.get("entry") or 0)
            stop = float(p.get("stop") or 0)
            qty = int(p.get("qty") or 1)
            pv = float(p.get("point_value") or 5.0)
            risk_total += float(
                p.get("risk_dollars")
                if p.get("risk_dollars") is not None
                else abs(_money(side, entry, stop, qty, pv))
            )
            mark = prices.get(str(p.get("symbol")))
            if mark is not None:
                unrealized_total += _money(side, entry, mark, qty, pv)

        # --- Simple at-a-glance trading snapshot ---
        try:
            from zoneinfo import ZoneInfo

            et_now = datetime.now(ZoneInfo("America/New_York"))
        except Exception:
            et_now = datetime.now(timezone.utc)
        et_mins = et_now.hour * 60 + et_now.minute
        nq_window_open = (9 * 60 + 30) <= et_mins < (12 * 60)
        last_closed = None
        if closed:
            last_closed = max(
                closed,
                key=lambda t: str(t.get("closed_at") or t.get("ts") or ""),
            )
        last_fill_ts = str((last_closed or {}).get("closed_at") or "") if last_closed else ""
        last_fill_pnl = (last_closed or {}).get("pnl_dollars")
        last_fill_sym = (last_closed or {}).get("symbol")
        mins_since_fill = None
        if last_fill_ts:
            try:
                lft = datetime.fromisoformat(last_fill_ts.replace("Z", "+00:00"))
                if lft.tzinfo is None:
                    lft = lft.replace(tzinfo=timezone.utc)
                mins_since_fill = (datetime.now(timezone.utc) - lft).total_seconds() / 60.0
            except Exception:
                mins_since_fill = None
        n_open = len(opens)
        n_exec = int(hb.get("signals_found") or 0)
        if agent_health in {"STUCK", "UNKNOWN"}:
            trade_status = "NOT TRADING — agent not scanning"
            trade_plain = "Fix / restart the agent before expecting paper fills."
        elif n_open > 0:
            trade_status = f"PAPER TRADING — {n_open} open position(s)"
            trade_plain = "Managing open paper risk live (stops/targets)."
        elif n_exec > 0:
            trade_status = f"PAPER ENTRY SIGNAL — {n_exec} executable this scan"
            trade_plain = "A+/A setup(s) present this cycle; check Open positions."
        else:
            trade_status = "SCANNING — flat (no new paper fill this cycle)"
            if not nq_window_open:
                trade_plain = (
                    "Flat is normal outside NQ champion window (09:30–12:00 ET BUY-only). "
                    f"Clock now ~{et_now.strftime('%H:%M')} ET."
                )
            else:
                trade_plain = (
                    "Inside NQ window, but no A+/A paper setup cleared gates this tick "
                    "(selectivity — not the same as dead)."
                )
        last_fill_line = "No closed paper trades yet."
        if last_closed is not None:
            pnl_s = _fmt_money(float(last_fill_pnl or 0))
            age_s = (
                f"{mins_since_fill:.0f}m ago"
                if mins_since_fill is not None and mins_since_fill < 180
                else (
                    f"{(mins_since_fill or 0) / 60:.1f}h ago"
                    if mins_since_fill is not None
                    else last_fill_ts[:19]
                )
            )
            last_fill_line = f"Last fill: {last_fill_sym} {pnl_s} · {age_s}"
        glance_equity = equity + realized + unrealized_total
        tech_status_html = f"""
      <div class="eq">AGENT: {agent_health}</div>
      <div class="meta">{alive}</div>
      <div class="meta"><b>Config:</b> {hb.get('config_version') or '—'} · <b>Mode:</b> paper / Yahoo delayed</div>
      <div class="meta"><b>Primary:</b> {decision}</div>
      <div class="meta"><b>Detail:</b> {hb.get('status_detail') or '—'}</div>
      <div class="meta"><b>Scheduler:</b> interval={hb.get('scheduler_interval_minutes') or 1}m · last tick {hb_age if hb_age is not None else '—'}s ago · scan_state={hb.get('scan_state') or '—'}</div>
      <div class="meta"><b>Provider:</b> {hb.get('feed_source', 'yahoo_delayed')} · {'REALTIME' if hb.get('is_realtime') else 'DELAYED Yahoo'} · expected_delay≈{hb.get('expected_delay_seconds') or hb.get('estimated_delay_seconds') or 'n/a'}s · observed_delay≈{hb.get('estimated_delay_seconds') or 'n/a'}s · stale_threshold≈{hb.get('stale_threshold_seconds') or 'n/a'}s</div>
      <div class="meta">Last fetch attempt: {hb.get('last_fetch_attempt') or '—'} · Last successful fetch: {hb.get('last_successful_fetch') or '—'}</div>
      <div class="meta"><b>Bar interval (strategy):</b> {hb.get('bar_interval') or '5m'} ({hb.get('bar_interval_seconds') or 300}s) — NOT the same as scheduler 1m ticks</div>
      <div class="meta">Latest completed market bar: {hb.get('last_market_bar') or '—'} · Last evaluated bar: {hb.get('last_evaluated_market_bar') or hb.get('last_market_bar') or '—'}</div>
      <div class="meta"><b>Strategy:</b> session={session} · executable this scan={sigs} · current candidates={len(hb.get('candidates') or [])} · last-eval candidates={len(hb.get('last_evaluated_candidates') or [])}</div>
      <div class="meta">Prices: {price_bits}</div>
      <div class="meta">{sup_note or "Supervisor status: waiting for first background update"}</div>
      <div class="meta">Received/heartbeat time (UTC): {hb_ts}</div>
      {silence_html}
"""

        sess_pnl = self.session_pnl()
        daily_pnl = self.daily_session_pnl()
        scan_hist = list(self._state.get("scan_history", []))

        def _fmt_cand(c: dict[str, Any]) -> str:
            local = c.get("local_score", c.get("strategy_local_score"))
            glob = c.get("global_score")
            return (
                f"{c.get('symbol')} strategy={c.get('strategy')} "
                f"direction={c.get('direction')} "
                f"local_score={local} global_score={glob} tier={c.get('tier')}"
            )

        def rows_scan_tape() -> str:
            if not scan_hist:
                return "<tr><td colspan='8'>Waiting for first scan cycle…</td></tr>"
            bits = []
            for row in scan_hist[:15]:
                cands = row.get("candidates") or []
                if cands:
                    cand_s = " · ".join(_fmt_cand(c) for c in cands)
                else:
                    last_c = row.get("last_evaluated_candidates") or []
                    cand_s = (
                        "current: none | last_eval: "
                        + " · ".join(_fmt_cand(c) for c in last_c[:6])
                        if last_c
                        else "—"
                    )
                reports = row.get("symbol_reports") or {}
                if reports:
                    vote_parts = []
                    for sym, rep in list(reports.items())[:8]:
                        engines = rep.get("engines") or {}
                        eng_bits = []
                        for n, e in engines.items():
                            local = e.get("strategy_local_score", e.get("confidence"))
                            glob = e.get("global_score")
                            tier = e.get("tier") or e.get("result")
                            because = str(e.get("because") or "")
                            if " conf=" in because:
                                because = because.split(" conf=")[0]
                            bit = f"{n}={tier}"
                            if local is not None:
                                bit += f" local={local}"
                            if glob is not None:
                                bit += f" global={glob}"
                            if because:
                                bit += f" ({because[:48]})"
                            eng_bits.append(bit)
                        eng_s = ", ".join(eng_bits) or (rep.get("reason") or "—")
                        mt = rep.get("market_time") or rep.get("last_evaluated_market_bar") or "—"
                        vote_parts.append(f"{sym} [mkt {mt}] {eng_s}")
                    vote_s = " · ".join(vote_parts) or "—"
                else:
                    votes = row.get("votes") or {}
                    vote_s = "; ".join(
                        f"{sym}: {', '.join(v) if v else 'none'}"
                        for sym, v in list(votes.items())[:4]
                    ) or "—"
                px = row.get("prices") or {}
                px_s = ", ".join(f"{k} {v}" for k, v in list(px.items())[:4]) or "—"
                feed = row.get("feed") or {}
                delay = feed.get("estimated_delay_seconds")
                delay_s = f"~{float(delay)/60:.0f}m delayed" if delay else ("RT" if feed.get("is_realtime") else "DELAYED FEED")
                n_found = row.get("signals_found", 0)
                # Setups column = executable A+/A count; Candidates lists journaled too
                bits.append(
                    "<tr>"
                    f"<td>{row.get('ts','')}</td>"
                    f"<td>{delay_s}</td>"
                    f"<td>{row.get('session','')}</td>"
                    f"<td>{row.get('decision','')}</td>"
                    f"<td>{n_found}</td>"
                    f"<td>{cand_s}</td>"
                    f"<td>{vote_s}</td>"
                    f"<td>{px_s}</td>"
                    "</tr>"
                )
            return "\n".join(bits)

        def _sess_cls(v: float) -> str:
            return "up" if v > 0 else ("down" if v < 0 else "")

        def rows_session_pnl() -> str:
            labels = [
                ("asia", "Asia (≈6pm–3am ET)"),
                ("london", "London (≈3am–9:30am ET)"),
                ("ny", "New York (≈9:30am–5pm ET)"),
                ("other", "Other / unknown"),
            ]
            bits = []
            for key, label in labels:
                row = sess_pnl.get(key) or {"pnl": 0.0, "trades": 0, "wins": 0, "losses": 0}
                pnl = float(row["pnl"])
                bits.append(
                    "<tr>"
                    f"<td>{label}</td>"
                    f"<td class='{_sess_cls(pnl)}'>{_fmt_money(pnl)}</td>"
                    f"<td>{int(row['trades'])}</td>"
                    f"<td>{int(row['wins'])}</td>"
                    f"<td>{int(row['losses'])}</td>"
                    "</tr>"
                )
            return "\n".join(bits)

        def rows_daily_pnl() -> str:
            if not daily_pnl:
                return "<tr><td colspan='7'>No closed trades yet.</td></tr>"
            bits = []
            for day, buckets in list(daily_pnl.items())[:21]:
                tot = buckets.get("total") or {"pnl": 0, "trades": 0, "wins": 0, "losses": 0}
                bits.append(
                    "<tr>"
                    f"<td><b>{day}</b></td>"
                    f"<td class='{_sess_cls(float(tot['pnl']))}'>{_fmt_money(float(tot['pnl']))}</td>"
                    f"<td>{_fmt_money(float((buckets.get('asia') or {}).get('pnl', 0)))}</td>"
                    f"<td>{_fmt_money(float((buckets.get('london') or {}).get('pnl', 0)))}</td>"
                    f"<td>{_fmt_money(float((buckets.get('ny') or {}).get('pnl', 0)))}</td>"
                    f"<td>{int(tot['trades'])}</td>"
                    f"<td>{int(tot['wins'])}W / {int(tot['losses'])}L</td>"
                    "</tr>"
                )
            return "\n".join(bits)

        def _dir_label(v: int) -> str:
            return "bull" if int(v or 0) > 0 else ("bear" if int(v or 0) < 0 else "flat")

        def why_selected_html() -> str:
            """Compact learning explanation for latest executed / rejected candidates."""
            try:
                from agent.learning.features import top_traits_from_features
            except Exception:
                top_traits_from_features = None  # type: ignore
            cands = hb.get("candidates") or hb.get("last_evaluated_candidates") or []
            if not cands and scan_hist:
                cands = (scan_hist[0] or {}).get("last_evaluated_candidates") or []
            if not cands:
                # Fall back to latest open position metadata
                if opens:
                    o = opens[0]
                    return (
                        f"<b>{o.get('symbol')} {o.get('side')}</b> · "
                        f"strategy={o.get('strategy_name') or o.get('strategy') or '—'} · "
                        f"tier={o.get('setup_tier') or '—'} · "
                        f"Waiting for next scored candidates to show router evidence."
                    )
                return "No candidate explanations yet — waiting for next scored bar."
            # Prefer executable-looking tiers first
            ordered = sorted(
                cands,
                key=lambda c: {"A+": 0, "A": 1, "B": 2}.get(str(c.get("tier") or ""), 9),
            )
            bits = []
            for c in ordered[:5]:
                ev = c.get("router_evidence") or {}
                feats = c.get("entry_features") or {}
                qp = c.get("quality_predictions") or {}
                hc = c.get("high_confidence_shadow") or {}
                pos, neg = ([], [])
                if top_traits_from_features is not None and feats:
                    pos, neg = top_traits_from_features(feats)
                reason = c.get("nonselected_reason") or ""
                decision = "SELECTED" if str(c.get("tier") or "") in {"A", "A+"} and not reason else (
                    reason or f"tier={c.get('tier')}"
                )
                bits.append(
                    "<div style='margin:8px 0;padding:8px 0;border-bottom:1px solid #333'>"
                    f"<b>{c.get('symbol')} {c.get('direction')}</b> · {c.get('strategy')} · "
                    f"tier={c.get('tier')} · global={c.get('global_score')}<br/>"
                    f"empirical WR={ev.get('shrunk_win_rate', ev.get('win_rate', '—'))} · "
                    f"raw={ev.get('raw_win_rate', '—')} · "
                    f"model p={ev.get('model_probability', qp.get('p_win', '—'))} · "
                    f"P(1R)={qp.get('p_1r', '—')} · E={ev.get('expectancy_r', qp.get('expected_r', '—'))} · "
                    f"PF={ev.get('profit_factor', '—')} · "
                    f"n={ev.get('sample_count', '—')} · level={ev.get('evidence_level', '—')}<br/>"
                    f"<span style='color:#8f8'>TOP+: {', '.join(pos) or '—'}</span> · "
                    f"<span style='color:#f88'>TOP-: {', '.join(neg) or '—'}</span><br/>"
                    f"Router_v1: {c.get('router_v1_decision') or decision} · "
                    f"High-confidence shadow: {hc.get('decision') or '—'} "
                    f"({hc.get('reason') or ''})"
                    "</div>"
                )
            return "\n".join(bits) if bits else "—"

        def adaptive_learning_status_html() -> str:
            """ADAPTIVE LEARNING STATUS panel."""
            bits = []
            try:
                from pathlib import Path as _P
                import json as _json

                root = _P(__file__).resolve().parents[3]
                deploy = root / "data" / "trade_quality_learning" / "DEPLOY_ROUTER_V2.json"
                champ = root / "data" / "learning" / "models" / "trade_quality_champion.json"
                chall = root / "data" / "learning" / "models" / "trade_quality_challenger.json"
                store = root / "data" / "learning" / "candidates.jsonl"
                prio = root / "data" / "cl_priority_learning" / "PRIORITY_CELL.json"
                n_store = sum(1 for _ in open(store, encoding="utf-8")) if store.exists() else 0
                bits.append(
                    f"<div class='meta'><b>Learning store size:</b> {n_store} candidates · "
                    f"execution_profile=balanced · router_v2 paper deploy="
                    f"{_json.loads(deploy.read_text(encoding='utf-8')).get('deploy') if deploy.exists() else False}"
                    "</div>"
                )
                if champ.exists():
                    cj = _json.loads(champ.read_text(encoding="utf-8"))
                    bits.append(
                        f"<div class='meta'><b>Champion:</b> {cj.get('version')} · "
                        f"kind={cj.get('kind')} · calibrated={cj.get('calibrated')} · "
                        f"brier={cj.get('brier_score')}</div>"
                    )
                if chall.exists():
                    cj = _json.loads(chall.read_text(encoding="utf-8"))
                    bits.append(
                        f"<div class='meta'><b>Challenger:</b> {cj.get('version')} · "
                        f"kind={cj.get('kind')} · calibrated={cj.get('calibrated')}</div>"
                    )
                if prio.exists():
                    pj = _json.loads(prio.read_text(encoding="utf-8"))
                    bits.append(
                        f"<div class='meta'><b>Priority learning cell:</b> {pj.get('cell')} · "
                        f"{pj.get('mode')} (no global promotion)</div>"
                    )
            except Exception as exc:
                bits.append(f"<div class='meta'>Adaptive status unavailable: {exc}</div>")
            # Latest candidate adaptive card
            bits.append("<div class='meta' style='margin-top:8px'>" + why_selected_html() + "</div>")
            return "\n".join(bits)

        def cl_winner_why_html() -> str:
            """WHY THE RECENT CL WINNER WON — anecdotal vs statistical."""
            try:
                from pathlib import Path as _P
                import json as _json

                path = _P(__file__).resolve().parents[3] / "data" / "cl_priority_learning" / "CL_PRIORITY_LEARNING_REPORT.json"
                if not path.exists():
                    return (
                        "No CL priority report yet. Run "
                        "<code>python scripts/run_cl_priority_learning_pass.py</code>."
                    )
                rep = _json.loads(path.read_text(encoding="utf-8"))
                w = rep.get("recent_cl_paper_winner") or {}
                snap = w.get("snapshot") or {}
                bits = [
                    f"<div class='meta' style='color:#fc6'><b>Warning:</b> {w.get('warning')}</div>",
                    f"<div class='meta'><b>{w.get('trade_id')}</b> · {snap.get('strategy')} · "
                    f"{snap.get('direction')} · session={snap.get('session')} · "
                    f"tier={snap.get('tier')} · global={snap.get('global_score')} · "
                    f"pnl=${snap.get('pnl_dollars')} · R={snap.get('realized_r')}</div>",
                    f"<div class='meta'>MTF 15m/1h/4h={snap.get('dir_15m')}/"
                    f"{snap.get('dir_1h')}/{snap.get('dir_4h')} aligned={snap.get('mtf_aligned')} · "
                    f"VWAP above={snap.get('above_vwap')} · agreeing={snap.get('agreeing_engines')}</div>",
                    "<div class='meta'><b>Anecdotal (single trade — not filters):</b></div>",
                ]
                for a in (w.get("anecdotal_traits") or [])[:12]:
                    bits.append(f"<div class='meta'>· {a}</div>")
                bits.append("<div class='meta'><b>Statistical candidates (CL LR hist win vs loss):</b></div>")
                useful = w.get("statistically_useful_traits") or []
                if not useful:
                    bits.append("<div class='meta'>· none with |delta|≥10pp yet</div>")
                for u in useful[:12]:
                    bits.append(
                        f"<div class='meta'>· {u.get('trait')}: W={u.get('winners')} "
                        f"L={u.get('losers')} Δ={u.get('delta')}</div>"
                    )
                hist = rep.get("cl_liquidity_reversal_historical") or {}
                ov = hist.get("overall") or {}
                bits.append(
                    f"<div class='meta'><b>CL LR historical overall:</b> n={ov.get('n')} "
                    f"WR={ov.get('wr')} shrunk={ov.get('shrunk_wr')} PF={ov.get('pf')} "
                    f"E={ov.get('expectancy_r')} (ref OOS WR≈49.1%)</div>"
                )
                return "\n".join(bits)
            except Exception as exc:
                return f"CL winner section error: {exc}"

        def rows_regime_context() -> str:
            reports = hb.get("symbol_reports") or {}
            if not reports:
                return "<tr><td colspan='9'>Waiting for scan with regime context…</td></tr>"
            bits = []
            for sym, rep in list(reports.items())[:12]:
                rg = rep.get("regime") or {}
                mc = rep.get("market_context") or {}
                vwap = "above" if mc.get("above_vwap") else ("below" if mc.get("below_vwap") else "—")
                ema = "bull" if mc.get("ema_bull") else ("bear" if mc.get("ema_bear") else "—")
                ox = "Y" if (mc.get("overextended_long") or mc.get("overextended_short")) else "N"
                age = rep.get("context_age_minutes")
                age_s = f"{age}m" if age is not None else "0m"
                last_bar = rep.get("last_evaluated_market_bar") or rep.get("market_time") or "—"
                bits.append(
                    "<tr>"
                    f"<td>{sym}</td>"
                    f"<td>{rg.get('regime', '—')}</td>"
                    f"<td>{rg.get('confidence', '—')}</td>"
                    f"<td>{_dir_label(mc.get('direction_15m', 0))}</td>"
                    f"<td>{_dir_label(mc.get('direction_1h', 0))}</td>"
                    f"<td>{_dir_label(mc.get('direction_4h', 0))}</td>"
                    f"<td>{vwap}</td>"
                    f"<td>{ema}</td>"
                    f"<td>{ox} · bar {last_bar} · age {age_s}</td>"
                    "</tr>"
                )
            return "\n".join(bits) or "<tr><td colspan='9'>—</td></tr>"

        def rows_candidate_table(cands: list[dict[str, Any]], empty_msg: str) -> str:
            if not cands:
                return f"<tr><td colspan='10'>{empty_msg}</td></tr>"
            bits = []
            for c in cands[:20]:
                br = str(c.get("score_breakdown") or "").replace("\n", "<br/>")
                local = c.get("local_score", c.get("strategy_local_score"))
                bits.append(
                    "<tr>"
                    f"<td>{c.get('symbol')}</td>"
                    f"<td>{c.get('strategy')}</td>"
                    f"<td>{c.get('direction')}</td>"
                    f"<td>{local}</td>"
                    f"<td>{c.get('global_score')}</td>"
                    f"<td>{c.get('tier')}</td>"
                    f"<td>{c.get('regime')}</td>"
                    f"<td>{c.get('setup_id') or '—'}</td>"
                    f"<td>{c.get('market_timestamp')}</td>"
                    f"<td style='font-size:0.75rem'>{br}</td>"
                    "</tr>"
                )
            return "\n".join(bits)

        def rows_global_candidates() -> str:
            cands = hb.get("candidates") or []
            if not cands and scan_hist:
                cands = (scan_hist[0] or {}).get("candidates") or []
            return rows_candidate_table(
                cands, "No candidates on CURRENT scheduler scan (often NO_NEW_BAR)."
            )

        def rows_last_eval_candidates() -> str:
            cands = hb.get("last_evaluated_candidates") or []
            if not cands and scan_hist:
                cands = (scan_hist[0] or {}).get("last_evaluated_candidates") or []
            return rows_candidate_table(
                cands, "No last-evaluated candidates yet."
            )

        def rows_config_version() -> str:
            try:
                from agent.journal.filter_calibration import performance_by_config_version

                rows = performance_by_config_version(list(closed)[:800])
                if not rows:
                    return "<tr><td colspan='6'>No closed actual trades yet.</td></tr>"
                bits = []
                for r in rows:
                    bits.append(
                        "<tr>"
                        f"<td>{r.get('config_version')}</td>"
                        f"<td>{r.get('count')}</td>"
                        f"<td>{_fmt_money(float(r.get('net_pnl') or 0))}</td>"
                        f"<td>{r.get('profit_factor')}</td>"
                        f"<td>{_fmt_money(float(r.get('expectancy') or 0))}</td>"
                        f"<td>{r.get('win_rate')}</td>"
                        "</tr>"
                    )
                return "\n".join(bits)
            except Exception as exc:
                return f"<tr><td colspan='6'>n/a ({exc})</td></tr>"

        def filter_calibration_html() -> str:
            try:
                from agent.journal.filter_calibration import build_filter_calibration
                from agent.journal.shadow import ShadowTracker

                shadow = ShadowTracker().all_closed()
                cal = build_filter_calibration(
                    actual_trades=list(closed),
                    shadow_trades=shadow,
                    min_b_sample=30,
                )
                b = cal["B_shadow"]
                a = cal["A_actual"]
                ap = cal["A_PLUS_actual"]
                return (
                    f"A+ actual: n={ap['count']} PF={ap['profit_factor']} "
                    f"E={_fmt_money(ap['expectancy'])} WR={ap['win_rate']} · "
                    f"A actual: n={a['count']} PF={a['profit_factor']} "
                    f"E={_fmt_money(a['expectancy'])} WR={a['win_rate']} · "
                    f"B shadow: n={b['count']} PF={b['profit_factor']} "
                    f"E={_fmt_money(b['expectancy'])} WR={b['win_rate']} · "
                    f"<b>FILTER ASSESSMENT: {cal['FILTER_ASSESSMENT']}</b> — {cal['note']}"
                )
            except Exception as exc:
                return f"Filter calibration n/a ({exc})"

        def shadow_summary_html() -> str:
            try:
                from agent.journal.shadow import ShadowTracker

                s = ShadowTracker().summary()
                return (
                    f"SHADOW B: closed={s.get('count')} open={s.get('open')} "
                    f"hyp_pnl={_fmt_money(float(s.get('hypothetical_pnl') or 0))} "
                    f"WR={s.get('win_rate')} (not mixed into paper equity)"
                )
            except Exception as exc:
                return f"SHADOW B: n/a ({exc})"

        def rows_execution_decisions() -> str:
            try:
                from agent.decision.execution_decisions import ExecutionDecisionLedger

                rows = ExecutionDecisionLedger().latest(30)
                # Prefer heartbeat-attached decisions when fresher
                hb_rows = (hb.get("feed_meta") or {}).get("execution_decisions") or hb.get(
                    "execution_decisions"
                )
                if hb_rows:
                    rows = list(hb_rows)[:30]
                if not rows:
                    return (
                        "<tr><td colspan='9'>No A/A+ execution decisions yet "
                        "(weekend gap or no executable candidates).</td></tr>"
                    )
                bits = []
                for r in rows:
                    dec = str(r.get("decision") or "")
                    reason = str(r.get("reason") or "")
                    if dec == "EXECUTED":
                        detail = f"EXECUTED · paper order {r.get('order_id') or '—'}"
                    else:
                        detail = f"REJECTED — {reason}"
                    bits.append(
                        "<tr>"
                        f"<td>{r.get('symbol')}</td>"
                        f"<td>{r.get('strategy')}</td>"
                        f"<td>{r.get('direction')}</td>"
                        f"<td>{r.get('local_score')}</td>"
                        f"<td>{r.get('global_score')}</td>"
                        f"<td>{r.get('tier')}</td>"
                        f"<td>{r.get('setup_id') or '—'}</td>"
                        f"<td>{r.get('market_timestamp')}</td>"
                        f"<td><b>{detail}</b></td>"
                        "</tr>"
                    )
                return "\n".join(bits)
            except Exception as exc:
                return f"<tr><td colspan='9'>n/a ({exc})</td></tr>"

        def opportunity_rate_html() -> str:
            try:
                from agent.research.opportunity_stats import OpportunityStatsStore

                s = OpportunityStatsStore().summary()
                flag = s.get("frequency_flag") or "none"
                return (
                    f"ACTIVE MARKET OPPORTUNITY RATE (weekend/maintenance excluded) · "
                    f"bars={s.get('market_bars_processed')} · "
                    f"candidates={s.get('strategy_candidates')} · "
                    f"A+={s.get('A+')} A={s.get('A')} B={s.get('B')} C={s.get('C')} · "
                    f"executions={s.get('actual_executions')} · "
                    f"cands/100bars={s.get('candidates_per_100_bars')} · "
                    f"A+/A per100={s.get('a_or_better_per_100_bars')} · "
                    f"exec/100bars={s.get('executions_per_100_bars')} · "
                    f"flag={flag}"
                )
            except Exception as exc:
                return f"Opportunity rate n/a ({exc})"

        def current_config_perf_html() -> str:
            try:
                from agent.journal.current_config_perf import (
                    current_config_actual_performance,
                )
                from agent.journal.shadow import ShadowTracker

                cur = current_config_actual_performance(
                    list(closed), ShadowTracker().all_closed()
                )
                ap, a, b = cur["A_PLUS_actual"], cur["A_actual"], cur["B_shadow"]
                return (
                    f"CURRENT CONFIG ACTUAL PERFORMANCE (opt_v1+) · "
                    f"A+ n={ap['count']} PF={ap['profit_factor']} "
                    f"E={_fmt_money(ap['expectancy'])} · "
                    f"A n={a['count']} PF={a['profit_factor']} "
                    f"E={_fmt_money(a['expectancy'])} · "
                    f"B shadow n={b['count']} PF={b['profit_factor']} "
                    f"E={_fmt_money(b['expectancy'])} WR={b['win_rate']} · "
                    f"ALL-TIME PAPER HISTORY remains in Closed trades / config table"
                )
            except Exception as exc:
                return f"Current config perf n/a ({exc})"

        def engine_audit_html() -> str:
            try:
                from agent.research.engine_audit import (
                    audit_from_last_evaluation,
                    quiet_engine_notes,
                )

                audit = audit_from_last_evaluation()
                notes = quiet_engine_notes(audit)
                bits = []
                for name, e in (audit.get("engines") or {}).items():
                    top = (e.get("top_rejection_reasons") or [{}])[0]
                    bits.append(
                        f"{name}: signals={e.get('signals')} none={e.get('none')} "
                        f"tiers={e.get('tier_counts')} top_reject={top.get('reason')}"
                    )
                body = " · ".join(bits) if bits else "no engine audit yet"
                quiet = (" | QUIET: " + "; ".join(notes)) if notes else ""
                return body + quiet
            except Exception as exc:
                return f"Engine audit n/a ({exc})"

        def cl_specialist_forward_html() -> str:
            """Forward-only CL specialist stats — never mixed with historical benchmark."""
            try:
                from agent.risk.strategy_lifecycle import StrategyLifecycleStore

                book = StrategyLifecycleStore("data/strategy_lifecycle.json").get_cell(
                    "cl_vwap_prox_momentum", "CL_BOOK"
                )
                closed = [
                    t
                    for t in (self._state.get("closed") or [])
                    if str(t.get("strategy_name") or "") == "cl_vwap_prox_momentum"
                    and not bool(t.get("e2e_test"))
                ]
                open_n = sum(
                    1
                    for t in (self._state.get("open") or [])
                    if str(t.get("strategy_name") or "") == "cl_vwap_prox_momentum"
                )
                rs = []
                for t in closed:
                    risk = float(t.get("risk_dollars") or 0)
                    pnl = float(t.get("pnl_dollars") or 0)
                    if risk > 1e-9:
                        rs.append(pnl / risk)
                wins = [r for r in rs if r > 0]
                losses = [r for r in rs if r < 0]
                n = len(rs)
                wr = (len(wins) / n) if n else None
                pf = (sum(wins) / abs(sum(losses))) if losses and sum(losses) != 0 else (999.0 if wins else None)
                e = (sum(rs) / n) if n else None
                avg_w = (sum(wins) / len(wins)) if wins else None
                avg_l = (sum(losses) / len(losses)) if losses else None
                eq = 0.0
                peak = 0.0
                max_dd = 0.0
                for r in rs:
                    eq += r
                    peak = max(peak, eq)
                    max_dd = min(max_dd, eq - peak)
                state = book.state
                return f"""
          <div class="meta"><b>Strategy:</b> cl_vwap_prox_momentum_v1 · <b>Config:</b> router_v1_clpaper1</div>
          <div class="meta"><b>State:</b> {state} · open={open_n} · forward closed={n}</div>
          <table>
            <thead><tr><th>Metric</th><th>Forward</th><th>Historical benchmark (research)</th></tr></thead>
            <tbody>
              <tr><td>Trades</td><td>{n}</td><td>121</td></tr>
              <tr><td>Wins / Losses</td><td>{len(wins)} / {len(losses)}</td><td>—</td></tr>
              <tr><td>WR</td><td>{(f'{wr*100:.1f}%' if wr is not None else '—')}</td><td>69.4%</td></tr>
              <tr><td>PF</td><td>{(f'{pf:.2f}' if pf is not None else '—')}</td><td>4.54</td></tr>
              <tr><td>E[R]</td><td>{(f'{e:+.3f}' if e is not None else '—')}</td><td>+1.08R</td></tr>
              <tr><td>Cumulative R</td><td>{eq:+.2f}</td><td>—</td></tr>
              <tr><td>Peak R</td><td>{peak:+.2f}</td><td>—</td></tr>
              <tr><td>DD from peak R</td><td>{(eq-peak):+.2f}</td><td>—</td></tr>
              <tr><td>Max DD R</td><td>{max_dd:.2f}</td><td>-5.0R</td></tr>
              <tr><td>Avg winner R</td><td>{(f'{avg_w:+.2f}' if avg_w is not None else '—')}</td><td>—</td></tr>
              <tr><td>Avg loser R</td><td>{(f'{avg_l:+.2f}' if avg_l is not None else '—')}</td><td>—</td></tr>
            </tbody>
          </table>
          <div class="meta">Lifecycle book: equity={book.equity_r:+.2f}R peak={book.equity_peak_r:+.2f}R dd={book.dd_from_peak_r:.2f}R · WATCH={book.watch_dd_r} SHADOW={book.shadow_dd_r} HARD={book.hard_kill_r}</div>
          <div class="meta">Do not mix historical benchmark with forward results. Do not tweak v1 during initial forward sample.</div>
                """
            except Exception as exc:
                return f"<div class='meta'>CL SPECIALIST section error: {exc}</div>"

        def strategy_lifecycle_table_html() -> str:
            try:
                from agent.risk.strategy_lifecycle import StrategyLifecycleStore

                path = "data/strategy_lifecycle.json"
                rows = StrategyLifecycleStore(path).snapshot()
                if not rows:
                    return "<div class='meta'>STRATEGY HEALTH: no lifecycle cells seeded yet.</div>"
                body = []
                for r in sorted(rows, key=lambda x: (x.get("strategy") or "", x.get("symbol") or "")):
                    body.append(
                        "<tr>"
                        f"<td>{r.get('strategy')}</td>"
                        f"<td>{r.get('symbol')}</td>"
                        f"<td>{r.get('state')}</td>"
                        f"<td>{r.get('forward_trades')}</td>"
                        f"<td>{_fmt_pct(r.get('rolling_wr'))}</td>"
                        f"<td>{_fmt_pct(r.get('expected_wr'))}</td>"
                        f"<td>{_fmt_num(r.get('rolling_e'))}</td>"
                        f"<td>{_fmt_num(r.get('expected_e'))}</td>"
                        f"<td>{_fmt_num(r.get('rolling_pf'))}</td>"
                        f"<td>{_fmt_num(r.get('equity_r'))}</td>"
                        f"<td>{_fmt_num(r.get('equity_peak_r'))}</td>"
                        f"<td>{_fmt_num(r.get('dd_from_peak_r'))}</td>"
                        f"<td>{_fmt_num(r.get('trailing_stop_r'))}</td>"
                        f"<td>{_fmt_num(r.get('hard_kill_r'))}</td>"
                        f"<td>{'Y' if r.get('drift_flag') else ''}</td>"
                        f"<td>{r.get('notes') or ''}</td>"
                        "</tr>"
                    )
                return (
                    "<table><thead><tr>"
                    "<th>Strategy</th><th>Symbol</th><th>State</th><th>Fwd n</th>"
                    "<th>Roll WR</th><th>Exp WR</th><th>Roll E</th><th>Exp E</th><th>PF</th>"
                    "<th>Eq R</th><th>Peak R</th><th>DD R</th><th>Trail thr</th><th>Hard kill</th>"
                    "<th>Drift</th><th>Notes</th>"
                    "</tr></thead><tbody>"
                    + "".join(body)
                    + "</tbody></table>"
                )
            except Exception as exc:
                return f"<div class='meta'>STRATEGY HEALTH error: {exc}</div>"

        def _fmt_pct(v):
            if v is None:
                return ""
            try:
                return f"{float(v)*100:.1f}%"
            except Exception:
                return ""

        def _fmt_num(v):
            if v is None:
                return ""
            try:
                return f"{float(v):.2f}"
            except Exception:
                return ""

        def circuit_summary_html() -> str:
            try:
                from agent.risk.circuit_breakers import CircuitBreakerStore

                rows = CircuitBreakerStore().snapshot()
                if not rows:
                    return "Strategy health: all ACTIVE (no pauses)"
                return "Strategy health: " + "; ".join(
                    f"{r['strategy']}/{r['session']}={r['state']} streak={r.get('loss_streak',0)}"
                    for r in rows[:12]
                )
            except Exception as exc:
                return f"Strategy health: n/a ({exc})"

        def rows_perf_regime() -> str:
            try:
                from agent.journal.performance_matrix import build_performance_matrix

                rows = build_performance_matrix(list(closed)[:500])
                if not rows:
                    return (
                        "<tr><td colspan='8'>No closed trades with regime tags yet "
                        "(pre-opt_v1 rows show UNKNOWN).</td></tr>"
                    )
                bits = []
                for r in rows[:24]:
                    bits.append(
                        "<tr>"
                        f"<td>{r.get('strategy')}</td>"
                        f"<td>{r.get('regime')}</td>"
                        f"<td>{r.get('session')}</td>"
                        f"<td>{r.get('trade_count')}</td>"
                        f"<td>{r.get('profit_factor')}</td>"
                        f"<td>{_fmt_money(float(r.get('expectancy') or 0))}</td>"
                        f"<td>{r.get('win_rate')}</td>"
                        f"<td>{r.get('average_r')}</td>"
                        "</tr>"
                    )
                return "\n".join(bits)
            except Exception as exc:
                return f"<tr><td colspan='8'>n/a ({exc})</td></tr>"

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta http-equiv="refresh" content="15"/>
  <title>Agent Paper Trading View</title>
  <style>
    :root {{
      --bg: #0f1419; --panel: #1a2332; --text: #e7ecf3; --muted: #8b9bb4; --line: #2a3548;
    }}
    body {{
      margin: 0; font-family: "Segoe UI", system-ui, sans-serif;
      background: radial-gradient(1200px 600px at 10% -10%, #1c3a5f 0%, var(--bg) 55%);
      color: var(--text); min-height: 100vh;
    }}
    header {{ padding: 28px 32px 8px; border-bottom: 1px solid var(--line); }}
    header h1 {{ margin: 0 0 6px; font-size: 1.6rem; }}
    header p {{ margin: 0; color: var(--muted); max-width: 820px; line-height: 1.45; }}
    .grid {{ display: grid; gap: 18px; padding: 18px 32px 40px; }}
    .card {{
      background: var(--panel); border: 1px solid var(--line); border-radius: 10px;
      padding: 16px 18px;
    }}
    h2 {{ margin: 0 0 12px; font-size: 1.05rem; color: #c9d4e5; }}
    details.fold {{ margin: 0; }}
    details.fold > summary {{
      list-style: none; cursor: pointer; user-select: none;
      display: flex; align-items: center; gap: 10px;
      margin: 0 0 0; font-size: 1.05rem; color: #c9d4e5; font-weight: 600;
    }}
    details.fold > summary::-webkit-details-marker {{ display: none; }}
    details.fold > summary::before {{
      content: "▸"; color: var(--muted); font-size: 0.95rem; width: 1em;
      transition: transform 0.12s ease;
    }}
    details.fold[open] > summary {{ margin-bottom: 12px; }}
    details.fold[open] > summary::before {{ content: "▾"; }}
    details.fold > summary .hint {{
      margin-left: auto; color: var(--muted); font-size: 0.75rem; font-weight: 500;
    }}
    .fold-body {{ overflow-x: auto; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 0.88rem; }}
    th, td {{ text-align: left; padding: 8px 8px; border-bottom: 1px solid var(--line); vertical-align: top; }}
    th {{ color: var(--muted); font-weight: 600; font-size: 0.75rem; text-transform: uppercase; }}
    .meta {{ color: var(--muted); font-size: 0.85rem; margin-top: 10px; }}
    .eq {{ font-size: 1.35rem; font-weight: 700; }}
    .up {{ color: #3dd68c; font-weight: 600; }}
    .down {{ color: #f07178; font-weight: 600; }}
    .run-banner {{
      margin: 0 0 14px; padding: 14px 16px; border-radius: 8px;
      border: 2px solid var(--line); background: #121926;
    }}
    .run-banner .title {{
      font-size: 1.55rem; font-weight: 800; letter-spacing: 0.02em; margin: 0 0 6px;
    }}
    .run-banner .plain {{
      font-size: 0.95rem; color: var(--text); margin: 0 0 4px; line-height: 1.4;
    }}
    .run-banner .sub {{
      font-size: 0.82rem; color: var(--muted); margin: 0; line-height: 1.4;
    }}
    .run-banner.ok {{ border-color: #3dd68c; background: #10261c; }}
    .run-banner.ok .title {{ color: #3dd68c; }}
    .run-banner.warn {{ border-color: #e6b450; background: #2a2110; }}
    .run-banner.warn .title {{ color: #e6b450; }}
    .run-banner.bad {{ border-color: #f07178; background: #2a1418; }}
    .run-banner.bad .title {{ color: #f07178; }}
    .run-banner.unknown {{ border-color: #8b9bb4; background: #161b24; }}
    .run-banner.unknown .title {{ color: #c9d4e5; }}
    .glance-grid {{
      display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
      gap: 10px; margin-top: 12px;
    }}
    .glance-cell {{
      background: #121926; border: 1px solid var(--line); border-radius: 8px; padding: 10px 12px;
    }}
    .glance-cell .lbl {{ color: var(--muted); font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.04em; }}
    .glance-cell .val {{ font-size: 1.05rem; font-weight: 700; margin-top: 4px; }}
  </style>
</head>
<body>
  <header>
    <h1>Agent Paper Trading View</h1>
    <p>Local paper blotter (not TradingView.com). Reloads every 15s.
    Read the top two cards first — everything else is optional detail (collapsed by default).</p>
  </header>
  <div class="grid">
    <div class="card">
      <h2>At a glance</h2>
      <div class="run-banner {run_banner_class}">
        <div class="title">{run_banner_title}</div>
        <p class="plain">{run_banner_plain}</p>
        <p class="sub">{run_banner_sub}</p>
      </div>
      <div class="run-banner {'ok' if n_open > 0 or n_exec > 0 else ('warn' if agent_health == 'RUNNING' else run_banner_class)}" style="margin-top:10px">
        <div class="title" style="font-size:1.2rem">{trade_status}</div>
        <p class="plain">{trade_plain}</p>
        <p class="sub">{last_fill_line} · Equity ${_fmt_money(glance_equity).lstrip('+')} · Realized {_fmt_money(realized)} · Open {n_open}</p>
      </div>
      <div class="glance-grid">
        <div class="glance-cell"><div class="lbl">Scan</div><div class="val">{agent_health}</div></div>
        <div class="glance-cell"><div class="lbl">Session</div><div class="val">{session.split('|')[0].strip() if session else '—'}</div></div>
        <div class="glance-cell"><div class="lbl">NQ window 9:30–12 ET</div><div class="val">{'OPEN' if nq_window_open else 'CLOSED'}</div></div>
        <div class="glance-cell"><div class="lbl">Config</div><div class="val" style="font-size:0.9rem">{hb.get('config_version') or '—'}</div></div>
      </div>
    </div>
    <div class="card">
      <h2>Paper account</h2>
      <div class="eq">${equity + realized + unrealized_total:,.2f}</div>
      <div class="meta">Equity mark-to-market (start ${equity:,.0f})</div>
      <table style="margin-top:12px">
        <thead><tr><th>Realized P&amp;L</th><th>Unrealized P&amp;L</th><th>Open risk (to stops)</th><th>Closed / Open</th></tr></thead>
        <tbody><tr>
          <td class="{'up' if realized>0 else ('down' if realized<0 else '')}">{_fmt_money(realized)}</td>
          <td class="{'up' if unrealized_total>0 else ('down' if unrealized_total<0 else '')}">{_fmt_money(unrealized_total)}</td>
          <td>${risk_total:,.2f}</td>
          <td>{len(closed)} / {len(opens)}</td>
        </tr></tbody>
      </table>
    </div>
    <div class="card">
      <details class="fold" data-fold="open_positions" open>
        <summary>Open positions<span class="hint">click to expand/collapse</span></summary>
        <div class="fold-body">
          <table>
            <thead><tr><th>Opened</th><th>Session</th><th>Sym</th><th>Side</th><th>Qty</th><th>Entry</th><th>Mark</th><th>Stop</th><th>TP1</th><th>Target</th><th>Risk $</th><th>Reward $</th><th>uPnL</th></tr></thead>
            <tbody>{rows_open()}</tbody>
          </table>
        </div>
      </details>
    </div>
    <div class="card">
      <details class="fold" data-fold="tech_status">
        <summary>Technical status (feed / scheduler / supervisor)<span class="hint">optional detail</span></summary>
        <div class="fold-body">
          {tech_status_html}
        </div>
      </details>
    </div>
    <div class="card">
      <details class="fold" data-fold="adaptive_learning">
        <summary>Adaptive Learning Status<span class="hint">optional detail</span></summary>
        <div class="fold-body">
          {adaptive_learning_status_html()}
        </div>
      </details>
    </div>
    <div class="card">
      <details class="fold" data-fold="cl_winner_why">
        <summary>Why the recent CL winner won<span class="hint">optional detail</span></summary>
        <div class="fold-body">
          {cl_winner_why_html()}
        </div>
      </details>
    </div>
    <div class="card">
      <details class="fold" data-fold="why_selected">
        <summary>Why selected / why passed (learning)<span class="hint">optional detail</span></summary>
        <div class="fold-body">
          <div class="meta">{why_selected_html()}</div>
        </div>
      </details>
    </div>
    <div class="card">
      <details class="fold" data-fold="scan_tape">
        <summary>Scan tape (proof of life — updates every minute)<span class="hint">optional detail</span></summary>
        <div class="fold-body">
          <table>
            <thead><tr><th>Received (UTC)</th><th>Feed</th><th>Session</th><th>Decision</th><th>Setups</th><th>Candidates (exact)</th><th>Per-symbol engines</th><th>Prices</th></tr></thead>
            <tbody>{rows_scan_tape()}</tbody>
          </table>
          <div class="meta">If Setups says N, Candidates must list those N rows. Hidden counts are a bug.</div>
        </div>
      </details>
    </div>
    <div class="card">
      <details class="fold" data-fold="session_pnl">
        <summary>P&amp;L by session (cumulative)<span class="hint">optional detail</span></summary>
        <div class="fold-body">
          <table>
            <thead><tr><th>Session</th><th>Realized P&amp;L</th><th>Trades</th><th>Wins</th><th>Losses</th></tr></thead>
            <tbody>{rows_session_pnl()}</tbody>
          </table>
          <div class="meta">Excludes demo fills and prune/bookkeeping closes. Session = when the trade opened.</div>
        </div>
      </details>
    </div>
    <div class="card">
      <details class="fold" data-fold="daily_pnl">
        <summary>P&amp;L by day × session<span class="hint">click to expand/collapse</span></summary>
        <div class="fold-body">
          <table>
            <thead><tr><th>Day (ET)</th><th>Day total</th><th>Asia</th><th>London</th><th>NY</th><th>Trades</th><th>W/L</th></tr></thead>
            <tbody>{rows_daily_pnl()}</tbody>
          </table>
          <div class="meta">Day keyed off market/open timestamp (honest for delayed feed). Cumulative session table above still available.</div>
        </div>
      </details>
    </div>
    <div class="card">
      <details class="fold" data-fold="regime_context">
        <summary>Current market regime / context (latest scan)<span class="hint">optional detail</span></summary>
        <div class="fold-body">
          <table>
            <thead><tr><th>Symbol</th><th>Regime</th><th>Conf</th><th>15m</th><th>1h</th><th>4h</th><th>VWAP</th><th>EMA</th><th>Overext</th></tr></thead>
            <tbody>{rows_regime_context()}</tbody>
          </table>
        </div>
      </details>
    </div>
    <div class="card">
      <details class="fold" data-fold="exec_decisions">
        <summary>A/A+ execution decisions (terminal)<span class="hint">click to expand/collapse</span></summary>
        <div class="fold-body">
          <table>
            <thead><tr><th>Symbol</th><th>Strategy</th><th>Dir</th><th>Local</th><th>Global</th><th>Tier</th><th>Setup ID</th><th>Market time</th><th>EXECUTION DECISION</th></tr></thead>
            <tbody>{rows_execution_decisions()}</tbody>
          </table>
          <div class="meta">Every A/A+ must end EXECUTED or REJECTED:&lt;reason&gt; — never silent.</div>
        </div>
      </details>
    </div>
    <div class="card">
      <details class="fold" data-fold="opp_rate">
        <summary>ACTIVE MARKET OPPORTUNITY RATE<span class="hint">click to expand/collapse</span></summary>
        <div class="fold-body">
          <div class="meta">{opportunity_rate_html()}</div>
          <div class="meta">{current_config_perf_html()}</div>
          <div class="meta">{engine_audit_html()}</div>
        </div>
      </details>
    </div>
    <div class="card">
      <details class="fold" data-fold="global_candidates">
        <summary>Current scan candidates<span class="hint">click to expand/collapse</span></summary>
        <div class="fold-body">
          <table>
            <thead><tr><th>Symbol</th><th>Strategy</th><th>Dir</th><th>Local</th><th>Global</th><th>Tier</th><th>Regime</th><th>Setup ID</th><th>Market time</th><th>Breakdown</th></tr></thead>
            <tbody>{rows_global_candidates()}</tbody>
          </table>
          <div class="meta">Empty on NO_NEW_BAR is normal — see Last evaluated bar candidates below.</div>
        </div>
      </details>
    </div>
    <div class="card">
      <details class="fold" data-fold="last_eval_candidates">
        <summary>Last evaluated bar candidates (persists across NO_NEW_BAR)<span class="hint">click to expand/collapse</span></summary>
        <div class="fold-body">
          <table>
            <thead><tr><th>Symbol</th><th>Strategy</th><th>Dir</th><th>Local</th><th>Global</th><th>Tier</th><th>Regime</th><th>Setup ID</th><th>Market time</th><th>Breakdown</th></tr></thead>
            <tbody>{rows_last_eval_candidates()}</tbody>
          </table>
        </div>
      </details>
    </div>
    <div class="card">
      <details class="fold" data-fold="config_version">
        <summary>Performance by config version<span class="hint">click to expand/collapse</span></summary>
        <div class="fold-body">
          <table>
            <thead><tr><th>Config version</th><th>Trades</th><th>Net P&amp;L</th><th>PF</th><th>Expectancy</th><th>WR</th></tr></thead>
            <tbody>{rows_config_version()}</tbody>
          </table>
          <div class="meta">{filter_calibration_html()}</div>
        </div>
      </details>
    </div>
    <div class="card">
      <details class="fold" data-fold="perf_regime">
        <summary>Strategy performance by regime<span class="hint">click to expand/collapse</span></summary>
        <div class="fold-body">
          <table>
            <thead><tr><th>Strategy</th><th>Regime</th><th>Session</th><th>Trades</th><th>PF</th><th>Expectancy</th><th>WR</th><th>Avg R</th></tr></thead>
            <tbody>{rows_perf_regime()}</tbody>
          </table>
          <div class="meta">Analytics only until min_closed_trades_strategy_regime ≥ 30. Shadow P&amp;L never mixes into paper equity.</div>
        </div>
      </details>
    </div>
    <div class="card">
      <details class="fold" data-fold="cl_specialist">
        <summary>CL SPECIALIST FORWARD TEST<span class="hint">optional detail</span></summary>
        <div class="fold-body">
          {cl_specialist_forward_html()}
        </div>
      </details>
    </div>
    <div class="card">
      <details class="fold" data-fold="shadow_health">
        <summary>Shadow B / strategy health / research<span class="hint">click to expand/collapse</span></summary>
        <div class="fold-body">
          <div class="meta">{shadow_summary_html()}</div>
          <div class="meta">{circuit_summary_html()}</div>
          <h3>STRATEGY HEALTH (lifecycle kill / drift)</h3>
          {strategy_lifecycle_table_html()}
          <div class="meta">States: ACTIVE → WATCH (DD or 2 weekly drift) → SHADOW_ONLY (DD≤−7.5R) → HARD_PAUSED (DD≤−9R). No auto-reactivation from HARD_PAUSED. Single losses do not kill.</div>
          <div class="meta">Exit-model research: data/exit_model_research.jsonl (shadow only — never modifies actual paper). Champion/challenger: config strategy_versions (no auto-promotion).</div>
          <div class="meta">Config version stamp on new records: router_v1_clpaper1. Adaptive promotion requires manual approval.</div>
        </div>
      </details>
    </div>
    <div class="card">
      <details class="fold" data-fold="closed_trades">
        <summary>Closed trades (learning journal)<span class="hint">click to expand/collapse</span></summary>
        <div class="fold-body">
          <table>
            <thead><tr><th>Opened</th><th>Closed</th><th>Hold min</th><th>Session</th><th>Trade</th><th>Entry</th><th>Exit</th><th>P&amp;L</th><th>Result</th><th>ID</th></tr></thead>
            <tbody>{rows_closed()}</tbody>
          </table>
          <div class="meta">CSV: {self.csv_path.as_posix()} · JSON: {self.json_path.as_posix()}</div>
        </div>
      </details>
    </div>
  </div>
  <script>
  (function () {{
    var KEY = "paper_view_folds_v3";
    function load() {{
      try {{ return JSON.parse(localStorage.getItem(KEY) || "{{}}"); }}
      catch (e) {{ return {{}}; }}
    }}
    function save(state) {{
      try {{ localStorage.setItem(KEY, JSON.stringify(state)); }} catch (e) {{}}
    }}
    var state = load();
    document.querySelectorAll("details.fold[data-fold]").forEach(function (el) {{
      var id = el.getAttribute("data-fold");
      if (Object.prototype.hasOwnProperty.call(state, id)) {{
        el.open = !!state[id];
      }}
      el.addEventListener("toggle", function () {{
        state[id] = el.open;
        save(state);
      }});
    }});
  }})();
  </script>
</body>
</html>
"""
        self.html_path.write_text(html, encoding="utf-8")
        return self.html_path
