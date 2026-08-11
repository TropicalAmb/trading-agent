"""Silent stop for the trading agent (no console flash from PowerShell)."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from _win_silent import kill_pids, python_cmd_pids  # noqa: E402

DATA = ROOT / "data"
STOP = DATA / "STOP_AGENT"


def main() -> int:
    DATA.mkdir(parents=True, exist_ok=True)
    STOP.write_text("stop\n", encoding="utf-8")
    pids = (
        set(python_cmd_pids("run_supervised.py"))
        | set(python_cmd_pids("agent.live_main"))
        | set(python_cmd_pids("start_agent.py"))  # stuck Start consoles
    )
    # Never kill this stop script itself
    pids.discard(os.getpid())
    kill_pids(pids)
    time.sleep(1)
    pids2 = (
        set(python_cmd_pids("run_supervised.py"))
        | set(python_cmd_pids("agent.live_main"))
        | set(python_cmd_pids("start_agent.py"))
    )
    pids2.discard(os.getpid())
    kill_pids(pids2)
    # Restore Windows sleep / lid settings armed by overnight supervisor
    try:
        from overnight_power import disarm_overnight_power

        disarm_overnight_power()
        print("Overnight power policy restored (sleep/lid).")
    except Exception as exc:
        print(f"Overnight power restore skipped: {exc}")
    print(f"Stopped. Cleared {len(pids | pids2)} process(es). STOP_AGENT set.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
