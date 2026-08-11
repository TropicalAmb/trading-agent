"""VWAP + Market Structure Shift deep research engine.

Deterministic OHLCV-only event detection + variant filtering.
Research-only — never imported into live decision path.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Iterable

import numpy as np
import pandas as pd

from agent.research.features_ict import (
    atr,
    bearish_fvg_mask,
    bullish_fvg_mask,
    displacement_mask,
    mtf_direction,
    resample_closes,
    session_vwap,
)
from agent.research.hc_strategies import RTrade, _exit_r, _friction, _regime_label, _session_label


@dataclass
class RichEvent:
    """One candidate setup with feature flags for ablation / filtering."""

    symbol: str
    i: int
    entry_ts: str
    side: str
    entry: float
    stop: float
    session: str
    regime: str
    mss_mode: str
    vwap_mode: str
    has_liq_sweep: bool
    has_pdh_pdl: bool
    has_sess_sweep: bool
    has_fvg: bool
    fvg_size_atr: float
    has_fvg_retest: bool
    has_displacement: bool
    mtf15: int
    mtf1h: int
    mtf4h: int
    mtf_score: int
    confirmation: str
    overext_vwap_atr: float
    overext_ema20_atr: float
    overext_struct_atr: float
    ny_window: str
    london_window: str
    ema20_align: bool
    ema50_align: bool
    rejection_candle: bool
    engulfing: bool
    entry_delay_bars: int
    structure_level: float
    atr_at_entry: float
    minute_of_day: int = 0
    pnl_by_r: dict[float, float] = field(default_factory=dict)
    features: dict[str, Any] = field(default_factory=dict)


def _ny_window(ts: pd.Timestamp) -> str:
    t = ts.hour * 60 + ts.minute
    if 4 * 60 <= t < 9 * 60 + 30:
        return "NY_PRE"
    if 9 * 60 + 30 <= t < 10 * 60:
        return "0930_1000"
    if 9 * 60 + 30 <= t < 10 * 60 + 30:
        return "0930_1030"
    if 9 * 60 + 30 <= t < 11 * 60:
        return "0930_1100"
    if 10 * 60 <= t < 11 * 60:
        return "1000_1100"
    if 11 * 60 <= t < 12 * 60:
        return "1100_1200"
    if 9 * 60 + 30 <= t < 16 * 60:
        return "NY_RTH"
    return "OTHER"


def _london_window(ts: pd.Timestamp) -> str:
    t = ts.hour * 60 + ts.minute
    if 3 * 60 <= t < 5 * 60:
        return "LONDON_OPEN"
    if 5 * 60 <= t < 7 * 60:
        return "LONDON_MID"
    if 7 * 60 <= t < 9 * 60 + 30:
        return "LONDON_LATE"
    if 3 * 60 <= t < 9 * 60 + 30:
        return "LONDON"
    return "OTHER"


def _confirmed_swings(df: pd.DataFrame, left: int = 3, right: int = 3) -> tuple[list[tuple[int, float]], list[tuple[int, float]]]:
    """Return lists of (index, price) for confirmed swing highs/lows (no future peek beyond right)."""
    highs: list[tuple[int, float]] = []
    lows: list[tuple[int, float]] = []
    h = df["high"].to_numpy(dtype=float)
    l = df["low"].to_numpy(dtype=float)
    n = len(df)
    for i in range(left, n - right):
        window_h = h[i - left : i + right + 1]
        window_l = l[i - left : i + right + 1]
        if h[i] >= window_h.max() and (window_h == h[i]).sum() == 1:
            highs.append((i, float(h[i])))
        if l[i] <= window_l.min() and (window_l == l[i]).sum() == 1:
            lows.append((i, float(l[i])))
    return highs, lows


def _last_swing_before(
    swings: list[tuple[int, float]], i: int, *, confirm_right: int = 3
) -> tuple[int, float] | None:
    """Only use swings fully confirmed by `confirm_right` bars before current i (no lookahead)."""
    for j in range(len(swings) - 1, -1, -1):
        if swings[j][0] + confirm_right < i:
            return swings[j]
    return None


def _precompute_pdh_pdl(df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """Per-bar prior-day high/low (NaN if unavailable)."""
    n = len(df)
    pdh = np.full(n, np.nan)
    pdl = np.full(n, np.nan)
    days = df.index.normalize()
    day_hl: dict[Any, tuple[float, float]] = {}
    for day, g in df.groupby(days):
        day_hl[day] = (float(g["high"].max()), float(g["low"].min()))
    ordered = sorted(day_hl.keys())
    prev_map: dict[Any, tuple[float, float]] = {}
    for k in range(1, len(ordered)):
        prev_map[ordered[k]] = day_hl[ordered[k - 1]]
    for i, day in enumerate(days):
        if day in prev_map:
            pdh[i], pdl[i] = prev_map[day]
    return pdh, pdl


def _precompute_day_running_hl(df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """Running session-day high/low excluding current bar."""
    n = len(df)
    run_h = np.full(n, np.nan)
    run_l = np.full(n, np.nan)
    h = df["high"].to_numpy(dtype=float)
    l = df["low"].to_numpy(dtype=float)
    days = df.index.normalize()
    cur_day = None
    mh = ml = np.nan
    for i in range(n):
        d = days[i]
        if d != cur_day:
            cur_day = d
            mh = ml = np.nan
        run_h[i] = mh
        run_l[i] = ml
        mh = h[i] if not np.isfinite(mh) else max(mh, h[i])
        ml = l[i] if not np.isfinite(ml) else min(ml, l[i])
    return run_h, run_l


def _precompute_mtf_dirs(df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """As-of each bar: 15m/1h/4h direction without lookahead (last completed bucket)."""
    n = len(df)
    d15 = np.zeros(n, dtype=np.int8)
    d1h = np.zeros(n, dtype=np.int8)
    d4h = np.zeros(n, dtype=np.int8)
    c15 = resample_closes(df, "15min")
    c1h = resample_closes(df, "1h")
    c4h = resample_closes(df, "4h")

    def series_dir_asof(closes: pd.Series) -> np.ndarray:
        out = np.zeros(n, dtype=np.int8)
        if len(closes) < 2:
            return out
        # map each bar timestamp to last closed resampled bar strictly before/equal
        idx = closes.index
        vals = closes.to_numpy(dtype=float)
        j = 1
        for i, ts in enumerate(df.index):
            while j < len(idx) - 1 and idx[j + 1] <= ts:
                j += 1
            while j > 1 and idx[j] > ts:
                j -= 1
            if idx[j] <= ts and j >= 1:
                a, b = vals[j - 1], vals[j]
                out[i] = 1 if b > a else (-1 if b < a else 0)
        return out

    return series_dir_asof(c15), series_dir_asof(c1h), series_dir_asof(c4h)


def detect_mss(
    df: pd.DataFrame,
    i: int,
    side: str,
    *,
    mode: str,
    atr_s: pd.Series,
    sh: list[tuple[int, float]],
    sl: list[tuple[int, float]],
    min_disp_atr: float = 0.35,
) -> tuple[bool, float, int]:
    """Return (ok, structure_level, mss_bar_index). Mode A–F."""
    c = float(df["close"].iloc[i])
    o = float(df["open"].iloc[i])
    h = float(df["high"].iloc[i])
    l = float(df["low"].iloc[i])
    av = float(atr_s.iloc[i] or 0)
    if av <= 0:
        return False, 0.0, i

    if side == "BUY":
        sw = _last_swing_before(sh, i)
        if sw is None:
            return False, 0.0, i
        level = sw[1]
        # short-term opposing: last confirmed swing high in last 12 bars
        recent = [x for x in sh if i - 12 <= x[0] and x[0] + 3 < i]
        st_level = recent[-1][1] if recent else level
        use_level = st_level if mode == "B" else level
        broke_close = c > use_level
        broke_wick = h > use_level
        body_thru = min(o, c) < use_level < max(o, c) and c > o and (c - o) >= min_disp_atr * av
        disp = (c - o) >= min_disp_atr * av and c > o
        if mode == "A":
            ok = broke_close
        elif mode == "B":
            ok = broke_close
        elif mode == "C":
            ok = broke_close
        elif mode == "D":
            ok = body_thru
        elif mode == "E":
            ok = broke_close and disp and (c - use_level) >= min_disp_atr * av
        elif mode == "F":
            # break on prior bar, hold/retest this bar
            if i < 1:
                return False, use_level, i
            pc = float(df["close"].iloc[i - 1])
            ok = pc > use_level and l <= use_level * 1.0001 and c > use_level and c > o
        else:
            ok = broke_close
        return ok, use_level, i
    else:
        sw = _last_swing_before(sl, i)
        if sw is None:
            return False, 0.0, i
        level = sw[1]
        recent = [x for x in sl if i - 12 <= x[0] and x[0] + 3 < i]
        st_level = recent[-1][1] if recent else level
        use_level = st_level if mode == "B" else level
        broke_close = c < use_level
        body_thru = min(o, c) < use_level < max(o, c) and c < o and (o - c) >= min_disp_atr * av
        disp = (o - c) >= min_disp_atr * av and c < o
        if mode == "A":
            ok = broke_close
        elif mode == "B":
            ok = broke_close
        elif mode == "C":
            ok = broke_close
        elif mode == "D":
            ok = body_thru
        elif mode == "E":
            ok = broke_close and disp and (use_level - c) >= min_disp_atr * av
        elif mode == "F":
            if i < 1:
                return False, use_level, i
            pc = float(df["close"].iloc[i - 1])
            ok = pc < use_level and h >= use_level * 0.9999 and c < use_level and c < o
        else:
            ok = broke_close
        return ok, use_level, i


def _vwap_context(
    df: pd.DataFrame,
    i: int,
    side: str,
    v: pd.Series,
    atr_s: pd.Series,
    mode: str,
) -> bool:
    c = float(df["close"].iloc[i])
    o = float(df["open"].iloc[i])
    h = float(df["high"].iloc[i])
    l = float(df["low"].iloc[i])
    pc = float(df["close"].iloc[i - 1])
    vv = float(v.iloc[i])
    av = float(atr_s.iloc[i] or 0)
    if av <= 0 or not np.isfinite(vv):
        return False
    slope = float(v.iloc[i] - v.iloc[max(0, i - 3)])

    if mode == "reclaim":
        if side == "BUY":
            return pc < vv and c > vv and c > o
        return pc > vv and c < vv and c < o
    if mode == "rejection":
        if side == "BUY":
            return h > vv >= c and c > o
        return l < vv <= c and c < o
    if mode == "reclaim_hold":
        if i + 1 >= len(df):
            return False
        if side == "BUY":
            return pc < vv and c > vv and float(df["close"].iloc[i + 1]) >= vv
        return pc > vv and c < vv and float(df["close"].iloc[i + 1]) <= vv
    if mode == "retest":
        # reclaim within last 6 bars, retest now
        for k in range(max(1, i - 6), i):
            pk = float(df["close"].iloc[k - 1])
            ck = float(df["close"].iloc[k])
            vk = float(v.iloc[k])
            if side == "BUY" and pk < vk and ck > vk:
                return l <= vv * 1.001 and c > vv and c > o
            if side == "SELL" and pk > vk and ck < vk:
                return h >= vv * 0.999 and c < vv and c < o
        return False
    if mode == "above_slope":
        if side == "BUY":
            return c > vv and slope > 0
        return c < vv and slope < 0
    if mode == "near":
        dist = abs(c - vv) / av
        if side == "BUY":
            return c >= vv and dist <= 0.75
        return c <= vv and dist <= 0.75
    if mode == "cross_accept":
        if side == "BUY":
            return pc < vv and c > vv and (c - vv) >= 0.15 * av
        return pc > vv and c < vv and (vv - c) >= 0.15 * av
    # default: meaningful interaction
    return abs(c - vv) / av <= 1.25 and ((side == "BUY" and c >= vv) or (side == "SELL" and c <= vv))


def scan_events(
    df: pd.DataFrame,
    symbol: str,
    *,
    mss_modes: Iterable[str] = ("A", "C", "D", "E", "F"),
    vwap_modes: Iterable[str] = ("reclaim", "retest", "rejection", "near", "cross_accept"),
    min_disp_atr: float = 0.35,
) -> list[RichEvent]:
    """Scan bars for VWAP+MSS events. Features computed once per (bar, side)."""
    if len(df) < 80:
        return []
    a = atr(df)
    v = session_vwap(df)
    e20 = df["close"].ewm(span=20, adjust=False).mean()
    e50 = df["close"].ewm(span=50, adjust=False).mean()
    sh, sl = _confirmed_swings(df)
    bull_fvg = bullish_fvg_mask(df).to_numpy()
    bear_fvg = bearish_fvg_mask(df).to_numpy()
    disp = displacement_mask(df, a, body_atr=0.9).to_numpy()
    pdh_arr, pdl_arr = _precompute_pdh_pdl(df)
    run_h, run_l = _precompute_day_running_hl(df)
    mtf15, mtf1h, mtf4h = _precompute_mtf_dirs(df)

    o_arr = df["open"].to_numpy(dtype=float)
    h_arr = df["high"].to_numpy(dtype=float)
    l_arr = df["low"].to_numpy(dtype=float)
    c_arr = df["close"].to_numpy(dtype=float)
    a_arr = a.to_numpy(dtype=float)
    v_arr = v.to_numpy(dtype=float)
    e20_arr = e20.to_numpy(dtype=float)
    e50_arr = e50.to_numpy(dtype=float)

    mss_modes = tuple(mss_modes)
    vwap_modes = tuple(vwap_modes)
    events: list[RichEvent] = []
    cooldown = 0

    for i in range(50, len(df) - 10):
        if cooldown > 0:
            cooldown -= 1
            continue
        ts = df.index[i]
        av = float(a_arr[i] or 0)
        if av <= 0 or not np.isfinite(v_arr[i]):
            continue
        sess = _session_label(ts)
        if sess == "OTHER":
            continue

        c, o, h, l = c_arr[i], o_arr[i], h_arr[i], l_arr[i]
        vv = v_arr[i]
        pc = c_arr[i - 1]
        emitted = False

        for side in ("BUY", "SELL"):
            # cheap VWAP gate: any meaningful interaction
            dist = abs(c - vv) / av
            if dist > 1.5 and not (
                (pc < vv <= c) or (pc > vv >= c) or (l < vv < h)
            ):
                continue

            passing_mss: list[tuple[str, float]] = []
            for mm in mss_modes:
                ok_mss, struct, _ = detect_mss(
                    df, i, side, mode=mm, atr_s=a, sh=sh, sl=sl, min_disp_atr=min_disp_atr
                )
                if ok_mss:
                    passing_mss.append((mm, struct))
            if not passing_mss:
                continue

            passing_vwap = [vm for vm in vwap_modes if _vwap_context(df, i, side, v, a, vm)]
            if not passing_vwap:
                continue

            # shared features for this (i, side)
            look0 = max(0, i - 16)
            if side == "BUY":
                lo_min = float(l_arr[look0:i].min()) if i > look0 else l
                prev_lo = float(l_arr[look0 : i - 1].min()) if i - look0 > 1 else lo_min
                has_liq = lo_min < prev_lo
                has_pdh = bool(np.isfinite(pdl_arr[i]) and lo_min < pdl_arr[i])
                has_ss = bool(np.isfinite(run_l[i]) and lo_min < run_l[i])
            else:
                hi_max = float(h_arr[look0:i].max()) if i > look0 else h
                prev_hi = float(h_arr[look0 : i - 1].max()) if i - look0 > 1 else hi_max
                has_liq = hi_max > prev_hi
                has_pdh = bool(np.isfinite(pdh_arr[i]) and hi_max > pdh_arr[i])
                has_ss = bool(np.isfinite(run_h[i]) and hi_max > run_h[i])

            fvg_ok = False
            fvg_sz = 0.0
            fvg_retest = False
            for k in range(max(2, i - 8), i + 1):
                if side == "BUY" and bull_fvg[k]:
                    bottom, top = h_arr[k - 2], l_arr[k]
                    gap = top - bottom
                    if gap > 0:
                        fvg_ok = True
                        fvg_sz = max(fvg_sz, gap / av)
                        if l <= top and c >= bottom:
                            fvg_retest = True
                if side == "SELL" and bear_fvg[k]:
                    top, bottom = l_arr[k - 2], h_arr[k]
                    gap = top - bottom
                    if gap > 0:
                        fvg_ok = True
                        fvg_sz = max(fvg_sz, gap / av)
                        if h >= bottom and c <= top:
                            fvg_retest = True

            want = 1 if side == "BUY" else -1
            d15, d1h, d4h = int(mtf15[i]), int(mtf1h[i]), int(mtf4h[i])
            mtf_score = int((d15 == want) + (d1h == want) + (d4h == want))
            rng = max(h - l, 1e-12)
            rejection = (side == "BUY" and (min(o, c) - l) >= 0.55 * rng and c > o) or (
                side == "SELL" and (h - max(o, c)) >= 0.55 * rng and c < o
            )
            engulf = False
            if i >= 1:
                po, pc_ = o_arr[i - 1], c_arr[i - 1]
                if side == "BUY":
                    engulf = c > po and o < pc_ and c > pc_
                else:
                    engulf = c < po and o > pc_ and c < pc_
            ema_bull = e20_arr[i] > e50_arr[i] and c > e20_arr[i]
            ema_bear = e20_arr[i] < e50_arr[i] and c < e20_arr[i]
            regime = _regime_label(df, i, a)
            nyw = _ny_window(ts)
            lonw = _london_window(ts)

            for mm, struct in passing_mss:
                if side == "BUY":
                    stop = min(float(l_arr[max(0, i - 3) : i + 1].min()), struct) - 0.15 * av
                    if stop >= c:
                        stop = c - av
                else:
                    stop = max(float(h_arr[max(0, i - 3) : i + 1].max()), struct) + 0.15 * av
                    if stop <= c:
                        stop = c + av
                ov_vwap = abs(c - vv) / av
                ov_ema = abs(c - e20_arr[i]) / av
                ov_struct = abs(c - struct) / av
                for vm in passing_vwap:
                    events.append(
                        RichEvent(
                            symbol=symbol,
                            i=i,
                            entry_ts=str(ts),
                            side=side,
                            entry=float(c),
                            stop=float(stop),
                            session=sess,
                            regime=regime,
                            mss_mode=mm,
                            vwap_mode=vm,
                            has_liq_sweep=has_liq,
                            has_pdh_pdl=has_pdh,
                            has_sess_sweep=has_ss,
                            has_fvg=fvg_ok,
                            fvg_size_atr=round(fvg_sz, 4),
                            has_fvg_retest=fvg_retest,
                            has_displacement=bool(disp[i]),
                            mtf15=d15,
                            mtf1h=d1h,
                            mtf4h=d4h,
                            mtf_score=mtf_score,
                            confirmation="mss_close",
                            overext_vwap_atr=round(float(ov_vwap), 4),
                            overext_ema20_atr=round(float(ov_ema), 4),
                            overext_struct_atr=round(float(ov_struct), 4),
                            ny_window=nyw,
                            london_window=lonw,
                            ema20_align=(ema_bull if side == "BUY" else ema_bear),
                            ema50_align=(ema_bull if side == "BUY" else ema_bear),
                            rejection_candle=rejection,
                            engulfing=engulf,
                            entry_delay_bars=0,
                            structure_level=float(struct),
                            atr_at_entry=av,
                            minute_of_day=int(ts.hour * 60 + ts.minute),
                        )
                    )
                    emitted = True
        if emitted:
            cooldown = 2
    return events


def attach_fixed_r_pnls(
    df: pd.DataFrame,
    events: list[RichEvent],
    targets: tuple[float, ...] = (1.0, 1.25, 1.5, 1.75, 2.0, 2.5),
) -> None:
    """Precompute signal-close fixed-R exits once per event (mutates events)."""
    if not events:
        return
    fr = _friction(events[0].symbol)
    # Deduplicate by (i, side, stop, entry) since many mss/vwap mode clones share path
    cache: dict[tuple[int, str, float, float, float], float] = {}
    for ev in events:
        pnls: dict[float, float] = {}
        for tr in targets:
            key = (ev.i, ev.side, round(ev.entry, 6), round(ev.stop, 6), tr)
            if key in cache:
                pnls[tr] = cache[key]
                continue
            risk = abs(ev.entry - ev.stop)
            if risk <= 1e-9:
                pnl = 0.0
            else:
                tgt = ev.entry + risk * tr if ev.side == "BUY" else ev.entry - risk * tr
                pnl = _exit_r(df, ev.i, ev.side, ev.entry, ev.stop, tgt, fr)
            cache[key] = pnl
            pnls[tr] = pnl
        ev.pnl_by_r = pnls


def event_to_trade_fast(ev: RichEvent, *, target_r: float, config_id: str, confirmation: str = "signal_close") -> RTrade | None:
    """Use precomputed pnl_by_r when available."""
    pnl = ev.pnl_by_r.get(float(target_r))
    if pnl is None:
        return None
    return RTrade(
        symbol=ev.symbol,
        strategy=config_id,
        family="vwap_mss",
        side=ev.side,
        entry_ts=ev.entry_ts,
        pnl_r=pnl,
        session=ev.session,
        regime=ev.regime,
        confirmation=confirmation,
        exit_style=f"{target_r}R",
        target_r=target_r,
    )


def event_to_trade(
    df: pd.DataFrame,
    ev: RichEvent,
    *,
    target_r: float,
    config_id: str,
    confirmation: str | None = None,
    entry_mode: str = "signal_close",
) -> RTrade | None:
    """Convert event to RTrade with chosen entry timing + fixed R target."""
    i = ev.i
    side = ev.side
    entry = ev.entry
    stop = ev.stop
    delay = 0
    fr = _friction(ev.symbol)

    if entry_mode == "next_bar":
        if i + 1 >= len(df) - 2:
            return None
        i = i + 1
        entry = float(df["close"].iloc[i])
        delay = 1
    elif entry_mode == "retest_structure":
        level = ev.structure_level
        found = None
        for j in range(i + 1, min(len(df) - 2, i + 8)):
            l = float(df["low"].iloc[j])
            h = float(df["high"].iloc[j])
            c = float(df["close"].iloc[j])
            if side == "BUY" and l <= level and c > level:
                found = j
                break
            if side == "SELL" and h >= level and c < level:
                found = j
                break
        if found is None:
            return None
        delay = found - ev.i
        i = found
        entry = float(df["close"].iloc[i])
    elif entry_mode == "vwap_retest":
        v = session_vwap(df)
        found = None
        for j in range(i + 1, min(len(df) - 2, i + 8)):
            vv = float(v.iloc[j])
            l = float(df["low"].iloc[j])
            h = float(df["high"].iloc[j])
            c = float(df["close"].iloc[j])
            if side == "BUY" and l <= vv and c > vv:
                found = j
                break
            if side == "SELL" and h >= vv and c < vv:
                found = j
                break
        if found is None:
            return None
        delay = found - ev.i
        i = found
        entry = float(df["close"].iloc[i])
    elif entry_mode == "rejection":
        if not ev.rejection_candle:
            return None
    elif entry_mode == "engulfing":
        if not ev.engulfing:
            return None

    risk = abs(entry - stop)
    if risk <= 1e-9:
        return None
    # no-chase hard reject optional via filter, not here
    tgt = entry + risk * target_r if side == "BUY" else entry - risk * target_r
    pnl = _exit_r(df, i, side, entry, stop, tgt, fr)
    return RTrade(
        symbol=ev.symbol,
        strategy=config_id,
        family="vwap_mss",
        side=side,
        entry_ts=str(df.index[i]),
        pnl_r=pnl,
        session=ev.session if delay == 0 else _session_label(df.index[i]),
        regime=ev.regime,
        confirmation=confirmation or entry_mode,
        exit_style=f"{target_r}R",
        target_r=target_r,
    )


def filter_events(events: list[RichEvent], **req: Any) -> list[RichEvent]:
    """Filter events by feature requirements. Missing keys = no filter."""
    out = []
    for e in events:
        ok = True
        if "mss_mode" in req and e.mss_mode != req["mss_mode"]:
            ok = False
        if "vwap_mode" in req and e.vwap_mode != req["vwap_mode"]:
            ok = False
        if req.get("need_liq") and not e.has_liq_sweep:
            ok = False
        if req.get("need_pdh_pdl") and not e.has_pdh_pdl:
            ok = False
        if req.get("need_sess_sweep") and not e.has_sess_sweep:
            ok = False
        if req.get("need_fvg") and not e.has_fvg:
            ok = False
        if req.get("need_fvg_retest") and not e.has_fvg_retest:
            ok = False
        if "min_fvg_atr" in req and e.fvg_size_atr < float(req["min_fvg_atr"]):
            ok = False
        if req.get("need_disp") and not e.has_displacement:
            ok = False
        if "min_mtf" in req and e.mtf_score < int(req["min_mtf"]):
            ok = False
        if req.get("need_reject") and not e.rejection_candle:
            ok = False
        if req.get("need_engulf") and not e.engulfing:
            ok = False
        if req.get("need_ema") and not e.ema20_align:
            ok = False
        if "max_overext" in req and e.overext_vwap_atr > float(req["max_overext"]):
            ok = False
        if "ny_window" in req:
            win = req["ny_window"]
            t = e.minute_of_day
            ranges = {
                "NY_PRE": (4 * 60, 9 * 60 + 30),
                "0930_1000": (9 * 60 + 30, 10 * 60),
                "0930_1030": (9 * 60 + 30, 10 * 60 + 30),
                "0930_1100": (9 * 60 + 30, 11 * 60),
                "1000_1100": (10 * 60, 11 * 60),
                "1100_1200": (11 * 60, 12 * 60),
                "NY_RTH": (9 * 60 + 30, 16 * 60),
            }
            lo, hi = ranges.get(win, (-1, -1))
            if not (lo <= t < hi):
                ok = False
        if "session" in req and e.session != req["session"]:
            ok = False
        if "london_window" in req and e.london_window != req["london_window"]:
            ok = False
        if ok:
            out.append(e)
    return out


def variant_specs() -> list[dict[str, Any]]:
    """Systematic VWAP+MSS variant grid (deep but non-combinatorial explosion)."""
    specs: list[dict[str, Any]] = []
    # Baseline MSS x VWAP x R
    for mm in ("A", "C", "D", "E", "F"):
        for vm in ("reclaim", "retest", "near", "cross_accept"):
            for tr in (1.0, 1.25, 1.5, 2.0):
                specs.append(
                    {
                        "id": f"base_m{mm}_{vm}_R{tr}",
                        "group": "baseline",
                        "mss_mode": mm,
                        "vwap_mode": vm,
                        "target_r": tr,
                        "entry_mode": "signal_close",
                    }
                )
    # Feature stacks on structural defaults (C/E × reclaim/retest × key R) — ablation-friendly IDs
    stacks = [
        ("v1_liq", {"need_liq": True}),
        ("v2_pdh", {"need_pdh_pdl": True}),
        ("v3_sess", {"need_sess_sweep": True}),
        ("v4_fvg", {"need_fvg": True}),
        ("v5_fvg_rt", {"need_fvg_retest": True}),
        ("v6_disp", {"need_disp": True}),
        ("v7_mtf15", {"min_mtf": 1}),
        ("v8_mtf2", {"min_mtf": 2}),
        ("v9_mtf3", {"min_mtf": 3}),
        ("v10_reject", {"need_reject": True}),
        ("v11_engulf", {"need_engulf": True}),
        ("v12_nochase", {"max_overext": 0.75}),
        ("v13_liq_fvg", {"need_liq": True, "need_fvg": True}),
        ("v14_pdh_fvg", {"need_pdh_pdl": True, "need_fvg": True}),
        ("v15_mtf_fvg", {"min_mtf": 2, "need_fvg": True}),
        ("v16_mtf_liq", {"min_mtf": 2, "need_liq": True}),
        ("v17_ema", {"need_ema": True}),
        ("v18_fvg015", {"need_fvg": True, "min_fvg_atr": 0.15}),
        ("v19_tight", {"max_overext": 0.5, "min_mtf": 2}),
        ("v20_quality", {"need_disp": True, "max_overext": 0.75, "min_mtf": 2}),
    ]
    for name, filt in stacks:
        for tr in (1.0, 1.25, 1.5):
            for mm, vm in (("C", "reclaim"), ("C", "retest"), ("E", "reclaim"), ("F", "retest")):
                specs.append(
                    {
                        "id": f"{name}_m{mm}_{vm}_R{tr}",
                        "group": name,
                        "mss_mode": mm,
                        "vwap_mode": vm,
                        "target_r": tr,
                        "entry_mode": "signal_close",
                        **filt,
                    }
                )
    for em in ("next_bar", "retest_structure", "vwap_retest", "rejection", "engulfing"):
        for tr in (1.25, 1.5):
            specs.append(
                {
                    "id": f"entry_{em}_mC_reclaim_R{tr}",
                    "group": "entry_timing",
                    "mss_mode": "C",
                    "vwap_mode": "reclaim",
                    "target_r": tr,
                    "entry_mode": em,
                }
            )
    for win in ("0930_1000", "0930_1030", "0930_1100", "1000_1100", "1100_1200"):
        for tr in (1.0, 1.25, 1.5):
            specs.append(
                {
                    "id": f"ny_{win}_mC_retest_R{tr}",
                    "group": "ny_open",
                    "mss_mode": "C",
                    "vwap_mode": "retest",
                    "target_r": tr,
                    "entry_mode": "signal_close",
                    "ny_window": win,
                    "need_disp": True,
                }
            )
    for win in ("LONDON_OPEN", "LONDON_MID", "LONDON_LATE"):
        for tr in (1.0, 1.25, 1.5):
            specs.append(
                {
                    "id": f"lon_{win}_mC_reclaim_R{tr}",
                    "group": "london",
                    "mss_mode": "C",
                    "vwap_mode": "reclaim",
                    "target_r": tr,
                    "entry_mode": "signal_close",
                    "london_window": win,
                }
            )
    return specs


def events_to_dicts(events: list[RichEvent]) -> list[dict[str, Any]]:
    return [asdict(e) for e in events]
