"""Run supply/demand + price-action research pass. Does NOT modify paper config."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent.research.sd_pa_research import run_sd_pa_research


def main() -> int:
    out = ROOT / "data" / "sd_pa_research"
    summary = run_sd_pa_research(out)
    print("\n==== VERDICT ====", flush=True)
    print(summary["verdict"], flush=True)
    print(summary.get("note") or "", flush=True)
    print("Report:", out / "SD_PA_RESEARCH_REPORT.md", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
