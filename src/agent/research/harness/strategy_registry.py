"""Strategy family registry — generators return list[RTrade] via hc_strategies + extensions."""

from __future__ import annotations

from typing import Callable

import numpy as np
import pandas as pd

from agent.research.features_ict import atr, mss_after_sweep, mtf_direction, resample_closes, session_vwap
from agent.research.hc_strategies import (
    RTrade,
    _exit_r,
    _friction,
    _regime_label,
    _session_label,
    gen_ema_pullback,
    gen_fvg_retest,
    gen_mtf_aligned_pullback,
    gen_orb,
    gen_pdh_pdl_sweep,
    gen_sweep_mss_fvg,
    gen_trend_continuation,
    gen_vwap_reclaim,
    gen_vwap_rejection,
)


def gen_breakout_retest(df: pd.DataFrame, symbol: str, *, target_r: float) -> list[RTrade]:
    if len(df) < 80:
        return []
    a = atr(df)
    fr = _friction(symbol)
    out: list[RTrade] = []
    i = 40
    while i < len(df) - 12:
        ts = df.index[i]
        if not (9 <= ts.hour < 16):
            i += 1
            continue
        look = df.iloc[i - 12 : i]
        level_hi, level_lo = float(look["high"].max()), float(look["low"].min())
        c, o = float(df["close"].iloc[i]), float(df["open"].iloc[i])
        av = float(a.iloc[i] or 0)
        if av <= 0:
            i += 1
            continue
        # breakout bar
        side = None
        level = None
        if c > level_hi and c > o and abs(c - o) <= 1.25 * av:
            side, level = "BUY", level_hi
        elif c < level_lo and c < o and abs(c - o) <= 1.25 * av:
            side, level = "SELL", level_lo
        else:
            i += 1
            continue
        # retest within next 6 bars
        entered = False
        for j in range(i + 1, min(len(df) - 6, i + 7)):
            cj, oj = float(df["close"].iloc[j]), float(df["open"].iloc[j])
            lj, hj = float(df["low"].iloc[j]), float(df["high"].iloc[j])
            if side == "BUY" and lj <= level + 0.25 * av and cj >= level and cj > oj:
                stop = level - 0.9 * av
            elif side == "SELL" and hj >= level - 0.25 * av and cj <= level and cj < oj:
                stop = level + 0.9 * av
            else:
                continue
            entry = cj
            risk = abs(entry - stop)
            if risk <= 1e-9:
                continue
            tgt = entry + risk * target_r if side == "BUY" else entry - risk * target_r
            pnl = _exit_r(df, j, side, entry, stop, tgt, fr)
            out.append(
                RTrade(
                    symbol=symbol,
                    strategy=f"BreakoutRetest_R{target_r}",
                    family="breakout_retest",
                    side=side,
                    entry_ts=str(df.index[j]),
                    pnl_r=pnl,
                    session=_session_label(df.index[j]),
                    regime=_regime_label(df, j, a),
                    confirmation="retest",
                    exit_style=f"{target_r}R",
                    target_r=target_r,
                )
            )
            entered = True
            i = j + 10
            break
        if not entered:
            i += 1
    return out


def gen_failed_breakout(df: pd.DataFrame, symbol: str, *, target_r: float) -> list[RTrade]:
    if len(df) < 80:
        return []
    a = atr(df)
    fr = _friction(symbol)
    out: list[RTrade] = []
    i = 40
    while i < len(df) - 10:
        ts = df.index[i]
        if not (9 <= ts.hour < 16):
            i += 1
            continue
        look = df.iloc[i - 12 : i]
        level_hi, level_lo = float(look["high"].max()), float(look["low"].min())
        prev = df.iloc[i - 1]
        c, o = float(df["close"].iloc[i]), float(df["open"].iloc[i])
        av = float(a.iloc[i] or 0)
        if av <= 0:
            i += 1
            continue
        side = None
        # failed upside break → short
        if float(prev["high"]) > level_hi and c < level_hi and c < o:
            side, stop = "SELL", float(prev["high"]) + 0.2 * av
        elif float(prev["low"]) < level_lo and c > level_lo and c > o:
            side, stop = "BUY", float(prev["low"]) - 0.2 * av
        else:
            i += 1
            continue
        entry = c
        risk = abs(entry - stop)
        if risk <= 1e-9:
            i += 1
            continue
        tgt = entry + risk * target_r if side == "BUY" else entry - risk * target_r
        pnl = _exit_r(df, i, side, entry, stop, tgt, fr)
        out.append(
            RTrade(
                symbol=symbol,
                strategy=f"FailedBreakout_R{target_r}",
                family="failed_breakout",
                side=side,
                entry_ts=str(ts),
                pnl_r=pnl,
                session=_session_label(ts),
                regime=_regime_label(df, i, a),
                confirmation="failed_break",
                exit_style=f"{target_r}R",
                target_r=target_r,
            )
        )
        i += 12
    return out


