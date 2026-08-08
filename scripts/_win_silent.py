"""Silent Windows process helpers — never flash a console window."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from typing import Iterable

CREATE_NO_WINDOW = 0x08000000


def _startupinfo_hidden():
    if sys.platform != "win32":
        return None
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = 0  # SW_HIDE
    return si


def run_silent(
    args: list[str],
    *,
    timeout: float = 25,
    text: bool = True,
    check: bool = False,
) -> subprocess.CompletedProcess:
    """Run a subprocess with no visible console (Windows)."""
    kwargs: dict = {
        "args": args,
        "timeout": timeout,
        "text": text,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.DEVNULL,
        "stdin": subprocess.DEVNULL,
    }
    if sys.platform == "win32":
        kwargs["creationflags"] = CREATE_NO_WINDOW
        kwargs["startupinfo"] = _startupinfo_hidden()
    return subprocess.run(**kwargs, check=check)


def check_output_silent(args: list[str], *, timeout: float = 25) -> str:
    r = run_silent(args, timeout=timeout)
    return r.stdout or ""


def python_cmd_pids(needle: str) -> list[int]:
    """PIDs of python/pythonw whose command line contains literal `needle`.

    Uses String.Contains (NOT -like) so dots are literal — avoids matching
    the wrong processes and accidentally taskkill'ing the supervisor.
    """
    safe = json.dumps(str(needle))
    ps = (
        "$ProgressPreference='SilentlyContinue'; "
        f"$needle = {safe}; "
        "Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | "
        "Where-Object { "
        "  $_.Name -like 'python*' -and $_.CommandLine -and "
        "  $_.CommandLine.Contains($needle) "
        "} | ForEach-Object { $_.ProcessId }"
    )
    try:
        out = check_output_silent(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-WindowStyle",
                "Hidden",
                "-Command",
                ps,
            ],
            timeout=25,
        )
    except Exception:
        return []
    pids: list[int] = []
    me = os.getpid()
    for line in out.splitlines():
        line = line.strip()
        if line.isdigit():
            pid = int(line)
            if pid != me:
                pids.append(pid)
    return pids


def kill_pids(pids: Iterable[int]) -> None:
    me = os.getpid()
    for pid in sorted(set(int(p) for p in pids if int(p) > 0 and int(p) != me)):
        try:
            run_silent(
                ["taskkill", "/PID", str(pid), "/F"],  # no /T — don't kill process trees blindly
                timeout=15,
            )
        except Exception:
            pass


def popen_detached(args: list[str], *, cwd: str | None = None) -> subprocess.Popen:
    """Start a background process with no console window."""
    kwargs: dict = {
        "args": args,
        "cwd": cwd,
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "close_fds": True,
    }
    if sys.platform == "win32":
        kwargs["creationflags"] = CREATE_NO_WINDOW
        kwargs["startupinfo"] = _startupinfo_hidden()
    return subprocess.Popen(**kwargs)
