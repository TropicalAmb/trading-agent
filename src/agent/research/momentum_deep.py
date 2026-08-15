"""Momentum winner/loser diagnostic research (no paper execution).

Pre-entry features only. Multi-TF context as features (not mandatory gates).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

import numpy as np
import pandas as pd

from agent.research.time_alignment import partial_bar_direction, partial_bar_trend


R_TARGETS = (1.0, 1.25, 1.5, 2.0)


def _ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False).mean()


def _atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
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


def _vwap(df: pd.DataFrame) -> pd.Series:
    vol = df["volume"].replace(0, np.nan).fillna(1.0) if "volume" in df.columns else pd.Series(1.0, index=df.index)
    px = df["close"].astype(float)
    idx = df.index
    if getattr(idx, "tz", None) is not None:
        days = idx.tz_convert("America/New_York").date
    else:
        days = idx.date
    return (px * vol).groupby(days).cumsum() / vol.groupby(days).cumsum()


def _htf_dir_asof(df: pd.DataFrame, rule: str) -> pd.Series:
    return partial_bar_direction(df, rule)


def _htf_trend_asof(df: pd.DataFrame, rule: str, ema_n: int = 20) -> pd.Series:
    return partial_bar_trend(df, rule, ema_n=ema_n)


def _prior_day_hl(df: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    daily = df.resample("1D", label="left", closed="left").agg({"high": "max", "low": "min"})
    return (
        daily["high"].shift(1).reindex(df.index, method="ffill"),
        daily["low"].shift(1).reindex(df.index, method="ffill"),
    )


def _session_bucket(ts: pd.Timestamp) -> str:
    if getattr(ts, "tzinfo", None) is not None:
        ts = ts.tz_convert("America/New_York")
    m = ts.hour * 60 + ts.minute
    if m >= 18 * 60 or m < 3 * 60:
        return "asia"
    if 3 * 60 <= m < 8 * 60:
        return "london"
    if 8 * 60 <= m < 9 * 60 + 30:
        return "ny_premarket"
    if 9 * 60 + 30 <= m < 10 * 60 + 30:
        return "ny_open"
    if 10 * 60 + 30 <= m < 12 * 60:
        return "ny_mid_morning"
    if 12 * 60 <= m < 14 * 60:
        return "ny_lunch"
    if 14 * 60 <= m < 17 * 60:
        return "ny_afternoon"
    return "globex"


def _swing(series: pd.Series, window: int = 20, which: str = "high") -> pd.Series:
    if which == "high":
        return series.rolling(window).max().shift(1)
    return series.rolling(window).min().shift(1)


def build_feature_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Full pre-entry feature matrix aligned to base bars (no lookahead)."""
    work = df.copy()
    work.columns = [str(c).lower() for c in work.columns]
    if "volume" not in work.columns:
        work["volume"] = 1.0
    if not isinstance(work.index, pd.DatetimeIndex):
        work.index = pd.to_datetime(work.index)

    work["ema20"] = _ema(work["close"], 20)
    work["ema50"] = _ema(work["close"], 50)
    work["atr"] = _atr(work, 14)
    work["vwap"] = _vwap(work)
    work["dir_4h"] = _htf_dir_asof(work, "4h")
    work["dir_1h"] = _htf_dir_asof(work, "1h")
    work["dir_15m"] = _htf_dir_asof(work, "15min")
    work["dir_5m"] = _htf_dir_asof(work, "5min")
    work["trend_4h"] = _htf_trend_asof(work, "4h")
    work["trend_1h"] = _htf_trend_asof(work, "1h")
    work["trend_15m"] = _htf_trend_asof(work, "15min")
    work["trend_5m"] = _htf_trend_asof(work, "5min")
    work["pdh"], work["pdl"] = _prior_day_hl(work)

    atr = work["atr"].replace(0, np.nan)
    work["ema20_slope"] = work["ema20"].diff(5) / atr
    work["ema50_slope"] = work["ema50"].diff(5) / atr
    work["ema_aligned_bull"] = (work["ema20"] > work["ema50"]).astype(int)
    work["ema_aligned_bear"] = (work["ema20"] < work["ema50"]).astype(int)
    work["close_vs_ema20"] = (work["close"] - work["ema20"]) / atr
    work["close_vs_ema50"] = (work["close"] - work["ema50"]) / atr
    work["close_vs_vwap"] = (work["close"] - work["vwap"]) / atr
    work["above_vwap"] = (work["close"] > work["vwap"]).astype(int)
    work["dist_pdh_atr"] = (work["pdh"] - work["close"]) / atr
    work["dist_pdl_atr"] = (work["close"] - work["pdl"]) / atr

    if getattr(work.index, "tz", None) is not None:
        day = work.index.tz_convert("America/New_York").date
    else:
        day = work.index.date
    sess_hi = work["high"].groupby(day).cummax()
    sess_lo = work["low"].groupby(day).cummin()
    work["dist_sess_hi_atr"] = (sess_hi - work["close"]) / atr
    work["dist_sess_lo_atr"] = (work["close"] - sess_lo) / atr
    work["swing_hi"] = _swing(work["high"], 20, "high")
    work["swing_lo"] = _swing(work["low"], 20, "low")
    work["dist_swing_hi_atr"] = (work["swing_hi"] - work["close"]) / atr
    work["dist_swing_lo_atr"] = (work["close"] - work["swing_lo"]) / atr

    work["atr_pctile"] = work["atr"].rolling(100, min_periods=20).apply(
        lambda x: float(pd.Series(x).rank(pct=True).iloc[-1]), raw=False
    )
    ret = work["close"].pct_change()
    work["realized_vol"] = ret.rolling(20).std()
    vol_ma = work["volume"].rolling(20).mean()
    work["rel_volume"] = work["volume"] / vol_ma.replace(0, np.nan)

    rng = (work["high"] - work["low"]).replace(0, np.nan)
    body = (work["close"] - work["open"]).abs()
    work["body_range"] = body / rng
    work["upper_wick_range"] = (work["high"] - work[["open", "close"]].max(axis=1)) / rng
    work["lower_wick_range"] = (work[["open", "close"]].min(axis=1) - work["low"]) / rng
    work["clv"] = (work["close"] - work["low"]) / rng
    for col in ("body_range", "upper_wick_range", "lower_wick_range", "clv"):
        work[f"prev_{col}"] = work[col].shift(1)

    # pullback: touched EMA20/VWAP in last 8 bars then momentum away
    touched_ema = (work["low"] <= work["ema20"]) | (work["high"] >= work["ema20"])
    touched_vwap = (work["low"] <= work["vwap"]) | (work["high"] >= work["vwap"])
    pull_touch = (touched_ema | touched_vwap).astype(int)
    work["pullback_recent"] = pull_touch.rolling(8).max().fillna(0).astype(int)
    work["pullback_depth_atr"] = ((work["ema20"] - work["low"]).clip(lower=0) / atr).rolling(8).max()
    # bars since last pull touch
    last_touch = np.full(len(work), -10**9, dtype=int)
    pt = pull_touch.to_numpy()
    cur = -10**9
    for i in range(len(work)):
        if pt[i]:
            cur = i
        last_touch[i] = cur
    idx = np.arange(len(work))
    work["bars_since_pullback"] = idx - last_touch
    work.loc[work["bars_since_pullback"] > 10_000, "bars_since_pullback"] = np.nan

    # breakout / retest vs prior swing
    work["breakout_up"] = (work["close"] > work["swing_hi"]).astype(int)
    work["breakout_dn"] = (work["close"] < work["swing_lo"]).astype(int)
    work["retest_up"] = (
        (work["low"] <= work["swing_hi"]) & (work["close"] > work["swing_hi"]) & (work["breakout_up"].shift(1) == 1)
    ).astype(int)
    work["retest_dn"] = (
        (work["high"] >= work["swing_lo"]) & (work["close"] < work["swing_lo"]) & (work["breakout_dn"].shift(1) == 1)
    ).astype(int)
    work["overext_long"] = ((work["close"] - work["ema20"]) > 1.8 * atr).astype(int)
    work["overext_short"] = ((work["ema20"] - work["close"]) > 1.8 * atr).astype(int)

    # momentum trigger
    prev_hi = work["high"].shift(1)
    prev_lo = work["low"].shift(1)
    work["mom_long"] = ((work["close"] > work["open"]) & (work["close"] > prev_hi)).astype(int)
    work["mom_short"] = ((work["close"] < work["open"]) & (work["close"] < prev_lo)).astype(int)

    # parity-style strict bias (for funnel / optional baseline)
    all_bull = (work["dir_15m"] == 1) & (work["dir_1h"] == 1) & (work["dir_4h"] == 1)
    all_bear = (work["dir_15m"] == -1) & (work["dir_1h"] == -1) & (work["dir_4h"] == -1)
    work["strict_long_bias"] = (all_bull & (work["close"] > work["vwap"])).astype(int)
    work["strict_short_bias"] = (all_bear & (work["close"] < work["vwap"])).astype(int)
    work["parity_mom_long"] = (work["strict_long_bias"] & work["mom_long"]).astype(int)
    work["parity_mom_short"] = (work["strict_short_bias"] & work["mom_short"]).astype(int)
    return work