def gen_momentum(df: pd.DataFrame, symbol: str, *, target_r: float) -> list[RTrade]:
    if len(df) < 60:
        return []
    a = atr(df)
    e20 = df["close"].ewm(span=20, adjust=False).mean()
    fr = _friction(symbol)
    out: list[RTrade] = []
    i = 40
    while i < len(df) - 8:
        ts = df.index[i]
        if not (9 <= ts.hour < 16):
            i += 1
            continue
        c, o = float(df["close"].iloc[i]), float(df["open"].iloc[i])
        av = float(a.iloc[i] or 0)
        body = abs(c - o)
        if av <= 0 or body < 0.4 * av or body > 1.2 * av:
            i += 1
            continue
        dist = abs(c - float(e20.iloc[i]))
        if dist > 0.6 * av:
            i += 1
            continue
        side = "BUY" if c > o else "SELL"
        stop = c - av if side == "BUY" else c + av
        entry = c
        risk = abs(entry - stop)
        tgt = entry + risk * target_r if side == "BUY" else entry - risk * target_r
        pnl = _exit_r(df, i, side, entry, stop, tgt, fr)
        out.append(
            RTrade(
                symbol=symbol,
                strategy=f"Momentum_R{target_r}",
                family="momentum",
                side=side,
                entry_ts=str(ts),
                pnl_r=pnl,
                session=_session_label(ts),
                regime=_regime_label(df, i, a),
                confirmation="impulse_close",
                exit_style=f"{target_r}R",
                target_r=target_r,
            )
        )
        i += 14
    return out


def gen_supply_demand(df: pd.DataFrame, symbol: str, *, target_r: float) -> list[RTrade]:
    """Proxy: base → impulse departure → return to base zone."""
    if len(df) < 100:
        return []
    a = atr(df)
    fr = _friction(symbol)
    out: list[RTrade] = []
    i = 50
    while i < len(df) - 15:
        ts = df.index[i]
        if not (9 <= ts.hour < 16):
            i += 1
            continue
        av = float(a.iloc[i] or 0)
        if av <= 0:
            i += 1
            continue
        base = df.iloc[i - 8 : i - 2]
        impulse = df.iloc[i - 2 : i + 1]
        base_hi, base_lo = float(base["high"].max()), float(base["low"].min())
        imp_move = float(impulse["close"].iloc[-1] - impulse["close"].iloc[0])
        if abs(imp_move) < 1.2 * av:
            i += 1
            continue
        side = "BUY" if imp_move > 0 else "SELL"
        # wait for return
        for j in range(i + 1, min(len(df) - 6, i + 16)):
            cj, oj = float(df["close"].iloc[j]), float(df["open"].iloc[j])
            lj, hj = float(df["low"].iloc[j]), float(df["high"].iloc[j])
            if side == "BUY" and lj <= base_hi and cj >= base_lo and cj > oj:
                stop = base_lo - 0.3 * av
            elif side == "SELL" and hj >= base_lo and cj <= base_hi and cj < oj:
                stop = base_hi + 0.3 * av
            else:
                continue
            entry = cj
            risk = abs(entry - stop)
            if risk <= 1e-9:
                continue
            tgt = entry + risk * target_r if side == "BUY" else entry - risk * target_r
            pnl = _exit_r(df, j, side, entry, stop, tgt, fr)
            out.append(
                RTrade(
                    symbol=symbol,
                    strategy=f"SupplyDemand_R{target_r}",
                    family="supply_demand",
                    side=side,
                    entry_ts=str(df.index[j]),
                    pnl_r=pnl,
                    session=_session_label(df.index[j]),
                    regime=_regime_label(df, j, a),
                    confirmation="zone_retest",
                    exit_style=f"{target_r}R",
                    target_r=target_r,
                )
            )
            i = j + 12
            break
        else:
            i += 1
    return out


