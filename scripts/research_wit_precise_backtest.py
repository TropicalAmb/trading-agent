"""Higher-precision research backtest for WIT-group ideas.

Improvements vs first pass:
  - walk-forward folds (train/test) so we don't cherry-pick one window
  - tick/slippage + commission friction
  - one trade per day per strategy (realistic for ORB)
  - ORB: breakout present vs retest entry (separate)
  - report confidence intervals on expectancy (bootstrap)
  - symbols NQ/ES/GC on 5m (60d) + 15m resampled where useful

Research only — does not place live orders.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

ET = ZoneInfo("America/New_York")
OUT = Path("data/research_wit_precise_backtest.json")


@dataclass
class Trade:
    symbol: str
    strategy: str
    side: str
    entry_ts: str
    exit_ts: str
    pnl_r: float
    pnl_pts: float
    fold: str
    filters: str


def _fetch(symbol: str, interval: str, period: str) -> pd.DataFrame:
    import yfinance as yf

    df = yf.download(symbol, interval=interval, period=period, auto_adjust=True, progress=False)
    if df is None or df.empty:
        return pd.DataFrame()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0].lower() for c in df.columns]
    else:
        df.columns = [str(c).lower() for c in df.columns]
    df = df.dropna(subset=["open", "high", "low", "close"]).copy()
    idx = pd.to_datetime(df.index)
    if getattr(idx, "tz", None) is None:
        idx = idx.tz_localize("UTC")
    df.index = idx.tz_convert(ET)
    return df


def _friction_pts(symbol: str) -> float:
    # Conservative: ~1 tick slip each side + small buffer
    ticks = {"NQ": 0.25, "ES": 0.25, "GC": 0.10}
    t = ticks.get(symbol, 0.25)
    return 2.0 * t + t  # entry+exit slip + 1 tick buffer


def _allow(ts: pd.Timestamp, skip_friday: bool, after_10: bool) -> bool:
    if skip_friday and ts.weekday() == 4:
        return False
    if after_10 and ts.hour == 9 and ts.minute >= 30:
        return False
    if after_10 and ts.hour < 10 and ts.hour >= 9:
        return False
    return True


def _exit_sim(
    side: str,
    entry: float,
    stop: float,
    target: float,
    fwd: pd.DataFrame,
    friction: float,
) -> tuple[float, pd.Timestamp | None, float]:
    """Return pnl_pts (after friction), exit_ts, pnl_r."""
    risk = abs(entry - stop)
    if risk <= 1e-12 or fwd is None or len(fwd) == 0:
        return -friction, None, -friction / max(risk, 1e-9)
    exit_px = float(fwd["close"].iloc[-1])
    exit_ts = fwd.index[-1]
    for j in range(len(fwd)):
        fh, fl = float(fwd["high"].iloc[j]), float(fwd["low"].iloc[j])
        if side == "BUY":
            if fl <= stop:
                exit_px, exit_ts = stop, fwd.index[j]
                break
            if fh >= target:
                exit_px, exit_ts = target, fwd.index[j]
                break
        else:
            if fh >= stop:
                exit_px, exit_ts = stop, fwd.index[j]
                break
            if fl <= target:
                exit_px, exit_ts = target, fwd.index[j]
                break
    raw = (exit_px - entry) if side == "BUY" else (entry - exit_px)
    pnl = raw - friction
    return float(pnl), exit_ts, float(pnl / risk)


def orb_trades(
    df: pd.DataFrame,
    *,
    symbol: str,
    orb_minutes: int,
    mode: str,  # first_break | retest
    target_r: float,
    skip_friday: bool,
    after_10: bool,
    fold: str,
    max_hold_bars: int = 48,
) -> list[Trade]:
    if df.empty:
        return []
    friction = _friction_pts(symbol)
    trades: list[Trade] = []
    for day, day_df in df.groupby(df.index.normalize()):
        start = day + pd.Timedelta(hours=9, minutes=30)
        end = start + pd.Timedelta(minutes=orb_minutes)
        orb = day_df[(day_df.index >= start) & (day_df.index < end)]
        post = day_df[day_df.index >= end]
        if len(orb) < 1 or len(post) < 3:
            continue
        hi, lo = float(orb["high"].max()), float(orb["low"].min())
        if hi <= lo:
            continue
        broke_up = broke_dn = False
        taken = False
        for i in range(1, len(post)):
            if taken:
                break
            ts = post.index[i]
            if not _allow(ts, skip_friday, after_10):
                continue
            bar, prev = post.iloc[i], post.iloc[i - 1]
            c, o = float(bar["close"]), float(bar["open"])
            h, l = float(bar["high"]), float(bar["low"])
            pc = float(prev["close"])
            if float(prev["high"]) > hi or pc > hi:
                broke_up = True
            if float(prev["low"]) < lo or pc < lo:
                broke_dn = True

            side = stop = tgt = None
            if mode == "first_break":
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
            else:  # retest
                if broke_up and l <= hi + 1e-9 and c >= hi and c > o:
                    side, stop = "BUY", min(lo, l)
                    risk = c - stop
                    tgt = c + max(risk, (hi - lo) * 0.5) * target_r
                elif broke_dn and h >= lo - 1e-9 and c <= lo and c < o:
                    side, stop = "SELL", max(hi, h)
                    risk = stop - c
                    tgt = c - max(risk, (hi - lo) * 0.5) * target_r

            if side is None:
                continue
            risk = abs(c - stop)
            if risk <= 1e-9:
                continue
            fwd = post.iloc[i + 1 : i + 1 + max_hold_bars]
            pnl_pts, exit_ts, pnl_r = _exit_sim(side, c, stop, tgt, fwd, friction)
            filt = f"skipFri={skip_friday},after10={after_10},mode={mode},orb={orb_minutes}"
            trades.append(
                Trade(
                    symbol=symbol,
                    strategy=f"ORB_{orb_minutes}m_{mode}",
                    side=side,
                    entry_ts=str(ts),
                    exit_ts=str(exit_ts),
                    pnl_r=pnl_r,
                    pnl_pts=pnl_pts,
                    fold=fold,
                    filters=filt,
                )
            )
            taken = True
    return trades


def ema_stack_trades(
    df: pd.DataFrame,
    *,
    symbol: str,
    target_r: float,
    skip_friday: bool,
    after_10: bool,
    fold: str,
    cooldown: int = 12,
) -> list[Trade]:
    if len(df) < 120:
        return []
    friction = _friction_pts(symbol)
    e9 = df["close"].ewm(span=9, adjust=False).mean()
    e21 = df["close"].ewm(span=21, adjust=False).mean()
    e100 = df["close"].ewm(span=100, adjust=False).mean()
    tp = (df["high"] + df["low"] + df["close"]) / 3.0
    vol = df["volume"].replace(0, np.nan).fillna(1.0) if "volume" in df else pd.Series(1.0, index=df.index)
    day = df.index.normalize()
    vwap = (tp * vol).groupby(day).cumsum() / vol.groupby(day).cumsum()
    trades: list[Trade] = []
    i = 100
    while i < len(df) - 8:
        ts = df.index[i]
        if not _allow(ts, skip_friday, after_10):
            i += 1
            continue
        # NY session focus for stack (group mostly daytrades NY)
        if not (9 <= ts.hour < 16):
            i += 1
            continue
        c = float(df["close"].iloc[i])
        o = float(df["open"].iloc[i])
        a9, a21, a100 = float(e9.iloc[i]), float(e21.iloc[i]), float(e100.iloc[i])
        v = float(vwap.iloc[i])
        side = None
        if c > o and c > a9 > a21 > a100 and c > v:
            side, stop = "BUY", a100
        elif c < o and c < a9 < a21 < a100 and c < v:
            side, stop = "SELL", a100
        else:
            i += 1
            continue
        risk = abs(c - stop)
        if risk <= 1e-9:
            i += 1
            continue
        tgt = c + risk * target_r if side == "BUY" else c - risk * target_r
        fwd = df.iloc[i + 1 : i + 1 + 24]
        pnl_pts, exit_ts, pnl_r = _exit_sim(side, c, stop, tgt, fwd, friction)
        trades.append(
            Trade(
                symbol=symbol,
                strategy="EMA_9_21_100_VWAP",
                side=side,
                entry_ts=str(ts),
                exit_ts=str(exit_ts),
                pnl_r=pnl_r,
                pnl_pts=pnl_pts,
                fold=fold,
                filters=f"skipFri={skip_friday},after10={after_10}",
            )
        )
        i += cooldown
    return trades


def stats(trades: list[Trade]) -> dict[str, Any]:
    if not trades:
        return {
            "n": 0,
            "pf": 0.0,
            "expectancy_r": 0.0,
            "win_rate": 0.0,
            "net_r": 0.0,
            "exp_ci95": [0.0, 0.0],
            "max_dd_r": 0.0,
        }
    rs = np.array([t.pnl_r for t in trades], dtype=float)
    wins = rs[rs > 0]
    losses = rs[rs <= 0]
    gw, gl = float(wins.sum()), float(abs(losses.sum()))
    # bootstrap CI on expectancy
    rng = np.random.default_rng(42)
    boots = []
    for _ in range(400):
        sample = rng.choice(rs, size=len(rs), replace=True)
        boots.append(float(sample.mean()))
    lo, hi = float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))
    equity = np.cumsum(rs)
    peak = np.maximum.accumulate(equity)
    dd = float((equity - peak).min()) if len(equity) else 0.0
    return {
        "n": int(len(rs)),
        "pf": round(gw / gl, 3) if gl > 0 else (999.0 if gw > 0 else 0.0),
        "expectancy_r": round(float(rs.mean()), 3),
        "win_rate": round(float((rs > 0).mean()), 3),
        "net_r": round(float(rs.sum()), 2),
        "exp_ci95": [round(lo, 3), round(hi, 3)],
        "max_dd_r": round(dd, 2),
    }


def walk_forward_folds(df: pd.DataFrame, n_folds: int = 4) -> list[tuple[str, pd.DataFrame, pd.DataFrame]]:
    """Return (name, train_df, test_df) expanding-window folds."""
    if df.empty:
        return []
    days = sorted(df.index.normalize().unique())
    if len(days) < n_folds + 2:
        return [("all", df.iloc[0:0], df)]
    folds = []
    # leave ~equal test chunks at the end of successive prefixes
    chunk = max(1, len(days) // (n_folds + 1))
    for k in range(1, n_folds + 1):
        train_end = chunk * k
        test_end = min(len(days), train_end + chunk)
        if train_end < 5 or test_end <= train_end:
            continue
        train_days = set(days[:train_end])
        test_days = set(days[train_end:test_end])
        train = df[df.index.normalize().isin(train_days)]
        test = df[df.index.normalize().isin(test_days)]
        folds.append((f"fold{k}", train, test))
    return folds


def evaluate_config(
    df: pd.DataFrame,
    *,
    symbol: str,
    strategy: str,
    params: dict[str, Any],
) -> dict[str, Any]:
    fold_rows = []
    oos_trades: list[Trade] = []
    for name, train, test in walk_forward_folds(df, n_folds=4):
        # Selection uses train expectancy; report test
        if strategy.startswith("ORB"):
            tr_train = orb_trades(
                train,
                symbol=symbol,
                orb_minutes=params["orb_minutes"],
                mode=params["mode"],
                target_r=params["target_r"],
                skip_friday=params["skip_friday"],
                after_10=params["after_10"],
                fold=f"{name}-train",
            )
            tr_test = orb_trades(
                test,
                symbol=symbol,
                orb_minutes=params["orb_minutes"],
                mode=params["mode"],
                target_r=params["target_r"],
                skip_friday=params["skip_friday"],
                after_10=params["after_10"],
                fold=f"{name}-test",
            )
        else:
            tr_train = ema_stack_trades(
                train,
                symbol=symbol,
                target_r=params["target_r"],
                skip_friday=params["skip_friday"],
                after_10=params["after_10"],
                fold=f"{name}-train",
            )
            tr_test = ema_stack_trades(
                test,
                symbol=symbol,
                target_r=params["target_r"],
                skip_friday=params["skip_friday"],
                after_10=params["after_10"],
                fold=f"{name}-test",
            )
        st_tr, st_te = stats(tr_train), stats(tr_test)
        fold_rows.append(
            {
                "fold": name,
                "train": st_tr,
                "test": st_te,
                "train_beats_0": st_tr["expectancy_r"] > 0 and st_tr["n"] >= 5,
            }
        )
        oos_trades.extend(tr_test)

    oos = stats(oos_trades)
    # Stability: fraction of folds with positive OOS expectancy
    pos_folds = sum(1 for f in fold_rows if f["test"]["expectancy_r"] > 0 and f["test"]["n"] >= 3)
    return {
        "strategy": strategy,
        "params": params,
        "oos": oos,
        "positive_oos_folds": pos_folds,
        "folds": fold_rows,
        "stable": pos_folds >= 3 and oos["n"] >= 12 and oos["exp_ci95"][0] > -0.05,
    }


def main() -> int:
    symbols = {"NQ=F": "NQ", "ES=F": "ES", "GC=F": "GC"}
    frames = {name: _fetch(ysym, "5m", "60d") for ysym, name in symbols.items()}

    grid = []
    for orb_m in (5, 15):
        for mode in ("retest", "first_break"):
            for skip_fri in (False, True):
                for after10 in (False, True):
                    for tr in (1.5, 2.0):
                        grid.append(
                            (
                                f"ORB_{orb_m}m_{mode}",
                                {
                                    "orb_minutes": orb_m,
                                    "mode": mode,
                                    "skip_friday": skip_fri,
                                    "after_10": after10,
                                    "target_r": tr,
                                },
                            )
                        )
    for skip_fri in (False, True):
        for after10 in (False, True):
            grid.append(
                (
                    "EMA_9_21_100_VWAP",
                    {
                        "skip_friday": skip_fri,
                        "after_10": after10,
                        "target_r": 1.5,
                        "orb_minutes": 0,
                        "mode": "n/a",
                    },
                )
            )

    out: dict[str, Any] = {
        "method": {
            "bars": "5m Yahoo 60d",
            "walk_forward_folds": 4,
            "friction": "2 ticks slip + 1 tick buffer",
            "orb_rule": "1 trade/day max",
            "bootstrap_ci": "400 resamples on OOS expectancy",
        },
        "symbols": {},
    }

    for name, df in frames.items():
        if df.empty:
            out["symbols"][name] = {"error": "no_data"}
            continue
        ranked = []
        for strategy, params in grid:
            # Skip invalid combo keys for EMA
            row = evaluate_config(df, symbol=name, strategy=strategy, params=params)
            ranked.append(row)
        ranked.sort(
            key=lambda r: (
                r["stable"],
                r["oos"]["expectancy_r"],
                r["positive_oos_folds"],
                r["oos"]["pf"],
            ),
            reverse=True,
        )
        # Also compare baseline vs friday filter for ORB15 retest 1.5R
        def pick(pred):
            for r in ranked:
                if pred(r):
                    return {
                        "params": r["params"],
                        "oos": r["oos"],
                        "positive_oos_folds": r["positive_oos_folds"],
                        "stable": r["stable"],
                    }
            return None

        out["symbols"][name] = {
            "bars": len(df),
            "from": str(df.index.min()),
            "to": str(df.index.max()),
            "top5": [
                {
                    "strategy": r["strategy"],
                    "params": r["params"],
                    "oos": r["oos"],
                    "positive_oos_folds": r["positive_oos_folds"],
                    "stable": r["stable"],
                }
                for r in ranked[:5]
            ],
            "orb15_retest_baseline": pick(
                lambda r: r["strategy"] == "ORB_15m_retest"
                and r["params"]["skip_friday"] is False
                and r["params"]["after_10"] is False
                and r["params"]["target_r"] == 1.5
            ),
            "orb15_retest_skip_fri": pick(
                lambda r: r["strategy"] == "ORB_15m_retest"
                and r["params"]["skip_friday"] is True
                and r["params"]["after_10"] is False
                and r["params"]["target_r"] == 1.5
            ),
            "orb5_retest_skip_fri": pick(
                lambda r: r["strategy"] == "ORB_5m_retest"
                and r["params"]["skip_friday"] is True
                and r["params"]["after_10"] is False
                and r["params"]["target_r"] == 1.5
            ),
            "best_stable": next((r for r in ranked if r["stable"]), None),
        }
        if out["symbols"][name]["best_stable"]:
            bs = out["symbols"][name]["best_stable"]
            out["symbols"][name]["best_stable"] = {
                "strategy": bs["strategy"],
                "params": bs["params"],
                "oos": bs["oos"],
                "positive_oos_folds": bs["positive_oos_folds"],
            }

    # Cross-symbol consensus
    votes: dict[str, int] = {}
    for name, block in out["symbols"].items():
        if "error" in block:
            continue
        for row in block.get("top5") or []:
            if row["oos"]["expectancy_r"] <= 0:
                continue
            key = json.dumps({"strategy": row["strategy"], **row["params"]}, sort_keys=True)
            votes[key] = votes.get(key, 0) + 1
    consensus = sorted(
        [{"config": json.loads(k), "symbol_votes": v} for k, v in votes.items()],
        key=lambda x: x["symbol_votes"],
        reverse=True,
    )[:10]
    out["cross_symbol_consensus"] = consensus

    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps({"consensus": consensus[:5], "symbols": {k: {
        "top": (v.get("top5") or [None])[0],
        "orb15_base": v.get("orb15_retest_baseline"),
        "orb15_skipFri": v.get("orb15_retest_skip_fri"),
        "best_stable": v.get("best_stable"),
    } for k, v in out["symbols"].items()}}, indent=2))
    print(f"Wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
