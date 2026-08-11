"""High-confidence research strategy generators — returns trades in R-space only."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np
import pandas as pd

from agent.research.features_ict import (
    atr,
    dealing_range_position,
    displacement_mask,
    fvg_zones,
    mss_after_sweep,
    mtf_direction,
    resample_closes,
    session_vwap,
)


@dataclass
class RTrade:
    symbol: str
    strategy: str
    family: str
    side: str
    entry_ts: str
    pnl_r: float
    session: str
    regime: str
    confirmation: str
    exit_style: str
    target_r: float


def _session_label(ts: pd.Timestamp) -> str:
    h, m = ts.hour, ts.minute
    t = h * 60 + m
    if 18 * 60 <= t or t < 3 * 60:
        return "ASIA"
    if 3 * 60 <= t < 9 * 60 + 30:
        return "LONDON"
    if 9 * 60 + 30 <= t < 11 * 60:
        return "NY_OPEN"
    if 11 * 60 <= t < 14 * 60:
        return "NY_MID"
    if 14 * 60 <= t < 16 * 60:
        return "NY_AFT"
    return "OTHER"


def _regime_label(df: pd.DataFrame, i: int, atr_s: pd.Series) -> str:
    if i < 30:
        return "UNKNOWN"
    window = df.iloc[i - 29 : i + 1]
    a = float(atr_s.iloc[i] or 0)
    if a <= 0:
        return "UNKNOWN"
    net = float(window["close"].iloc[-1] - window["close"].iloc[0])
    rng = float(window["high"].max() - window["low"].min())
    if rng < 1.2 * a:
        return "COMPRESSION"
    if rng > 4.0 * a:
        return "EXPANSION" if abs(net) > 1.5 * a else "HIGH_VOLATILITY"
    if net > 1.2 * a:
        return "TREND_UP"
    if net < -1.2 * a:
        return "TREND_DOWN"
    return "RANGE"


def _exit_r(
    df: pd.DataFrame,
    i: int,
    side: str,
    entry: float,
    stop: float,
    target: float,
    friction: float,
    max_hold: int = 36,
) -> float:
    risk = abs(entry - stop)
    if risk <= 1e-12:
        return 0.0
    fwd = df.iloc[i + 1 : i + 1 + max_hold]
    if fwd.empty:
        return -friction / risk
    exit_px = float(fwd["close"].iloc[-1])
    for j in range(len(fwd)):
        fh, fl = float(fwd["high"].iloc[j]), float(fwd["low"].iloc[j])
        if side == "BUY":
            if fl <= stop:
                exit_px = stop
                break
            if fh >= target:
                exit_px = target
                break
        else:
            if fh >= stop:
                exit_px = stop
                break
            if fl <= target:
                exit_px = target
                break
    raw = (exit_px - entry) if side == "BUY" else (entry - exit_px)
    return float((raw - friction) / risk)


def _friction(symbol: str) -> float:
    ticks = {"NQ": 0.25, "ES": 0.25, "GC": 0.10, "CL": 0.01, "MES": 0.25, "MNQ": 0.25, "MGC": 0.10, "MCL": 0.01}
    t = ticks.get(symbol, 0.25)
    return 2.0 * t + t


def gen_ema_pullback(df: pd.DataFrame, symbol: str, *, target_r: float, confirm: str = "close") -> list[RTrade]:
    if len(df) < 80:
        return []
    e20 = df["close"].ewm(span=20, adjust=False).mean()
    e50 = df["close"].ewm(span=50, adjust=False).mean()
    a = atr(df)
    fr = _friction(symbol)
    out: list[RTrade] = []
    i = 55
    while i < len(df) - 8:
        ts = df.index[i]
        if not (9 <= ts.hour < 16):
            i += 1
            continue
        c, o = float(df["close"].iloc[i]), float(df["open"].iloc[i])
        a20, a50, av = float(e20.iloc[i]), float(e50.iloc[i]), float(a.iloc[i] or 0)
        if av <= 0:
            i += 1
            continue
        side = None
        if a20 > a50 and abs(c - a20) <= 0.55 * av and c >= a20 and c > o:
            side, stop = "BUY", a20 - av
        elif a20 < a50 and abs(c - a20) <= 0.55 * av and c <= a20 and c < o:
            side, stop = "SELL", a20 + av
        else:
            i += 1
            continue
        if confirm == "engulf" and i >= 1:
            prev_o, prev_c = float(df["open"].iloc[i - 1]), float(df["close"].iloc[i - 1])
            if side == "BUY" and not (c > prev_o and o < prev_c and c > o):
                i += 1
                continue
            if side == "SELL" and not (c < prev_o and o > prev_c and c < o):
                i += 1
                continue
        entry = c
        tgt = entry + abs(entry - stop) * target_r if side == "BUY" else entry - abs(entry - stop) * target_r
        pnl = _exit_r(df, i, side, entry, stop, tgt, fr)
        out.append(
            RTrade(
                symbol=symbol,
                strategy=f"EMA20_pb_R{target_r}_{confirm}",
                family="EMA_pullback",
                side=side,
                entry_ts=str(ts),
                pnl_r=pnl,
                session=_session_label(ts),
                regime=_regime_label(df, i, a),
                confirmation=confirm,
                exit_style=f"{target_r}R",
                target_r=target_r,
            )
        )
        i += 16
    return out


def gen_vwap_reclaim(df: pd.DataFrame, symbol: str, *, target_r: float, confirm: str = "close") -> list[RTrade]:
    if len(df) < 60:
        return []
    v = session_vwap(df)
    a = atr(df)
    fr = _friction(symbol)
    out: list[RTrade] = []
    i = 40
    while i < len(df) - 8:
        ts = df.index[i]
        if not (9 <= ts.hour < 16):
            i += 1
            continue
        c, o = float(df["close"].iloc[i]), float(df["open"].iloc[i])
        pc = float(df["close"].iloc[i - 1])
        vv, av = float(v.iloc[i]), float(a.iloc[i] or 0)
        if av <= 0:
            i += 1
            continue
        side = None
        if pc < vv and c > vv and c > o:
            side, stop = "BUY", c - av
        elif pc > vv and c < vv and c < o:
            side, stop = "SELL", c + av
        else:
            i += 1
            continue
        if confirm == "hold" and i + 1 < len(df):
            # wait one bar hold
            i2 = i + 1
            c2 = float(df["close"].iloc[i2])
            if side == "BUY" and c2 < vv:
                i += 1
                continue
            if side == "SELL" and c2 > vv:
                i += 1
                continue
            i = i2
            c = c2
            ts = df.index[i]
        entry = c
        tgt = entry + abs(entry - stop) * target_r if side == "BUY" else entry - abs(entry - stop) * target_r
        pnl = _exit_r(df, i, side, entry, stop, tgt, fr)
        out.append(
            RTrade(
                symbol=symbol,
                strategy=f"VWAP_reclaim_R{target_r}_{confirm}",
                family="VWAP_reclaim",
                side=side,
                entry_ts=str(ts),
                pnl_r=pnl,
                session=_session_label(ts),
                regime=_regime_label(df, i, a),
                confirmation=confirm,
                exit_style=f"{target_r}R",
                target_r=target_r,
            )
        )
        i += 18
    return out


def gen_vwap_rejection(df: pd.DataFrame, symbol: str, *, target_r: float) -> list[RTrade]:
    if len(df) < 60:
        return []
    v = session_vwap(df)
    a = atr(df)
    fr = _friction(symbol)
    out: list[RTrade] = []
    i = 40
    while i < len(df) - 8:
        ts = df.index[i]
        if not (9 <= ts.hour < 16):
            i += 1
            continue
        c, o = float(df["close"].iloc[i]), float(df["open"].iloc[i])
        h, l = float(df["high"].iloc[i]), float(df["low"].iloc[i])
        vv, av = float(v.iloc[i]), float(a.iloc[i] or 0)
        if av <= 0:
            i += 1
            continue
        side = None
        if l < vv <= c and c < o:
            side, stop = "SELL", h + 0.2 * av
        elif h > vv >= c and c > o:
            side, stop = "BUY", l - 0.2 * av
        else:
            i += 1
            continue
        entry = c
        tgt = entry + abs(entry - stop) * target_r if side == "BUY" else entry - abs(entry - stop) * target_r
        pnl = _exit_r(df, i, side, entry, stop, tgt, fr)
        out.append(
            RTrade(
                symbol=symbol,
                strategy=f"VWAP_reject_R{target_r}",
                family="VWAP_rejection",
                side=side,
                entry_ts=str(ts),
                pnl_r=pnl,
                session=_session_label(ts),
                regime=_regime_label(df, i, a),
                confirmation="wick_reject",
                exit_style=f"{target_r}R",
                target_r=target_r,
            )
        )
        i += 12
    return out


def gen_pdh_pdl_sweep(df: pd.DataFrame, symbol: str, *, target_r: float, with_mss: bool) -> list[RTrade]:
    if len(df) < 100:
        return []
    a = atr(df)
    fr = _friction(symbol)
    out: list[RTrade] = []
    days = sorted(df.index.normalize().unique())
    for di in range(1, len(days)):
        prev = df[df.index.normalize() == days[di - 1]]
        cur = df[df.index.normalize() == days[di]]
        if len(prev) < 8 or len(cur) < 12:
            continue
        pdh, pdl = float(prev["high"].max()), float(prev["low"].min())
        swept_hi = swept_lo = False
        taken = False
        for i in range(2, len(cur) - 8):
            if taken:
                break
            ts = cur.index[i]
            if not (9 <= ts.hour < 16):
                continue
            h, l = float(cur["high"].iloc[i]), float(cur["low"].iloc[i])
            c, o = float(cur["close"].iloc[i]), float(cur["open"].iloc[i])
            if h > pdh:
                swept_hi = True
            if l < pdl:
                swept_lo = True
            glob_i = df.index.get_loc(ts)
            if isinstance(glob_i, slice):
                continue
            side = None
            entry_i = glob_i
            if swept_hi and c < pdh and c < o:
                side, stop = "SELL", h + 0.15 * float(a.iloc[glob_i] or 1)
                if with_mss:
                    mss_i = mss_after_sweep(df, sweep_i=glob_i, side="SELL")
                    if mss_i is None:
                        continue
                    entry_i = mss_i
                    c = float(df["close"].iloc[entry_i])
                    stop = max(stop, float(df["high"].iloc[glob_i : entry_i + 1].max()))
                    ts = df.index[entry_i]
            elif swept_lo and c > pdl and c > o:
                side, stop = "BUY", l - 0.15 * float(a.iloc[glob_i] or 1)
                if with_mss:
                    mss_i = mss_after_sweep(df, sweep_i=glob_i, side="BUY")
                    if mss_i is None:
                        continue
                    entry_i = mss_i
                    c = float(df["close"].iloc[entry_i])
                    stop = min(stop, float(df["low"].iloc[glob_i : entry_i + 1].min()))
                    ts = df.index[entry_i]
            else:
                continue
            entry = c
            risk = abs(entry - stop)
            if risk <= 1e-9:
                continue
            tgt = entry + risk * target_r if side == "BUY" else entry - risk * target_r
            pnl = _exit_r(df, entry_i, side, entry, stop, tgt, fr)
            out.append(
                RTrade(
                    symbol=symbol,
                    strategy=f"PDHPDL_sweep{'_MSS' if with_mss else ''}_R{target_r}",
                    family="PDH_PDL_sweep_MSS" if with_mss else "PDH_PDL_sweep",
                    side=side,
                    entry_ts=str(ts),
                    pnl_r=pnl,
                    session=_session_label(ts),
                    regime=_regime_label(df, entry_i, a),
                    confirmation="mss" if with_mss else "reclaim",
                    exit_style=f"{target_r}R",
                    target_r=target_r,
                )
            )
            taken = True
    return out


def gen_fvg_retest(df: pd.DataFrame, symbol: str, *, target_r: float, require_discount: bool) -> list[RTrade]:
    if len(df) < 80:
        return []
    # Sample recent zones only (speed); still deterministic
    zones = fvg_zones(df)
    if len(zones) > 120:
        zones = zones[-120:]
    a = atr(df)
    dr = dealing_range_position(df)
    fr = _friction(symbol)
    out: list[RTrade] = []
    used = set()
    for z in zones:
        zi = z["i"]
        for j in range(zi + 1, min(len(df) - 6, zi + 16)):
            if j in used:
                continue
            ts = df.index[j]
            if not (9 <= ts.hour < 16):
                continue
            c = float(df["close"].iloc[j])
            o = float(df["open"].iloc[j])
            l, h = float(df["low"].iloc[j]), float(df["high"].iloc[j])
            if require_discount:
                pos = float(dr.iloc[j]) if np.isfinite(dr.iloc[j]) else 0.5
                if z["side"] == "BUY" and pos > 0.5:
                    continue
                if z["side"] == "SELL" and pos < 0.5:
                    continue
            hit = False
            if z["side"] == "BUY" and l <= z["top"] and c >= z["bottom"] and c > o:
                hit = True
                stop = z["bottom"] - 0.2 * float(a.iloc[j] or 1)
            elif z["side"] == "SELL" and h >= z["bottom"] and c <= z["top"] and c < o:
                hit = True
                stop = z["top"] + 0.2 * float(a.iloc[j] or 1)
            if not hit:
                continue
            entry = c
            risk = abs(entry - stop)
            if risk <= 1e-9:
                continue
            tgt = entry + risk * target_r if z["side"] == "BUY" else entry - risk * target_r
            pnl = _exit_r(df, j, z["side"], entry, stop, tgt, fr)
            out.append(
                RTrade(
                    symbol=symbol,
                    strategy=f"FVG_retest_R{target_r}{'_disc' if require_discount else ''}",
                    family="FVG_retest",
                    side=z["side"],
                    entry_ts=str(ts),
                    pnl_r=pnl,
                    session=_session_label(ts),
                    regime=_regime_label(df, j, a),
                    confirmation="fvg_retest",
                    exit_style=f"{target_r}R",
                    target_r=target_r,
                )
            )
            used.add(j)
            break
    return out


def gen_sweep_mss_fvg(df: pd.DataFrame, symbol: str, *, target_r: float) -> list[RTrade]:
    """Swing raid → MSS → enter on reclaim (FVG optional via displacement proxy)."""
    if len(df) < 120:
        return []
    a = atr(df)
    fr = _friction(symbol)
    disp = displacement_mask(df, a, body_atr=1.1)
    out: list[RTrade] = []
    i = 40
    while i < len(df) - 30:
        ts = df.index[i]
        if not (9 <= ts.hour < 15):
            i += 1
            continue
        pre = df.iloc[i - 12 : i]
        sh, sl = float(pre["high"].max()), float(pre["low"].min())
        h, l = float(df["high"].iloc[i]), float(df["low"].iloc[i])
        side = None
        if h > sh:
            side = "SELL"
        elif l < sl:
            side = "BUY"
        else:
            i += 1
            continue
        mss_i = mss_after_sweep(df, sweep_i=i, side=side)
        if mss_i is None or not bool(disp.iloc[mss_i]):
            i += 1
            continue
        # enter on next confirming close
        j = mss_i
        c = float(df["close"].iloc[j])
        if side == "BUY":
            stop = float(df["low"].iloc[i : j + 1].min()) - 0.1 * float(a.iloc[j] or 1)
        else:
            stop = float(df["high"].iloc[i : j + 1].max()) + 0.1 * float(a.iloc[j] or 1)
        entry = c
        risk = abs(entry - stop)
        if risk <= 1e-9:
            i = j + 5
            continue
        tgt = entry + risk * target_r if side == "BUY" else entry - risk * target_r
        pnl = _exit_r(df, j, side, entry, stop, tgt, fr)
        out.append(
            RTrade(
                symbol=symbol,
                strategy=f"Sweep_MSS_disp_R{target_r}",
                family="Sweep_MSS_FVG",
                side=side,
                entry_ts=str(df.index[j]),
                pnl_r=pnl,
                session=_session_label(df.index[j]),
                regime=_regime_label(df, j, a),
                confirmation="sweep_mss_displacement",
                exit_style=f"{target_r}R",
                target_r=target_r,
            )
        )
        i = j + 12
    by_day: dict = {}
    for t in out:
        by_day.setdefault(str(t.entry_ts)[:10], t)
    return list(by_day.values())


def gen_mtf_aligned_pullback(
    df: pd.DataFrame, symbol: str, *, target_r: float, need: int = 3
) -> list[RTrade]:
    """EMA pullback only when MTF 15m/1h/4h alignment count >= need (of 3)."""
    if len(df) < 100:
        return []
    base = gen_ema_pullback(df, symbol, target_r=target_r, confirm="close")
    if not base:
        return []
    c15 = resample_closes(df, "15min")
    c1h = resample_closes(df, "1h")
    c4h = resample_closes(df, "4h")
    kept: list[RTrade] = []
    for t in base:
        ts = pd.Timestamp(t.entry_ts)
        if df.index.tz is not None and ts.tzinfo is None:
            ts = ts.tz_localize(df.index.tz)
        # directions as of ts
        d15 = mtf_direction(c15[c15.index <= ts])
        d1h = mtf_direction(c1h[c1h.index <= ts])
        d4h = mtf_direction(c4h[c4h.index <= ts])
        want = 1 if t.side == "BUY" else -1
        score = sum(1 for d in (d15, d1h, d4h) if d == want)
        if score < need:
            continue
        t.strategy = f"MTF{need}_EMA_pb_R{target_r}"
        t.family = "MTF_EMA_pullback"
        t.confirmation = f"mtf_{score}of3"
        kept.append(t)
    return kept


def gen_orb(
    df: pd.DataFrame,
    symbol: str,
    *,
    orb_m: int,
    mode: str,
    target_r: float,
    vwap_align: bool,
) -> list[RTrade]:
    if df.empty:
        return []
    v = session_vwap(df) if vwap_align else None
    a = atr(df)
    fr = _friction(symbol)
    out: list[RTrade] = []
    for day, day_df in df.groupby(df.index.normalize()):
        start = day + pd.Timedelta(hours=9, minutes=30)
        end = start + pd.Timedelta(minutes=orb_m)
        orb = day_df[(day_df.index >= start) & (day_df.index < end)]
        post = day_df[day_df.index >= end]
        if len(orb) < 1 or len(post) < 3:
            continue
        hi, lo = float(orb["high"].max()), float(orb["low"].min())
        broke_up = broke_dn = False
        taken = False
        for i in range(1, len(post)):
            if taken:
                break
            ts = post.index[i]
            if ts.weekday() == 4:
                continue
            bar, prev = post.iloc[i], post.iloc[i - 1]
            c, o = float(bar["close"]), float(bar["open"])
            pc = float(prev["close"])
            if float(prev["high"]) > hi or pc > hi:
                broke_up = True
            if float(prev["low"]) < lo or pc < lo:
                broke_dn = True
            side = None
            if mode == "first_break":
                if (not broke_up) and c > hi and c > o:
                    side, stop = "BUY", lo
                    broke_up = True
                elif (not broke_dn) and c < lo and c < o:
                    side, stop = "SELL", hi
                    broke_dn = True
            else:
                if broke_up and float(bar["low"]) <= hi and c >= hi and c > o:
                    side, stop = "BUY", min(lo, float(bar["low"]))
                elif broke_dn and float(bar["high"]) >= lo and c <= lo and c < o:
                    side, stop = "SELL", max(hi, float(bar["high"]))
            if side is None:
                continue
            if vwap_align and v is not None:
                vv = float(v.reindex(post.index).ffill().iloc[i])
                if side == "BUY" and c < vv:
                    continue
                if side == "SELL" and c > vv:
                    continue
            entry = c
            risk = abs(entry - stop)
            if risk <= 1e-9:
                continue
            tgt = entry + risk * target_r if side == "BUY" else entry - risk * target_r
            # map to global index
            gi = df.index.get_loc(ts)
            if isinstance(gi, slice):
                continue
            pnl = _exit_r(df, int(gi), side, entry, stop, tgt, fr)
            out.append(
                RTrade(
                    symbol=symbol,
                    strategy=f"ORB{orb_m}_{mode}_R{target_r}{'_VWAP' if vwap_align else ''}",
                    family="opening_range",
                    side=side,
                    entry_ts=str(ts),
                    pnl_r=pnl,
                    session=_session_label(ts),
                    regime=_regime_label(df, int(gi), a),
                    confirmation=mode,
                    exit_style=f"{target_r}R",
                    target_r=target_r,
                )
            )
            taken = True
    return out


def gen_trend_continuation(df: pd.DataFrame, symbol: str, *, target_r: float) -> list[RTrade]:
    if len(df) < 80:
        return []
    e20 = df["close"].ewm(span=20, adjust=False).mean()
    a = atr(df)
    fr = _friction(symbol)
    out: list[RTrade] = []
    i = 40
    while i < len(df) - 10:
        ts = df.index[i]
        if not (9 <= ts.hour < 16):
            i += 1
            continue
        av = float(a.iloc[i] or 0)
        if av <= 0:
            i += 1
            continue
        window = df.iloc[i - 10 : i]
        impulse = float(window["close"].iloc[-1] - window["close"].iloc[0])
        c, o = float(df["close"].iloc[i]), float(df["open"].iloc[i])
        a20 = float(e20.iloc[i])
        side = None
        if impulse > 1.0 * av and abs(c - a20) <= 1.1 * av and c > o and c >= a20:
            side, stop = "BUY", c - 0.95 * av
        elif impulse < -1.0 * av and abs(c - a20) <= 1.1 * av and c < o and c <= a20:
            side, stop = "SELL", c + 0.95 * av
        else:
            i += 1
            continue
        entry = c
        tgt = entry + abs(entry - stop) * target_r if side == "BUY" else entry - abs(entry - stop) * target_r
        pnl = _exit_r(df, i, side, entry, stop, tgt, fr)
        out.append(
            RTrade(
                symbol=symbol,
                strategy=f"TrendCont_R{target_r}",
                family="trend_continuation",
                side=side,
                entry_ts=str(ts),
                pnl_r=pnl,
                session=_session_label(ts),
                regime=_regime_label(df, i, a),
                confirmation="shallow_retrace",
                exit_style=f"{target_r}R",
                target_r=target_r,
            )
        )
        i += 14
    return out


def all_generators(*, include_orb: bool = True) -> list[tuple[str, Callable]]:
    """Compact but multi-family grid (kept finite so walk-forward finishes)."""
    gens: list[tuple[str, Callable]] = []
    for tr in (1.0, 1.5, 2.0):
        gens.append((f"EMA_pb_{tr}", lambda df, sym, tr=tr: gen_ema_pullback(df, sym, target_r=tr)))
        gens.append(
            (f"EMA_pb_engulf_{tr}", lambda df, sym, tr=tr: gen_ema_pullback(df, sym, target_r=tr, confirm="engulf"))
        )
        gens.append((f"VWAP_reclaim_{tr}", lambda df, sym, tr=tr: gen_vwap_reclaim(df, sym, target_r=tr)))
        gens.append(
            (
                f"VWAP_reclaim_hold_{tr}",
                lambda df, sym, tr=tr: gen_vwap_reclaim(df, sym, target_r=tr, confirm="hold"),
            )
        )
        gens.append((f"VWAP_reject_{tr}", lambda df, sym, tr=tr: gen_vwap_rejection(df, sym, target_r=tr)))
        gens.append(
            (f"PDHPDL_{tr}", lambda df, sym, tr=tr: gen_pdh_pdl_sweep(df, sym, target_r=tr, with_mss=False))
        )
        gens.append(
            (f"PDHPDL_MSS_{tr}", lambda df, sym, tr=tr: gen_pdh_pdl_sweep(df, sym, target_r=tr, with_mss=True))
        )
        gens.append(
            (f"FVG_{tr}", lambda df, sym, tr=tr: gen_fvg_retest(df, sym, target_r=tr, require_discount=False))
        )
        gens.append(
            (f"FVG_disc_{tr}", lambda df, sym, tr=tr: gen_fvg_retest(df, sym, target_r=tr, require_discount=True))
        )
        gens.append((f"SweepMSSFVG_{tr}", lambda df, sym, tr=tr: gen_sweep_mss_fvg(df, sym, target_r=tr)))
        gens.append(
            (f"MTF2_EMA_{tr}", lambda df, sym, tr=tr: gen_mtf_aligned_pullback(df, sym, target_r=tr, need=2))
        )
        gens.append(
            (f"MTF3_EMA_{tr}", lambda df, sym, tr=tr: gen_mtf_aligned_pullback(df, sym, target_r=tr, need=3))
        )
        gens.append((f"TrendCont_{tr}", lambda df, sym, tr=tr: gen_trend_continuation(df, sym, target_r=tr)))
    if include_orb:
        for tr in (1.0, 1.5, 2.0):
            for orb_m in (5, 15):
                for mode in ("first_break", "retest"):
                    for vw in (True, False):
                        gens.append(
                            (
                                f"ORB{orb_m}_{mode}_vwap{int(vw)}_{tr}",
                                lambda df, sym, orb_m=orb_m, mode=mode, vw=vw, tr=tr: gen_orb(
                                    df, sym, orb_m=orb_m, mode=mode, target_r=tr, vwap_align=vw
                                ),
                            )
                        )
    return gens