def gen_mss_retest(df: pd.DataFrame, symbol: str, *, target_r: float) -> list[RTrade]:
    if len(df) < 100:
        return []
    a = atr(df)
    fr = _friction(symbol)
    out: list[RTrade] = []
    i = 40
    while i < len(df) - 25:
        ts = df.index[i]
        if not (9 <= ts.hour < 15):
            i += 1
            continue
        pre = df.iloc[i - 12 : i]
        sh, sl = float(pre["high"].max()), float(pre["low"].min())
        h, l = float(df["high"].iloc[i]), float(df["low"].iloc[i])
        if h > sh:
            side = "SELL"
        elif l < sl:
            side = "BUY"
        else:
            i += 1
            continue
        mss_i = mss_after_sweep(df, sweep_i=i, side=side)
        if mss_i is None:
            i += 1
            continue
        level = float(df["close"].iloc[mss_i])
        for j in range(mss_i + 1, min(len(df) - 6, mss_i + 12)):
            cj, oj = float(df["close"].iloc[j]), float(df["open"].iloc[j])
            lj, hj = float(df["low"].iloc[j]), float(df["high"].iloc[j])
            av = float(a.iloc[j] or 0)
            if side == "BUY" and lj <= level and cj >= level and cj > oj:
                stop = float(df["low"].iloc[i : j + 1].min()) - 0.1 * av
            elif side == "SELL" and hj >= level and cj <= level and cj < oj:
                stop = float(df["high"].iloc[i : j + 1].max()) + 0.1 * av
            else:
                continue
            entry = cj
            risk = abs(entry - stop)
            if risk <= 1e-9:
                continue
            tgt = entry + risk * target_r if side == "BUY" else entry - risk * target_r
            pnl = _exit_r(df, j, side, entry, stop, tgt, fr)
            out.append(
                RTrade(
                    symbol=symbol,
                    strategy=f"MSS_retest_R{target_r}",
                    family="mss_retest",
                    side=side,
                    entry_ts=str(df.index[j]),
                    pnl_r=pnl,
                    session=_session_label(df.index[j]),
                    regime=_regime_label(df, j, a),
                    confirmation="mss_retest",
                    exit_style=f"{target_r}R",
                    target_r=target_r,
                )
            )
            i = j + 12
            break
        else:
            i += 1
    return out


def gen_vwap_mss(df: pd.DataFrame, symbol: str, *, target_r: float) -> list[RTrade]:
    """VWAP reclaim then require MSS in same direction."""
    base = gen_vwap_reclaim(df, symbol, target_r=target_r, confirm="close")
    if not base:
        return []
    a = atr(df)
    kept: list[RTrade] = []
    for t in base:
        ts = pd.Timestamp(t.entry_ts)
        if df.index.tz is not None and ts.tzinfo is None:
            ts = ts.tz_localize(df.index.tz)
        loc = df.index.get_indexer([ts], method="nearest")[0]
        if loc < 20:
            continue
        side = t.side
        # look back for sweep+mss shortly before entry
        found = False
        for si in range(max(20, loc - 16), loc):
            pre = df.iloc[si - 12 : si]
            sh, sl = float(pre["high"].max()), float(pre["low"].min())
            if side == "BUY" and float(df["low"].iloc[si]) < sl:
                if mss_after_sweep(df, sweep_i=si, side="BUY") is not None:
                    found = True
                    break
            if side == "SELL" and float(df["high"].iloc[si]) > sh:
                if mss_after_sweep(df, sweep_i=si, side="SELL") is not None:
                    found = True
                    break
        if not found:
            continue
        t.strategy = f"VWAP_MSS_R{target_r}"
        t.family = "vwap_mss"
        t.confirmation = "vwap_reclaim_mss"
        kept.append(t)
    return kept


