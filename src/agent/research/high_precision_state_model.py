"""Leak-aware, high-precision NQ market-state model research.

The model is intentionally isolated from paper execution. It learns only from
completed 15-minute bars in the old research-only NQ history, fixes its entry
threshold on the chronological validation segment, and is then evaluated once
on the untouched long holdout plus corrected Databento and Yahoo current data.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from math import pi
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from agent.research.broad_strategy_discovery import (
    Candidate,
    SplitLock,
    _resample_complete,
    _session_vwap_features,
    _stats,
    _trade_day,
    freeze_split_lock,
    simulate_candidates,
)
from agent.research.current_specialist_validation import _verified_continuous_cache
from agent.research.harness.datasets import fetch_yahoo


FEATURE_COLUMNS = (
    "ret1_side",
    "ret2_side",
    "ret4_side",
    "ret16_side",
    "trend_side",
    "vwap_side",
    "rsi_side",
    "body_side",
    "wick_balance_side",
    "range16_side",
    "range64_side",
    "session_return_side",
    "atr_ratio",
    "volume_z",
    "bar_range_atr",
    "hour_sin",
    "hour_cos",
    "weekday_sin",
    "weekday_cos",
)

MODEL_PARAMS = {
    "learning_rate": 0.05,
    "max_iter": 160,
    "max_depth": 3,
    "min_samples_leaf": 200,
    "l2_regularization": 5.0,
    "random_state": 20260814,
}
RISK_ATR = 0.75
TARGET_R = 1.60
MAX_HOLD_MINUTES = 120
SIDE_MARGIN = 0.05
THRESHOLDS = (0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90)


def _state_frame(bars_15m: pd.DataFrame) -> pd.DataFrame:
    f = _session_vwap_features(bars_15m).copy()
    f["ret1"] = f["close"].pct_change(1)
    f["ret2"] = f["close"].pct_change(2)
    f["ret4"] = f["close"].pct_change(4)
    f["ret16"] = f["close"].pct_change(16)
    ema12 = f["close"].ewm(span=12, adjust=False).mean()
    ema48 = f["close"].ewm(span=48, adjust=False).mean()
    f["trend"] = (ema12 - ema48) / f["atr"].replace(0, np.nan)
    f["vwap_distance"] = (f["close"] - f["vwap"]) / f["atr"].replace(0, np.nan)
    f["rsi_centered"] = (f["rsi5"] - 50.0) / 50.0
    f["body"] = (f["close"] - f["open"]) / f["atr"].replace(0, np.nan)
    upper_wick = f["high"] - f[["open", "close"]].max(axis=1)
    lower_wick = f[["open", "close"]].min(axis=1) - f["low"]
    f["wick_balance"] = (lower_wick - upper_wick) / f["atr"].replace(0, np.nan)
    for lookback in (16, 64):
        rolling_high = f["high"].rolling(lookback).max()
        rolling_low = f["low"].rolling(lookback).min()
        position = (f["close"] - rolling_low) / (rolling_high - rolling_low).replace(0, np.nan)
        f[f"range{lookback}"] = position - 0.5
    trade_days = pd.Series(_trade_day(f.index), index=f.index)
    session_open = f["open"].groupby(trade_days).transform("first")
    f["session_return"] = (f["close"] - session_open) / f["atr"].replace(0, np.nan)
    f["atr_ratio_feature"] = f["atr_fast"] / f["atr_slow"].replace(0, np.nan)
    volume_mean = f["volume"].shift(1).rolling(100).mean()
    volume_std = f["volume"].shift(1).rolling(100).std(ddof=0).replace(0, np.nan)
    f["volume_z_feature"] = (f["volume"] - volume_mean) / volume_std
    f["bar_range_atr_feature"] = (f["high"] - f["low"]) / f["atr"].replace(0, np.nan)
    minutes = f.index.hour * 60 + f.index.minute
    f["hour_sin_feature"] = np.sin(2.0 * pi * minutes / (24.0 * 60.0))
    f["hour_cos_feature"] = np.cos(2.0 * pi * minutes / (24.0 * 60.0))
    f["weekday_sin_feature"] = np.sin(2.0 * pi * f.index.dayofweek / 5.0)
    f["weekday_cos_feature"] = np.cos(2.0 * pi * f.index.dayofweek / 5.0)
    return f


def _feature_values(row: pd.Series, side: str) -> dict[str, float]:
    sign = 1.0 if side == "BUY" else -1.0
    return {
        "ret1_side": float(row["ret1"]) * sign,
        "ret2_side": float(row["ret2"]) * sign,
        "ret4_side": float(row["ret4"]) * sign,
        "ret16_side": float(row["ret16"]) * sign,
        "trend_side": float(row["trend"]) * sign,
        "vwap_side": float(row["vwap_distance"]) * sign,
        "rsi_side": float(row["rsi_centered"]) * sign,
        "body_side": float(row["body"]) * sign,
        "wick_balance_side": float(row["wick_balance"]) * sign,
        "range16_side": float(row["range16"]) * sign,
        "range64_side": float(row["range64"]) * sign,
        "session_return_side": float(row["session_return"]) * sign,
        "atr_ratio": float(row["atr_ratio_feature"]),
        "volume_z": float(row["volume_z_feature"]),
        "bar_range_atr": float(row["bar_range_atr_feature"]),
        "hour_sin": float(row["hour_sin_feature"]),
        "hour_cos": float(row["hour_cos_feature"]),
        "weekday_sin": float(row["weekday_sin_feature"]),
        "weekday_cos": float(row["weekday_cos_feature"]),
    }


def build_decision_rows(
    bars_15m: pd.DataFrame, *, include_label: bool
) -> pd.DataFrame:
    """Create two side-specific rows at each half hour using completed features."""
    f = _state_frame(bars_15m)
    records: list[dict[str, Any]] = []
    horizon_bars = int(MAX_HOLD_MINUTES / 15)
    final_signal_position = len(f) - horizon_bars - 1 if include_label else len(f) - 2
    for i in range(100, max(100, final_signal_position + 1)):
        signal_ts = pd.Timestamp(f.index[i])
        if signal_ts.minute not in (0, 30) or signal_ts.hour == 17:
            continue
        row = f.iloc[i]
        values = _feature_values(row, "BUY")
        if not all(np.isfinite(value) for value in values.values()):
            continue
        entry_position = i + 1
        entry_ts = pd.Timestamp(f.index[entry_position])
        entry = float(f["open"].iloc[entry_position])
        risk = RISK_ATR * float(row["atr"])
        if not np.isfinite(entry) or not np.isfinite(risk) or risk <= 0:
            continue
        for side in ("BUY", "SELL"):
            record: dict[str, Any] = {
                **_feature_values(row, side),
                "signal_ts": str(signal_ts),
                "entry_ts": str(entry_ts),
                "side": side,
                "entry": entry,
                "stop": entry - risk if side == "BUY" else entry + risk,
                "risk_points": risk,
            }
            if include_label:
                target = entry + risk if side == "BUY" else entry - risk
                stop = float(record["stop"])
                label = 0
                label_exit_ts = pd.Timestamp(f.index[min(len(f) - 1, entry_position + horizon_bars - 1)])
                for j in range(entry_position, min(len(f), entry_position + horizon_bars)):
                    future = f.iloc[j]
                    stop_hit = float(future["low"]) <= stop if side == "BUY" else float(future["high"]) >= stop
                    target_hit = float(future["high"]) >= target if side == "BUY" else float(future["low"]) <= target
                    if stop_hit:
                        label_exit_ts = pd.Timestamp(f.index[j])
                        break
                    if target_hit:
                        label = 1
                        label_exit_ts = pd.Timestamp(f.index[j])
                        break
                record["won_tp1_before_stop"] = label
                record["label_exit_ts"] = str(label_exit_ts)
            records.append(record)
    return pd.DataFrame.from_records(records)


def _assign_periods(rows: pd.DataFrame, split: SplitLock) -> pd.Series:
    entry = pd.to_datetime(rows["entry_ts"], utc=True).dt.tz_convert("America/New_York")
    trade_day = (entry + pd.Timedelta(hours=6)).dt.normalize().dt.tz_localize(None)
    development_end = pd.Timestamp(split.development_end).tz_localize(None)
    validation_end = pd.Timestamp(split.validation_end).tz_localize(None)
    return pd.Series(
        np.where(
            trade_day <= development_end,
            "development",
            np.where(trade_day <= validation_end, "validation", "holdout"),
        ),
        index=rows.index,
    )


def _candidates(
    rows: pd.DataFrame,
    probabilities: np.ndarray,
    threshold: float,
) -> list[Candidate]:
    scored = rows.copy()
    scored["probability"] = probabilities
    out: list[Candidate] = []
    for _entry_ts, group in scored.groupby("entry_ts", sort=True):
        ordered = group.sort_values("probability", ascending=False)
        best = ordered.iloc[0]
        second_probability = float(ordered.iloc[1]["probability"]) if len(ordered) > 1 else 0.0
        probability = float(best["probability"])
        if probability < threshold or probability - second_probability < SIDE_MARGIN:
            continue
        entry_ts = pd.Timestamp(best["entry_ts"])
        out.append(
            Candidate(
                family="high_precision_state_model",
                variant=f"hgb_depth3_threshold_{threshold:.2f}",
                source_id="regime_selector",
                symbol="NQ",
                side=str(best["side"]),
                signal_ts=str(best["signal_ts"]),
                entry_ts=str(entry_ts),
                entry=float(best["entry"]),
                stop=float(best["stop"]),
                target_r=TARGET_R,
                forced_exit_ts=str(entry_ts + pd.Timedelta(minutes=MAX_HOLD_MINUTES)),
                notes=(
                    "Predeclared shallow HGB; completed 15m state; opposing-side margin; "
                    "0.75 ATR hard stop; configured 1R scale-out and runner"
                ),
            )
        )
    return out


def _replay(
    rows: pd.DataFrame,
    probabilities: np.ndarray,
    threshold: float,
    execution_bars: pd.DataFrame,
) -> list[dict[str, Any]]:
    return simulate_candidates(_candidates(rows, probabilities, threshold), execution_bars)


def _selection_score(row: dict[str, Any]) -> tuple[int, int, float, float, float, int]:
    stats = row["validation"]
    desired = int(
        stats["n"] >= 50
        and stats["wr"] >= 0.70
        and stats["pf"] >= 1.30
        and stats["expectancy_r"] >= 0.15
    )
    viable = int(stats["n"] >= 50 and stats["pf"] >= 1.0 and stats["expectancy_r"] > 0)
    return (
        desired,
        viable,
        float(stats["wr_wilson_95"][0]),
        float(stats["expectancy_r"]),
        float(stats["pf"]),
        int(stats["n"]),
    )


def _gate(
    validation: dict[str, Any],
    holdout: dict[str, Any],
    paid: dict[str, Any],
    yahoo: dict[str, Any],
) -> list[str]:
    failures: list[str] = []
    checks = (
        (validation["n"] >= 50, "validation_n<50"),
        (validation["wr"] >= 0.70, "validation_WR<70%"),
        (validation["pf"] >= 1.30, "validation_PF<1.30"),
        (validation["expectancy_r"] >= 0.15, "validation_E<0.15R"),
        (holdout["n"] >= 50, "holdout_n<50"),
        (holdout["wr"] >= 0.70, "holdout_WR<70%"),
        (holdout["pf"] >= 1.30, "holdout_PF<1.30"),
        (holdout["expectancy_r"] >= 0.15, "holdout_E<0.15R"),
        (paid["n"] >= 10, "paid_n<10"),
        (paid["wr"] >= 0.70, "paid_WR<70%"),
        (paid["pf"] >= 1.20, "paid_PF<1.20"),
        (paid["expectancy_r"] >= 0.10, "paid_E<0.10R"),
        (yahoo["n"] >= 10, "yahoo_n<10"),
        (yahoo["wr"] >= 0.70, "yahoo_WR<70%"),
        (yahoo["pf"] >= 1.20, "yahoo_PF<1.20"),
        (yahoo["expectancy_r"] >= 0.10, "yahoo_E<0.10R"),
    )
    for ok, label in checks:
        if not ok:
            failures.append(label)
    return failures


def run_high_precision_state_model(
    external_parquet: Path,
    databento_cache_dir: Path,
    *,
    progress: Any | None = None,
) -> dict[str, Any]:
    from sklearn.ensemble import HistGradientBoostingClassifier

    say = progress or (lambda _message: None)
    external_1m = pd.read_parquet(external_parquet).sort_index()
    external_15m = _resample_complete(external_1m, "15min")
    split = freeze_split_lock(external_1m)
    say("build external decision labels")
    labeled = build_decision_rows(external_15m, include_label=True)
    labeled["period"] = _assign_periods(labeled, split)
    exit_period = _assign_periods(
        labeled.rename(columns={"entry_ts": "original_entry_ts", "label_exit_ts": "entry_ts"}),
        split,
    )
    labeled = labeled[exit_period == labeled["period"]].copy()
    development = labeled[labeled["period"] == "development"].copy()
    validation = labeled[labeled["period"] == "validation"].copy()
    holdout = labeled[labeled["period"] == "holdout"].copy()
    if len(development) < 5000 or development["won_tp1_before_stop"].nunique() < 2:
        raise RuntimeError("insufficient external development rows")
    say(f"fit model on {len(development)} development rows")
    model = HistGradientBoostingClassifier(**MODEL_PARAMS)
    model.fit(development[list(FEATURE_COLUMNS)], development["won_tp1_before_stop"])
    development_probability = model.predict_proba(development[list(FEATURE_COLUMNS)])[:, 1]
    validation_probability = model.predict_proba(validation[list(FEATURE_COLUMNS)])[:, 1]
    holdout_probability = model.predict_proba(holdout[list(FEATURE_COLUMNS)])[:, 1]

    threshold_rows: list[dict[str, Any]] = []
    for threshold in THRESHOLDS:
        say(f"validation threshold {threshold:.2f}")
        rows = _replay(validation, validation_probability, threshold, external_1m)
        threshold_rows.append({"threshold": threshold, "validation": _stats(rows)})
    selected = max(threshold_rows, key=_selection_score)
    threshold = float(selected["threshold"])
    say(f"open untouched holdout at threshold {threshold:.2f}")
    development_stats = _stats(
        _replay(development, development_probability, threshold, external_1m)
    )
    validation_stats = selected["validation"]
    holdout_stats = _stats(_replay(holdout, holdout_probability, threshold, external_1m))

    paid_1m, paid_meta = _verified_continuous_cache(databento_cache_dir, "NQ")
    paid_15m = _resample_complete(paid_1m, "15min")
    paid_rows = build_decision_rows(paid_15m, include_label=False)
    paid_probability = model.predict_proba(paid_rows[list(FEATURE_COLUMNS)])[:, 1]
    paid_stats = _stats(_replay(paid_rows, paid_probability, threshold, paid_1m))

    try:
        yahoo_5m = fetch_yahoo("NQ=F", "5m", "60d").sort_index()
    except Exception:
        yahoo_5m = pd.DataFrame()
    if len(yahoo_5m):
        yahoo_15m = _resample_complete(yahoo_5m, "15min", base_minutes=5)
        yahoo_rows = build_decision_rows(yahoo_15m, include_label=False)
        yahoo_probability = model.predict_proba(yahoo_rows[list(FEATURE_COLUMNS)])[:, 1]
        yahoo_stats = _stats(_replay(yahoo_rows, yahoo_probability, threshold, yahoo_5m))
        yahoo_window = [str(yahoo_5m.index.min()), str(yahoo_5m.index.max())]
    else:
        yahoo_stats = _stats([])
        yahoo_window = None
    failures = _gate(validation_stats, holdout_stats, paid_stats, yahoo_stats)
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "PASS" if not failures else "FAIL",
        "purpose": "Predeclared high-precision NQ state model with chronological external training and frozen current checks",
        "execution_change_made": False,
        "paper_remains_fail_closed": bool(failures),
        "model": "HistGradientBoostingClassifier",
        "model_params": MODEL_PARAMS,
        "features": list(FEATURE_COLUMNS),
        "feature_timing": "completed 15m signal bar; next 15m open entry; no future/unfinished features",
        "decision_cadence": "one opportunity per side every 30 minutes; highest side requires 0.05 probability margin",
        "label": "1R TP1 before 1R stop within 120 minutes; stop-first ambiguity",
        "execution": {
            "risk_atr": RISK_ATR,
            "target_r": TARGET_R,
            "maximum_hold_minutes": MAX_HOLD_MINUTES,
            "configured_two_contract_management": True,
            "friction": True,
        },
        "split_lock": split.__dict__,
        "row_counts": {
            "development": len(development),
            "validation": len(validation),
            "holdout": len(holdout),
        },
        "threshold_search_validation_only": threshold_rows,
        "selected_threshold": threshold,
        "development": development_stats,
        "validation": validation_stats,
        "untouched_holdout": holdout_stats,
        "paid_databento_current": paid_stats,
        "independent_yahoo_current": yahoo_stats,
        "gate_failures": failures,
        "paid_cache_identity": paid_meta.get("databento"),
        "paid_window": [str(paid_1m.index.min()), str(paid_1m.index.max())],
        "yahoo_window": yahoo_window,
        "anti_overfit": [
            "model hyperparameters and feature list predeclared before results",
            "model fitted on development only",
            "probability threshold selected on validation only",
            "holdout opened once after threshold freeze",
            "current Databento and Yahoo evaluated without refit",
            "all final performance uses non-overlapping configured execution replay",
        ],
    }


def write_high_precision_report(payload: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "HIGH_PRECISION_STATE_MODEL.json").write_text(
        json.dumps(payload, indent=2, default=str), encoding="utf-8"
    )
    lines = [
        "# High-Precision NQ State Model",
        "",
        f"**Status: {payload['status']}**",
        "",
        f"- Frozen validation threshold: {payload['selected_threshold']:.2f}",
        f"- Model: `{payload['model']}` with predeclared shallow depth and regularization",
        f"- Feature timing: {payload['feature_timing']}",
        "",
        "| Segment | n | WR | PF | Expectancy |",
        "|---|---:|---:|---:|---:|",
    ]
    for label, key in (
        ("Development", "development"),
        ("Validation", "validation"),
        ("Untouched long holdout", "untouched_holdout"),
        ("Paid Databento current", "paid_databento_current"),
        ("Independent Yahoo current", "independent_yahoo_current"),
    ):
        stats = payload[key]
        lines.append(
            f"| {label} | {stats['n']} | {stats['wr']:.1%} | {stats['pf']:.2f} | {stats['expectancy_r']:+.3f}R |"
        )
    lines.extend(
        [
            "",
            "## Promotion decision",
            "",
            (
                "Every validation, untouched holdout, paid-current, and independent-current gate passed."
                if payload["status"] == "PASS"
                else "No paper change. Gate failures: " + ", ".join(payload["gate_failures"])
            ),
            "",
            "The label is used only for development training. Every displayed performance row comes from the configured two-contract replay with stop-first ambiguity and friction.",
        ]
    )
    (output_dir / "HIGH_PRECISION_STATE_MODEL.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
