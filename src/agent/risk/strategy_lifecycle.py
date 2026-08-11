"""Strategy-level kill / drift framework (additive to circuit breakers).

States per strategy×symbol (and optional BOOK) cell:
  ACTIVE | WATCH | SHADOW_ONLY | HARD_PAUSED

Severity order (drawdown from peak, more negative = more severe):
  WATCH_dd > SHADOW_dd > HARD_dd   (e.g. -5 > -7.5 > -9)
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Sequence

import numpy as np


LIFECYCLE_STATES = ("ACTIVE", "WATCH", "SHADOW_ONLY", "HARD_PAUSED")

# Explicit CL specialist thresholds from validation evidence
# hist maxDD=-5R, MC p95≈-6R → WATCH=-5, SHADOW=1.25*6=-7.5, HARD=1.5*6=-9
CL_DEFAULT_THRESHOLDS = {
    "watch_dd_r": -5.0,
    "shadow_dd_r": -7.5,
    "hard_kill_r": -9.0,
}


def cell_key(strategy: str, symbol: str) -> str:
    return f"{strategy}|{str(symbol).upper()}"


def equity_curve_r(pnl_r: Sequence[float]) -> dict[str, float]:
    rs = np.asarray(list(pnl_r), dtype=float)
    if len(rs) == 0:
        return {"peak": 0.0, "equity": 0.0, "dd_from_peak": 0.0, "max_dd": 0.0}
    eq = np.cumsum(rs)
    peak = np.maximum.accumulate(eq)
    dd = eq - peak
    return {
        "peak": float(peak[-1]),
        "equity": float(eq[-1]),
        "dd_from_peak": float(dd[-1]),
        "max_dd": float(dd.min()),
    }


def compute_kill_thresholds(historical_pnl_r: Sequence[float]) -> dict[str, float]:
    """Ordered thresholds: |watch| < |shadow| < |hard|."""
    rs = np.asarray(list(historical_pnl_r), dtype=float)
    if len(rs) < 20:
        return {
            "hist_max_dd_r": -4.0,
            "hist_p95_dd_r": -4.0,
            "watch_dd_r": -4.0,
            "trailing_stop_r": -6.0,
            "shadow_dd_r": -6.0,
            "hard_kill_r": -8.0,
            "n": float(len(rs)),
            "method": "default_thin_sample",
        }
    path = equity_curve_r(rs)
    hist_max_dd = float(path["max_dd"])
    rng = np.random.default_rng(7)
    dds = [equity_curve_r(rng.choice(rs, size=len(rs), replace=True))["max_dd"] for _ in range(2000)]
    p95 = float(np.percentile(dds, 5))
    hist_mag = abs(hist_max_dd)
    p95_mag = abs(p95)
    watch_mag = max(hist_mag, 4.0)
    shadow_mag = max(1.25 * p95_mag, watch_mag + 1.0)
    hard_mag = max(1.5 * p95_mag, shadow_mag + 1.0)
    return {
        "hist_max_dd_r": hist_max_dd,
        "hist_p95_dd_r": p95,
        "watch_dd_r": -float(watch_mag),
        "trailing_stop_r": -float(shadow_mag),
        "shadow_dd_r": -float(shadow_mag),
        "hard_kill_r": -float(hard_mag),
        "n": float(len(rs)),
        "method": "historical_bootstrap_ordered",
    }


def thresholds_from_cfg(cfg: dict[str, Any] | None, strategy: str) -> dict[str, float]:
    lc = (cfg or {}).get("strategy_lifecycle") or {}
    strat = lc.get(strategy) or {}
    if strategy == "cl_vwap_prox_momentum" or strat:
        watch = float(strat.get("watch_dd_r", CL_DEFAULT_THRESHOLDS["watch_dd_r"]))
        shadow = float(strat.get("shadow_dd_r", CL_DEFAULT_THRESHOLDS["shadow_dd_r"]))
        hard = float(strat.get("hard_kill_r", CL_DEFAULT_THRESHOLDS["hard_kill_r"]))
    else:
        watch, shadow, hard = -4.0, -6.0, -8.0
    # Enforce severity order
    if not (watch > shadow > hard):  # -5 > -7.5 > -9
        watch, shadow, hard = (
            CL_DEFAULT_THRESHOLDS["watch_dd_r"],
            CL_DEFAULT_THRESHOLDS["shadow_dd_r"],
            CL_DEFAULT_THRESHOLDS["hard_kill_r"],
        )
    return {"watch_dd_r": watch, "shadow_dd_r": shadow, "hard_kill_r": hard}


@dataclass
class StrategyCellState:
    strategy: str
    symbol: str
    state: str = "ACTIVE"
    equity_r: float = 0.0
    equity_peak_r: float = 0.0
    dd_from_peak_r: float = 0.0
    max_dd_r: float = 0.0
    watch_dd_r: float = -5.0
    trailing_stop_r: float = -7.5  # alias shadow
    shadow_dd_r: float = -7.5
    hard_kill_r: float = -9.0
    expected_wr: float | None = None
    expected_e: float | None = None
    forward_trades: int = 0
    forward_wins: int = 0
    forward_losses: int = 0
    rolling_wr: float | None = None
    rolling_e: float | None = None
    rolling_pf: float | None = None
    drift_flag: bool = False
    drift_weeks_under: int = 0
    last_review_ts: float = 0.0
    notes: str = ""

    def key(self) -> str:
        return cell_key(self.strategy, self.symbol)


class StrategyLifecycleStore:
    def __init__(self, path: str | Path = "data/strategy_lifecycle.json"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._state: dict[str, Any] = {"cells": {}, "updated": None}
        self.load()

    def load(self) -> None:
        if self.path.exists():
            try:
                self._state = json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:
                self._state = {"cells": {}, "updated": None}
        self._state.setdefault("cells", {})

    def save(self) -> None:
        self._state["updated"] = time.time()
        self.path.write_text(json.dumps(self._state, indent=2), encoding="utf-8")

    def get_cell(self, strategy: str, symbol: str) -> StrategyCellState:
        k = cell_key(strategy, symbol)
        raw = (self._state.get("cells") or {}).get(k) or {}
        thr = CL_DEFAULT_THRESHOLDS if strategy == "cl_vwap_prox_momentum" else {
            "watch_dd_r": -4.0,
            "shadow_dd_r": -6.0,
            "hard_kill_r": -8.0,
        }
        return StrategyCellState(
            strategy=strategy,
            symbol=str(symbol).upper(),
            state=str(raw.get("state") or "ACTIVE"),
            equity_r=float(raw.get("equity_r") or 0.0),
            equity_peak_r=float(raw.get("equity_peak_r") or 0.0),
            dd_from_peak_r=float(raw.get("dd_from_peak_r") or 0.0),
            max_dd_r=float(raw.get("max_dd_r") or 0.0),
            watch_dd_r=float(raw.get("watch_dd_r", thr["watch_dd_r"])),
            trailing_stop_r=float(raw.get("trailing_stop_r", raw.get("shadow_dd_r", thr["shadow_dd_r"]))),
            shadow_dd_r=float(raw.get("shadow_dd_r", thr["shadow_dd_r"])),
            hard_kill_r=float(raw.get("hard_kill_r", thr["hard_kill_r"])),
            expected_wr=raw.get("expected_wr"),
            expected_e=raw.get("expected_e"),
            forward_trades=int(raw.get("forward_trades") or 0),
            forward_wins=int(raw.get("forward_wins") or 0),
            forward_losses=int(raw.get("forward_losses") or 0),
            rolling_wr=raw.get("rolling_wr"),
            rolling_e=raw.get("rolling_e"),
            rolling_pf=raw.get("rolling_pf"),
            drift_flag=bool(raw.get("drift_flag")),
            drift_weeks_under=int(raw.get("drift_weeks_under") or 0),
            last_review_ts=float(raw.get("last_review_ts") or 0.0),
            notes=str(raw.get("notes") or ""),
        )

    def put_cell(self, cell: StrategyCellState) -> None:
        self._state["cells"][cell.key()] = asdict(cell)
        self.save()

    def get_state(self, strategy: str, symbol: str) -> str:
        # Book-level state for CL family overrides if more severe
        st = self.get_cell(strategy, symbol).state
        if strategy == "cl_vwap_prox_momentum":
            book = self.get_cell(strategy, "CL_BOOK").state
            order = {"ACTIVE": 0, "WATCH": 1, "SHADOW_ONLY": 2, "HARD_PAUSED": 3}
            if order.get(book, 0) > order.get(st, 0):
                return book
        return st if st in LIFECYCLE_STATES else "ACTIVE"

    def seed_thresholds(
        self,
        strategy: str,
        symbol: str,
        historical_pnl_r: Sequence[float],
        *,
        expected_wr: float | None = None,
        expected_e: float | None = None,
        cfg: dict[str, Any] | None = None,
    ) -> StrategyCellState:
        if strategy == "cl_vwap_prox_momentum" or (cfg and strategy in ((cfg.get("strategy_lifecycle") or {}))):
            thr = thresholds_from_cfg(cfg, strategy)
        else:
            computed = compute_kill_thresholds(historical_pnl_r)
            thr = {
                "watch_dd_r": computed["watch_dd_r"],
                "shadow_dd_r": computed["shadow_dd_r"],
                "hard_kill_r": computed["hard_kill_r"],
            }
        cell = self.get_cell(strategy, symbol)
        cell.watch_dd_r = float(thr["watch_dd_r"])
        cell.shadow_dd_r = float(thr["shadow_dd_r"])
        cell.trailing_stop_r = float(thr["shadow_dd_r"])
        cell.hard_kill_r = float(thr["hard_kill_r"])
        cell.expected_wr = expected_wr
        cell.expected_e = expected_e
        cell.notes = (
            f"seeded_ordered:watch={cell.watch_dd_r},shadow={cell.shadow_dd_r},"
            f"hard={cell.hard_kill_r}"
        )
        assert cell.watch_dd_r > cell.shadow_dd_r > cell.hard_kill_r
        self.put_cell(cell)
        return cell

    def record_forward_trade(
        self,
        strategy: str,
        symbol: str,
        pnl_r: float,
        *,
        cfg: dict[str, Any] | None = None,
    ) -> StrategyCellState:
        thr = thresholds_from_cfg(cfg, strategy)
        cell = self.get_cell(strategy, symbol)
        if cell.state == "HARD_PAUSED":
            return cell
        # Apply explicit thresholds from config
        cell.watch_dd_r = thr["watch_dd_r"]
        cell.shadow_dd_r = thr["shadow_dd_r"]
        cell.trailing_stop_r = thr["shadow_dd_r"]
        cell.hard_kill_r = thr["hard_kill_r"]

        cell.forward_trades += 1
        if pnl_r > 0:
            cell.forward_wins += 1
        elif pnl_r < 0:
            cell.forward_losses += 1
        cell.equity_r = float(cell.equity_r + pnl_r)
        cell.equity_peak_r = float(max(cell.equity_peak_r, cell.equity_r))
        cell.dd_from_peak_r = float(cell.equity_r - cell.equity_peak_r)
        cell.max_dd_r = float(min(cell.max_dd_r, cell.dd_from_peak_r))

        if cell.dd_from_peak_r <= cell.hard_kill_r:
            cell.state = "HARD_PAUSED"
            cell.notes = f"HARD_KILL dd={cell.dd_from_peak_r:.2f} <= {cell.hard_kill_r:.2f}"
        elif cell.dd_from_peak_r <= cell.shadow_dd_r:
            cell.state = "SHADOW_ONLY"
            cell.notes = f"SHADOW_DD dd={cell.dd_from_peak_r:.2f} <= {cell.shadow_dd_r:.2f}"
        elif cell.dd_from_peak_r <= cell.watch_dd_r:
            if cell.state == "ACTIVE":
                cell.state = "WATCH"
            cell.notes = f"WATCH_DD dd={cell.dd_from_peak_r:.2f} <= {cell.watch_dd_r:.2f}"
        self.put_cell(cell)

        # Aggregate CL book equity (separate curve; not whole-account)
        if strategy == "cl_vwap_prox_momentum" and str(symbol).upper() in {"CL", "MCL"}:
            book = self.get_cell(strategy, "CL_BOOK")
            if book.state != "HARD_PAUSED":
                book.watch_dd_r = thr["watch_dd_r"]
                book.shadow_dd_r = thr["shadow_dd_r"]
                book.trailing_stop_r = thr["shadow_dd_r"]
                book.hard_kill_r = thr["hard_kill_r"]
                book.forward_trades += 1
                if pnl_r > 0:
                    book.forward_wins += 1
                elif pnl_r < 0:
                    book.forward_losses += 1
                book.equity_r = float(book.equity_r + pnl_r)
                book.equity_peak_r = float(max(book.equity_peak_r, book.equity_r))
                book.dd_from_peak_r = float(book.equity_r - book.equity_peak_r)
                book.max_dd_r = float(min(book.max_dd_r, book.dd_from_peak_r))
                if book.dd_from_peak_r <= book.hard_kill_r:
                    book.state = "HARD_PAUSED"
                    book.notes = f"HARD_KILL book dd={book.dd_from_peak_r:.2f}"
                elif book.dd_from_peak_r <= book.shadow_dd_r:
                    book.state = "SHADOW_ONLY"
                    book.notes = f"SHADOW_DD book dd={book.dd_from_peak_r:.2f}"
                elif book.dd_from_peak_r <= book.watch_dd_r:
                    if book.state == "ACTIVE":
                        book.state = "WATCH"
                    book.notes = f"WATCH_DD book dd={book.dd_from_peak_r:.2f}"
                if book.expected_wr is None:
                    book.expected_wr = 0.694
                    book.expected_e = 1.08
                self.put_cell(book)
        return cell

    def weekly_drift_review(
        self,
        strategy: str,
        symbol: str,
        recent_pnl_r: Sequence[float],
        *,
        wr_floor_delta: float = 0.12,
        e_floor_delta: float = 0.35,
    ) -> StrategyCellState:
        cell = self.get_cell(strategy, symbol)
        if cell.state == "HARD_PAUSED":
            return cell
        rs = list(recent_pnl_r)
        if len(rs) < 8:
            cell.last_review_ts = time.time()
            self.put_cell(cell)
            return cell
        wins = sum(1 for r in rs if r > 0)
        wr = wins / len(rs)
        e = sum(rs) / len(rs)
        gw = sum(r for r in rs if r > 0)
        gl = abs(sum(r for r in rs if r < 0))
        pf = (gw / gl) if gl > 1e-12 else (999.0 if gw > 0 else 0.0)
        cell.rolling_wr = wr
        cell.rolling_e = e
        cell.rolling_pf = pf
        under = False
        if cell.expected_wr is not None and wr < float(cell.expected_wr) - wr_floor_delta:
            under = True
        if cell.expected_e is not None and e < float(cell.expected_e) - e_floor_delta:
            under = True
        if under:
            cell.drift_weeks_under += 1
            cell.drift_flag = True
        else:
            cell.drift_weeks_under = 0
            cell.drift_flag = False
            if cell.state == "WATCH" and cell.dd_from_peak_r > cell.watch_dd_r:
                cell.state = "ACTIVE"
                cell.notes = "drift_normalized"
        if cell.drift_weeks_under >= 2 and cell.state == "ACTIVE":
            cell.state = "WATCH"
            cell.notes = "DRIFT_WATCH:2_consecutive_weekly_underperformance"
        cell.last_review_ts = time.time()
        self.put_cell(cell)
        return cell

    def snapshot(self) -> list[dict[str, Any]]:
        out = []
        for k, v in (self._state.get("cells") or {}).items():
            row = dict(v)
            row["key"] = k
            out.append(row)
        return out


def blocks_execution(state: str) -> bool:
    return state in {"SHADOW_ONLY", "HARD_PAUSED"}
