"""NQ_CONTEXT_ENTRY — three simple NY-morning triggers (research family).

Triggers only:
  A) PULLBACK_REJECTION
  B) LIQUIDITY_SWEEP_RECLAIM
  C) BREAKOUT_RETEST

Deterministic setup defines the candidate. Global score is optional telemetry —
never an entry gate for this family.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Iterable, Sequence

import numpy as np
import pandas as pd

from agent.research.features_ict import atr, session_vwap, swing_high_low
from agent.research.time_alignment import partial_bar_direction
from agent.research.harness.metrics import trade_stats

FAMILY = "NQ_CONTEXT_ENTRY"
TRIGGERS = ("PULLBACK", "LIQUIDITY", "BREAKOUT_RETEST")
CONFIRMATIONS = (
    "signal_close",
    "next_bar",
    "rejection_wick",
    "engulf",
    "break_prior_hl",
)
EXIT_RS = (1.0, 1.25, 1.5, 1.75, 2.0)
SESSION_WINDOWS = {
    "0830_0930": (8 * 60 + 30, 9 * 60 + 30),
    "0930_1030": (9 * 60 + 30, 10 * 60 + 30),
    "0930_1100": (9 * 60 + 30, 11 * 60),
    "0930_1130": (9 * 60 + 30, 11 * 60 + 30),
    "0930_1200": (9 * 60 + 30, 12 * 60),
    "0945_1145": (9 * 60 + 45, 11 * 60 + 45),
    "1000_1130": (10 * 60, 11 * 60 + 30),
    "1000_1200": (10 * 60, 12 * 60),
    "1000_1215": (10 * 60, 12 * 60 + 15),
}
FRICTION_NQ = 0.75  # 2 ticks slip + 1 tick buffer


@dataclass
class NQTrade:
    symbol: str
    trigger: str
    side: str
    entry_ts: str
    exit_ts: str
    pnl_r: float
    session_window: str
    confirmation: str
    exit_style: str
    target_r: float
    entry: float
    stop: float
    target: float
    context: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d


def _minutes(ts: pd.Timestamp) -> int:
    return int(ts.hour) * 60 + int(ts.minute)


def in_window(ts: pd.Timestamp, window: str) -> bool:
    lo, hi = SESSION_WINDOWS[window]
    m = _minutes(ts)
    return lo <= m < hi


def enrich_context_5m_bars(df5: pd.DataFrame, *, use_4h: bool = False) -> pd.DataFrame:
    """Add NQ_CONTEXT_ENTRY columns onto already-5m OHLC bars (live/paper path)."""
    from agent.data.kaggle_nq import resample_ohlcv

    out = df5.copy()
    if getattr(out.index, "tz", None) is None:
        out.index = pd.to_datetime(out.index, utc=True).tz_convert("America/New_York")
    else:
        out.index = out.index.tz_convert("America/New_York")

    out["dir_15m"] = partial_bar_direction(out, "15min")
    out["dir_1h"] = partial_bar_direction(out, "1h")
    if use_4h:
        out["dir_4h"] = partial_bar_direction(out, "4h")
    else:
        out["dir_4h"] = 0.0

    if "vwap_eth" in out.columns and float(out["vwap_eth"].fillna(0).abs().sum()) > 0:
        out["vwap"] = out["vwap_eth"].replace(0, np.nan)
        if "vwap_rth" in out.columns:
            rth = (out.index.hour * 60 + out.index.minute >= 9 * 60 + 30) & (
                out.index.hour * 60 + out.index.minute < 16 * 60
            )
            out.loc[rth, "vwap"] = out.loc[rth, "vwap_rth"].replace(0, np.nan)
        out["vwap"] = out["vwap"].ffill()
    else:
        out["vwap"] = session_vwap(out)

    out["ema20"] = out["close"].ewm(span=20, adjust=False).mean()
    out["ema50"] = out["close"].ewm(span=50, adjust=False).mean()
    out["atr"] = atr(out, 14)

    day = out.index.normalize()
    daily = out.groupby(day).agg(high=("high", "max"), low=("low", "min"))
    out["pdh"] = day.map(daily["high"].shift(1))
    out["pdl"] = day.map(daily["low"].shift(1))

    ids = []
    for ts in out.index:
        key = ts.normalize() if ts.hour >= 18 else (ts.normalize() - pd.Timedelta(days=1))
        ids.append(key)
    out["sess_key"] = ids
    out["session_high"] = out.groupby("sess_key")["high"].cummax()
    out["session_low"] = out.groupby("sess_key")["low"].cummin()

    sh, sl = swing_high_low(out, left=3, right=3)
    out["swing_high"] = sh.ffill()
    out["swing_low"] = sl.ffill()
    return out


def build_context_5m(df_1m: pd.DataFrame, *, use_4h: bool = False) -> pd.DataFrame:
    """Construct 5m execution bars + context columns from 1m raw.

    Direction columns are built from 1m→15m/1h (research-accurate), then remaining
    context columns match the live enricher.
    """
    from agent.data.kaggle_nq import resample_ohlcv

    df5 = resample_ohlcv(df_1m, "5min")
    # Use the same point-in-time feature path as live/paper.  Computing a
    # finished 1h close for every earlier 5m row is look-ahead leakage.
    return enrich_context_5m_bars(df5, use_4h=use_4h)


def _rejection_long(o, h, l, c) -> bool:
    body = abs(c - o)
    lower = min(o, c) - l
    return c >= o and lower >= max(body, 1e-9) * 0.6


def _rejection_short(o, h, l, c) -> bool:
    body = abs(c - o)
    upper = h - max(o, c)
    return c <= o and upper >= max(body, 1e-9) * 0.6


def _engulf_long(po, pc, o, c) -> bool:
    return c > o and c >= max(po, pc) and o <= min(po, pc)


def _engulf_short(po, pc, o, c) -> bool:
    return c < o and c <= min(po, pc) and o >= max(po, pc)


def _confirm(
    df5: pd.DataFrame,
    i: int,
    side: str,
    kind: str,
) -> int | None:
    """Return entry bar index or None."""
    if i >= len(df5) - 2:
        return None
    o, h, l, c = (float(df5[x].iloc[i]) for x in ("open", "high", "low", "close"))
    if kind == "signal_close":
        if side == "BUY" and c >= o:
            return i
        if side == "SELL" and c <= o:
            return i
        return None
    if kind == "next_bar":
        j = i + 1
        cj, oj = float(df5["close"].iloc[j]), float(df5["open"].iloc[j])
        if side == "BUY" and cj > oj:
            return j
        if side == "SELL" and cj < oj:
            return j
        return None
    if kind == "rejection_wick":
        ok = _rejection_long(o, h, l, c) if side == "BUY" else _rejection_short(o, h, l, c)
        return i if ok else None
    if kind == "engulf":
        if i < 1:
            return None
        po, pc = float(df5["open"].iloc[i - 1]), float(df5["close"].iloc[i - 1])
        ok = _engulf_long(po, pc, o, c) if side == "BUY" else _engulf_short(po, pc, o, c)
        return i if ok else None
    if kind == "break_prior_hl":
        if i < 1:
            return None
        ph, pl = float(df5["high"].iloc[i - 1]), float(df5["low"].iloc[i - 1])
        if side == "BUY" and c > ph:
            return i
        if side == "SELL" and c < pl:
            return i
        return None
    return None


def _exit_1m(
    df_1m: pd.DataFrame,
    entry_ts: pd.Timestamp,
    side: str,
    entry: float,
    stop: float,
    target: float,
    *,
    max_hold_minutes: int = 180,
    friction: float = FRICTION_NQ,
) -> tuple[float, str]:
    """Simulate on 1m path. If stop and target both print in same bar → stop (conservative)."""
    risk = abs(entry - stop)
    if risk <= 1e-12:
        return 0.0, str(entry_ts)
    # enter from next 1m bar after signal bar close
    fwd = df_1m.loc[df_1m.index > entry_ts].iloc[:max_hold_minutes]
    if fwd.empty:
        return -friction / risk, str(entry_ts)
    exit_px = float(fwd["close"].iloc[-1])
    exit_ts = fwd.index[-1]
    for ts, row in fwd.iterrows():
        h, l = float(row["high"]), float(row["low"])
        hit_stop = (l <= stop) if side == "BUY" else (h >= stop)
        hit_tgt = (h >= target) if side == "BUY" else (l <= target)
        if hit_stop and hit_tgt:
            exit_px, exit_ts = stop, ts
            break
        if hit_stop:
            exit_px, exit_ts = stop, ts
            break
        if hit_tgt:
            exit_px, exit_ts = target, ts
            break
    raw = (exit_px - entry) if side == "BUY" else (entry - exit_px)
    return float((raw - friction) / risk), str(exit_ts)


def _structural_target(
    side: str,
    entry: float,
    stop: float,
    swing_hi: float,
    swing_lo: float,
    *,
    min_r: float = 1.0,
) -> float | None:
    """Structural target only if it clears min_r — blocks tiny-target WR inflation."""
    risk = abs(entry - stop)
    if risk <= 1e-12:
        return None
    if side == "BUY":
        lvl = swing_hi
        if lvl > entry and (lvl - entry) / risk >= min_r:
            return float(lvl)
    else:
        lvl = swing_lo
        if lvl < entry and (entry - lvl) / risk >= min_r:
            return float(lvl)
    return None


def generate_candidates(
    df5: pd.DataFrame,
    *,
    trigger: str,
    window: str,
    confirmation: str,
    min_stop_atr: float = 0.45,
    require_rejection_for_pullback: bool = False,
    zone_atr: float = 0.25,
    stop_atr: float = 0.40,
    vwap_buffer_atr: float = 0.10,
    sides: tuple[str, ...] = ("BUY", "SELL"),
    cooldown_bars: int = 8,
) -> list[dict[str, Any]]:
    """Generate setup candidates on 5m bars (no exits yet). NumPy-fast path."""
    out: list[dict[str, Any]] = []
    n = len(df5)
    if n < 80:
        return out

    idx = df5.index
    minutes = (idx.hour * 60 + idx.minute).astype(np.int32)
    lo_m, hi_m = SESSION_WINDOWS[window]
    in_sess = (minutes >= lo_m) & (minutes < hi_m)

    o = df5["open"].to_numpy(dtype=float)
    h = df5["high"].to_numpy(dtype=float)
    l = df5["low"].to_numpy(dtype=float)
    c = df5["close"].to_numpy(dtype=float)
    a = df5["atr"].to_numpy(dtype=float)
    vwap = df5["vwap"].to_numpy(dtype=float)
    e20 = df5["ema20"].to_numpy(dtype=float)
    e50 = df5["ema50"].to_numpy(dtype=float)
    d15 = df5["dir_15m"].to_numpy(dtype=float)
    d1h = df5["dir_1h"].to_numpy(dtype=float)
    pdl = df5["pdl"].to_numpy(dtype=float)
    pdh = df5["pdh"].to_numpy(dtype=float)
    sess_lo = df5["session_low"].to_numpy(dtype=float)
    sess_hi = df5["session_high"].to_numpy(dtype=float)
    sw_lo = df5["swing_low"].to_numpy(dtype=float)
    sw_hi = df5["swing_high"].to_numpy(dtype=float)

    # Breakout levels: structure from bars [i-18, i-7), break hunt in [i-6, i), retest at i
    roll_hi = pd.Series(h).rolling(12, min_periods=12).max().shift(7).to_numpy()
    roll_lo = pd.Series(l).rolling(12, min_periods=12).min().shift(7).to_numpy()
    close_s = pd.Series(c)
    max_c6 = close_s.rolling(6, min_periods=1).max().shift(1).to_numpy()
    min_c6 = close_s.rolling(6, min_periods=1).min().shift(1).to_numpy()

    i = 60
    while i < n - 3:
        if not in_sess[i] or not np.isfinite(a[i]) or a[i] <= 0:
            i += 1
            continue
        ai = a[i]
        side = None
        stop = None

        if trigger == "PULLBACK":
            zone_lo = e20[i] - zone_atr * ai
            zone_hi = e20[i] + zone_atr * ai
            if (
                "BUY" in sides
                and d15[i] > 0
                and d1h[i] > 0
                and e20[i] > e50[i]
                and c[i] >= vwap[i] - vwap_buffer_atr * ai
                and np.isfinite(vwap[i])
            ):
                touched = zone_lo <= l[i] <= zone_hi or zone_lo <= c[i] <= zone_hi
                if touched:
                    side, stop = "BUY", min(l[i], e20[i]) - stop_atr * ai
            elif (
                "SELL" in sides
                and d15[i] < 0
                and d1h[i] < 0
                and e20[i] < e50[i]
                and c[i] <= vwap[i] + vwap_buffer_atr * ai
                and np.isfinite(vwap[i])
            ):
                touched = zone_lo <= h[i] <= zone_hi or zone_lo <= c[i] <= zone_hi
                if touched:
                    side, stop = "SELL", max(h[i], e20[i]) + stop_atr * ai

        elif trigger == "LIQUIDITY":
            levels_lo = [x for x in (pdl[i], sess_lo[i], sw_lo[i]) if np.isfinite(x)]
            levels_hi = [x for x in (pdh[i], sess_hi[i], sw_hi[i]) if np.isfinite(x)]
            swept_lo = any(l[i] < lvl <= c[i] for lvl in levels_lo)
            swept_hi = any(h[i] > lvl >= c[i] for lvl in levels_hi)
            # Stronger context filter
            if "BUY" in sides and swept_lo and d1h[i] > 0 and d15[i] >= 0:
                side, stop = "BUY", min(levels_lo) - 0.5 * ai
            elif "SELL" in sides and swept_hi and d1h[i] < 0 and d15[i] <= 0:
                side, stop = "SELL", max(levels_hi) + 0.5 * ai

        elif trigger == "BREAKOUT_RETEST":
            level_hi, level_lo = roll_hi[i], roll_lo[i]
            if not (np.isfinite(level_hi) and np.isfinite(level_lo)):
                i += 1
                continue
            broke_up = bool(max_c6[i] > level_hi) if np.isfinite(max_c6[i]) else False
            broke_dn = bool(min_c6[i] < level_lo) if np.isfinite(min_c6[i]) else False
            if (
                "BUY" in sides
                and broke_up
                and l[i] <= level_hi + 0.15 * ai
                and c[i] >= level_hi
                and c[i] > o[i]
                and d1h[i] > 0
            ):
                side, stop = "BUY", level_hi - 0.6 * ai
            elif (
                "SELL" in sides
                and broke_dn
                and h[i] >= level_lo - 0.15 * ai
                and c[i] <= level_lo
                and c[i] < o[i]
                and d1h[i] < 0
            ):
                side, stop = "SELL", level_lo + 0.6 * ai

        if side is None or stop is None:
            i += 1
            continue

        # Minimum stop distance in ATR — avoid noise stops
        if abs(c[i] - stop) < min_stop_atr * ai:
            i += 1
            continue

        conf = confirmation
        if require_rejection_for_pullback and trigger == "PULLBACK":
            conf = "rejection_wick"

        # confirmations (inline for speed)
        entry_i = None
        if conf == "signal_close":
            if (side == "BUY" and c[i] >= o[i]) or (side == "SELL" and c[i] <= o[i]):
                entry_i = i
        elif conf == "next_bar":
            j = i + 1
            if (side == "BUY" and c[j] > o[j]) or (side == "SELL" and c[j] < o[j]):
                entry_i = j
        elif conf == "rejection_wick":
            if side == "BUY" and _rejection_long(o[i], h[i], l[i], c[i]):
                entry_i = i
            elif side == "SELL" and _rejection_short(o[i], h[i], l[i], c[i]):
                entry_i = i
        elif conf == "engulf" and i >= 1:
            if side == "BUY" and _engulf_long(o[i - 1], c[i - 1], o[i], c[i]):
                entry_i = i
            elif side == "SELL" and _engulf_short(o[i - 1], c[i - 1], o[i], c[i]):
                entry_i = i
        elif conf == "break_prior_hl" and i >= 1:
            if side == "BUY" and c[i] > h[i - 1]:
                entry_i = i
            elif side == "SELL" and c[i] < l[i - 1]:
                entry_i = i

        if entry_i is None:
            i += 1
            continue
        entry = float(c[entry_i])
        if abs(entry - stop) < max(0.25, min_stop_atr * ai * 0.5):
            i += 1
            continue
        vw = float(vwap[entry_i]) if np.isfinite(vwap[entry_i]) else entry
        out.append(
            {
                "trigger": trigger,
                "side": side,
                "signal_i": i,
                "entry_i": entry_i,
                "entry_ts": idx[entry_i],
                "entry": entry,
                "stop": float(stop),
                "session_window": window,
                "confirmation": conf,
                "atr": float(ai),
                "swing_high": float(sw_hi[i]) if np.isfinite(sw_hi[i]) else entry,
                "swing_low": float(sw_lo[i]) if np.isfinite(sw_lo[i]) else entry,
                "dir_15m": float(d15[i]),
                "dir_1h": float(d1h[i]),
                "above_vwap": float(entry >= vw),
                "ema_aligned": float((e20[i] > e50[i]) if side == "BUY" else (e20[i] < e50[i])),
            }
        )
        i = entry_i + int(cooldown_bars)
    return out


def realize_trades(
    candidates: Sequence[dict[str, Any]],
    df_1m: pd.DataFrame,
    *,
    target_r: float | str = 1.5,
    symbol: str = "NQ",
    min_target_r: float = 0.9,
) -> list[NQTrade]:
    trades: list[NQTrade] = []
    if not candidates:
        return trades
    # Pre-extract for faster slicing
    idx = df_1m.index
    high = df_1m["high"].to_numpy(dtype=float)
    low = df_1m["low"].to_numpy(dtype=float)
    close = df_1m["close"].to_numpy(dtype=float)
    for cand in candidates:
        entry, stop = float(cand["entry"]), float(cand["stop"])
        side = cand["side"]
        risk = abs(entry - stop)
        if risk <= 1e-12:
            continue
        if isinstance(target_r, str) and target_r == "structural":
            tgt = _structural_target(
                side, entry, stop, cand["swing_high"], cand["swing_low"], min_r=max(min_target_r, 1.0)
            )
            if tgt is None:
                continue
            style = "structural"
            tr = abs(tgt - entry) / risk
        else:
            tr = float(target_r)
            if tr < min_target_r:
                continue
            tgt = entry + tr * risk if side == "BUY" else entry - tr * risk
            style = f"{tr}R"

        entry_ts = pd.Timestamp(cand["entry_ts"])
        pos = idx.searchsorted(entry_ts, side="right")
        end = min(len(idx), pos + 180)
        if pos >= len(idx):
            pnl, exit_ts = -FRICTION_NQ / risk, str(entry_ts)
        else:
            exit_px = float(close[end - 1])
            exit_ts = str(idx[end - 1])
            for j in range(pos, end):
                hj, lj = high[j], low[j]
                hit_stop = (lj <= stop) if side == "BUY" else (hj >= stop)
                hit_tgt = (hj >= tgt) if side == "BUY" else (lj <= tgt)
                if hit_stop and hit_tgt:
                    exit_px, exit_ts = stop, str(idx[j])
                    break
                if hit_stop:
                    exit_px, exit_ts = stop, str(idx[j])
                    break
                if hit_tgt:
                    exit_px, exit_ts = tgt, str(idx[j])
                    break
            raw = (exit_px - entry) if side == "BUY" else (entry - exit_px)
            pnl = float((raw - FRICTION_NQ) / risk)

        trades.append(
            NQTrade(
                symbol=symbol,
                trigger=cand["trigger"],
                side=side,
                entry_ts=str(cand["entry_ts"]),
                exit_ts=exit_ts,
                pnl_r=pnl,
                session_window=cand["session_window"],
                confirmation=cand["confirmation"],
                exit_style=style,
                target_r=float(tr),
                entry=entry,
                stop=stop,
                target=float(tgt),
                context={
                    "dir_15m": cand["dir_15m"],
                    "dir_1h": cand["dir_1h"],
                    "above_vwap": cand["above_vwap"],
                    "ema_aligned": cand["ema_aligned"],
                },
            )
        )
    return trades


def stats_for(trades: Sequence[NQTrade]) -> dict[str, Any]:
    st = trade_stats([t.pnl_r for t in trades], [t.entry_ts for t in trades])
    longs = [t for t in trades if getattr(t, "side", None) == "BUY"]
    shorts = [t for t in trades if getattr(t, "side", None) == "SELL"]
    st["long_n"] = len(longs)
    st["short_n"] = len(shorts)
    st["long_wr"] = float(np.mean([t.pnl_r > 0 for t in longs])) if longs else 0.0
    st["short_wr"] = float(np.mean([t.pnl_r > 0 for t in shorts])) if shorts else 0.0
    if trades:
        st["session"] = getattr(trades[0], "session_window", None)
        st["trigger"] = getattr(trades[0], "trigger", None)
    return st


def rolling_walk_forward_splits(
    index: pd.DatetimeIndex,
    *,
    n_folds: int = 4,
    holdout_frac: float = 0.20,
) -> dict[str, Any]:
    """Chronological rolling train/val folds + untouched final holdout (newest)."""
    days = pd.DatetimeIndex(sorted(pd.Series(index.normalize().unique())))
    if len(days) < 40:
        n_hold = max(5, int(len(days) * holdout_frac))
    else:
        n_hold = max(20, int(len(days) * holdout_frac))
    holdout_days = set(days[-n_hold:])
    research_days = days[:-n_hold]
    folds = []
    if len(research_days) < n_folds * 5:
        n_folds = max(2, len(research_days) // 10) or 1
    edges = np.linspace(0, len(research_days), n_folds + 1).astype(int)
    for i in range(n_folds):
        # expanding train, next slice validation
        val0, val1 = int(edges[i]), int(edges[i + 1])
        if val1 <= val0:
            continue
        train_set = set(research_days[:val0]) if val0 > 0 else set(research_days[: max(1, val1 // 2)])
        if not train_set:
            # first fold: use 60% of fold as train inside fold
            mid = val0 + max(1, int(0.6 * (val1 - val0)))
            train_set = set(research_days[val0:mid])
            val_set = set(research_days[mid:val1])
        else:
            val_set = set(research_days[val0:val1])
        folds.append({"fold": i + 1, "train_days": train_set, "val_days": val_set})
    return {
        "folds": folds,
        "holdout_days": holdout_days,
        "research_days": set(research_days),
        "n_holdout_days": len(holdout_days),
        "n_research_days": len(research_days),
    }


def _day_key(ts: pd.Timestamp) -> pd.Timestamp:
    t = pd.Timestamp(ts)
    if t.tzinfo is not None:
        return t.tz_convert("America/New_York").normalize()
    return t.normalize()


def filter_by_days(trades: Sequence[NQTrade], days: set) -> list[NQTrade]:
    day_set = {_day_key(d) for d in days}
    return [t for t in trades if _day_key(pd.Timestamp(t.entry_ts)) in day_set]
