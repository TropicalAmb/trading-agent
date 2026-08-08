"""Reliable Start button for Windows double-click / desktop shortcut."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
STOP = DATA / "STOP_AGENT"
STATUS = DATA / "supervisor_status.json"
HTML = DATA / "paper_trading_view.html"
PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"
PYTHONW = ROOT / ".venv" / "Scripts" / "pythonw.exe"
SUPERVISOR = ROOT / "scripts" / "run_supervised.py"


def say(msg: str = "") -> None:
    print(msg, flush=True)


def find_supervisor_pids() -> list[int]:
    sys.path.insert(0, str(ROOT / "scripts"))
    try:
        from _win_silent import python_cmd_pids

        return python_cmd_pids("run_supervised.py")
    except Exception:
        return []


def clear_stop() -> None:
    if STOP.exists():
        STOP.unlink(missing_ok=True)


def run_healthcheck() -> bool:
    say("Checking market data...")
    r = subprocess.run(
        [str(PYTHON), str(ROOT / "scripts" / "healthcheck.py")],
        cwd=str(ROOT),
    )
    return r.returncode == 0


def install_autostart() -> None:
    flags = 0x08000000 if sys.platform == "win32" else 0  # CREATE_NO_WINDOW
    si = None
    if sys.platform == "win32":
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = 0
    for name in ("install_watchdog.ps1", "install_autostart.ps1"):
        ps1 = ROOT / "scripts" / name
        if not ps1.exists():
            continue
        say(f"Installing {name}...")
        subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-WindowStyle",
                "Hidden",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(ps1),
            ],
            cwd=str(ROOT),
            stdin=subprocess.DEVNULL,
            creationflags=flags,
            startupinfo=si,
        )


def launch_supervisor() -> None:
    exe = PYTHONW if PYTHONW.exists() else PYTHON
    subprocess.Popen(
        [str(exe), str(SUPERVISOR)],
        cwd=str(ROOT),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=0x00000008 | 0x08000000,  # DETACHED | CREATE_NO_WINDOW
        close_fds=True,
    )


def wait_until_running(timeout_sec: float = 20.0) -> bool:
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        pids = find_supervisor_pids()
        if pids and STATUS.exists():
            try:
                st = json.loads(STATUS.read_text(encoding="utf-8"))
                if st.get("state") in {"running", "started", "agent_exited"}:
                    # agent_exited briefly during restart still means supervisor is up
                    if st.get("state") == "running" or pids:
                        age = st.get("heartbeat_age_sec")
                        if st.get("state") == "running" or age is not None:
                            return True
            except Exception:
                pass
        if pids and time.time() > deadline - 5:
            return True
        time.sleep(1)
    return bool(find_supervisor_pids())


def open_paper_view() -> None:
    if HTML.exists():
        os.startfile(str(HTML))  # type: ignore[attr-defined]


def main() -> int:
    os.chdir(ROOT)
    os.environ["USE_MOCK_BROKER"] = "true"
    DATA.mkdir(parents=True, exist_ok=True)

    say("")
    say("=== Trading Agent Start ===")
    say(f"Folder: {ROOT}")
    say("")

    if not PYTHON.exists():
        say("ERROR: .venv Python missing. Open Cursor in trading-agent and recreate venv.")
        return 1

    clear_stop()

    existing = find_supervisor_pids()
    if existing:
        say(f"Already running (supervisor pid {existing[0]}).")
        say("Opening Paper View...")
        open_paper_view()
        say("")
        say("Nothing else to do. Use Stop Trading Agent if you want to shut it down.")
        return 0

    if not run_healthcheck():
        say("Health check failed — not starting.")
        return 1

    say("Installing login autostart (if allowed)...")
    install_autostart()

    say("Starting background supervisor...")
    launch_supervisor()

    ok = wait_until_running()
    if ok:
        say("SUCCESS — agent is running in the background.")
        if STATUS.exists():
            try:
                st = json.loads(STATUS.read_text(encoding="utf-8"))
                say(f"  state: {st.get('state')}  supervisor_pid: {st.get('supervisor_pid')}")
                say(f"  heartbeat_age_sec: {st.get('heartbeat_age_sec')}")
            except Exception:
                pass
    else:
        say("WARNING: started, but could not confirm yet.")
        say("Check data\\agent_supervisor.log")

    say("Opening Paper View...")
    open_paper_view()
    say("")
    say(f"Log: {DATA / 'agent_supervisor.log'}")
    say("You can close this window — the bot keeps running.")
    say(f"Checked at {datetime.now(timezone.utc).isoformat()}")
    return 0 if ok else 2


if __name__ == "__main__":
    code = main()
    say("")
    # Auto-close — do not leave a stuck "Press Enter" console open forever.
    # That was a major source of random leftover terminals on the desktop.
    if code == 0:
        say("Closing in 3 seconds...")
        time.sleep(3)
    else:
        say("Press Enter to close (error)...")
        try:
            input()
        except EOFError:
            time.sleep(8)
    raise SystemExit(code)