def gen_fvg_mtf(df: pd.DataFrame, symbol: str, *, target_r: float, need: int = 2) -> list[RTrade]:
    base = gen_fvg_retest(df, symbol, target_r=target_r, require_discount=True)
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
        want = 1 if t.side == "BUY" else -1
        score = sum(
            1
            for s in (
                mtf_direction(c15[c15.index <= ts]),
                mtf_direction(c1h[c1h.index <= ts]),
                mtf_direction(c4h[c4h.index <= ts]),
            )
            if s == want
        )
        if score < need:
            continue
        t.strategy = f"FVG_MTF{need}_R{target_r}"
        t.family = "fvg_mtf"
        t.confirmation = f"fvg_mtf_{score}of3"
        kept.append(t)
    return kept


def gen_orb_failed(df: pd.DataFrame, symbol: str, *, orb_m: int, target_r: float) -> list[RTrade]:
    """Failed ORB: break then close back inside range."""
    if df.empty:
        return []
    a = atr(df)
    fr = _friction(symbol)
    out: list[RTrade] = []
    for day, day_df in df.groupby(df.index.normalize()):
        start = day + pd.Timedelta(hours=9, minutes=30)
        end = start + pd.Timedelta(minutes=orb_m)
        orb = day_df[(day_df.index >= start) & (day_df.index < end)]
        post = day_df[day_df.index >= end]
        if len(orb) < 1 or len(post) < 4:
            continue
        hi, lo = float(orb["high"].max()), float(orb["low"].min())
        taken = False
        for i in range(1, len(post)):
            if taken or post.index[i].weekday() == 4:
                continue
            prev, bar = post.iloc[i - 1], post.iloc[i]
            c, o = float(bar["close"]), float(bar["open"])
            side = None
            if float(prev["high"]) > hi and c < hi and c < o:
                side, stop = "SELL", float(prev["high"])
            elif float(prev["low"]) < lo and c > lo and c > o:
                side, stop = "BUY", float(prev["low"])
            if side is None:
                continue
            entry = c
            risk = abs(entry - stop)
            if risk <= 1e-9:
                continue
            tgt = entry + risk * target_r if side == "BUY" else entry - risk * target_r
            gi = df.index.get_loc(post.index[i])
            if isinstance(gi, slice):
                continue
            pnl = _exit_r(df, int(gi), side, entry, stop, tgt, fr)
            out.append(
                RTrade(
                    symbol=symbol,
                    strategy=f"ORB{orb_m}_failed_R{target_r}",
                    family="orb_failed",
                    side=side,
                    entry_ts=str(post.index[i]),
                    pnl_r=pnl,
                    session=_session_label(post.index[i]),
                    regime=_regime_label(df, int(gi), a),
                    confirmation="failed_orb",
                    exit_style=f"{target_r}R",
                    target_r=target_r,
                )
            )
            taken = True
    return out


GenFn = Callable[[pd.DataFrame, str], list[RTrade]]


