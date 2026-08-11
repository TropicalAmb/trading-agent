"""Databento onboarding helper — verifies key and optionally pulls a small NQ sample.

Usage:
  1) Sign up at https://databento.com (free credits ~$125 for new accounts)
  2) Copy API key (starts with db-) into .env:
       DATABENTO_API_KEY=db-xxxxxxxx
  3) pip install databento
  4) python scripts/setup_databento.py
  5) Optional pull:
       python scripts/setup_databento.py --pull-nq --days 30
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")


def main() -> int:
    parser = argparse.ArgumentParser(description="Databento setup / smoke test")
    parser.add_argument("--pull-nq", action="store_true", help="Pull NQ 1m bars sample")
    parser.add_argument("--days", type=int, default=7, help="Lookback days for sample pull")
    args = parser.parse_args()

    key = (os.getenv("DATABENTO_API_KEY") or "").strip()
    print("=== Databento setup ===")
    print("Package check...", flush=True)
    try:
        import databento as db  # noqa: F401

        print("  databento: OK")
    except ImportError:
        print("  databento: MISSING — run: pip install databento")
        return 1

    if not key:
        print("API key: MISSING")
        print("  1. Create account: https://databento.com")
        print("  2. Portal → API keys → copy key starting with db-")
        print("  3. Add to .env: DATABENTO_API_KEY=db-...")
        print("  4. Re-run this script")
        return 2

    print(f"API key: present ({key[:5]}…{key[-4:]})")
    from agent.data.databento_historical import DatabentoHistoricalProvider, cost_estimate_note

    print(cost_estimate_note())
    prov = DatabentoHistoricalProvider(api_key=key)
    print("Health:", prov.health())

    if args.pull_nq:
        print(f"Pulling NQ 5m for {args.days}d (uses credits)...", flush=True)
        try:
            bars = prov.get_bars("NQ", interval="5m", period=f"{args.days}d")
            print(f"  OK: {len(bars)} bars, first={bars[0].timestamp}, last={bars[-1].timestamp}")
            out = ROOT / "data" / "databento_cache"
            out.mkdir(parents=True, exist_ok=True)
            # Save a lightweight CSV for research scripts
            import pandas as pd

            df = prov.to_dataframe(bars)
            path = out / f"NQ_5m_{args.days}d.csv"
            df.to_csv(path)
            print(f"  Saved {path}")
        except Exception as exc:
            print(f"  PULL FAILED: {exc}")
            return 3
    else:
        print("Skip pull (pass --pull-nq to download a small sample and spend credits).")

    print("Done. Wire research scripts with market_data.provider=databento when ready.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
