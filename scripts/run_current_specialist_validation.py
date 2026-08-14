"""Run locked current-strategy replay and exact-stamp paper-forward report."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent.config import load_settings
from agent.research.current_specialist_validation import (
    run_yahoo_locked_replay,
    summarize_true_forward,
    write_report,
)


def main() -> int:
    cfg = load_settings(ROOT / "config" / "settings.yaml")
    stamp = str(cfg.get("config_version") or "")
    paper_path = ROOT / str((cfg.get("paper") or {}).get("json_path", "data/paper_trades.json"))
    state = (
        json.loads(paper_path.read_text(encoding="utf-8"))
        if paper_path.exists()
        else {}
    )
    payload = {
        "active_specialists": [
            name
            for name in ((cfg.get("confluence") or {}).get("engines") or [])
            if name in set(cfg.get("paper_specialist_engines") or [])
        ],
        "yahoo_locked_replay": run_yahoo_locked_replay(),
    }
    payload["true_forward"] = summarize_true_forward(
        state, stamp, payload["active_specialists"]
    )
    out = ROOT / "data" / "current_specialist_validation"
    write_report(payload, out)
    print(out / "CURRENT_SPECIALIST_VALIDATION.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
