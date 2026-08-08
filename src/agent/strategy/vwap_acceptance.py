from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, time, timezone
from typing import Any, Optional
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)
ET = ZoneInfo("America/New_York")
CT = ZoneInfo("America/Chicago")


@dataclass
class AcceptanceSignal:
    symbol: str
    side: str
    entry: float
    stop: float
    target: float
    confidence: int
    reason: str
    vwap: float
    pd_poc_proxy: float
    ts: datetime
    risk_dollars: float
    reward_dollars: float


def _ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False).mean()


def _session_vwap(df: pd.DataFrame) -> pd.Series:
    typical = (df["high"] + df["low"] + df["close"]) / 3.0
    vol = df["volume"].replace(0, np.nan).fillna(1.0)
    idx = df.index
    days = idx.tz_convert(ET).date if getattr(idx, "tz", None) is not None else idx.date
    return (typical * vol).groupby(days).cumsum() / vol.groupby(days).cumsum()


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
    val = float(tr.rolling(n).mean().iloc[-1])
    return val if np.isfinite(val) and val > 0 else float(df["close"].iloc[-1]) * 0.001


def _prior_day_poc_proxy(df: pd.DataFrame) -> Optional[float]:
    """Volume-weighted price of prior session as POC proxy (no full volume profile)."""
    idx = df.index
    if getattr(idx, "tz", None) is not None:
        local = idx.tz_convert(ET).tz_localize(None)
        df = df.copy()
        df.index = local
    days = sorted(set(df.index.date))
    if len(days) < 2:
        return None
    prev = df[df.index.date == days[-2]]
    if prev.empty:
        return None
    typical = (prev["high"] + prev["low"] + prev["close"]) / 3.0
    vol = prev["volume"].replace(0, np.nan).fillna(1.0)
    return float((typical * vol).sum() / vol.sum())


def _is_trend_day(day: pd.DataFrame, atr: float, mult: float = 1.8) -> bool:
    if len(day) < 6:
        return False
    rng = float(day["high"].max() - day["low"].min())
    return rng > atr * mult


