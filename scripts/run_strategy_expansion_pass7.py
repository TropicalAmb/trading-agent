"""Validate frozen Reddit indicator, flag, rejection, and squeeze hypotheses."""

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


PASS7_FAMILIES = (
    "nq_macd_ema_vwap_momentum",
    "nq_flag_ema_vwap_pullback",
    "nq_vwap_ema9_rejection",
    "balanced_keltner_stochastic_reentry",
    "bollinger_keltner_mfi_squeeze",
)


def main() -> int:
    output_dir = ROOT / "data" / "strategy_expansion_pass7"
    payload = run_long_history_validation(
        ROOT / "data" / "external_nq_quality" / "external_nq_2010_2025.parquet",
        ROOT / "data" / "databento",
        family_names=PASS7_FAMILIES,
        progress=lambda message: print(message, flush=True),
    )
    payload["translation_warning"] = (
        "Reddit descriptions contain discretionary language. Each family is a frozen mechanical "
        "translation evaluated with the configured two-contract lifecycle; reported post win rates "
        "are hypotheses, not evidence for these implementations."
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
