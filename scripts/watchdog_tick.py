"""Independent watchdog tick — run by Windows Task Scheduler every 5 minutes.

MUST stay fully silent (no console flash). Task is Hidden + no WakeToRun.
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from _win_silent import kill_pids, popen_detached, python_cmd_pids  # noqa: E402

DATA = ROOT / "data"
LOG = DATA / "watchdog.log"
STATUS = DATA / "supervisor_status.json"
BLOTTER = DATA / "paper_trades.json"
STOP = DATA / "STOP_AGENT"
LOCK = DATA / "supervisor.lock"
PYTHONW = ROOT / ".venv" / "Scripts" / "pythonw.exe"
PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"
SUPERVISOR = ROOT / "scripts" / "run_supervised.py"

MAX_HEARTBEAT_AGE_SEC = 300
MAX_SUPERVISOR_STATUS_AGE_SEC = 360


def log(msg: str) -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    line = f"{datetime.now(timezone.utc).isoformat()} {msg}"
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def age_of_iso(ts: str | None) -> float | None:
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - dt).total_seconds()
    except Exception:
        return None


def supervisor_pids() -> list[int]:
    return python_cmd_pids("run_supervised.py")


def kill_all_agent_procs() -> None:
    pids = set(python_cmd_pids("run_supervised.py")) | set(
        python_cmd_pids("agent.live_main")
    )
    for pid in sorted(pids):
        log(f"watchdog killing pid={pid}")
    kill_pids(pids)


def start_supervisor() -> None:
    exe = PYTHONW if PYTHONW.exists() else PYTHON
    if STOP.exists():
        try:
            age = time.time() - STOP.stat().st_mtime
            if age > 600:
                STOP.unlink(missing_ok=True)
                log("cleared stale STOP_AGENT")
            else:
                log("STOP_AGENT present and recent — not starting")
                return
        except Exception:
            pass
    if supervisor_pids():
        log("supervisor already running — not starting another")
        return
    try:
        if LOCK.exists():
            LOCK.unlink(missing_ok=True)
            log("cleared orphan supervisor.lock")
    except Exception:
        pass

    log(f"starting supervisor via {exe}")
    popen_detached([str(exe), str(SUPERVISOR)], cwd=str(ROOT))


def heartbeat_age() -> float | None:
    if not BLOTTER.exists():
        return None
    try:
        data = json.loads(BLOTTER.read_text(encoding="utf-8"))
        return age_of_iso((data.get("heartbeat") or {}).get("ts"))
    except Exception:
        return None


def supervisor_status_age() -> float | None:
    if not STATUS.exists():
        return None
    try:
        data = json.loads(STATUS.read_text(encoding="utf-8"))
        return age_of_iso(data.get("ts"))
    except Exception:
        return None


def main() -> int:
    os.chdir(ROOT)
    DATA.mkdir(parents=True, exist_ok=True)

    if STOP.exists():
        try:
            age = time.time() - STOP.stat().st_mtime
        except Exception:
            age = 9999
        if age <= 600:
            log("healthy-skip: STOP_AGENT set by user")
            return 0

    hb = heartbeat_age()
    st = supervisor_status_age()
    pids = supervisor_pids()

    hb_ok = hb is not None and hb <= MAX_HEARTBEAT_AGE_SEC
    if hb_ok:
        log(
            f"ok hb={round(hb,1)}s status={None if st is None else round(st,1)}s pids={pids}"
        )
        return 0

    reasons: list[str] = [f"heartbeat_age={hb}"]
    if not pids:
        reasons.append("no supervisor process")
    if st is None or st > MAX_SUPERVISOR_STATUS_AGE_SEC:
        reasons.append(f"supervisor_status_age={st}")

    log(f"UNHEALTHY: {', '.join(reasons)} — restarting")
    kill_all_agent_procs()
    time.sleep(2)
    start_supervisor()
    time.sleep(8)
    hb2 = heartbeat_age()
    pids2 = supervisor_pids()
    log(f"after restart pids={pids2} hb={hb2}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
