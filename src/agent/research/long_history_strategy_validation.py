"""Long-history, leak-aware validation for high-hit-rate Reddit strategy ideas.

The public NQ file is development evidence only.  Parameters are selected on its
chronological validation segment, opened once on its holdout, and then frozen
before replay on the paid corrected Databento cache and current Yahoo bars.
Nothing in this module changes paper/live execution configuration.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
import json

import pandas as pd

from agent.research.broad_strategy_discovery import (
    FAMILY_SOURCE,
    FAMILY_SPECS,
    SOURCE_CATALOG,
    Candidate,
    SplitLock,
    _binomial_upper_tail,
    _four_block_stability,
    _resample_complete,
    _selection_score,
    _stats,
    freeze_split_lock,
    simulate_candidates,
)
from agent.research.current_specialist_validation import _verified_continuous_cache
from agent.research.harness.datasets import fetch_yahoo


# These are the high-hit-rate hypotheses from the broader 11-family screen.
# Breakout/trend families remain documented in broad discovery, but their public
# premise is high payoff at a lower win rate and therefore cannot meet this user-
# requested 70% objective by construction.
LONG_HISTORY_FAMILIES = (
    "vwap_band_reentry",
    "atr_rsi_failure_reversion",
    "intraday_capitulation_reversal",
    "trend_capitulation_reclaim",
    "london_range_sweep_reversal",
    "initial_balance_failed_break",
    "overnight_gap_reversion",
    "balanced_value_area_reversion",
    "daily_ibs_capitulation_reversion",
)

Progress = Callable[[str], None]


def _period_for_external(ts: str | pd.Timestamp, split: SplitLock) -> str:
    value = pd.Timestamp(ts)
    if value.tzinfo is not None:
        value = value.tz_convert("America/New_York").tz_localize(None)
    trade_day = (value + pd.Timedelta(hours=6)).normalize()
    development_end = pd.Timestamp(split.development_end).tz_localize(None)
    validation_end = pd.Timestamp(split.validation_end).tz_localize(None)
    if trade_day <= development_end:
        return "development"
    if trade_day <= validation_end:
        return "validation"
    return "holdout"


def _slice_external(
    rows: list[dict[str, Any]], split: SplitLock, period: str
) -> list[dict[str, Any]]:
    return [row for row in rows if _period_for_external(row["entry_ts"], split) == period]


def _long_gate(
    all_stats: dict[str, Any],
    validation: dict[str, Any],
    holdout: dict[str, Any],
) -> tuple[bool, list[str]]:
    failures: list[str] = []
    for ok, label in (
        (all_stats["n"] >= 100, "all_n<100"),
        (all_stats["wr"] >= 0.70, "all_WR<70%"),
        (all_stats["pf"] >= 1.30, "all_PF<1.30"),
        (all_stats["expectancy_r"] >= 0.15, "all_E<0.15R"),
        (validation["n"] >= 20, "validation_n<20"),
        (validation["wr"] >= 0.70, "validation_WR<70%"),
        (validation["pf"] >= 1.20, "validation_PF<1.20"),
        (validation["expectancy_r"] >= 0.10, "validation_E<0.10R"),
        (holdout["n"] >= 30, "holdout_n<30"),
        (holdout["wr"] >= 0.70, "holdout_WR<70%"),
        (holdout["pf"] >= 1.20, "holdout_PF<1.20"),
        (holdout["expectancy_r"] >= 0.10, "holdout_E<0.10R"),
        (bool(all_stats["anti_cheat_ok"]), "anti_cheat_fail"),
    ):
        if not ok:
            failures.append(label)
    return not failures, failures


def _current_gate(
    paid: dict[str, Any], independent: dict[str, Any]
) -> tuple[bool, list[str]]:
    failures: list[str] = []
    for ok, label in (
        (paid["n"] >= 10, "paid_recent_n<10"),
        (paid["wr"] >= 0.70, "paid_recent_WR<70%"),
        (paid["pf"] >= 1.20, "paid_recent_PF<1.20"),
        (paid["expectancy_r"] >= 0.10, "paid_recent_E<0.10R"),
        (independent["n"] >= 10, "independent_current_n<10"),
        (independent["wr"] >= 0.70, "independent_current_WR<70%"),
        (independent["pf"] >= 1.20, "independent_current_PF<1.20"),
        (independent["expectancy_r"] >= 0.10, "independent_current_E<0.10R"),
    ):
        if not ok:
            failures.append(label)
    return not failures, failures


def _interval_for(family: str) -> str:
    return "15m" if family in {
        "intraday_capitulation_reversal",
        "overnight_gap_reversion",
        "daily_ibs_capitulation_reversion",
    } else "5m"


def _annual_stats(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    years = sorted({pd.Timestamp(row["entry_ts"]).year for row in rows})
    return [
        {"year": year, **_stats([r for r in rows if pd.Timestamp(r["entry_ts"]).year == year])}
        for year in years
    ]


def _run_frozen(
    *,
    family: str,
    generator: Callable[..., list[Candidate]],
    spec: dict[str, Any],
    frames: dict[str, pd.DataFrame],
) -> list[dict[str, Any]]:
    interval = _interval_for(family)
    candidates = generator(frames["1m"], frames[interval], "NQ", spec)
    return simulate_candidates(candidates, frames["1m"])


def run_long_history_validation(
    external_parquet: Path,
    databento_cache_dir: Path,
    *,
    family_names: tuple[str, ...] | None = None,
    progress: Progress | None = None,
) -> dict[str, Any]:
    say = progress or (lambda _message: None)
    active_families = family_names or LONG_HISTORY_FAMILIES
    unknown = sorted(set(active_families) - set(LONG_HISTORY_FAMILIES))
    if unknown:
        raise ValueError(f"unknown long-history families: {unknown}")
    external_1m = pd.read_parquet(external_parquet).sort_index()
    split = freeze_split_lock(external_1m)
    external_frames = {
        "1m": external_1m,
        "5m": _resample_complete(external_1m, "5min"),
        "15m": _resample_complete(external_1m, "15min"),
    }
    paid_1m, paid_meta = _verified_continuous_cache(databento_cache_dir, "NQ")
    paid_frames = {
        "1m": paid_1m,
        "5m": _resample_complete(paid_1m, "5min"),
        "15m": _resample_complete(paid_1m, "15min"),
    }
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

    family_specs = {
        family: (generator, specs)
        for family, generator, specs in FAMILY_SPECS
        if family in active_families
    }
    variants: list[dict[str, Any]] = []
    rows_by_variant: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for family in active_families:
        generator, specs = family_specs[family]
        for spec in specs:
            variant = str(spec["id"])
            say(f"external {family}/{variant}")
            rows = _run_frozen(
                family=family,
                generator=generator,
                spec=spec,
                frames=external_frames,
            )
            rows_by_variant[(family, variant)] = rows
            variants.append(
                {
                    "family": family,
                    "variant": variant,
                    "spec": spec,
                    "source_id": FAMILY_SOURCE[family],
                    "development": _stats(_slice_external(rows, split, "development")),
                    "validation": _stats(_slice_external(rows, split, "validation")),
                    "selected": False,
                }
            )

    finalists: list[dict[str, Any]] = []
    for family in active_families:
        pool = [row for row in variants if row["family"] == family]
        selected = max(pool, key=lambda row: _selection_score(row["validation"]))
        selected["selected"] = True
        variant = str(selected["variant"])
        generator, specs = family_specs[family]
        spec = next(spec for spec in specs if str(spec["id"]) == variant)
        external_rows = rows_by_variant[(family, variant)]
        holdout = _stats(_slice_external(external_rows, split, "holdout"))
        all_stats = _stats(external_rows)
        long_pass, long_failures = _long_gate(all_stats, selected["validation"], holdout)

        say(f"paid-current {family}/{variant}")
        paid_rows = _run_frozen(
            family=family, generator=generator, spec=spec, frames=paid_frames
        )
        yahoo_rows = (
            _run_frozen(family=family, generator=generator, spec=spec, frames=yahoo_frames)
            if len(yahoo_5m)
            else []
        )
        paid_stats = _stats(paid_rows)
        yahoo_stats = _stats(yahoo_rows)
        current_pass, current_failures = _current_gate(paid_stats, yahoo_stats)
        finalists.append(
            {
                **selected,
                "external_all": all_stats,
                "external_holdout": holdout,
                "external_annual": _annual_stats(external_rows),
                "external_stability_4_blocks": _four_block_stability(external_rows),
                "external_long_gate_pass": long_pass,
                "external_long_gate_failures": long_failures,
                "paid_recent": paid_stats,
                "independent_yahoo_current": yahoo_stats,
                "current_dual_source_pass": current_pass,
                "current_dual_source_failures": current_failures,
                "paper_eligible": long_pass and current_pass,
            }
        )

    # Family finalists only—not every discarded variant—are multiplicity-adjusted.
    ordered = sorted(
        enumerate(finalists),
        key=lambda pair: _binomial_upper_tail(
            int(round(pair[1]["external_holdout"]["wr"] * pair[1]["external_holdout"]["n"])),
            int(pair[1]["external_holdout"]["n"]),
        ),
    )
    running = 0.0
    for rank, (index, row) in enumerate(ordered):
        stats = row["external_holdout"]
        p_value = _binomial_upper_tail(
            int(round(stats["wr"] * stats["n"])), int(stats["n"])
        )
        adjusted = min(1.0, (len(ordered) - rank) * p_value)
        running = max(running, adjusted)
        finalists[index]["external_holdout_p_holm"] = round(running, 6)

    paper_eligible = [row for row in finalists if row["paper_eligible"]]
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "PASS" if paper_eligible else "NO_STRATEGY_CLEARED_ALL_GATES",
        "purpose": "Start-over long-history validation of selective Reddit strategy hypotheses",
        "execution_change_made": False,
        "paper_remains_fail_closed": not bool(paper_eligible),
        "data_policy": {
            "external_development": external_parquet.name,
            "external_provenance": "WARN_UNVERIFIED_PROVENANCE; scale-error interval quarantined; research-only",
            "paid_final": "audited corrected Databento NQ.v.0 local cache; no API call or added spend",
            "independent_current": "Yahoo NQ=F 5m/60d; frozen variant; no refit",
            "position_management": "two contracts; half +1R; runner; break-even/trailing; stop-first ambiguity; friction",
        },
        "protocol": {
            "external_split": "50% development / 25% validation / 25% holdout by CME trade date",
            "selection": "one pre-declared variant per family selected on external validation only",
            "final_checks": "external holdout, then frozen paid-recent Databento and frozen Yahoo current",
            "no_overlap": "one open position per family/symbol",
            "paper_gate": "long-history gate AND paid-recent gate AND independent-current gate",
        },
        "external_split_lock": asdict(split),
        "external_rows_1m": len(external_1m),
        "external_window": [str(external_1m.index.min()), str(external_1m.index.max())],
        "paid_cache_identity": paid_meta.get("databento"),
        "paid_cache_quality": paid_meta.get("quality_audit"),
        "paid_window": [str(paid_1m.index.min()), str(paid_1m.index.max())],
        "yahoo_window": [str(yahoo_5m.index.min()), str(yahoo_5m.index.max())]
        if len(yahoo_5m)
        else None,
        "sources": SOURCE_CATALOG,
        "families": list(active_families),
        "n_families": len(active_families),
        "n_variants": len(variants),
        "variants_development_validation_only": variants,
        "finalists": finalists,
        "paper_eligible": paper_eligible,
    }


def write_long_history_report(payload: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "LONG_HISTORY_STRATEGY_VALIDATION.json").write_text(
        json.dumps(payload, indent=2, default=str), encoding="utf-8"
    )
    lines = [
        "# Long-History Strategy Validation",
        "",
        f"**Status: {payload['status']}**",
        "",
        "No paper strategy is enabled unless the external holdout, corrected paid Databento recent window, and independent current Yahoo window all pass. The external file is research-only.",
        "",
        "| Family | Variant | Long n | Long WR | Holdout n | Holdout WR | Paid n | Paid WR | Yahoo n | Yahoo WR | Eligible |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload["finalists"]:
        all_stats = row["external_all"]
        hold = row["external_holdout"]
        paid = row["paid_recent"]
        yahoo = row["independent_yahoo_current"]
        lines.append(
            f"| {row['family']} | {row['variant']} | {all_stats['n']} | {all_stats['wr']:.1%} | "
            f"{hold['n']} | {hold['wr']:.1%} | {paid['n']} | {paid['wr']:.1%} | "
            f"{yahoo['n']} | {yahoo['wr']:.1%} | {'YES' if row['paper_eligible'] else 'NO'} |"
        )
    lines.extend(
        [
            "",
            "## Method",
            "",
            "Public hypotheses were encoded as completed-bar rules with a small pre-declared parameter set. Selection used only the external validation segment. The final external holdout was opened after selection, and the chosen variant was then frozen for corrected Databento and Yahoo checks. All results include the configured two-contract scale-out, stop-first bar ambiguity, gap-through-stop handling, and friction.",
            "",
            "## Promotion decision",
            "",
            "Paper remains fail-closed unless `paper_eligible` contains a strategy. A high win rate with too few trades is explicitly rejected.",
        ]
    )
    (output_dir / "LONG_HISTORY_STRATEGY_VALIDATION.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )
