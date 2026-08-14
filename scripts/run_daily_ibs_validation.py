"""Run the explicitly 70%-claimed Reddit daily IBS family in isolation."""

from __future__ import annotations

from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent.research.long_history_strategy_validation import (
    run_long_history_validation,
    write_long_history_report,
)


def main() -> int:
    output_dir = ROOT / "data" / "daily_ibs_validation"
    payload = run_long_history_validation(
        ROOT / "data" / "external_nq_quality" / "external_nq_2010_2025.parquet",
        ROOT / "data" / "databento",
        family_names=("daily_ibs_capitulation_reversion",),
        progress=lambda message: print(message, flush=True),
    )
    write_long_history_report(payload, output_dir)
    finalist = payload["finalists"][0]
    print(
        json.dumps(
            {
                "status": payload["status"],
                "external_all": finalist["external_all"],
                "external_holdout": finalist["external_holdout"],
                "paid_recent": finalist["paid_recent"],
                "independent_yahoo_current": finalist["independent_yahoo_current"],
                "paper_eligible": finalist["paper_eligible"],
                "report": str(output_dir / "LONG_HISTORY_STRATEGY_VALIDATION.md"),
            },
            indent=2,
        ),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
