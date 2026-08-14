"""Validate frozen BVC/VPIN-style OHLCV microstructure proxy hypotheses."""

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


PASS6_FAMILIES = (
    "bvc_cvd_divergence",
    "bvc_absorption_reversal",
    "bvc_pressure_breakout",
    "vpin_failed_extension",
    "impact_shock_reversal",
)


def main() -> int:
    output_dir = ROOT / "data" / "strategy_expansion_pass6"
    payload = run_long_history_validation(
        ROOT / "data" / "external_nq_quality" / "external_nq_2010_2025.parquet",
        ROOT / "data" / "databento",
        family_names=PASS6_FAMILIES,
        progress=lambda message: print(message, flush=True),
    )
    payload["proxy_warning"] = (
        "BVC/VPIN-style fields are estimated from one-minute OHLCV and are not true bid/ask delta, "
        "queue imbalance, cancellations, or depth. No strategy may be promoted on proxy semantics alone."
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
