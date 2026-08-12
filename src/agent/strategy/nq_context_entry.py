"""Live/paper evaluator for locked NQ_CONTEXT_ENTRY champion.

Champion (Databento strict WR>=65%):
  PULLBACK BUY-only · 0930_1200 · signal_close · 1.15R
  zone_atr=0.30 · stop_atr=0.55 · vwap_buffer_atr=0.20 · cooldown=2
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

import pandas as pd

from agent.research.nq_context_entry import enrich_context_5m_bars, generate_candidates
from agent.strategy.indicator_parity import IndicatorParitySignal

STRATEGY_NAME = "nq_context_entry"
DEFAULT_VERSION = "nq_context_entry_pullback_v1"


def evaluate_nq_context_entry(
    symbol: str,
    bars: pd.DataFrame,
    cfg: dict[str, Any],
    *,
    point_value: float = 20.0,
) -> Optional[IndicatorParitySignal]:
    strat = cfg.get(STRATEGY_NAME) or {}
    if not bool(strat.get("enabled", True)):
        return None
    sym = symbol.upper()
    allowed = {s.upper() for s in (strat.get("symbols") or ["NQ", "MNQ"])}
    if sym not in allowed:
        return None
    if bars is None or len(bars) < 80:
        return None

    window = str(strat.get("window", "0930_1200"))
    confirmation = str(strat.get("confirmation", "signal_close"))
    trigger = str(strat.get("trigger", "PULLBACK"))
    zone_atr = float(strat.get("zone_atr", 0.30))
    stop_atr = float(strat.get("stop_atr", 0.55))
    vwap_buf = float(strat.get("vwap_buffer_atr", 0.20))
    cooldown = int(strat.get("cooldown_bars", 2))
    target_r = float(strat.get("target_r_multiple", 1.15))
    sides = tuple(str(s).upper() for s in (strat.get("sides") or ["BUY"]))
    min_stop = float(strat.get("min_stop_atr", max(0.25, stop_atr * 0.7)))
    version = str(strat.get("strategy_version", DEFAULT_VERSION))

    df5 = enrich_context_5m_bars(bars)
    cands = generate_candidates(
        df5,
        trigger=trigger,
        window=window,
        confirmation=confirmation,
        zone_atr=zone_atr,
        stop_atr=stop_atr,
        vwap_buffer_atr=vwap_buf,
        sides=sides,
        cooldown_bars=cooldown,
        min_stop_atr=min_stop,
    )
    if not cands:
        return None

    last_i = len(df5) - 1
    # Fire only when the latest completed bar is the entry bar (exactly-once via BarCursor).
    hit = next((c for c in reversed(cands) if int(c["entry_i"]) == last_i), None)
    if hit is None:
        return None

    entry = float(hit["entry"])
    stop = float(hit["stop"])
    side = str(hit["side"]).upper()
    risk = abs(entry - stop)
    if risk <= 1e-12:
        return None
    if side == "BUY":
        target = entry + risk * target_r
    else:
        target = entry - risk * target_r

    ts = df5.index[-1].to_pydatetime()
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    risk_d = risk * point_value
    reward_d = abs(target - entry) * point_value
    return IndicatorParitySignal(
        symbol=sym,
        side=side,
        entry=entry,
        stop=stop,
        target=target,
        confidence=78,
        reason=(
            f"{version}:{trigger}:{window}:{confirmation} "
            f"zone={zone_atr} stopATR={stop_atr} target={target_r}R"
        ),
        ts=ts,
        risk_dollars=risk_d,
        reward_dollars=reward_d,
        level=float(df5["ema20"].iloc[-1]) if pd.notna(df5["ema20"].iloc[-1]) else entry,
        entry_mode="nq_context_entry_v1",
        state={
            "trigger": trigger,
            "session_window": window,
            "confirmation": confirmation,
            "dir_15m": float(hit.get("dir_15m") or 0),
            "dir_1h": float(hit.get("dir_1h") or 0),
            "above_vwap": float(hit.get("above_vwap") or 0),
            "ema_aligned": float(hit.get("ema_aligned") or 0),
            "strategy_version": version,
        },
    )
