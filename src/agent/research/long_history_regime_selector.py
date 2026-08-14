"""Nonlinear regime router trained only on old long-history strategy outcomes."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import json

import numpy as np
import pandas as pd

from agent.research.broad_strategy_discovery import (
    FAMILY_SPECS,
    _completed_feature_position,
    _entry_feature_frame,
    _resample_complete,
    _selection_score,
    _stats,
    freeze_split_lock,
    simulate_candidates,
)
from agent.research.current_specialist_validation import _verified_continuous_cache
from agent.research.harness.datasets import fetch_yahoo
from agent.research.long_history_strategy_validation import (
    LONG_HISTORY_FAMILIES,
    _interval_for,
    _period_for_external,
)


NUMERIC_FEATURES = (
    "ret_1",
    "ret_3",
    "ret_12",
    "volume_z",
    "trend_atr",
    "vwap_dist_atr",
    "atr_ratio",
    "rsi5_side",
)
CATEGORICAL_FEATURES = ("family", "hour", "weekday")


def _merge_variant_summaries(paths: list[Path]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        rows.extend(payload["variants_development_validation_only"])
    return rows


def _development_variants(summary_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    picked: list[dict[str, Any]] = []
    for family in LONG_HISTORY_FAMILIES:
        pool = [row for row in summary_rows if row["family"] == family]
        if pool:
            picked.append(max(pool, key=lambda row: _selection_score(row["development"])))
    return picked


def _feature_rows(
    trade_rows: list[dict[str, Any]],
    feature_frame: pd.DataFrame,
    *,
    split: Any | None,
) -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    feature_index = feature_frame.index
    for trade in trade_rows:
        entry_ts = pd.Timestamp(trade["entry_ts"])
        local_entry = entry_ts
        if entry_ts.tzinfo is not None:
            local_entry = entry_ts.tz_convert("America/New_York").tz_localize(None)
        feature_ts = local_entry
        if feature_index.tz is not None:
            feature_ts = local_entry.tz_localize("America/New_York").tz_convert(feature_index.tz)
        position = _completed_feature_position(feature_index, feature_ts)
        if position < 55:
            continue
        feature = feature_frame.iloc[position]
        side_sign = 1.0 if str(trade["side"]).upper() == "BUY" else -1.0
        values = {
            "ret_1": float(feature["ret_1"]) * side_sign,
            "ret_3": float(feature["ret_3"]) * side_sign,
            "ret_12": float(feature["ret_12"]) * side_sign,
            "volume_z": float(feature["volume_z"]),
            "trend_atr": float(feature["trend_atr"]) * side_sign,
            "vwap_dist_atr": float(feature["vwap_dist_atr"]) * side_sign,
            "atr_ratio": float(feature["atr_ratio"]),
            "rsi5_side": (float(feature["rsi5"]) - 50.0) / 50.0 * side_sign,
        }
        if not all(np.isfinite(value) for value in values.values()):
            continue
        period = None
        if split is not None:
            period = _period_for_external(local_entry, split)
            if _period_for_external(trade["exit_ts"], split) != period:
                continue
        records.append(
            {
                **values,
                "family": str(trade["family"]),
                "hour": int(local_entry.hour),
                "weekday": int(local_entry.dayofweek),
                "period": period,
                "won": int(float(trade["pnl_r"]) > 0),
                "pnl_r": float(trade["pnl_r"]),
                "entry_ts": str(entry_ts),
                "exit_ts": str(trade["exit_ts"]),
            }
        )
    return pd.DataFrame(records)


def _nonoverlap(part: pd.DataFrame, threshold: float) -> pd.DataFrame:
    eligible = part[part["probability"] >= threshold].copy()
    if eligible.empty:
        return eligible
    eligible["_entry"] = pd.to_datetime(eligible["entry_ts"], utc=True)
    eligible["_exit"] = pd.to_datetime(eligible["exit_ts"], utc=True)
    eligible = eligible.sort_values(["_entry", "probability"], ascending=[True, False])
    kept: list[int] = []
    unavailable_until: pd.Timestamp | None = None
    for index, row in eligible.iterrows():
        entry = pd.Timestamp(row["_entry"])
        if unavailable_until is not None and entry <= unavailable_until:
            continue
        kept.append(index)
        unavailable_until = pd.Timestamp(row["_exit"])
    return eligible.loc[kept].drop(columns=["_entry", "_exit"])


def _part_stats(part: pd.DataFrame, threshold: float) -> dict[str, Any]:
    filtered = _nonoverlap(part, threshold)
    return _stats(
        [
            {"pnl_r": float(row.pnl_r), "entry_ts": str(row.entry_ts)}
            for row in filtered.itertuples()
        ]
    )


def _generate_selected_rows(
    selected: list[dict[str, Any]], frames: dict[str, pd.DataFrame], progress: Any
) -> list[dict[str, Any]]:
    family_lookup = {family: (generator, specs) for family, generator, specs in FAMILY_SPECS}
    all_rows: list[dict[str, Any]] = []
    for selected_row in selected:
        family = str(selected_row["family"])
        variant = str(selected_row["variant"])
        generator, specs = family_lookup[family]
        spec = next(spec for spec in specs if str(spec["id"]) == variant)
        progress(f"base {family}/{variant}")
        candidates = generator(frames["1m"], frames[_interval_for(family)], "NQ", spec)
        all_rows.extend(simulate_candidates(candidates, frames["1m"]))
    return all_rows


def run_long_history_regime_selector(
    external_parquet: Path,
    databento_cache_dir: Path,
    variant_report_paths: list[Path],
    *,
    progress: Any | None = None,
) -> dict[str, Any]:
    from sklearn.compose import ColumnTransformer
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import OneHotEncoder, StandardScaler

    say = progress or (lambda _message: None)
    summaries = _merge_variant_summaries(variant_report_paths)
    selected = _development_variants(summaries)
    external_1m = pd.read_parquet(external_parquet).sort_index()
    external_frames = {
        "1m": external_1m,
        "5m": _resample_complete(external_1m, "5min"),
        "15m": _resample_complete(external_1m, "15min"),
    }
    split = freeze_split_lock(external_1m)
    external_trades = _generate_selected_rows(selected, external_frames, say)
    data = _feature_rows(external_trades, _entry_feature_frame(external_frames["5m"]), split=split)
    train = data[data["period"] == "development"].copy()
    validation = data[data["period"] == "validation"].copy()
    holdout = data[data["period"] == "holdout"].copy()
    if len(train) < 500 or train["won"].nunique() < 2 or len(validation) < 100:
        return {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "status": "INSUFFICIENT",
            "counts": {"development": len(train), "validation": len(validation), "holdout": len(holdout)},
        }

    model = Pipeline(
        [
            (
                "features",
                ColumnTransformer(
                    [
                        ("numeric", StandardScaler(), list(NUMERIC_FEATURES)),
                        (
                            "categorical",
                            OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                            list(CATEGORICAL_FEATURES),
                        ),
                    ],
                    sparse_threshold=0.0,
                ),
            ),
            (
                "model",
                HistGradientBoostingClassifier(
                    learning_rate=0.05,
                    max_iter=120,
                    max_depth=2,
                    min_samples_leaf=100,
                    l2_regularization=2.0,
                    random_state=1701,
                ),
            ),
        ]
    )
    columns = list(NUMERIC_FEATURES + CATEGORICAL_FEATURES)
    model.fit(train[columns], train["won"])
    for part in (train, validation, holdout):
        part["probability"] = model.predict_proba(part[columns])[:, 1] if len(part) else []

    thresholds: list[dict[str, Any]] = []
    for threshold in (0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80):
        thresholds.append({"threshold": threshold, "validation": _part_stats(validation, threshold)})
    viable = [
        row
        for row in thresholds
        if row["validation"]["n"] >= 30
        and row["validation"]["wr"] >= 0.70
        and row["validation"]["pf"] >= 1.30
        and row["validation"]["expectancy_r"] >= 0.15
    ]
    candidates = viable or [row for row in thresholds if row["validation"]["n"] >= 30] or thresholds
    chosen = max(
        candidates,
        key=lambda row: (
            row["validation"]["wr"],
            row["validation"]["expectancy_r"],
            row["validation"]["n"],
        ),
    )
    threshold = float(chosen["threshold"])
    external_stats = {
        "development": _part_stats(train, threshold),
        "validation": _part_stats(validation, threshold),
        "holdout": _part_stats(holdout, threshold),
    }

    paid_1m, paid_meta = _verified_continuous_cache(databento_cache_dir, "NQ")
    paid_frames = {
        "1m": paid_1m,
        "5m": _resample_complete(paid_1m, "5min"),
        "15m": _resample_complete(paid_1m, "15min"),
    }
    paid_trades = _generate_selected_rows(selected, paid_frames, say)
    paid_data = _feature_rows(paid_trades, _entry_feature_frame(paid_frames["5m"]), split=None)
    if len(paid_data):
        paid_data["probability"] = model.predict_proba(paid_data[columns])[:, 1]
    paid_stats = _part_stats(paid_data, threshold) if len(paid_data) else _stats([])

    try:
        yahoo_5m = fetch_yahoo("NQ=F", "5m", "60d").sort_index()
    except Exception:
        yahoo_5m = pd.DataFrame()
    yahoo_frames = {
        "1m": yahoo_5m,
        "5m": yahoo_5m,
        "15m": _resample_complete(yahoo_5m, "15min", base_minutes=5)
        if len(yahoo_5m)
        else pd.DataFrame(),
    }
    yahoo_trades = _generate_selected_rows(selected, yahoo_frames, say) if len(yahoo_5m) else []
    yahoo_data = (
        _feature_rows(yahoo_trades, _entry_feature_frame(yahoo_frames["5m"]), split=None)
        if len(yahoo_5m)
        else pd.DataFrame()
    )
    if len(yahoo_data):
        yahoo_data["probability"] = model.predict_proba(yahoo_data[columns])[:, 1]
    yahoo_stats = _part_stats(yahoo_data, threshold) if len(yahoo_data) else _stats([])

    failures: list[str] = []
    for ok, label in (
        (external_stats["validation"]["n"] >= 30, "validation_n<30"),
        (external_stats["validation"]["wr"] >= 0.70, "validation_WR<70%"),
        (external_stats["validation"]["pf"] >= 1.30, "validation_PF<1.30"),
        (external_stats["validation"]["expectancy_r"] >= 0.15, "validation_E<0.15R"),
        (external_stats["holdout"]["n"] >= 30, "holdout_n<30"),
        (external_stats["holdout"]["wr"] >= 0.70, "holdout_WR<70%"),
        (external_stats["holdout"]["pf"] >= 1.30, "holdout_PF<1.30"),
        (external_stats["holdout"]["expectancy_r"] >= 0.15, "holdout_E<0.15R"),
        (paid_stats["n"] >= 10, "paid_n<10"),
        (paid_stats["wr"] >= 0.70, "paid_WR<70%"),
        (paid_stats["pf"] >= 1.20, "paid_PF<1.20"),
        (paid_stats["expectancy_r"] >= 0.10, "paid_E<0.10R"),
        (yahoo_stats["n"] >= 10, "yahoo_n<10"),
        (yahoo_stats["wr"] >= 0.70, "yahoo_WR<70%"),
        (yahoo_stats["pf"] >= 1.20, "yahoo_PF<1.20"),
        (yahoo_stats["expectancy_r"] >= 0.10, "yahoo_E<0.10R"),
    ):
        if not ok:
            failures.append(label)
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "PASS" if not failures else "FAIL",
        "paper_eligible": not failures,
        "execution_change_made": False,
        "model": "single predeclared HistGradientBoosting classifier; depth=2, leaf>=100, L2=2",
        "anti_leakage": "model development only; fixed thresholds validation only; completed entry features; same-partition exit embargo; nonoverlap; untouched holdout",
        "selected_base_variants_on_development": [
            {"family": row["family"], "variant": row["variant"]} for row in selected
        ],
        "counts_before_probability_filter": {
            "development": len(train),
            "validation": len(validation),
            "holdout": len(holdout),
            "paid": len(paid_data),
            "yahoo": len(yahoo_data),
        },
        "threshold_search_validation_only": thresholds,
        "threshold": threshold,
        "external": external_stats,
        "paid_recent": paid_stats,
        "independent_yahoo_current": yahoo_stats,
        "failures": failures,
        "paid_cache_identity": paid_meta.get("databento"),
        "external_window": [str(external_1m.index.min()), str(external_1m.index.max())],
        "paid_window": [str(paid_1m.index.min()), str(paid_1m.index.max())],
        "yahoo_window": [str(yahoo_5m.index.min()), str(yahoo_5m.index.max())]
        if len(yahoo_5m)
        else None,
    }


def write_regime_report(payload: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "LONG_HISTORY_REGIME_SELECTOR.json").write_text(
        json.dumps(payload, indent=2, default=str), encoding="utf-8"
    )
    external = payload.get("external", {})
    lines = [
        "# Long-History Regime Selector",
        "",
        f"**Status: {payload['status']}**",
        "",
        "This research-only router can permit a frozen base family only when old-regime entry features predict a win. It does not alter paper configuration.",
        "",
        f"- Threshold selected on validation only: {payload.get('threshold', 'n/a')}",
    ]
    if external:
        for name in ("development", "validation", "holdout"):
            stats = external[name]
            lines.append(
                f"- {name.title()}: n={stats['n']}, WR={stats['wr']:.1%}, PF={stats['pf']:.2f}, E={stats['expectancy_r']:+.3f}R"
            )
        paid = payload["paid_recent"]
        yahoo = payload["independent_yahoo_current"]
        lines.extend(
            [
                f"- Paid recent: n={paid['n']}, WR={paid['wr']:.1%}, PF={paid['pf']:.2f}, E={paid['expectancy_r']:+.3f}R",
                f"- Yahoo current: n={yahoo['n']}, WR={yahoo['wr']:.1%}, PF={yahoo['pf']:.2f}, E={yahoo['expectancy_r']:+.3f}R",
                f"- Gate failures: {', '.join(payload['failures']) or 'none'}",
            ]
        )
    (output_dir / "LONG_HISTORY_REGIME_SELECTOR.md").write_text("\n".join(lines), encoding="utf-8")