def build_registry() -> list[tuple[str, str, GenFn, dict]]:
    """Return (config_id, family, fn, meta) with bounded R targets + confirmations.

    meta documents parameter ranges for audit.
    """
    regs: list[tuple[str, str, GenFn, dict]] = []
    targets = (1.0, 1.5, 2.0)
    for tr in targets:
        meta = {"target_r": tr, "reason": "bounded R grid 1.0/1.5/2.0"}
        regs += [
            (f"liq_sweep_PDHPDL_R{tr}", "liquidity_sweep_reclaim", lambda d, s, tr=tr: gen_pdh_pdl_sweep(d, s, target_r=tr, with_mss=False), meta),
            (f"liq_sweep_MSS_R{tr}", "liquidity_sweep_mss", lambda d, s, tr=tr: gen_pdh_pdl_sweep(d, s, target_r=tr, with_mss=True), meta),
            (f"sweep_MSS_disp_R{tr}", "sweep_mss_fvg", lambda d, s, tr=tr: gen_sweep_mss_fvg(d, s, target_r=tr), meta),
            (f"vwap_reclaim_R{tr}", "vwap_reclaim", lambda d, s, tr=tr: gen_vwap_reclaim(d, s, target_r=tr, confirm="close"), meta),
            (f"vwap_reclaim_hold_R{tr}", "vwap_reclaim", lambda d, s, tr=tr: gen_vwap_reclaim(d, s, target_r=tr, confirm="hold"), meta),
            (f"vwap_reject_R{tr}", "vwap_rejection", lambda d, s, tr=tr: gen_vwap_rejection(d, s, target_r=tr), meta),
            (f"vwap_mss_R{tr}", "vwap_mss", lambda d, s, tr=tr: gen_vwap_mss(d, s, target_r=tr), meta),
            (f"ema_pb_R{tr}", "ema_pullback", lambda d, s, tr=tr: gen_ema_pullback(d, s, target_r=tr, confirm="close"), meta),
            (f"ema_pb_engulf_R{tr}", "ema_pullback", lambda d, s, tr=tr: gen_ema_pullback(d, s, target_r=tr, confirm="engulf"), meta),
            (f"trend_cont_R{tr}", "trend_continuation", lambda d, s, tr=tr: gen_trend_continuation(d, s, target_r=tr), meta),
            (f"breakout_retest_R{tr}", "breakout_retest", lambda d, s, tr=tr: gen_breakout_retest(d, s, target_r=tr), meta),
            (f"failed_break_R{tr}", "failed_breakout", lambda d, s, tr=tr: gen_failed_breakout(d, s, target_r=tr), meta),
            (f"momentum_R{tr}", "momentum", lambda d, s, tr=tr: gen_momentum(d, s, target_r=tr), meta),
            (f"fvg_R{tr}", "fvg_retest", lambda d, s, tr=tr: gen_fvg_retest(d, s, target_r=tr, require_discount=False), meta),
            (f"fvg_disc_R{tr}", "fvg_retest", lambda d, s, tr=tr: gen_fvg_retest(d, s, target_r=tr, require_discount=True), meta),
            (f"fvg_mtf2_R{tr}", "fvg_mtf", lambda d, s, tr=tr: gen_fvg_mtf(d, s, target_r=tr, need=2), meta),
            (f"fvg_mtf3_R{tr}", "fvg_mtf", lambda d, s, tr=tr: gen_fvg_mtf(d, s, target_r=tr, need=3), meta),
            (f"mss_retest_R{tr}", "mss_retest", lambda d, s, tr=tr: gen_mss_retest(d, s, target_r=tr), meta),
            (f"supply_demand_R{tr}", "supply_demand", lambda d, s, tr=tr: gen_supply_demand(d, s, target_r=tr), meta),
            (f"mtf2_ema_R{tr}", "mtf_ema", lambda d, s, tr=tr: gen_mtf_aligned_pullback(d, s, target_r=tr, need=2), meta),
            (f"mtf3_ema_R{tr}", "mtf_ema", lambda d, s, tr=tr: gen_mtf_aligned_pullback(d, s, target_r=tr, need=3), meta),
        ]
        for orb_m in (5, 15):
            for mode in ("first_break", "retest"):
                for vw in (True, False):
                    regs.append(
                        (
                            f"orb{orb_m}_{mode}_vwap{int(vw)}_R{tr}",
                            "opening_range",
                            lambda d, s, orb_m=orb_m, mode=mode, vw=vw, tr=tr: gen_orb(
                                d, s, orb_m=orb_m, mode=mode, target_r=tr, vwap_align=vw
                            ),
                            {**meta, "orb_m": orb_m, "mode": mode, "vwap_align": vw},
                        )
                    )
            regs.append(
                (
                    f"orb{orb_m}_failed_R{tr}",
                    "orb_failed",
                    lambda d, s, orb_m=orb_m, tr=tr: gen_orb_failed(d, s, orb_m=orb_m, target_r=tr),
                    {**meta, "orb_m": orb_m},
                )
            )
    return regs
