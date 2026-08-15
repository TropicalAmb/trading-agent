"""Run broad, source-backed strategy discovery on audited local Databento caches."""

from __future__ import annotations

from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent.research.broad_strategy_discovery import run_discovery, write_discovery


def main() -> int:
    output_dir = ROOT / "data" / "broad_strategy_discovery"
    payload = run_discovery(ROOT / "data" / "databento")
    write_discovery(payload, output_dir)
    summary = {
        "status": payload["status"],
        "n_families": payload["n_families"],
        "n_variants": payload["n_variants"],
        "passing": [
            {
                "family": row["family"],
                "symbol": row["symbol"],
                "variant": row["variant"],
                "all": row["all"],
                "holdout": row["holdout"],
            }
            for row in payload["passing"]
        ],
        "passing_meta_selectors": payload.get("passing_meta_selectors", []),
        "report": str(output_dir / "BROAD_STRATEGY_DISCOVERY.md"),
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
