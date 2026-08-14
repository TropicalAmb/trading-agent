"""Run the final nonlinear long-history regime-selector experiment."""

from __future__ import annotations

from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent.research.long_history_regime_selector import (
    run_long_history_regime_selector,
    write_regime_report,
)


def main() -> int:
    output_dir = ROOT / "data" / "long_history_regime_selector"
    payload = run_long_history_regime_selector(
        ROOT / "data" / "external_nq_quality" / "external_nq_2010_2025.parquet",
        ROOT / "data" / "databento",
        [
            ROOT / "data" / "long_history_strategy_validation" / "LONG_HISTORY_STRATEGY_VALIDATION.json",
            ROOT / "data" / "daily_ibs_validation" / "LONG_HISTORY_STRATEGY_VALIDATION.json",
        ],
        progress=lambda message: print(message, flush=True),
    )
    write_regime_report(payload, output_dir)
    print(json.dumps(payload, indent=2, default=str), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
