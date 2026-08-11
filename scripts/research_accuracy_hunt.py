"""Multi-strategy accuracy hunt — not ORB-only.

Ranks OOS configs by win rate with floors on expectancy, n, and PF.
Writes data/research_accuracy_hunt.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from research_wit_precise_backtest import (  # noqa: E402
    Trade,
    _allow,
    _exit_sim,
    _fetch,
    _friction_pts,
    ema_stack_trades,
    orb_trades,
    stats,
    walk_forward_folds,
)

OUT = Path("data/research_accuracy_hunt.json")


def _session_vwap(df: pd.DataFrame) -> pd.Series:
    tp = (df["high"] + df["low"] + df["close"]) / 3.0
    vol = df["volume"].replace(0, np.nan).fillna(1.0) if "volume" in df else pd.Series(1.0, index=df.index)
    day = df.index.normalize()
    return (tp * vol).groupby(day).cumsum() / vol.groupby(day).cumsum()


def _atr_series(df: pd.DataFrame, n: int = 14) -> pd.Series:
    prev = df["close"].shift(1)
    tr = pd.concat(
        [
            (df["high"] - df["low"]).abs(),
            (df["high"] - prev).abs(),
            (df["low"] - prev).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.rolling(n).mean()


def orb_vwap_trades(
    df: pd.DataFrame,
    *,
    symbol: str,
    orb_minutes: int,
    mode: str,
    target_r: float,
    skip_friday: bool,
    after_10: bool,
    fold: str,
    require_vwap: bool = True,
    max_hold_bars: int = 48,
) -> list[Trade]:
    """ORB + optional VWAP side filter (long only above VWAP, short only below)."""
    base = orb_trades(
        df,
        symbol=symbol,
        orb_minutes=orb_minutes,
        mode=mode,
        target_r=target_r,
        skip_friday=skip_friday,
        after_10=after_10,
        fold=fold,
        max_hold_bars=max_hold_bars,
    )
    if not require_vwap or not base:
        for t in base:
            t.strategy = f"ORB_{orb_minutes}m_{mode}_raw"
            t.filters += f",targetR={target_r}"
        return base

    vwap = _session_vwap(df)
    kept: list[Trade] = []
    for t in base:
        try:
            ts = pd.Timestamp(t.entry_ts)
            if ts.tzinfo is None and df.index.tz is not None:
                ts = ts.tz_localize(df.index.tz)
            elif ts.tzinfo is not None and df.index.tz is not None:
                ts = ts.tz_convert(df.index.tz)
            loc = df.index.get_indexer([ts], method="nearest")[0]
            if loc < 0:
                continue
            c = float(df["close"].iloc[loc])
            v = float(vwap.iloc[loc])
            if t.side == "BUY" and c < v:
                continue
            if t.side == "SELL" and c > v:
                continue
            t.strategy = f"ORB_{orb_minutes}m_{mode}_VWAP"
            t.filters += f",vwap=1,targetR={target_r}"
            kept.append(t)
        except Exception:
            continue
    return kept


def vwap_reclaim_trades(
    df: pd.DataFrame,
    *,
    symbol: str,
    target_r: float,
    skip_friday: bool,
    after_10: bool,
    fold: str,
    cooldown: int = 18,
) -> list[Trade]:
    """Close crosses back through VWAP with body confirmation; stop beyond swing."""
    if len(df) < 80:
        return []
    friction = _friction_pts(symbol)
    vwap = _session_vwap(df)
    atr = _atr_series(df)
    trades: list[Trade] = []
    i = 40
    while i < len(df) - 10:
        ts = df.index[i]
        if not _allow(ts, skip_friday, after_10) or not (9 <= ts.hour < 16):
            i += 1
            continue
        c = float(df["close"].iloc[i])
        o = float(df["open"].iloc[i])
        pc = float(df["close"].iloc[i - 1])
        v = float(vwap.iloc[i])
        a = float(atr.iloc[i] or 0)
        if not np.isfinite(a) or a <= 0:
            i += 1
            continue
        side = None
        # reclaim up: was below, closes above VWAP with bullish body
        if pc < v and c > v and c > o:
            side, stop = "BUY", c - 1.0 * a
        elif pc > v and c < v and c < o:
            side, stop = "SELL", c + 1.0 * a
        else:
            i += 1
            continue
        risk = abs(c - stop)
        if risk <= 1e-9:
            i += 1
            continue
        tgt = c + risk * target_r if side == "BUY" else c - risk * target_r
        fwd = df.iloc[i + 1 : i + 1 + 30]
        pnl_pts, exit_ts, pnl_r = _exit_sim(side, c, stop, tgt, fwd, friction)
        trades.append(
            Trade(
                symbol=symbol,
                strategy="VWAP_reclaim",
                side=side,
                entry_ts=str(ts),
                exit_ts=str(exit_ts),
                pnl_r=pnl_r,
                pnl_pts=pnl_pts,
                fold=fold,
                filters=f"skipFri={skip_friday},after10={after_10},targetR={target_r}",
            )
        )
        i += cooldown
    return trades


def sweep_reclaim_trades(
    df: pd.DataFrame,
    *,
    symbol: str,
    target_r: float,
    skip_friday: bool,
    after_10: bool,
    fold: str,
) -> list[Trade]:
    """Prior-day high/low sweep then reclaim (fade). Max 1/day."""
    if len(df) < 100:
        return []
    friction = _friction_pts(symbol)
    trades: list[Trade] = []
    days = sorted(df.index.normalize().unique())
    for di in range(1, len(days)):
        prev = df[df.index.normalize() == days[di - 1]]
        cur = df[df.index.normalize() == days[di]]
        if len(prev) < 10 or len(cur) < 10:
            continue
        pdh, pdl = float(prev["high"].max()), float(prev["low"].min())
        swept_hi = swept_lo = False
        taken = False
        for i in range(2, len(cur) - 8):
            if taken:
                break
            ts = cur.index[i]
            if not _allow(ts, skip_friday, after_10) or not (9 <= ts.hour < 16):
                continue
            h = float(cur["high"].iloc[i])
            l = float(cur["low"].iloc[i])
            c = float(cur["close"].iloc[i])
            o = float(cur["open"].iloc[i])
            if h > pdh:
                swept_hi = True
            if l < pdl:
                swept_lo = True
            side = None
            # fade: swept high then close back below PDH
            if swept_hi and c < pdh and c < o:
                side, stop = "SELL", h + (h - c) * 0.1
                risk = stop - c
                tgt = c - risk * target_r
            elif swept_lo and c > pdl and c > o:
                side, stop = "BUY", l - (c - l) * 0.1
                risk = c - stop
                tgt = c + risk * target_r
            else:
                continue
            if risk <= 1e-9:
                continue
            fwd = cur.iloc[i + 1 : i + 1 + 36]
            pnl_pts, exit_ts, pnl_r = _exit_sim(side, c, stop, tgt, fwd, friction)
            trades.append(
                Trade(
                    symbol=symbol,
                    strategy="PDH_PDL_sweep_reclaim",
                    side=side,
                    entry_ts=str(ts),
                    exit_ts=str(exit_ts),
                    pnl_r=pnl_r,
                    pnl_pts=pnl_pts,
                    fold=fold,
                    filters=f"skipFri={skip_friday},after10={after_10},targetR={target_r}",
                )
            )
            taken = True
    return trades


def ema_pullback_trades(
    df: pd.DataFrame,
    *,
    symbol: str,
    target_r: float,
    skip_friday: bool,
    after_10: bool,
    fold: str,
    cooldown: int = 16,
) -> list[Trade]:
    """Trend + pullback to EMA20 with EMA50 stack."""
    if len(df) < 80:
        return []
    friction = _friction_pts(symbol)
    e20 = df["close"].ewm(span=20, adjust=False).mean()
    e50 = df["close"].ewm(span=50, adjust=False).mean()
    atr = _atr_series(df)
    trades: list[Trade] = []
    i = 55
    while i < len(df) - 10:
        ts = df.index[i]
        if not _allow(ts, skip_friday, after_10) or not (9 <= ts.hour < 16):
            i += 1
            continue
        c = float(df["close"].iloc[i])
        o = float(df["open"].iloc[i])
        a20, a50 = float(e20.iloc[i]), float(e50.iloc[i])
        a = float(atr.iloc[i] or 0)
        if not np.isfinite(a) or a <= 0:
            i += 1
            continue
        dist = abs(c - a20)
        side = None
        if a20 > a50 and dist <= 0.55 * a and c > o and c >= a20:
            side, stop = "BUY", a20 - 1.0 * a
        elif a20 < a50 and dist <= 0.55 * a and c < o and c <= a20:
            side, stop = "SELL", a20 + 1.0 * a
        else:
            i += 1
            continue
        risk = abs(c - stop)
        if risk <= 1e-9:
            i += 1
            continue
        tgt = c + risk * target_r if side == "BUY" else c - risk * target_r
        fwd = df.iloc[i + 1 : i + 1 + 28]
        pnl_pts, exit_ts, pnl_r = _exit_sim(side, c, stop, tgt, fwd, friction)
        trades.append(
            Trade(
                symbol=symbol,
                strategy="EMA20_pullback",
                side=side,
                entry_ts=str(ts),
                exit_ts=str(exit_ts),
                pnl_r=pnl_r,
                pnl_pts=pnl_pts,
                fold=fold,
                filters=f"skipFri={skip_friday},after10={after_10},targetR={target_r}",
            )
        )
        i += cooldown
    return trades


def triple_confirm_orb(
    df: pd.DataFrame,
    *,
    symbol: str,
    orb_minutes: int,
    mode: str,
    target_r: float,
    skip_friday: bool,
    after_10: bool,
    fold: str,
) -> list[Trade]:
    """ORB + VWAP side + EMA9>21>100 alignment (3 confirms)."""
    vwap_hits = orb_vwap_trades(
        df,
        symbol=symbol,
        orb_minutes=orb_minutes,
        mode=mode,
        target_r=target_r,
        skip_friday=skip_friday,
        after_10=after_10,
        fold=fold,
        require_vwap=True,
    )
    if not vwap_hits:
        return []
    e9 = df["close"].ewm(span=9, adjust=False).mean()
    e21 = df["close"].ewm(span=21, adjust=False).mean()
    e100 = df["close"].ewm(span=100, adjust=False).mean()
    kept: list[Trade] = []
    for t in vwap_hits:
        try:
            ts = pd.Timestamp(t.entry_ts)
            if ts.tzinfo is None and df.index.tz is not None:
                ts = ts.tz_localize(df.index.tz)
            elif ts.tzinfo is not None and df.index.tz is not None:
                ts = ts.tz_convert(df.index.tz)
            loc = df.index.get_indexer([ts], method="nearest")[0]
            a9, a21, a100 = float(e9.iloc[loc]), float(e21.iloc[loc]), float(e100.iloc[loc])
            if t.side == "BUY" and not (a9 > a21 > a100):
                continue
            if t.side == "SELL" and not (a9 < a21 < a100):
                continue
            t.strategy = f"TRIPLE_ORB_{orb_minutes}m_{mode}"
            t.filters += ",ema_stack=1"
            kept.append(t)
        except Exception:
            continue
    return kept


def oos_book(
    frames: dict[str, pd.DataFrame],
    gen: Callable[..., list[Trade]],
    kwargs: dict[str, Any],
) -> list[Trade]:
    all_t: list[Trade] = []
    for sym, df in frames.items():
        for name, _tr, test in walk_forward_folds(df, n_folds=4):
            all_t.extend(gen(test, symbol=sym, fold=f"{name}-test", **kwargs))
    return all_t


def main() -> int:
    frames = {
        "NQ": _fetch("NQ=F", "5m", "60d"),
        "ES": _fetch("ES=F", "5m", "60d"),
        "GC": _fetch("GC=F", "5m", "60d"),
    }
    configs: list[tuple[str, Callable[..., list[Trade]], dict[str, Any]]] = []

    for orb_m in (5, 15):
        for mode in ("first_break", "retest"):
            for skip_fri in (True, False):
                for tr in (1.0, 1.5, 2.0):
                    configs.append(
                        (
                            f"ORB_{orb_m}_{mode}_R{tr}_fri{int(skip_fri)}",
                            orb_trades,
                            {
                                "orb_minutes": orb_m,
                                "mode": mode,
                                "target_r": tr,
                                "skip_friday": skip_fri,
                                "after_10": False,
                            },
                        )
                    )
                    configs.append(
                        (
                            f"ORB_VWAP_{orb_m}_{mode}_R{tr}_fri{int(skip_fri)}",
                            orb_vwap_trades,
                            {
                                "orb_minutes": orb_m,
                                "mode": mode,
                                "target_r": tr,
                                "skip_friday": skip_fri,
                                "after_10": False,
                                "require_vwap": True,
                            },
                        )
                    )
                    configs.append(
                        (
                            f"TRIPLE_{orb_m}_{mode}_R{tr}_fri{int(skip_fri)}",
                            triple_confirm_orb,
                            {
                                "orb_minutes": orb_m,
                                "mode": mode,
                                "target_r": tr,
                                "skip_friday": skip_fri,
                                "after_10": False,
                            },
                        )
                    )

    for skip_fri in (True, False):
        for after10 in (True, False):
            for tr in (1.0, 1.5):
                configs.append(
                    (
                        f"EMA_stack_R{tr}_fri{int(skip_fri)}_a10{int(after10)}",
                        ema_stack_trades,
                        {
                            "target_r": tr,
                            "skip_friday": skip_fri,
                            "after_10": after10,
                        },
                    )
                )
                configs.append(
                    (
                        f"EMA20_pb_R{tr}_fri{int(skip_fri)}_a10{int(after10)}",
                        ema_pullback_trades,
                        {
                            "target_r": tr,
                            "skip_friday": skip_fri,
                            "after_10": after10,
                        },
                    )
                )
                configs.append(
                    (
                        f"VWAP_reclaim_R{tr}_fri{int(skip_fri)}_a10{int(after10)}",
                        vwap_reclaim_trades,
                        {
                            "target_r": tr,
                            "skip_friday": skip_fri,
                            "after_10": after10,
                        },
                    )
                )
                configs.append(
                    (
                        f"SWEEP_reclaim_R{tr}_fri{int(skip_fri)}_a10{int(after10)}",
                        sweep_reclaim_trades,
                        {
                            "target_r": tr,
                            "skip_friday": skip_fri,
                            "after_10": after10,
                        },
                    )
                )

    ranked = []
    for name, gen, kwargs in configs:
        trades = oos_book(frames, gen, kwargs)
        st = stats(trades)
        by_sym: dict[str, Any] = {}
        for sym in frames:
            st_s = stats([t for t in trades if t.symbol == sym])
            if st_s["n"]:
                by_sym[sym] = st_s
        # Accuracy score: prefer WR, but require edge
        qualifies = (
            st["n"] >= 15
            and st["expectancy_r"] > 0
            and st["pf"] >= 1.15
            and st["exp_ci95"][0] > -0.05
        )
        high_acc = qualifies and st["win_rate"] >= 0.62
        ranked.append(
            {
                "name": name,
                "oos": st,
                "by_symbol": by_sym,
                "qualifies_edge": qualifies,
                "high_accuracy": high_acc,
            }
        )

    # Sort: high_accuracy first, then WR, then expectancy
    ranked.sort(
        key=lambda r: (
            r["high_accuracy"],
            r["qualifies_edge"],
            r["oos"]["win_rate"],
            r["oos"]["expectancy_r"],
            r["oos"]["n"],
        ),
        reverse=True,
    )

    top_acc = [r for r in ranked if r["high_accuracy"]][:15]
    top_edge = [r for r in ranked if r["qualifies_edge"]][:15]
    best = top_acc[0] if top_acc else (top_edge[0] if top_edge else ranked[0])

    out = {
        "goal": "Maximize win rate with positive OOS expectancy (multi-strategy, not ORB-only)",
        "floors": {
            "n": 15,
            "expectancy_r": ">0",
            "pf": ">=1.15",
            "high_accuracy_wr": ">=0.62",
        },
        "n_configs_tested": len(ranked),
        "high_accuracy_count": len([r for r in ranked if r["high_accuracy"]]),
        "best": best,
        "top_high_accuracy": top_acc,
        "top_positive_edge": top_edge,
        "note": "If high_accuracy_count=0, no config cleared 62% WR with edge floors — report best WR among +E configs.",
    }
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "n_configs": len(ranked),
                "high_acc_count": out["high_accuracy_count"],
                "best": {
                    "name": best["name"],
                    "oos": best["oos"],
                    "high_accuracy": best["high_accuracy"],
                    "qualifies_edge": best["qualifies_edge"],
                },
                "top5_acc": [
                    {"name": r["name"], "wr": r["oos"]["win_rate"], "E": r["oos"]["expectancy_r"], "n": r["oos"]["n"], "pf": r["oos"]["pf"]}
                    for r in (top_acc or top_edge)[:5]
                ],
            },
            indent=2,
        )
    )
    print("Wrote", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
