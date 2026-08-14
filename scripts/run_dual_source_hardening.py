"""Dual Yahoo + Databento research hardening. Uses local Databento caches only (no API spend)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent.research.dual_source_hardening import run_all


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--skip-sd-pa",
        action="store_true",
        help="Reuse prior SD/PA outputs; only (re)run full registry phases",
    )
    args = ap.parse_args()
    out = ROOT / "data" / "dual_source_hardening"
    # Est. from approved book cache pull (NQ+ES+CL+GC 180d)
    payload = run_all(out, est_spend=25.5875, skip_sd_pa=bool(args.skip_sd_pa))
    print("\n==== SD/PA VERDICTS ====", flush=True)
    for k, v in (payload.get("sd_pa") or {}).items():
        print(f"  {k}: {v.get('verdict')}", flush=True)
    print("==== REGISTRY ====", flush=True)
    for k, v in (payload.get("registry") or {}).items():
        print(
            f"  {k}: selected={v.get('n_selected')} gate_pass={v.get('n_gate_pass_final')}",
            flush=True,
        )
    print("Report:", out / "DUAL_SOURCE_HARDENING_REPORT.md", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
