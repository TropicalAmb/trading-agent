"""Specialist momentum candidates preserved from momentum_deep evidence.

cl_vwap_prox_momentum_v1:
  5m parity-bias momentum + |VWAP dist| <= 0.25 ATR on CL/MCL

nq_ny_open_momentum_v1:
  5m parity-bias momentum in NY open session on NQ/MNQ

Research/shadow by default until validation + explicit paper enable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

import pandas as pd

from agent.research.momentum_deep import _session_bucket, build_feature_frame
from agent.strategy.indicator_parity import IndicatorParitySignal


def _parity_mom_signal(frame: pd.DataFrame, i: int = -1) -> Optional[str]:
    row = frame.iloc[i]
    if int(row.get("parity_mom_long", 0)) == 1:
        return "BUY"
    if int(row.get("parity_mom_short", 0)) == 1:
        return "SELL"
    return None


def _build_signal(
    *,
    symbol: str,
    side: str,
    row: pd.Series,
    ts: datetime,
    point_value: float,
    stop_atr_mult: float,
    target_r: float,
    reason: str,
    entry_mode: str,
) -> IndicatorParitySignal:
    entry = float(row["close"])
    atr = float(row["atr"] or 0) or abs(entry) * 0.001
    if side == "BUY":
        stop = entry - atr * stop_atr_mult
        target = entry + abs(entry - stop) * target_r
    else:
        stop = entry + atr * stop_atr_mult
        target = entry - abs(stop - entry) * target_r
    risk_d = abs(entry - stop) * point_value
    reward_d = abs(target - entry) * point_value
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return IndicatorParitySignal(
        symbol=symbol.upper(),
        side=side,
        entry=entry,
        stop=stop,
        target=target,
        confidence=70,
        reason=reason,
        ts=ts,
        risk_dollars=risk_d,
        reward_dollars=reward_d,
        level=float(row["vwap"]) if pd.notna(row.get("vwap")) else entry,
        entry_mode=entry_mode,
        state={
            "abs_dist_vwap_atr": float(row["close_vs_vwap"]) if pd.notna(row.get("close_vs_vwap")) else None,
            "dir_4h": int(row["dir_4h"]),
            "dir_1h": int(row["dir_1h"]),
            "dir_15m": int(row["dir_15m"]),
            "session": _session_bucket(pd.Timestamp(ts)),
        },
    )


def evaluate_cl_vwap_prox_momentum(
    symbol: str,
    bars: pd.DataFrame,
    cfg: dict[str, Any],
    *,
    point_value: float = 100.0,
) -> Optional[IndicatorParitySignal]:
    """Exact CL specialist: parity-bias mom + |VWAP|<=0.25 ATR on 5m semantics."""
    strat = cfg.get("cl_vwap_prox_momentum") or cfg.get("specialists") or {}
    if not bool(strat.get("enabled", True)):
        return None
    sym = symbol.upper()
    allowed = {s.upper() for s in (strat.get("symbols") or ["CL", "MCL"])}
    if sym not in allowed:
        return None
    if bars is None or len(bars) < 100:
        return None
    max_vwap = float(strat.get("max_abs_vwap_atr", 0.25))
    stop_atr = float(strat.get("stop_atr_mult", 1.0))
    target_r = float(strat.get("target_r_multiple", 2.0))
    frame = build_feature_frame(bars)
    side = _parity_mom_signal(frame, -1)
    if side is None:
        return None
    row = frame.iloc[-1]
    dist = abs(float(row["close_vs_vwap"])) if pd.notna(row.get("close_vs_vwap")) else 999.0
    if dist > max_vwap:
        return None
    ts = bars.index[-1].to_pydatetime()
    return _build_signal(
        symbol=sym,
        side=side,
        row=row,
        ts=ts,
        point_value=point_value,
        stop_atr_mult=stop_atr,
        target_r=target_r,
        reason=f"cl_vwap_prox_momentum_v1:parity_mom+|vwap|<={max_vwap}ATR",
        entry_mode="cl_vwap_prox_v1",
    )


def evaluate_nq_ny_open_momentum(
    symbol: str,
    bars: pd.DataFrame,
    cfg: dict[str, Any],
    *,
    point_value: float = 20.0,
) -> Optional[IndicatorParitySignal]:
    """NQ NY-open parity-bias momentum (promising / not confirmed)."""
    strat = cfg.get("nq_ny_open_momentum") or cfg.get("specialists") or {}
    if not bool(strat.get("enabled", True)):
        return None
    sym = symbol.upper()
    allowed = {s.upper() for s in (strat.get("symbols") or ["NQ", "MNQ"])}
    if sym not in allowed:
        return None
    if bars is None or len(bars) < 100:
        return None
    sessions = {str(s).lower() for s in (strat.get("sessions") or ["ny_open"])}
    stop_atr = float(strat.get("stop_atr_mult", 1.0))
    target_r = float(strat.get("target_r_multiple", 2.0))
    frame = build_feature_frame(bars)
    side = _parity_mom_signal(frame, -1)
    if side is None:
        return None
    ts = bars.index[-1].to_pydatetime()
    sess = _session_bucket(pd.Timestamp(ts))
    if sess not in sessions:
        return None
    row = frame.iloc[-1]
    return _build_signal(
        symbol=sym,
        side=side,
        row=row,
        ts=ts,
        point_value=point_value,
        stop_atr_mult=stop_atr,
        target_r=target_r,
        reason=f"nq_ny_open_momentum_v1:parity_mom+session={sess}",
        entry_mode="nq_ny_open_v1",
    )


def evaluate_session_open_momentum(
    symbol: str,
    bars: pd.DataFrame,
    cfg: dict[str, Any],
    *,
    point_value: float = 20.0,
    session: str | None = None,
) -> Optional[IndicatorParitySignal]:
    """Parity-bias momentum restricted to a session-open bucket (asia/london/ny_open).

    Research/shadow by default. Does not replace nq_ny_open_momentum.
    """
    strat = cfg.get("session_open_momentum") or {}
    if not bool(strat.get("enabled", True)):
        return None
    sym = symbol.upper()
    allowed = {s.upper() for s in (strat.get("symbols") or ["NQ", "MNQ", "ES", "MES"])}
    if sym not in allowed:
        return None
    if bars is None or len(bars) < 100:
        return None
    want = str(session or "").lower()
    if not want:
        # If called without session, allow any configured session list
        sessions = {str(s).lower() for s in (strat.get("sessions") or ["asia", "london", "ny_open"])}
    else:
        sessions = {want}
    stop_atr = float(strat.get("stop_atr_mult", 1.0))
    target_r = float(strat.get("target_r_multiple", 2.0))
    frame = build_feature_frame(bars)
    side = _parity_mom_signal(frame, -1)
    if side is None:
        return None
    ts = bars.index[-1].to_pydatetime()
    sess = _session_bucket(pd.Timestamp(ts))
    if sess not in sessions:
        return None
    row = frame.iloc[-1]
    return _build_signal(
        symbol=sym,
        side=side,
        row=row,
        ts=ts,
        point_value=point_value,
        stop_atr_mult=stop_atr,
        target_r=target_r,
        reason=f"session_open_momentum:{sess}:parity_mom",
        entry_mode=f"session_open_{sess}",
    )