def _htf_agree_mask(side: int, row: pd.Series) -> dict[str, Any]:
    dirs = {
        "4h": int(row["dir_4h"]),
        "1h": int(row["dir_1h"]),
        "15m": int(row["dir_15m"]),
        "5m": int(row["dir_5m"]),
    }
    agree = [k for k, v in dirs.items() if v == side]
    conflict = [k for k, v in dirs.items() if v == -side]
    label = "+".join(agree) if agree else "none"
    return {
        "htf_agree_count": len(agree),
        "htf_agree_set": label,
        "htf_conflict_set": "+".join(conflict) if conflict else "none",
        "agree_4h": int(dirs["4h"] == side),
        "agree_1h": int(dirs["1h"] == side),
        "agree_15m": int(dirs["15m"] == side),
        "agree_5m": int(dirs["5m"] == side),
        "agree_1h_15m": int(dirs["1h"] == side and dirs["15m"] == side),
        "agree_1h_15m_5m": int(dirs["1h"] == side and dirs["15m"] == side and dirs["5m"] == side),
        "agree_4h_1h": int(dirs["4h"] == side and dirs["1h"] == side),
        "agree_4h_1h_15m": int(dirs["4h"] == side and dirs["1h"] == side and dirs["15m"] == side),
        "agree_15m_5m": int(dirs["15m"] == side and dirs["5m"] == side),
        "agree_all4": int(len(agree) == 4),
    }