def evaluate_vwap_acceptance(
    symbol: str,
    bars: pd.DataFrame,
    cfg: dict[str, Any],
    *,
    point_value: float = 5.0,
    now: datetime | None = None,
) -> Optional[AcceptanceSignal]:
    """VWAP/POC acceptance including reclaim/rejection.

    A separate ``vwap_reclaim`` engine is intentionally not registered —
    long reclaim and short rejection are already covered below.
    """
    strat = cfg.get("vwap_acceptance", {})
    if bars is None or len(bars) < 50:
        return None

    df = bars.copy()
    df.columns = [c.lower() for c in df.columns]
    if "volume" not in df.columns:
        df["volume"] = 1.0
    idx = pd.to_datetime(df.index)
    if getattr(idx, "tz", None) is not None:
        idx = idx.tz_convert(ET).tz_localize(None)
    df.index = idx

    now = now or datetime.now(ET)
    now_et = now.replace(tzinfo=ET) if now.tzinfo is None else now.astimezone(ET)
    # globex = trade whenever CME micros are open (Asia/London/NY). Schedule layer
    # already blocks the real exchange break + weekend. Do not add RTH-only locks.
    session_filter = str(strat.get("session_filter", "rth")).lower()
    if session_filter != "globex":
        flatten_raw = strat.get("flatten_ct")
        if flatten_raw:
            if now_et.astimezone(CT).time() >= time(
                *map(int, str(flatten_raw).split(":"))
            ):
                return None

        entry_start = time(*map(int, str(strat.get("entry_start", "09:45")).split(":")))
        entry_end = time(*map(int, str(strat.get("entry_end", "14:30")).split(":")))
        last_bar_t = df.index[-1].time()
        # Support overnight windows (e.g. 18:00 → 16:55)
        if entry_start <= entry_end:
            in_window = entry_start <= last_bar_t <= entry_end
        else:
            in_window = last_bar_t >= entry_start or last_bar_t <= entry_end
        if not in_window:
            return None

    today = df.index[-1].date()
    day = df[df.index.date == today]
    # Early Asia after 18:00 ET often has <8 calendar-day bars — use rolling tape
    if len(day) < 8:
        day = df.iloc[-78:]
    if len(day) < 8:
        return None

    atr = _atr(df)
    if _is_trend_day(day, atr, float(strat.get("trend_day_atr_mult", 1.8))):
        if bool(strat.get("skip_trend_days", True)):
            logger.info("%s trend day — skip acceptance fades", symbol)
            return None

    df["vwap"] = _session_vwap(df)
    df["ema_fast"] = _ema(df["close"], int(strat.get("fast_ema", 20)))
    df["ema_slow"] = _ema(df["close"], int(strat.get("slow_ema", 50)))
    poc = _prior_day_poc_proxy(df)
    if poc is None:
        return None

    row = df.iloc[-1]
    prev = df.iloc[-2]
    close = float(row["close"])
    open_ = float(row["open"])
    vwap = float(row["vwap"])
    zone = float(strat.get("accept_zone_atr", 0.25)) * atr

    # Value magnet = blend of session VWAP and prior POC
    value = (vwap + poc) / 2.0
    dist = close - value

    # Extension then acceptance back into zone
    ext = float(strat.get("extension_atr", 0.9)) * atr
    long_ext = dist <= -ext  # price extended below value
    short_ext = dist >= ext

    in_zone = abs(close - value) <= zone
    # Acceptance: candle holds in zone / reclaim (not a spike-through)
    long_accept = (
        long_ext is False
        and in_zone
        and close > open_
        and close >= float(prev["high"])
        and close >= value - zone
    )
    # For long we also allow reclaim from below into zone this bar
    long_reclaim = (
        float(prev["close"]) < value - zone
        and close >= value - zone
        and close > open_
        and abs(close - value) <= zone * 1.2
    )
    short_accept = (
        in_zone
        and close < open_
        and close <= float(prev["low"])
        and close <= value + zone
    )
    short_reclaim = (
        float(prev["close"]) > value + zone
        and close <= value + zone
        and close < open_
        and abs(close - value) <= zone * 1.2
    )

    # Mild countertrend only — avoid fading a stacked EMA trend hard
    ema_f = float(row["ema_fast"])
    ema_s = float(row["ema_slow"])
    buy = (long_accept or long_reclaim) and not (ema_f < ema_s * 0.999 and close < vwap - 2 * zone)
    sell = (short_accept or short_reclaim) and not (ema_f > ema_s * 1.001 and close > vwap + 2 * zone)

    # Prefer reclaim from true extension
    if long_reclaim and float(prev["close"]) < value - ext * 0.5:
        buy = True
    if short_reclaim and float(prev["close"]) > value + ext * 0.5:
        sell = True

    if buy == sell:
        return None
    if not buy and not sell:
        return None

    side = "BUY" if buy else "SELL"
    entry = close
    stop_atr = float(strat.get("stop_atr_mult", 1.0))
    target_dollars = float(strat.get("target_dollars", 150))
    max_risk = float(strat.get("max_risk_dollars", 100))
    min_reward = float(strat.get("min_reward_dollars", 100))
    target_r = float(strat.get("target_r_multiple", 2.0))

    if side == "BUY":
        stop = min(entry - atr * stop_atr, value - atr * stop_atr)
        risk_pts = max(entry - stop, atr * 0.4)
        max_risk_pts = max_risk / point_value
        if risk_pts > max_risk_pts:
            stop = entry - max_risk_pts
            risk_pts = max_risk_pts
        target_pts = max(risk_pts * target_r, target_dollars / point_value)
        target = entry + target_pts
    else:
        stop = max(entry + atr * stop_atr, value + atr * stop_atr)
        risk_pts = max(stop - entry, atr * 0.4)
        max_risk_pts = max_risk / point_value
        if risk_pts > max_risk_pts:
            stop = entry + max_risk_pts
            risk_pts = max_risk_pts
        target_pts = max(risk_pts * target_r, target_dollars / point_value)
        target = entry - target_pts

    risk_dollars = risk_pts * point_value
    reward_dollars = abs(target - entry) * point_value
    if risk_dollars > max_risk + 1e-6 or reward_dollars < min_reward:
        return None

    conf = 60
    conf += 10 if abs(close - value) <= zone else 0
    conf += 10 if (side == "BUY" and long_reclaim) or (side == "SELL" and short_reclaim) else 0
    conf += 8 if reward_dollars >= 140 else 0
    conf += 5 if risk_dollars <= 80 else 0
    conf = min(96, conf)
    if conf < int(strat.get("min_confidence", 70)):
        return None

    reason = (
        f"{side} VWAP/POC-acceptance value={value:.2f} vwap={vwap:.2f} "
        f"poc={poc:.2f}"
    )
    return AcceptanceSignal(
        symbol=symbol,
        side=side,
        entry=float(entry),
        stop=float(stop),
        target=float(target),
        confidence=int(conf),
        reason=reason,
        vwap=vwap,
        pd_poc_proxy=float(poc),
        ts=datetime.now(timezone.utc),
        risk_dollars=float(risk_dollars),
        reward_dollars=float(reward_dollars),
    )


class VwapAcceptanceScanner:
    def __init__(self, cfg: dict[str, Any], bar_source):
        self.cfg = cfg
        self.bar_source = bar_source

    def scan_universe(self) -> list[AcceptanceSignal]:
        out: list[AcceptanceSignal] = []
        for sym in self.cfg.get("universe", {}).get("symbols", []):
            try:
                meta = self.cfg.get("instruments", {}).get(sym, {})
                sig = evaluate_vwap_acceptance(
                    sym,
                    self.bar_source(sym),
                    self.cfg,
                    point_value=float(meta.get("point_value", 5.0)),
                )
                if sig:
                    out.append(sig)
                    logger.info("%s", sig.reason)
            except Exception:
                logger.exception("acceptance scan failed %s", sym)
        out.sort(key=lambda s: s.confidence, reverse=True)
        return out
