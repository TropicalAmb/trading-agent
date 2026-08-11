"""Focused high-WR pass: premarket ORB + wait, tight OR, 1R targets, ES-only."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from research_wit_precise_backtest import (  # noqa: E402
    Trade,
    _allow,
    _exit_sim,
    _fetch,
    _friction_pts,
    stats,
    walk_forward_folds,
)
from research_accuracy_hunt import (  # noqa: E402
    _atr_series,
    _session_vwap,
    orb_vwap_trades,
    triple_confirm_orb,
)

OUT = Path("data/research_high_wr_pass.json")


def premarket_orb_trades(
    df: pd.DataFrame,
    *,
    symbol: str,
    target_r: float,
    skip_friday: bool,
    fold: str,
    wait_minutes: int = 15,
    pm_start_h: int = 4,
    require_vwap: bool = True,
    max_or_atr: float | None = 1.2,
    max_hold_bars: int = 48,
) -> list[Trade]:
    """Premarket range (4:00–9:30) break after NY open + wait_minutes."""
    if df.empty:
        return []
    friction = _friction_pts(symbol)
    vwap = _session_vwap(df)
    atr = _atr_series(df)
    trades: list[Trade] = []
    for day, day_df in df.groupby(df.index.normalize()):
        pm0 = day + pd.Timedelta(hours=pm_start_h)
        ny = day + pd.Timedelta(hours=9, minutes=30)
        entry_open = ny + pd.Timedelta(minutes=wait_minutes)
        pm = day_df[(day_df.index >= pm0) & (day_df.index < ny)]
        post = day_df[day_df.index >= entry_open]
        if len(pm) < 5 or len(post) < 3:
            continue
        hi, lo = float(pm["high"].max()), float(pm["low"].min())
        if hi <= lo:
            continue
        # OR width filter vs ATR at NY open
        if max_or_atr is not None:
            near = day_df[day_df.index <= ny]
            if len(near) < 20:
                continue
            a = float(atr.reindex(near.index).ffill().iloc[-1] or 0)
            if not np.isfinite(a) or a <= 0 or (hi - lo) > max_or_atr * a:
                continue
        broke_up = broke_dn = False
        taken = False
        for i in range(1, len(post)):
            if taken:
                break
            ts = post.index[i]
            if not _allow(ts, skip_friday, after_10=False):
                continue
            if ts.hour >= 16:
                break
            bar, prev = post.iloc[i], post.iloc[i - 1]
            c, o = float(bar["close"]), float(bar["open"])
            pc = float(prev["close"])
            if float(prev["high"]) > hi or pc > hi:
                broke_up = True
            if float(prev["low"]) < lo or pc < lo:
                broke_dn = True
            side = stop = tgt = None
            # first break after wait
            if (not broke_up) and c > hi and c > o:
                side, stop = "BUY", lo
                risk = c - stop
                tgt = c + risk * target_r
                broke_up = True
            elif (not broke_dn) and c < lo and c < o:
                side, stop = "SELL", hi
                risk = stop - c
                tgt = c - risk * target_r
                broke_dn = True
            if side is None:
                continue
            if require_vwap:
                v = float(vwap.reindex(post.index).ffill().iloc[i])
                if side == "BUY" and c < v:
                    continue
                if side == "SELL" and c > v:
                    continue
            risk = abs(c - stop)
            if risk <= 1e-9:
                continue
            fwd = post.iloc[i + 1 : i + 1 + max_hold_bars]
            pnl_pts, exit_ts, pnl_r = _exit_sim(side, c, stop, tgt, fwd, friction)
            trades.append(
                Trade(
                    symbol=symbol,
                    strategy=f"PM_ORB_wait{wait_minutes}",
                    side=side,
                    entry_ts=str(ts),
                    exit_ts=str(exit_ts),
                    pnl_r=pnl_r,
                    pnl_pts=pnl_pts,
                    fold=fold,
                    filters=f"skipFri={skip_friday},vwap={int(require_vwap)},R={target_r},maxOrAtr={max_or_atr}",
                )
            )
            taken = True
    return trades


def ny_orb_wait_trades(
    df: pd.DataFrame,
    *,
    symbol: str,
    orb_minutes: int,
    target_r: float,
    skip_friday: bool,
    fold: str,
    wait_after_orb: int = 15,
    require_vwap: bool = True,
    mode: str = "first_break",
) -> list[Trade]:
    """Classic NY ORB but delay entries until OR end + wait_after_orb."""
    if df.empty:
        return []
    friction = _friction_pts(symbol)
    vwap = _session_vwap(df)
    trades: list[Trade] = []
    for day, day_df in df.groupby(df.index.normalize()):
        start = day + pd.Timedelta(hours=9, minutes=30)
        end = start + pd.Timedelta(minutes=orb_minutes)
        gate = end + pd.Timedelta(minutes=wait_after_orb)
        orb = day_df[(day_df.index >= start) & (day_df.index < end)]
        post = day_df[day_df.index >= gate]
        early = day_df[(day_df.index >= end) & (day_df.index < gate)]
        if len(orb) < 1 or len(post) < 3:
            continue
        hi, lo = float(orb["high"].max()), float(orb["low"].min())
        broke_up = bool(len(early) and (early["high"].max() > hi or early["close"].iloc[-1] > hi))
        broke_dn = bool(len(early) and (early["low"].min() < lo or early["close"].iloc[-1] < lo))
        taken = False
        for i in range(1, len(post)):
            if taken:
                break
            ts = post.index[i]
            if not _allow(ts, skip_friday, after_10=False) or ts.hour >= 16:
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
                # only enter if break happens after wait (not already broken in wait window for first_break purity)
                if (not broke_up) and c > hi and c > o:
                    side, stop = "BUY", lo
                elif (not broke_dn) and c < lo and c < o:
                    side, stop = "SELL", hi
                else:
                    # re-arm: allow retest-style if already broken during wait
                    if broke_up and float(bar["low"]) <= hi and c >= hi and c > o:
                        side, stop = "BUY", min(lo, float(bar["low"]))
                    elif broke_dn and float(bar["high"]) >= lo and c <= lo and c < o:
                        side, stop = "SELL", max(hi, float(bar["high"]))
            else:
                if broke_up and float(bar["low"]) <= hi and c >= hi and c > o:
                    side, stop = "BUY", min(lo, float(bar["low"]))
                elif broke_dn and float(bar["high"]) >= lo and c <= lo and c < o:
                    side, stop = "SELL", max(hi, float(bar["high"]))
            if side is None:
                continue
            if require_vwap:
                v = float(vwap.reindex(post.index).ffill().iloc[i])
                if side == "BUY" and c < v:
                    continue
                if side == "SELL" and c > v:
                    continue
            risk = abs(c - stop)
            if risk <= 1e-9:
                continue
            tgt = c + risk * target_r if side == "BUY" else c - risk * target_r
            if side == "BUY" and (not broke_up) and c > hi:
                broke_up = True
            if side == "SELL" and (not broke_dn) and c < lo:
                broke_dn = True
            fwd = post.iloc[i + 1 : i + 1 + 48]
            pnl_pts, exit_ts, pnl_r = _exit_sim(side, c, stop, tgt, fwd, friction)
            trades.append(
                Trade(
                    symbol=symbol,
                    strategy=f"ORB{orb_minutes}_wait{wait_after_orb}_{mode}",
                    side=side,
                    entry_ts=str(ts),
                    exit_ts=str(exit_ts),
                    pnl_r=pnl_r,
                    pnl_pts=pnl_pts,
                    fold=fold,
                    filters=f"skipFri={skip_friday},vwap={int(require_vwap)},R={target_r}",
                )
            )
            taken = True
    return trades


def book(frames, gen, kwargs):
    out = []
    for sym, df in frames.items():
        for name, _tr, test in walk_forward_folds(df, n_folds=4):
            out.extend(gen(test, symbol=sym, fold=f"{name}-test", **kwargs))
    return out


def main() -> int:
    frames_all = {
        "NQ": _fetch("NQ=F", "5m", "60d"),
        "ES": _fetch("ES=F", "5m", "60d"),
        "GC": _fetch("GC=F", "5m", "60d"),
    }
    frames_es = {"ES": frames_all["ES"]}

    configs = []
    for wait in (15, 0):
        for tr in (1.0, 1.5):
            for vwap in (True, False):
                for max_atr in (1.2, 2.0, None):
                    configs.append(
                        (
                            f"PM_ORB_wait{wait}_R{tr}_vwap{int(vwap)}_atr{max_atr}",
                            frames_all,
                            premarket_orb_trades,
                            {
                                "target_r": tr,
                                "skip_friday": True,
                                "wait_minutes": wait,
                                "require_vwap": vwap,
                                "max_or_atr": max_atr,
                            },
                        )
                    )
    for orb_m in (5, 15):
        for wait in (15,):
            for tr in (1.0, 1.5):
                for mode in ("first_break", "retest"):
                    configs.append(
                        (
                            f"NY_ORB{orb_m}_wait{wait}_{mode}_R{tr}",
                            frames_all,
                            ny_orb_wait_trades,
                            {
                                "orb_minutes": orb_m,
                                "wait_after_orb": wait,
                                "target_r": tr,
                                "skip_friday": True,
                                "require_vwap": True,
                                "mode": mode,
                            },
                        )
                    )
    # ES-only sniper variants
    for tr in (1.0, 1.5):
        configs.append(
            (
                f"ES_TRIPLE_5_fb_R{tr}",
                frames_es,
                triple_confirm_orb,
                {
                    "orb_minutes": 5,
                    "mode": "first_break",
                    "target_r": tr,
                    "skip_friday": True,
                    "after_10": False,
                },
            )
        )
        configs.append(
            (
                f"ES_ORB_VWAP_5_fb_R{tr}",
                frames_es,
                orb_vwap_trades,
                {
                    "orb_minutes": 5,
                    "mode": "first_break",
                    "target_r": tr,
                    "skip_friday": True,
                    "after_10": False,
                    "require_vwap": True,
                },
            )
        )
        configs.append(
            (
                f"ES_PM_ORB_wait15_R{tr}",
                frames_es,
                premarket_orb_trades,
                {
                    "target_r": tr,
                    "skip_friday": True,
                    "wait_minutes": 15,
                    "require_vwap": True,
                    "max_or_atr": 1.2,
                },
            )
        )

    ranked = []
    for name, frames, gen, kwargs in configs:
        trades = book(frames, gen, kwargs)
        st = stats(trades)
        ok = st["n"] >= 12 and st["expectancy_r"] > 0 and st["pf"] >= 1.1
        ranked.append(
            {
                "name": name,
                "oos": st,
                "edge": ok,
                "high_wr": ok and st["win_rate"] >= 0.62,
            }
        )

    ranked.sort(
        key=lambda r: (r["high_wr"], r["edge"], r["oos"]["win_rate"], r["oos"]["expectancy_r"]),
        reverse=True,
    )
    # also absolute highest WR with n>=12 regardless of E
    by_wr = sorted(ranked, key=lambda r: (r["oos"]["n"] >= 12, r["oos"]["win_rate"], r["oos"]["expectancy_r"]), reverse=True)

    out = {
        "source_idea": "FB claim: premarket ORB >90% WR if wait first 15m of NY — tested rigorously OOS",
        "n_configs": len(ranked),
        "high_wr_ge_62_with_edge": [r for r in ranked if r["high_wr"]][:10],
        "best_edge_by_wr": [r for r in ranked if r["edge"]][:10],
        "highest_wr_any": by_wr[:10],
        "best": next((r for r in ranked if r["high_wr"]), None)
        or next((r for r in ranked if r["edge"]), ranked[0]),
    }
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps({
        "n": len(ranked),
        "ge62_edge": len(out["high_wr_ge_62_with_edge"]),
        "best": out["best"],
        "top5_edge": [
            {"name": r["name"], "wr": r["oos"]["win_rate"], "E": r["oos"]["expectancy_r"], "n": r["oos"]["n"], "pf": r["oos"]["pf"]}
            for r in out["best_edge_by_wr"][:5]
        ],
        "top5_wr_any": [
            {"name": r["name"], "wr": r["oos"]["win_rate"], "E": r["oos"]["expectancy_r"], "n": r["oos"]["n"]}
            for r in out["highest_wr_any"][:5]
        ],
    }, indent=2))
    print("Wrote", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
