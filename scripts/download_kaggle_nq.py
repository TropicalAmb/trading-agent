"""Download Kaggle NQ 1m dataset into data/kaggle/ (gitignored)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent.data.kaggle_nq import DEFAULT_FILENAME, download_kaggle_nq


def main() -> None:
    path = download_kaggle_nq(dest_dir=ROOT / "data" / "kaggle")
    print(f"OK {path} ({path.stat().st_size} bytes) expected_name={DEFAULT_FILENAME}")


if __name__ == "__main__":
    main()