def simulate_path(
    frame: pd.DataFrame,
    i: int,
    side: str,
    entry: float,
    stop: float,
    risk: float,
    horizon: int = 240,
) -> dict[str, float]:
    n = len(frame)
    mfe = 0.0
    mae = 0.0
    bars_mfe = 0
    bars_mae = 0
    hit: dict[str, float | None] = {f"hit_{r}R": None for r in R_TARGETS}
    exit_r = None
    for j in range(i + 1, min(i + horizon, n)):
        hi = float(frame["high"].iloc[j])
        lo = float(frame["low"].iloc[j])
        if side == "BUY":
            fav = (hi - entry) / risk
            adv = (entry - lo) / risk
            if lo <= stop and exit_r is None:
                exit_r = -1.0
            for r in R_TARGETS:
                if hit[f"hit_{r}R"] is None and hi >= entry + r * risk:
                    hit[f"hit_{r}R"] = float(j - i)
        else:
            fav = (entry - lo) / risk
            adv = (hi - entry) / risk
            if hi >= stop and exit_r is None:
                exit_r = -1.0
            for r in R_TARGETS:
                if hit[f"hit_{r}R"] is None and lo <= entry - r * risk:
                    hit[f"hit_{r}R"] = float(j - i)
        if fav > mfe:
            mfe = fav
            bars_mfe = j - i
        if adv > mae:
            mae = adv
            bars_mae = j - i
        if exit_r is not None and all(hit[f"hit_{r}R"] is not None for r in R_TARGETS):
            break
    # binary outcomes: did price reach +R before -1R stop?
    out: dict[str, Any] = {
        "mfe_r": float(mfe),
        "mae_r": float(mae),
        "bars_to_mfe": int(bars_mfe),
        "bars_to_mae": int(bars_mae),
    }
    for r in R_TARGETS:
        key = f"hit_{r}R"
        bars = hit[key]
        # win if target hit and (stop not hit earlier OR target bars < would need stop order)
        # approximate: win if MFE>=r and MAE<1 before that — use first-touch scan
        out[f"win_{r}R"] = 0
        out[f"bars_to_{r}R"] = bars
    # proper first-touch for each R
    for r in R_TARGETS:
        won = 0
        for j in range(i + 1, min(i + horizon, n)):
            hi = float(frame["high"].iloc[j])
            lo = float(frame["low"].iloc[j])
            if side == "BUY":
                if lo <= stop:
                    won = 0
                    break
                if hi >= entry + r * risk:
                    won = 1
                    break
            else:
                if hi >= stop:
                    won = 0
                    break
                if lo <= entry - r * risk:
                    won = 1
                    break
        out[f"win_{r}R"] = won
    # primary 2R pnl_r used for expectancy tables
    out["pnl_r"] = 2.0 if out["win_2.0R"] else -1.0
    # refine: if neither, time exit partial
    if out["win_2.0R"] == 0:
        # check if stop hit
        stopped = False
        for j in range(i + 1, min(i + horizon, n)):
            hi = float(frame["high"].iloc[j])
            lo = float(frame["low"].iloc[j])
            if side == "BUY" and lo <= stop:
                stopped = True
                break
            if side == "SELL" and hi >= stop:
                stopped = True
                break
            if side == "BUY" and hi >= entry + 2 * risk:
                out["pnl_r"] = 2.0
                stopped = True
                break
            if side == "SELL" and lo <= entry - 2 * risk:
                out["pnl_r"] = 2.0
                stopped = True
                break
        if not stopped:
            j = min(i + horizon - 1, n - 1)
            px = float(frame["close"].iloc[j])
            out["pnl_r"] = (px - entry) / risk if side == "BUY" else (entry - px) / risk
    return out


