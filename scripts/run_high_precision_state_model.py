"""Run the frozen high-precision NQ state-model validation."""

from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent.research.high_precision_state_model import (
    run_high_precision_state_model,
    write_high_precision_report,
)


def main() -> int:
    output_dir = ROOT / "data" / "high_precision_state_model"
    payload = run_high_precision_state_model(
        ROOT / "data" / "external_nq_quality" / "external_nq_2010_2025.parquet",
        ROOT / "data" / "databento",
        progress=lambda message: print(message, flush=True),
    )
    write_high_precision_report(payload, output_dir)
    print(
        json.dumps(
            {
                "status": payload["status"],
                "threshold": payload["selected_threshold"],
                "validation": payload["validation"],
                "holdout": payload["untouched_holdout"],
                "paid": payload["paid_databento_current"],
                "yahoo": payload["independent_yahoo_current"],
                "gate_failures": payload["gate_failures"],
                "report": str(output_dir / "HIGH_PRECISION_STATE_MODEL.md"),
            },
            indent=2,
        ),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
