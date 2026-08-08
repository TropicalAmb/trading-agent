"""Always-on supervisor for the trading agent.

Hardening vs overnight death:
- Detached child (no Ctrl+C)
- Stale-heartbeat kill + restart
- No hanging PowerShell cleanup
- Stay-awake requests every poll
- Never exit on Yahoo blips (agent retries; supervisor always relaunches)
"""

from __future__ import annotations

import atexit
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
LOG = DATA / "agent_supervisor.log"
AGENT_LOG = DATA / "agent_runtime.log"
LOCK_FILE = DATA / "supervisor.lock"
STOP_FILE = DATA / "STOP_AGENT"
STATUS_FILE = DATA / "supervisor_status.json"
BLOTTER_JSON = DATA / "paper_trades.json"

PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"
PYTHONW = ROOT / ".venv" / "Scripts" / "pythonw.exe"
AGENT_PY = PYTHONW if PYTHONW.exists() else PYTHON
CMD = [str(AGENT_PY), "-m", "agent.live_main", "--mock", "--webhook"]

# Stuck detection: NO_NEW_BAR (same 5m bar) is healthy — only missing scheduler ticks are stuck.
SCHEDULER_WARNING_SEC = 90
SCHEDULER_STUCK_SEC = 150
STALE_HEARTBEAT_SEC = SCHEDULER_STUCK_SEC  # backward-compatible name
WATCH_POLL_SEC = 20
RESTART_STATE_FILE = DATA / "supervisor_restarts.json"
CREATE_NEW_PROCESS_GROUP = 0x00000200
DETACHED_PROCESS = 0x00000008
CREATE_NO_WINDOW = 0x08000000

_lock_fh = None
_mutex_handle = None


def log(msg: str) -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    line = f"{datetime.now(timezone.utc).isoformat()} {msg}"
    try:
        print(line, flush=True)
    except Exception:
        pass
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def explain_exit(code: int) -> str:
    u = code & 0xFFFFFFFF
    known = {
        0: "clean exit",
        1: "error exit",
        0xC000013A: "killed by Ctrl+C / console close (0xC000013A)",
        0xC0000005: "access violation (0xC0000005)",
    }
    return known.get(u, f"exit {code} (unsigned={u})")


def write_status(**kwargs) -> None:
    payload = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "supervisor_pid": os.getpid(),
        **kwargs,
    }
    STATUS_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def prevent_sleep(enable: bool = True) -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ES_CONTINUOUS = 0x80000000
        ES_SYSTEM_REQUIRED = 0x00000001
        ES_AWAYMODE_REQUIRED = 0x00000040
        if enable:
            flag = ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_AWAYMODE_REQUIRED
        else:
            flag = ES_CONTINUOUS
        ctypes.windll.kernel32.SetThreadExecutionState(flag)
    except Exception as exc:
        log(f"prevent_sleep failed: {exc}")