def collect_momentum_signals(
    frame: pd.DataFrame,
    *,
    symbol: str,
    chart_tf: str,
    mode: str = "trigger",
    cooldown: int = 12,
    stop_atr_mult: float = 1.0,
    point_value: float = 5.0,
) -> list[dict[str, Any]]:
    """mode: trigger = pure mom candle; parity_bias = strict HTF+VWAP + mom."""
    rows: list[dict[str, Any]] = []
    i = 80
    n = len(frame)
    while i < n - 5:
        if mode == "parity_bias":
            long_sig = bool(frame["parity_mom_long"].iloc[i])
            short_sig = bool(frame["parity_mom_short"].iloc[i])
        else:
            long_sig = bool(frame["mom_long"].iloc[i])
            short_sig = bool(frame["mom_short"].iloc[i])
        if not long_sig and not short_sig:
            i += 1
            continue
        side = "BUY" if long_sig else "SELL"
        side_i = 1 if side == "BUY" else -1
        row = frame.iloc[i]
        atr = float(row["atr"] or 0) or abs(float(row["close"])) * 0.001
        entry = float(row["close"])
        if side == "BUY":
            stop = entry - atr * stop_atr_mult
        else:
            stop = entry + atr * stop_atr_mult
        risk = abs(entry - stop)
        if risk <= 0 or not np.isfinite(risk):
            i += 1
            continue
        path = simulate_path(frame, i, side, entry, stop, risk)
        htf = _htf_agree_mask(side_i, row)
        ts = frame.index[i]
        feat = {
            "symbol": symbol,
            "timestamp": str(ts),
            "session": _session_bucket(pd.Timestamp(ts)),
            "direction": side,
            "chart_tf": chart_tf,
            "mode": mode,
            "dir_4h": int(row["dir_4h"]),
            "dir_1h": int(row["dir_1h"]),
            "dir_15m": int(row["dir_15m"]),
            "dir_5m": int(row["dir_5m"]),
            "trend_4h": int(row["trend_4h"]),
            "trend_1h": int(row["trend_1h"]),
            "trend_15m": int(row["trend_15m"]),
            "trend_5m": int(row["trend_5m"]),
            "ema20": float(row["ema20"]),
            "ema50": float(row["ema50"]),
            "ema20_slope": float(row["ema20_slope"]) if pd.notna(row["ema20_slope"]) else np.nan,
            "ema50_slope": float(row["ema50_slope"]) if pd.notna(row["ema50_slope"]) else np.nan,
            "ema_aligned": int(row["ema_aligned_bull"] if side == "BUY" else row["ema_aligned_bear"]),
            "above_vwap": int(row["above_vwap"]),
            "vwap_side_ok": int((side == "BUY" and row["above_vwap"] == 1) or (side == "SELL" and row["above_vwap"] == 0)),
            "dist_vwap_atr": float(row["close_vs_vwap"]) if pd.notna(row["close_vs_vwap"]) else np.nan,
            "abs_dist_vwap_atr": float(abs(row["close_vs_vwap"])) if pd.notna(row["close_vs_vwap"]) else np.nan,
            "dist_ema20_atr": float(row["close_vs_ema20"]) if pd.notna(row["close_vs_ema20"]) else np.nan,
            "dist_ema50_atr": float(row["close_vs_ema50"]) if pd.notna(row["close_vs_ema50"]) else np.nan,
            "dist_pdh_atr": float(row["dist_pdh_atr"]) if pd.notna(row["dist_pdh_atr"]) else np.nan,
            "dist_pdl_atr": float(row["dist_pdl_atr"]) if pd.notna(row["dist_pdl_atr"]) else np.nan,
            "dist_sess_hi_atr": float(row["dist_sess_hi_atr"]) if pd.notna(row["dist_sess_hi_atr"]) else np.nan,
            "dist_sess_lo_atr": float(row["dist_sess_lo_atr"]) if pd.notna(row["dist_sess_lo_atr"]) else np.nan,
            "dist_swing_hi_atr": float(row["dist_swing_hi_atr"]) if pd.notna(row["dist_swing_hi_atr"]) else np.nan,
            "dist_swing_lo_atr": float(row["dist_swing_lo_atr"]) if pd.notna(row["dist_swing_lo_atr"]) else np.nan,
            "atr": atr,
            "atr_pctile": float(row["atr_pctile"]) if pd.notna(row["atr_pctile"]) else np.nan,
            "realized_vol": float(row["realized_vol"]) if pd.notna(row["realized_vol"]) else np.nan,
            "rel_volume": float(row["rel_volume"]) if pd.notna(row["rel_volume"]) else np.nan,
            "body_range": float(row["body_range"]) if pd.notna(row["body_range"]) else np.nan,
            "upper_wick_range": float(row["upper_wick_range"]) if pd.notna(row["upper_wick_range"]) else np.nan,
            "lower_wick_range": float(row["lower_wick_range"]) if pd.notna(row["lower_wick_range"]) else np.nan,
            "clv": float(row["clv"]) if pd.notna(row["clv"]) else np.nan,
            "prev_body_range": float(row["prev_body_range"]) if pd.notna(row["prev_body_range"]) else np.nan,
            "prev_clv": float(row["prev_clv"]) if pd.notna(row["prev_clv"]) else np.nan,
            "pullback_recent": int(row["pullback_recent"]),
            "pullback_depth_atr": float(row["pullback_depth_atr"]) if pd.notna(row["pullback_depth_atr"]) else np.nan,
            "bars_since_pullback": float(row["bars_since_pullback"]) if pd.notna(row["bars_since_pullback"]) else np.nan,
            "breakout": int(row["breakout_up"] if side == "BUY" else row["breakout_dn"]),
            "retest": int(row["retest_up"] if side == "BUY" else row["retest_dn"]),
            "overextended": int(row["overext_long"] if side == "BUY" else row["overext_short"]),
            "entry": entry,
            "stop": stop,
            "risk_pts": risk,
            "pnl_dollars_1": float(path["pnl_r"] * risk * point_value),
            "win": int(path["pnl_r"] > 0),
        }
        feat.update(htf)
        feat.update(path)
        rows.append(feat)
        i = i + cooldown
    return rows


