"""Validate the frozen second-pass strategy families on long and current data."""

from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent.research.long_history_strategy_validation import (
    run_long_history_validation,
    write_long_history_report,
)


PASS2_FAMILIES = (
    "prior_day_level_failure",
    "opening_range_retest_continuation",
    "opening_range_midpoint_continuation",
    "conditional_overnight_reversal",
    "value_area_breakout_continuation",
    "overnight_range_break_retest",
    "session_extreme_two_bar_reversal",
    "weekly_value_area_failed_auction",
)


def main() -> int:
    output_dir = ROOT / "data" / "strategy_expansion_pass2"
    payload = run_long_history_validation(
        ROOT / "data" / "external_nq_quality" / "external_nq_2010_2025.parquet",
        ROOT / "data" / "databento",
        family_names=PASS2_FAMILIES,
        progress=lambda message: print(message, flush=True),
    )
    write_long_history_report(payload, output_dir)
    print(
        json.dumps(
            {
                "status": payload["status"],
                "families": payload["n_families"],
                "variants": payload["n_variants"],
                "paper_eligible": [
                    {"family": row["family"], "variant": row["variant"]}
                    for row in payload["paper_eligible"]
                ],
                "report": str(output_dir / "LONG_HISTORY_STRATEGY_VALIDATION.md"),
            },
            indent=2,
        ),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