def acquire_lock() -> bool:
    """Single-instance lock via Windows named mutex + file PID marker."""
    global _lock_fh, _mutex_handle
    DATA.mkdir(parents=True, exist_ok=True)

    # Hard guarantee on Windows: only one supervisor across Task Scheduler races
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes

            kernel32 = ctypes.windll.kernel32
            kernel32.CreateMutexW.argtypes = [
                wintypes.LPVOID,
                wintypes.BOOL,
                wintypes.LPCWSTR,
            ]
            kernel32.CreateMutexW.restype = wintypes.HANDLE
            kernel32.GetLastError.restype = wintypes.DWORD
            kernel32.SetLastError.argtypes = [wintypes.DWORD]

            ERROR_ALREADY_EXISTS = 183
            WAIT_OBJECT_0 = 0
            WAIT_TIMEOUT = 258

            kernel32.SetLastError(0)
            handle = kernel32.CreateMutexW(
                None, False, "Global\\TradingAgentSupervisorMutex"
            )
            if not handle:
                log("CreateMutexW returned NULL")
                return False
            # Take ownership with zero-timeout wait (atomic across processes)
            wait = kernel32.WaitForSingleObject(handle, 0)
            if wait != WAIT_OBJECT_0:
                kernel32.CloseHandle(handle)
                log(f"mutex busy (wait={wait}) — exiting duplicate")
                return False
            _mutex_handle = handle
        except Exception as exc:
            log(f"mutex acquire failed (falling back to file lock): {exc}")

    if LOCK_FILE.exists():
        try:
            raw = LOCK_FILE.read_text(encoding="utf-8").strip()
            old_pid = int(raw) if raw.isdigit() else -1
            if old_pid > 0 and old_pid != os.getpid():
                try:
                    os.kill(old_pid, 0)
                    return False
                except OSError:
                    LOCK_FILE.unlink(missing_ok=True)
            else:
                LOCK_FILE.unlink(missing_ok=True)
        except Exception:
            pass
    try:
        fd = os.open(str(LOCK_FILE), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        _lock_fh = os.fdopen(fd, "w", encoding="utf-8")
        _lock_fh.write(str(os.getpid()))
        _lock_fh.flush()
        return True
    except FileExistsError:
        return False
    except OSError:
        return False


def release_lock() -> None:
    global _lock_fh, _mutex_handle
    if _lock_fh is not None:
        try:
            _lock_fh.close()
        except Exception:
            pass
        _lock_fh = None
    try:
        if LOCK_FILE.exists():
            raw = LOCK_FILE.read_text(encoding="utf-8").strip()
            if raw == str(os.getpid()) or not raw:
                LOCK_FILE.unlink(missing_ok=True)
    except Exception:
        pass
    if _mutex_handle is not None and sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.kernel32.ReleaseMutex(_mutex_handle)
            ctypes.windll.kernel32.CloseHandle(_mutex_handle)
        except Exception:
            pass
        _mutex_handle = None


def kill_pid_tree(pid: int) -> None:
    if pid <= 0:
        return
    flags = CREATE_NO_WINDOW if sys.platform == "win32" else 0
    si = None
    if sys.platform == "win32":
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = 0
    subprocess.run(
        ["taskkill", "/PID", str(pid), "/T", "/F"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        timeout=15,
        creationflags=flags,
        startupinfo=si,
    )


def kill_stray_agents(*, keep_pid: int | None = None) -> None:
    """Cleanup stray live_main processes — silent (no console flash)."""
    try:
        sys.path.insert(0, str(ROOT / "scripts"))
        from _win_silent import python_cmd_pids

        pids = python_cmd_pids("agent.live_main")
    except Exception as exc:
        log(f"stray cleanup skipped: {exc}")
        return

    for pid in pids:
        if keep_pid and pid == keep_pid:
            continue
        log(f"Killing stray live_main pid={pid}")
        try:
            # Never kill our own PID / process tree root
            if pid == os.getpid():
                continue
            kill_pid_tree(pid)
        except Exception as exc:
            log(f"kill failed pid={pid}: {exc}")


def heartbeat_age_sec() -> float | None:
    if not BLOTTER_JSON.exists():
        return None
    try:
        data = json.loads(BLOTTER_JSON.read_text(encoding="utf-8"))
        ts = (data.get("heartbeat") or {}).get("ts")
        if not ts:
            return None
        hb = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        if hb.tzinfo is None:
            hb = hb.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - hb).total_seconds()
    except Exception:
        return None


def load_restart_state() -> dict:
    if RESTART_STATE_FILE.exists():
        try:
            return json.loads(RESTART_STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"restart_count": 0, "restart_reason": None, "last_restart_timestamp": None}


def save_restart_state(state: dict) -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    RESTART_STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def wait_with_watchdog(proc: subprocess.Popen) -> int:
    started = time.time()
    stuck_hits = 0
    rst = load_restart_state()
    while True:
        code = proc.poll()
        if code is not None:
            return int(code)

        if STOP_FILE.exists():
            log("STOP_AGENT seen — stopping agent child")
            kill_pid_tree(proc.pid or 0)
            try:
                return int(proc.wait(timeout=15))
            except Exception:
                return 1

        age = heartbeat_age_sec()
        uptime = time.time() - started
        health = "healthy"
        # Only scheduler silence is stuck — same Yahoo bar / NO_NEW_BAR is healthy
        if age is not None and uptime > SCHEDULER_WARNING_SEC:
            if age > SCHEDULER_STUCK_SEC:
                health = "STUCK"
                stuck_hits += 1
            elif age > SCHEDULER_WARNING_SEC:
                health = "DEGRADED"
                stuck_hits = 0
            else:
                stuck_hits = 0
            # Require 2 consecutive stuck polls (~40s) to avoid false kills
            if stuck_hits >= 2:
                reason = f"scheduler_heartbeat_stuck_{age:.0f}s"
                log(
                    f"STUCK: no scheduler heartbeat for {age:.0f}s "
                    f"(threshold {SCHEDULER_STUCK_SEC}s) — killing hung agent pid={proc.pid}. "
                    f"NOTE: unchanged 5m Yahoo bars are NOT a restart reason."
                )
                rst["restart_count"] = int(rst.get("restart_count") or 0) + 1
                rst["restart_reason"] = reason
                rst["last_restart_timestamp"] = datetime.now(timezone.utc).isoformat()
                save_restart_state(rst)
                kill_pid_tree(proc.pid or 0)
                try:
                    return int(proc.wait(timeout=15))
                except Exception:
                    return 1

        prevent_sleep(True)
        write_status(
            agent_pid=proc.pid,
            state="running",
            health=health,
            heartbeat_age_sec=None if age is None else round(age, 1),
            supervisor_uptime_sec=round(uptime, 1),
            restart_count=rst.get("restart_count", 0),
            restart_reason=rst.get("restart_reason"),
            last_restart_timestamp=rst.get("last_restart_timestamp"),
            scheduler_warning_seconds=SCHEDULER_WARNING_SEC,
            scheduler_stuck_seconds=SCHEDULER_STUCK_SEC,
        )
        time.sleep(WATCH_POLL_SEC)


def launch_agent() -> tuple[subprocess.Popen, object]:
    AGENT_LOG.parent.mkdir(parents=True, exist_ok=True)
    log_fh = open(AGENT_LOG, "a", encoding="utf-8")
    log_fh.write(f"\n----- agent start {datetime.now(timezone.utc).isoformat()} -----\n")
    log_fh.flush()

    flags = 0
    si = None
    if sys.platform == "win32":
        # No console flash; avoid DETACHED_PROCESS (flaky child lifetime).
        flags = CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = 0

    env = os.environ.copy()
    env["USE_MOCK_BROKER"] = "true"
    env.pop("TERM", None)

    proc = subprocess.Popen(
        CMD,
        cwd=str(ROOT),
        stdout=log_fh,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        env=env,
        creationflags=flags,
        startupinfo=si,
        close_fds=False,
    )
    return proc, log_fh


def main() -> int:
    os.chdir(ROOT)
    os.environ.setdefault("USE_MOCK_BROKER", "true")
    DATA.mkdir(parents=True, exist_ok=True)

    if not acquire_lock():
        log("Another supervisor already holds the lock — exiting duplicate")
        return 0
    atexit.register(release_lock)
    atexit.register(lambda: prevent_sleep(False))
    prevent_sleep(True)
    log(f"Supervisor started pid={os.getpid()} agent_cmd={' '.join(CMD)}")
    write_status(state="started")

    try:
        while True:
            if STOP_FILE.exists():
                log("STOP_AGENT present — supervisor exiting")
                write_status(state="stopped_by_user")
                return 0

            log("Cleanup strays...")
            try:
                kill_stray_agents()
            except Exception as exc:
                log(f"cleanup error (continuing): {exc}")

            log("Launching agent.live_main (detached, no console)")
            write_status(state="launching")
            proc, log_fh = launch_agent()
            try:
                code = wait_with_watchdog(proc)
            finally:
                try:
                    log_fh.close()
                except Exception:
                    pass

            why = explain_exit(code)
            log(f"Agent exited code={code} ({why})")
            write_status(state="agent_exited", last_exit_code=code, last_exit_explain=why)

            if STOP_FILE.exists():
                log("STOP_AGENT present after exit — not restarting")
                write_status(state="stopped_by_user")
                return 0

            delay = 8 if (code & 0xFFFFFFFF) == 0xC000013A else 5
            log(f"Restarting in {delay}s (autonomous restart)")
            # Chunked sleep so stay-awake keeps firing if OS tries to suspend
            for _ in range(delay):
                prevent_sleep(True)
                time.sleep(1)
    finally:
        prevent_sleep(False)
        release_lock()
        log("Supervisor stopped")
        write_status(state="supervisor_stopped")


if __name__ == "__main__":
    raise SystemExit(main())