def trade_stats(df: pd.DataFrame, r_col: str = "pnl_r") -> dict[str, Any]:
    if df is None or len(df) == 0:
        return {"n": 0, "wr": None, "pf": None, "E": None, "max_dd": 0.0, "trades_per_week": 0.0, "label": "EMPTY"}
    rs = df[r_col].astype(float).to_numpy()
    rs = rs[np.isfinite(rs)]
    if len(rs) == 0:
        return {"n": 0, "wr": None, "pf": None, "E": None, "max_dd": 0.0, "trades_per_week": 0.0, "label": "EMPTY"}
    wins = rs[rs > 0]
    losses = rs[rs < 0]
    gw = float(wins.sum()) if len(wins) else 0.0
    gl = float(abs(losses.sum())) if len(losses) else 0.0
    eq = np.cumsum(rs)
    dd = float((eq - np.maximum.accumulate(eq)).min()) if len(eq) else 0.0
    days = sorted({str(t)[:10] for t in df["timestamp"]})
    n_days = max(len(days), 1)
    n = len(rs)
    label = "VERY PRELIMINARY" if n < 30 else ("PROMISING / NOT CONFIRMED" if n < 100 else "STRONGER SAMPLE")
    return {
        "n": n,
        "wr": float((rs > 0).mean()),
        "pf": (gw / gl) if gl > 1e-12 else (999.0 if gw > 0 else 0.0),
        "E": float(rs.mean()),
        "max_dd": dd,
        "trades_per_week": n / n_days * 5.0,
        "label": label,
    }


def conditional_table(df: pd.DataFrame, mask: pd.Series, name: str) -> dict[str, Any]:
    sub = df.loc[mask]
    st = trade_stats(sub)
    st["conditions"] = name
    st["n_before"] = len(df)
    st["pct_retained"] = (len(sub) / len(df)) if len(df) else 0.0
    return st


def sample_label(n: int) -> str:
    if n < 30:
        return "VERY PRELIMINARY"
    if n < 100:
        return "PROMISING / NOT CONFIRMED"
    return "STRONGER SAMPLE"
