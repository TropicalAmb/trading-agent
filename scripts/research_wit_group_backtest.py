"""Research backtest: ideas from FB Women in Day Trading group.

NOT wired into live decisions. Paper research only.
Ideas tested:
  - NY ORB 5m / 15m with retest (no first-break chase)
  - EMA 9/21/100 stack + VWAP filter (group-popular entry style)
  - Filters: skip Friday, no entries before 10:00 ET
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import time
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

ET = ZoneInfo("America/New_York")
OUT = Path("data/research_wit_group_backtest.json")


@dataclass
class Trade:
    symbol: str
    strategy: str
    side: str
    entry_ts: str
    exit_ts: str
    entry: float
    exit: float
    pnl_pts: float
    r_multiple: float
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
    df = df.rename(columns={"adj close": "close"})
    df = df.dropna(subset=["open", "high", "low", "close"]).copy()
    idx = pd.to_datetime(df.index)
    if idx.tz is None:
        idx = idx.tz_localize("UTC")
    df.index = idx.tz_convert(ET)
    return df


def _ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False).mean()


def _session_vwap(df: pd.DataFrame) -> pd.Series:
    tp = (df["high"] + df["low"] + df["close"]) / 3.0
    vol = df["volume"].replace(0, np.nan).fillna(1.0)
    day = df.index.normalize()
    return (tp * vol).groupby(day).cumsum() / vol.groupby(day).cumsum()


def _allow(ts: pd.Timestamp, *, skip_friday: bool, after_10: bool) -> bool:
    if skip_friday and ts.weekday() == 4:
        return False
    if after_10 and (ts.hour, ts.minute) < (10, 0):
        # still allow London etc if before NY; only gate NY morning chaos
        if ts.hour >= 9:
            return False
    return True


def backtest_orb(
    df: pd.DataFrame,
    *,
    symbol: str,
    orb_minutes: int,
    open_hhmm: str = "09:30",
    target_r: float = 1.5,
    skip_friday: bool = False,
    after_10: bool = False,
    require_retest: bool = True,
) -> list[Trade]:
    if df.empty or len(df) < 50:
        return []
    oh, om = map(int, open_hhmm.split(":"))
    trades: list[Trade] = []
    # Group by calendar day in ET
    for day, day_df in df.groupby(df.index.normalize()):
        start = day + pd.Timedelta(hours=oh, minutes=om)
        end = start + pd.Timedelta(minutes=orb_minutes)
        orb = day_df[(day_df.index >= start) & (day_df.index < end)]
        post = day_df[day_df.index >= end]
        if len(orb) < 1 or len(post) < 4:
            continue
        hi, lo = float(orb["high"].max()), float(orb["low"].min())
        rng = hi - lo
        if rng <= 0:
            continue
        broke_up = broke_dn = False
        entered = False
        for i in range(1, len(post)):
            bar = post.iloc[i]
            prev = post.iloc[i - 1]
            ts = post.index[i]
            if not _allow(ts, skip_friday=skip_friday, after_10=after_10):
                continue
            if entered:
                break
            c, o = float(bar["close"]), float(bar["open"])
            h, l = float(bar["high"]), float(bar["low"])
            pc = float(prev["close"])
            # First break flags
            if pc > hi:
                broke_up = True
            if pc < lo:
                broke_dn = True
            side = None
            stop = tgt = None
            if require_retest:
                if broke_up and l <= hi and c >= hi and c > o:
                    side = "BUY"
                    stop = lo
                    risk = c - stop
                    tgt = c + risk * target_r
                elif broke_dn and h >= lo and c <= lo and c < o:
                    side = "SELL"
                    stop = hi
                    risk = stop - c
                    tgt = c - risk * target_r
            else:
                if c > hi and c > o and not broke_up:
                    side = "BUY"
                    stop = lo
                    risk = c - stop
                    tgt = c + risk * target_r
                    broke_up = True
                elif c < lo and c < o and not broke_dn:
                    side = "SELL"
                    stop = hi
                    risk = stop - c
                    tgt = c - risk * target_r
                    broke_dn = True
            if side is None or risk <= 0:
                continue
            # Simulate forward within day
            fwd = post.iloc[i + 1 :]
            exit_px = float(fwd["close"].iloc[-1]) if len(fwd) else c
            exit_ts = fwd.index[-1] if len(fwd) else ts
            for j in range(len(fwd)):
                fh, fl = float(fwd["high"].iloc[j]), float(fwd["low"].iloc[j])
                if side == "BUY":
                    if fl <= stop:
                        exit_px, exit_ts = stop, fwd.index[j]
                        break
                    if fh >= tgt:
                        exit_px, exit_ts = tgt, fwd.index[j]
                        break
                else:
                    if fh >= stop:
                        exit_px, exit_ts = stop, fwd.index[j]
                        break
                    if fl <= tgt:
                        exit_px, exit_ts = tgt, fwd.index[j]
                        break
            pnl = (exit_px - c) if side == "BUY" else (c - exit_px)
            r = pnl / risk
            filt = f"skipFri={skip_friday},after10={after_10},retest={require_retest}"
            trades.append(
                Trade(
                    symbol=symbol,
                    strategy=f"ORB_{orb_minutes}m",
                    side=side,
                    entry_ts=str(ts),
                    exit_ts=str(exit_ts),
                    entry=float(c),
                    exit=float(exit_px),
                    pnl_pts=float(pnl),
                    r_multiple=float(r),
                    filters=filt,
                )
            )
            entered = True
    return trades


def backtest_ema_stack(
    df: pd.DataFrame,
    *,
    symbol: str,
    target_r: float = 1.5,
    skip_friday: bool = False,
    after_10: bool = False,
) -> list[Trade]:
    """Group idea: close above/below EMA9/21/100 with VWAP support."""
    if df.empty or len(df) < 120:
        return []
    e9 = _ema(df["close"], 9)
    e21 = _ema(df["close"], 21)
    e100 = _ema(df["close"], 100)
    vwap = _session_vwap(df)
    trades: list[Trade] = []
    i = 100
    while i < len(df) - 6:
        ts = df.index[i]
        if not _allow(ts, skip_friday=skip_friday, after_10=after_10):
            i += 1
            continue
        c = float(df["close"].iloc[i])
        o = float(df["open"].iloc[i])
        a9, a21, a100 = float(e9.iloc[i]), float(e21.iloc[i]), float(e100.iloc[i])
        v = float(vwap.iloc[i])
        side = None
        if c > o and c > a9 > a21 > a100 and c > v:
            side = "BUY"
        elif c < o and c < a9 < a21 < a100 and c < v:
            side = "SELL"
        if side is None:
            i += 1
            continue
        # Stop beyond EMA100; target R
        stop = a100 - (c - a100) * 0.05 if side == "BUY" else a100 + (a100 - c) * 0.05
        risk = abs(c - stop)
        if risk <= 1e-9:
            i += 1
            continue
        tgt = c + risk * target_r if side == "BUY" else c - risk * target_r
        fwd = df.iloc[i + 1 : i + 25]
        exit_px = float(fwd["close"].iloc[-1]) if len(fwd) else c
        exit_ts = fwd.index[-1] if len(fwd) else ts
        for j in range(len(fwd)):
            fh, fl = float(fwd["high"].iloc[j]), float(fwd["low"].iloc[j])
            if side == "BUY":
                if fl <= stop:
                    exit_px, exit_ts = stop, fwd.index[j]
                    break
                if fh >= tgt:
                    exit_px, exit_ts = tgt, fwd.index[j]
                    break
            else:
                if fh >= stop:
                    exit_px, exit_ts = stop, fwd.index[j]
                    break
                if fl <= tgt:
                    exit_px, exit_ts = tgt, fwd.index[j]
                    break
        pnl = (exit_px - c) if side == "BUY" else (c - exit_px)
        trades.append(
            Trade(
                symbol=symbol,
                strategy="EMA_9_21_100_VWAP",
                side=side,
                entry_ts=str(ts),
                exit_ts=str(exit_ts),
                entry=float(c),
                exit=float(exit_px),
                pnl_pts=float(pnl),
                r_multiple=float(pnl / risk),
                filters=f"skipFri={skip_friday},after10={after_10}",
            )
        )
        i += 8  # cooldown bars
    return trades


def summarize(trades: list[Trade]) -> dict[str, Any]:
    if not trades:
        return {"n": 0, "pf": 0, "expectancy_r": 0, "win_rate": 0, "net_r": 0}
    rs = [t.r_multiple for t in trades]
    wins = [r for r in rs if r > 0]
    losses = [r for r in rs if r <= 0]
    gw, gl = sum(wins), abs(sum(losses))
    return {
        "n": len(trades),
        "pf": round(gw / gl, 3) if gl > 0 else (999.0 if gw > 0 else 0.0),
        "expectancy_r": round(sum(rs) / len(rs), 3),
        "win_rate": round(len(wins) / len(rs), 3),
        "net_r": round(sum(rs), 2),
    }


def window_slice(df: pd.DataFrame, days: int) -> pd.DataFrame:
    if df.empty:
        return df
    cutoff = df.index.max() - pd.Timedelta(days=days)
    return df[df.index >= cutoff]


def main() -> int:
    symbols = {"NQ=F": "NQ", "ES=F": "ES", "GC=F": "GC"}
    # 5m ~60d; 1h for longer trend of filters
    frames_5m = {sym: _fetch(sym, "5m", "60d") for sym in symbols}
    frames_1h = {sym: _fetch(sym, "1h", "730d") for sym in symbols}

    results: dict[str, Any] = {"source": "FB Women in Day Trading group research", "windows": {}}

    for label, days, use_1h in (
        ("1w", 7, False),
        ("1m", 30, False),
        ("2m_5m", 60, False),
        ("1y_1h", 365, True),
    ):
        bucket: dict[str, Any] = {}
        frames = frames_1h if use_1h else frames_5m
        for ysym, name in symbols.items():
            df = window_slice(frames.get(ysym, pd.DataFrame()), days)
            if df.empty:
                bucket[name] = {"error": "no_data"}
                continue
            variants = []
            for skip_fri in (False, True):
                for after10 in (False, True):
                    for orb_m in (5, 15):
                        tr = backtest_orb(
                            df,
                            symbol=name,
                            orb_minutes=orb_m,
                            skip_friday=skip_fri,
                            after_10=after10,
                            require_retest=True,
                        )
                        variants.append(
                            {
                                "strategy": f"ORB_{orb_m}m_retest",
                                "skip_friday": skip_fri,
                                "after_10et": after10,
                                **summarize(tr),
                            }
                        )
                    tr_ema = backtest_ema_stack(
                        df,
                        symbol=name,
                        skip_friday=skip_fri,
                        after_10=after10,
                    )
                    variants.append(
                        {
                            "strategy": "EMA_9_21_100_VWAP",
                            "skip_friday": skip_fri,
                            "after_10et": after10,
                            **summarize(tr_ema),
                        }
                    )
            # Rank by expectancy then PF among n>=8
            ranked = sorted(
                [v for v in variants if v["n"] >= 8],
                key=lambda x: (x["expectancy_r"], x["pf"], x["n"]),
                reverse=True,
            )
            bucket[name] = {
                "bars": len(df),
                "from": str(df.index.min()) if len(df) else None,
                "to": str(df.index.max()) if len(df) else None,
                "top": ranked[:6],
                "baseline_orb15": next(
                    (
                        v
                        for v in variants
                        if v["strategy"] == "ORB_15m_retest"
                        and not v["skip_friday"]
                        and not v["after_10et"]
                    ),
                    None,
                ),
                "filtered_orb15": next(
                    (
                        v
                        for v in variants
                        if v["strategy"] == "ORB_15m_retest"
                        and v["skip_friday"]
                        and v["after_10et"]
                    ),
                    None,
                ),
            }
        results["windows"][label] = bucket

    # Aggregate recommendation scores across NQ/ES 1m window
    recs = []
    for label in ("1m", "2m_5m", "1y_1h"):
        for name in ("NQ", "ES"):
            top = (results["windows"].get(label) or {}).get(name, {}).get("top") or []
            if top:
                recs.append({"window": label, "symbol": name, **top[0]})
    results["recommendations_raw"] = recs
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps(results, indent=2)[:8000])
    print(f"\nWrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
