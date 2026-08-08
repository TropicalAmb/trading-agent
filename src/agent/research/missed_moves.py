"""Post-event missed-move research — NEVER used in live decision path."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import pandas as pd


@dataclass
class MissedMove:
    symbol: str
    bar_ts: str
    direction: str
    atr_move: float
    horizon_bars: int
    had_a_or_better: bool
    had_b: bool
    had_any_candidate: bool
    tag: str  # MISSED_DIRECTIONAL_MOVE


def _atr(df: pd.DataFrame, n: int = 14) -> float:
    prev = df["close"].shift(1)
    tr = pd.concat(
        [
            (df["high"] - df["low"]).abs(),
            (df["high"] - prev).abs(),
            (df["low"] - prev).abs(),
        ],
        axis=1,
    ).max(axis=1)
    v = float(tr.rolling(n).mean().iloc[-1] or 0.0)
    return v if v > 0 else float(df["close"].iloc[-1]) * 0.001


def scan_missed_moves(
    df: pd.DataFrame,
    *,
    symbol: str,
    candidates_by_bar: dict[str, list[dict[str, Any]]] | None = None,
    horizons: tuple[int, ...] = (3, 6, 12),
    atr_threshold: float = 1.5,
    adverse_atr: float = 0.5,
) -> list[MissedMove]:
    """Look forward from each bar; research-only (uses future bars)."""
    if df is None or len(df) < 30:
        return []
    candidates_by_bar = candidates_by_bar or {}
    out: list[MissedMove] = []
    max_h = max(horizons)
    for i in range(20, len(df) - max_h):
        window = df.iloc[: i + 1]
        atr = _atr(window)
        entry = float(df["close"].iloc[i])
        ts = str(df.index[i])
        cands = candidates_by_bar.get(ts) or []
        had_a = any(str(c.get("tier", "")).upper() in {"A", "A+"} for c in cands)
        had_b = any(str(c.get("tier", "")).upper() == "B" for c in cands)
        had_any = bool(cands)

        for h in horizons:
            fwd = df.iloc[i + 1 : i + 1 + h]
            if len(fwd) < h:
                continue
            # Long move
            mfe_long = float(fwd["high"].max() - entry) / atr
            mae_long = float(entry - fwd["low"].min()) / atr
            if mfe_long >= atr_threshold and mae_long < adverse_atr:
                out.append(
                    MissedMove(
                        symbol=symbol,
                        bar_ts=ts,
                        direction="BUY",
                        atr_move=round(mfe_long, 3),
                        horizon_bars=h,
                        had_a_or_better=had_a,
                        had_b=had_b,
                        had_any_candidate=had_any,
                        tag="MISSED_DIRECTIONAL_MOVE",
                    )
                )
                break
            mfe_short = float(entry - fwd["low"].min()) / atr
            mae_short = float(fwd["high"].max() - entry) / atr
            if mfe_short >= atr_threshold and mae_short < adverse_atr:
                out.append(
                    MissedMove(
                        symbol=symbol,
                        bar_ts=ts,
                        direction="SELL",
                        atr_move=round(mfe_short, 3),
                        horizon_bars=h,
                        had_a_or_better=had_a,
                        had_b=had_b,
                        had_any_candidate=had_any,
                        tag="MISSED_DIRECTIONAL_MOVE",
                    )
                )
                break
    return out


def summarize_missed(moves: list[MissedMove]) -> dict[str, Any]:
    n = len(moves)
    a = sum(1 for m in moves if m.had_a_or_better)
    b_only = sum(1 for m in moves if m.had_b and not m.had_a_or_better)
    none = sum(1 for m in moves if not m.had_any_candidate)
    return {
        "large_directional_moves": n,
        "a_or_better_present": a,
        "b_only_present": b_only,
        "no_setup_detected": none,
        "note": "research-only; does not affect live decisions",
    }
