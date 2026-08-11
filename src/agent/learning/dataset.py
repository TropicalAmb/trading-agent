"""Unified candidate-outcome dataset (entry-time features only)."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

from agent.learning.shrink import shrink_rate


FEATURE_COLS = [
    "symbol",
    "strategy",
    "direction",
    "session",
    "regime",
    "dir_15m",
    "dir_1h",
    "dir_4h",
    "mtf_aligned",
    "above_vwap",
    "below_vwap",
    "vwap_dist_atr",
    "ema_bull",
    "ema_bear",
    "price_vs_ema20_atr",
    "price_vs_ema50_atr",
    "ema20_above_ema50",
    "overextended",
    "near_pdh",
    "near_pdl",
    "momentum_aligned",
    "body_atr",
    "upper_wick_atr",
    "lower_wick_atr",
    "close_loc",
    "atr",
    "atr_pctile",
    "stop_dist_atr",
    "target_r",
    "local_score",
    "global_score",
    "tier_rank",
    "agreeing_n",
]

TARGET_COLS = [
    "win",
    "realized_r",
    "mfe_r",
    "mae_r",
    "target_before_stop",
    "hit_1r_before_stop",
    "hit_2r_before_stop",
]


def _norm_dir(raw: Any) -> str:
    d = str(raw or "").upper()
    if d in {"BUY", "LONG"}:
        return "LONG"
    if d in {"SELL", "SHORT"}:
        return "SHORT"
    return d or "UNKNOWN"


def _tier_rank(t: Any) -> int:
    return {"A+": 4, "A": 3, "B": 2, "C": 1}.get(str(t or "").upper(), 0)


def _r_from_levels(side: str, entry: float, stop: float, exit_px: float) -> Optional[float]:
    risk = abs(entry - stop)
    if risk <= 1e-12:
        return None
    if _norm_dir(side) == "LONG":
        return (exit_px - entry) / risk
    if _norm_dir(side) == "SHORT":
        return (entry - exit_px) / risk
    return None


def _parse_ts(raw: Any) -> Optional[pd.Timestamp]:
    if raw is None or raw == "":
        return None
    try:
        return pd.Timestamp(raw)
    except Exception:
        return None


@dataclass
class DatasetAudit:
    usable_rows: int = 0
    date_min: str | None = None
    date_max: str | None = None
    by_strategy: dict[str, int] = field(default_factory=dict)
    by_symbol: dict[str, int] = field(default_factory=dict)
    by_session: dict[str, int] = field(default_factory=dict)
    by_regime: dict[str, int] = field(default_factory=dict)
    missingness: dict[str, float] = field(default_factory=dict)
    class_balance: dict[str, float] = field(default_factory=dict)
    duplicate_setup_ids: int = 0
    legacy_excluded: list[dict[str, Any]] = field(default_factory=list)
    sources: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "usable_rows": self.usable_rows,
            "date_min": self.date_min,
            "date_max": self.date_max,
            "by_strategy": self.by_strategy,
            "by_symbol": self.by_symbol,
            "by_session": self.by_session,
            "by_regime": self.by_regime,
            "missingness": self.missingness,
            "class_balance": self.class_balance,
            "duplicate_setup_ids": self.duplicate_setup_ids,
            "legacy_excluded": self.legacy_excluded[:50],
            "legacy_excluded_count": len(self.legacy_excluded),
            "sources": self.sources,
        }


def _row_from_shadow(t: dict[str, Any]) -> Optional[dict[str, Any]]:
    entry = t.get("entry")
    stop = t.get("stop")
    exit_px = t.get("exit")
    if entry is None or stop is None or exit_px is None:
        return None
    side = t.get("side") or t.get("direction")
    r = t.get("r_achieved")
    if r is None:
        r = _r_from_levels(side, float(entry), float(stop), float(exit_px))
    if r is None:
        return None
    risk = abs(float(entry) - float(stop))
    mfe_r = t.get("mfe_r")
    mae_r = t.get("mae_r")
    if mfe_r is None and t.get("mfe_pts") is not None and risk > 0:
        mfe_r = float(t["mfe_pts"]) / risk
    if mae_r is None and t.get("mae_pts") is not None and risk > 0:
        mae_r = float(t["mae_pts"]) / risk
    exit_reason = str(t.get("exit_reason") or "")
    target_hit = exit_reason.lower() in {"target", "tp", "take_profit"}
    stop_hit = exit_reason.lower() in {"stop", "stopped", "sl"}
    return {
        "source": "shadow",
        "candidate_id": t.get("id"),
        "setup_id": t.get("setup_id") or t.get("structural_key"),
        "structural_key": t.get("structural_key"),
        "market_timestamp": t.get("opened_at") or t.get("market_timestamp"),
        "symbol": str(t.get("symbol") or "").upper(),
        "strategy": str(t.get("strategy") or t.get("strategy_name") or "unknown"),
        "direction": _norm_dir(side),
        "session": str(t.get("session") or "unknown").lower().split()[0],
        "regime": str(t.get("regime") or "UNKNOWN").upper(),
        "entry": float(entry),
        "stop": float(stop),
        "target": float(t["target"]) if t.get("target") is not None else None,
        "local_score": t.get("strategy_local_score"),
        "global_score": t.get("global_score"),
        "tier": t.get("tier") or t.get("setup_tier"),
        "tier_rank": _tier_rank(t.get("tier") or t.get("setup_tier")),
        "win": 1 if float(r) > 0 else 0,
        "realized_r": float(r),
        "mfe_r": float(mfe_r) if mfe_r is not None else None,
        "mae_r": float(mae_r) if mae_r is not None else None,
        "target_before_stop": 1 if target_hit else (0 if stop_hit else int(float(r) > 0)),
        "hit_1r_before_stop": 1 if (mfe_r is not None and float(mfe_r) >= 1.0) or float(r) >= 1.0 else 0,
        "hit_2r_before_stop": 1 if (mfe_r is not None and float(mfe_r) >= 2.0) or float(r) >= 2.0 else 0,
        "config_version": t.get("config_version"),
        "execution_mode": "SHADOW",
    }


def _row_from_paper(t: dict[str, Any]) -> Optional[dict[str, Any]]:
    if str(t.get("source", "")) == "demo":
        return None
    if str(t.get("exit_reason", "")) in {"universe_prune", "corr_conflict_prune"}:
        return None
    if t.get("exit") is None and str(t.get("status", "")).upper() != "CLOSED":
        return None
    entry, stop, exit_px = t.get("entry"), t.get("stop"), t.get("exit")
    if entry is None or stop is None or exit_px is None:
        return None
    side = t.get("side") or t.get("direction")
    r = t.get("r_achieved")
    if r is None:
        r = _r_from_levels(side, float(entry), float(stop), float(exit_px))
    if r is None:
        return None
    risk = abs(float(entry) - float(stop))
    mfe_pts = t.get("mfe_pts") or t.get("peak_favorable_pts")
    mae_pts = t.get("mae_pts")
    mfe_r = (float(mfe_pts) / risk) if mfe_pts is not None and risk > 0 else None
    mae_r = (float(mae_pts) / risk) if mae_pts is not None and risk > 0 else None
    exit_reason = str(t.get("exit_reason") or "")
    target_hit = "target" in exit_reason.lower() or exit_reason.lower() == "tp"
    stop_hit = "stop" in exit_reason.lower()
    return {
        "source": "paper",
        "candidate_id": t.get("id"),
        "setup_id": t.get("setup_id") or t.get("id"),
        "structural_key": t.get("structural_key"),
        "market_timestamp": t.get("market_timestamp") or t.get("opened_at"),
        "symbol": str(t.get("symbol") or "").upper(),
        "strategy": str(t.get("strategy_name") or t.get("strategy") or "unknown"),
        "direction": _norm_dir(side),
        "session": str(t.get("session") or "unknown").lower().split()[0],
        "regime": str(t.get("regime") or "UNKNOWN").upper(),
        "entry": float(entry),
        "stop": float(stop),
        "target": float(t["target"]) if t.get("target") is not None else None,
        "local_score": t.get("strategy_local_score"),
        "global_score": t.get("global_score") if t.get("global_score") is not None else t.get("confidence"),
        "tier": t.get("setup_tier") or t.get("tier"),
        "tier_rank": _tier_rank(t.get("setup_tier") or t.get("tier")),
        "win": 1 if float(r) > 0 else 0,
        "realized_r": float(r),
        "mfe_r": mfe_r,
        "mae_r": mae_r,
        "target_before_stop": 1 if target_hit else (0 if stop_hit else int(float(r) > 0)),
        "hit_1r_before_stop": 1 if (mfe_r is not None and mfe_r >= 1.0) or float(r) >= 1.0 else 0,
        "hit_2r_before_stop": 1 if (mfe_r is not None and mfe_r >= 2.0) or float(r) >= 2.0 else 0,
        "config_version": t.get("config_version"),
        "execution_mode": "ACTUAL",
    }


def enrich_features_from_bars(row: dict[str, Any], df: pd.DataFrame) -> dict[str, Any]:
    """Compute entry-time features from bars up to market_timestamp (no lookahead)."""
    out = dict(row)
    ts = _parse_ts(row.get("market_timestamp"))
    if df is None or df.empty or ts is None:
        return out
    try:
        from agent.context.market_context import build_market_context
        from agent.context.regime import MarketRegimeClassifier
    except Exception:
        return out

    # Slice to bars at/before entry
    idx = df.index
    if getattr(idx, "tz", None) is not None and ts.tzinfo is None:
        ts = ts.tz_localize(idx.tz)
    elif getattr(idx, "tz", None) is None and ts.tzinfo is not None:
        ts = ts.tz_localize(None)
    hist = df.loc[:ts]
    if len(hist) < 40:
        return out
    hist = hist.iloc[:-0] if False else hist  # keep all <= ts
    try:
        regime = MarketRegimeClassifier().classify(hist)
        ctx = build_market_context(hist, regime_result=regime)
    except Exception:
        return out

    last = hist.iloc[-1]
    o, h, l, c = float(last["open"]), float(last["high"]), float(last["low"]), float(last["close"])
    prev = hist["close"].shift(1)
    tr = pd.concat([(hist["high"] - hist["low"]).abs(), (hist["high"] - prev).abs(), (hist["low"] - prev).abs()], axis=1).max(axis=1)
    atr_s = tr.rolling(14).mean()
    atr = float(atr_s.iloc[-1] or 0.0)
    if atr <= 0:
        atr = abs(c) * 0.001
    ema20 = float(hist["close"].ewm(span=20, adjust=False).mean().iloc[-1])
    ema50 = float(hist["close"].ewm(span=50, adjust=False).mean().iloc[-1])
    atr_hist = atr_s.dropna()
    atr_pctile = float((atr_hist <= atr).mean()) if len(atr_hist) else None

    # VWAP approx
    typ = (hist["high"] + hist["low"] + hist["close"]) / 3.0
    vol = hist["volume"].replace(0, np.nan).fillna(1.0) if "volume" in hist.columns else pd.Series(1.0, index=hist.index)
    vwap = float((typ * vol).iloc[-78:].sum() / max(vol.iloc[-78:].sum(), 1e-9))

    direction = _norm_dir(row.get("direction"))
    sign = 1 if direction == "LONG" else -1
    mtf = 0
    if sign > 0:
        mtf = int(ctx.direction_15m > 0) + int(ctx.direction_1h > 0) + int(ctx.direction_4h > 0)
    elif sign < 0:
        mtf = int(ctx.direction_15m < 0) + int(ctx.direction_1h < 0) + int(ctx.direction_4h < 0)

    body = abs(c - o)
    upper = h - max(c, o)
    lower = min(c, o) - l
    rng = max(h - l, 1e-12)
    stop = float(row["stop"]) if row.get("stop") is not None else None
    target = row.get("target")
    stop_dist_atr = abs(float(row["entry"]) - stop) / atr if stop is not None else None
    target_r = None
    if target is not None and stop is not None and abs(float(row["entry"]) - stop) > 1e-12:
        target_r = abs(float(target) - float(row["entry"])) / abs(float(row["entry"]) - stop)

    out.update(
        {
            "dir_15m": int(ctx.direction_15m),
            "dir_1h": int(ctx.direction_1h),
            "dir_4h": int(ctx.direction_4h),
            "mtf_aligned": int(mtf),
            "above_vwap": int(bool(ctx.above_vwap)),
            "below_vwap": int(bool(ctx.below_vwap)),
            "vwap_dist_atr": (c - vwap) / atr,
            "ema_bull": int(bool(ctx.ema_bull)),
            "ema_bear": int(bool(ctx.ema_bear)),
            "price_vs_ema20_atr": (c - ema20) / atr,
            "price_vs_ema50_atr": (c - ema50) / atr,
            "ema20_above_ema50": int(ema20 > ema50),
            "overextended": int(bool(ctx.overextended_long or ctx.overextended_short)),
            "near_pdh": int(bool(ctx.near_pdh)),
            "near_pdl": int(bool(ctx.near_pdl)),
            "momentum_aligned": int(
                (direction == "LONG" and ctx.momentum_up)
                or (direction == "SHORT" and ctx.momentum_down)
            ),
            "body_atr": body / atr,
            "upper_wick_atr": upper / atr,
            "lower_wick_atr": lower / atr,
            "close_loc": (c - l) / rng,
            "atr": atr,
            "atr_pctile": atr_pctile,
            "stop_dist_atr": stop_dist_atr,
            "target_r": target_r,
            "regime": str(ctx.regime.value if hasattr(ctx.regime, "value") else ctx.regime),
        }
    )
    return out


def build_unified_dataset(
    *,
    paper_path: str | Path = "data/paper_trades.json",
    shadow_path: str | Path = "data/shadow_trades.json",
    learning_path: str | Path | None = "data/learning/candidates.jsonl",
    backfill_bars: bool = False,
    bar_cache: dict[str, pd.DataFrame] | None = None,
) -> tuple[pd.DataFrame, DatasetAudit]:
    audit = DatasetAudit()
    rows: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []

    paper_p = Path(paper_path)
    if paper_p.exists():
        data = json.loads(paper_p.read_text(encoding="utf-8"))
        for t in data.get("closed_trades") or []:
            r = _row_from_paper(t)
            if r is None:
                excluded.append({"source": "paper", "id": t.get("id"), "why": "incomplete_levels_or_demo"})
                continue
            rows.append(r)
            audit.sources["paper"] = audit.sources.get("paper", 0) + 1

    shadow_p = Path(shadow_path)
    if shadow_p.exists():
        data = json.loads(shadow_p.read_text(encoding="utf-8"))
        for t in data.get("closed") or []:
            r = _row_from_shadow(t)
            if r is None:
                excluded.append({"source": "shadow", "id": t.get("id"), "why": "incomplete_outcome"})
                continue
            rows.append(r)
            audit.sources["shadow"] = audit.sources.get("shadow", 0) + 1

    if learning_path and Path(learning_path).exists():
        from agent.learning.store import LearningStore

        for t in LearningStore(learning_path).all_rows():
            if t.get("final_result") in (None, "", "OPEN"):
                continue
            if t.get("realized_r") is None and t.get("win") is None:
                excluded.append({"source": "learning", "id": t.get("candidate_id"), "why": "no_label"})
                continue
            row = {
                "source": "learning_store",
                "candidate_id": t.get("candidate_id"),
                "setup_id": t.get("setup_id"),
                "market_timestamp": t.get("timestamp") or t.get("market_timestamp"),
                "symbol": str(t.get("symbol") or "").upper(),
                "strategy": str(t.get("strategy") or "unknown"),
                "direction": _norm_dir(t.get("direction") or t.get("side")),
                "session": str(t.get("session") or "unknown").lower().split()[0],
                "regime": str(t.get("regime") or "UNKNOWN").upper(),
                "entry": t.get("entry"),
                "stop": t.get("stop"),
                "target": t.get("target"),
                "local_score": t.get("local_score"),
                "global_score": t.get("global_score"),
                "tier": t.get("tier"),
                "tier_rank": _tier_rank(t.get("tier")),
                "win": int(t.get("win") if t.get("win") is not None else (1 if float(t.get("realized_r") or 0) > 0 else 0)),
                "realized_r": float(t.get("realized_r") or 0),
                "mfe_r": t.get("mfe_r"),
                "mae_r": t.get("mae_r"),
                "target_before_stop": t.get("target_before_stop"),
                "hit_1r_before_stop": t.get("hit_1r_before_stop"),
                "hit_2r_before_stop": t.get("hit_2r_before_stop"),
                "execution_mode": t.get("executed_or_shadow") or t.get("execution_mode"),
            }
            # Merge explicit feature columns if present
            feats = t.get("features") or {}
            if isinstance(feats, dict):
                row.update(feats)
            for k in FEATURE_COLS:
                if k in t and t[k] is not None:
                    row[k] = t[k]
            rows.append(row)
            audit.sources["learning_store"] = audit.sources.get("learning_store", 0) + 1

    # Deduplicate by setup_id (keep first chronological)
    rows.sort(key=lambda r: str(r.get("market_timestamp") or ""))
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for r in rows:
        sid = str(r.get("setup_id") or "")
        key = sid or f"{r.get('symbol')}|{r.get('strategy')}|{r.get('direction')}|{r.get('market_timestamp')}|{r.get('entry')}"
        if key in seen:
            audit.duplicate_setup_ids += 1
            excluded.append({"source": r.get("source"), "id": r.get("candidate_id"), "why": "duplicate_setup_id", "setup_id": sid})
            continue
        seen.add(key)
        deduped.append(r)

    if backfill_bars and bar_cache is not None:
        enriched = []
        for r in deduped:
            df = bar_cache.get(str(r.get("symbol") or "").upper())
            enriched.append(enrich_features_from_bars(r, df) if df is not None else r)
        deduped = enriched

    df = pd.DataFrame(deduped)
    audit.legacy_excluded = excluded
    audit.usable_rows = len(df)
    if len(df):
        ts = pd.to_datetime(df["market_timestamp"], errors="coerce")
        audit.date_min = str(ts.min())
        audit.date_max = str(ts.max())
        audit.by_strategy = dict(Counter(df["strategy"].astype(str)))
        audit.by_symbol = dict(Counter(df["symbol"].astype(str)))
        audit.by_session = dict(Counter(df["session"].astype(str)))
        audit.by_regime = dict(Counter(df["regime"].astype(str)))
        miss = {}
        for c in FEATURE_COLS:
            if c not in df.columns:
                miss[c] = 1.0
            else:
                miss[c] = float(df[c].isna().mean())
        audit.missingness = miss
        wins = float(df["win"].mean()) if "win" in df.columns else 0.0
        audit.class_balance = {"win_rate": wins, "loss_rate": 1.0 - wins, "n": float(len(df))}
    return df, audit


def time_splits(df: pd.DataFrame, train_frac: float = 0.6, val_frac: float = 0.2) -> dict[str, pd.DataFrame]:
    if df.empty:
        return {"train": df, "val": df, "final": df}
    d = df.copy()
    d["_ts"] = pd.to_datetime(d["market_timestamp"], errors="coerce")
    d = d.sort_values("_ts")
    n = len(d)
    i1 = max(int(n * train_frac), 1)
    i2 = max(int(n * (train_frac + val_frac)), i1 + 1)
    i2 = min(i2, n - 1) if n > 2 else n
    return {
        "train": d.iloc[:i1].drop(columns=["_ts"]),
        "val": d.iloc[i1:i2].drop(columns=["_ts"]),
        "final": d.iloc[i2:].drop(columns=["_ts"]),
    }


def numeric_matrix(df: pd.DataFrame, cols: list[str] | None = None) -> tuple[np.ndarray, list[str]]:
    cols = cols or [c for c in FEATURE_COLS if c not in {"symbol", "strategy", "direction", "session", "regime"}]
    # One-hot light categoricals that are usually present
    work = df.copy()
    for cat in ("strategy", "symbol", "session", "regime", "direction"):
        if cat in work.columns:
            dummies = pd.get_dummies(work[cat].astype(str), prefix=cat, dummy_na=True)
            work = pd.concat([work, dummies], axis=1)
            cols = cols + [c for c in dummies.columns if c not in cols]
    use = [c for c in cols if c in work.columns]
    X = work[use].apply(pd.to_numeric, errors="coerce")
    X = X.fillna(X.median(numeric_only=True))
    X = X.fillna(0.0)
    return X.to_numpy(dtype=float), use
