"""Keep Windows from sleeping while the paper agent is supposed to trade overnight.

Uses:
1) SetThreadExecutionState (SYSTEM + AWAYMODE) — refreshed by supervisor loop
2) powercfg standby/hibernate timeouts → 0 while armed (AC + DC), restored on disarm

Screen may still turn off (OK). Lid-close sleep is also set to Do Nothing while armed
so closing the lid does not kill Globex coverage; restored on stop.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
STATE = DATA / "overnight_power_state.json"


def _run(cmd: list[str]) -> tuple[int, str]:
    try:
        p = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0,
        )
        out = (p.stdout or "") + (p.stderr or "")
        return int(p.returncode), out.strip()
    except Exception as exc:
        return 1, str(exc)


def _parse_ac_dc_indexes(out: str) -> tuple[str | None, str | None]:
    """Parse powercfg query output — index is on the same line after the colon."""
    ac = dc = None
    for line in out.splitlines():
        s = line.strip()
        if "Current AC Power Setting Index" in s and ":" in s:
            try:
                ac = str(int(s.split(":", 1)[1].strip(), 16))
            except Exception:
                pass
        elif "Current DC Power Setting Index" in s and ":" in s:
            try:
                dc = str(int(s.split(":", 1)[1].strip(), 16))
            except Exception:
                pass
    return ac, dc


def _query_ac_dc(alias: str) -> tuple[str | None, str | None]:
    """Return (ac_seconds, dc_seconds) as strings from powercfg /query."""
    code, out = _run(["powercfg", "/query", "SCHEME_CURRENT", "SUB_SLEEP", alias])
    if code != 0:
        return None, None
    return _parse_ac_dc_indexes(out)


def _query_lid() -> tuple[str | None, str | None]:
    code, out = _run(["powercfg", "/query", "SCHEME_CURRENT", "SUB_BUTTONS", "LIDACTION"])
    if code != 0:
        return None, None
    return _parse_ac_dc_indexes(out)


def thread_execution_state(enable: bool = True) -> None:
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
    except Exception:
        pass


def arm_overnight_power() -> dict:
    """Disable sleep/hibernate while agent runs; persist prior values for restore."""
    DATA.mkdir(parents=True, exist_ok=True)
    thread_execution_state(True)
    if sys.platform != "win32":
        return {"armed": False, "reason": "not_windows"}

    state: dict = {"armed": True}
    if STATE.exists():
        try:
            prev = json.loads(STATE.read_text(encoding="utf-8"))
            if prev.get("armed") and prev.get("saved"):
                # Already armed by a prior supervisor — keep original saved baselines
                thread_execution_state(True)
                return prev
        except Exception:
            pass

    stand_ac, stand_dc = _query_ac_dc("STANDBYIDLE")
    hib_ac, hib_dc = _query_ac_dc("HIBERNATEIDLE")
    lid_ac, lid_dc = _query_lid()
    state["saved"] = {
        "standby_ac": stand_ac,
        "standby_dc": stand_dc,
        "hibernate_ac": hib_ac,
        "hibernate_dc": hib_dc,
        "lid_ac": lid_ac,
        "lid_dc": lid_dc,
    }

    # 0 = never sleep / never hibernate
    _run(["powercfg", "/change", "standby-timeout-ac", "0"])
    _run(["powercfg", "/change", "standby-timeout-dc", "0"])
    _run(["powercfg", "/change", "hibernate-timeout-ac", "0"])
    _run(["powercfg", "/change", "hibernate-timeout-dc", "0"])
    # Lid: 0 = Do nothing (AC + DC) so lid-close does not suspend overnight
    _run(["powercfg", "/SETACVALUEINDEX", "SCHEME_CURRENT", "SUB_BUTTONS", "LIDACTION", "0"])
    _run(["powercfg", "/SETDCVALUEINDEX", "SCHEME_CURRENT", "SUB_BUTTONS", "LIDACTION", "0"])
    _run(["powercfg", "/SETACTIVE", "SCHEME_CURRENT"])

    STATE.write_text(json.dumps(state, indent=2), encoding="utf-8")
    return state


def disarm_overnight_power() -> dict:
    """Restore prior sleep/lid settings and clear execution state."""
    thread_execution_state(False)
    if sys.platform != "win32":
        return {"armed": False}
    saved = {}
    if STATE.exists():
        try:
            saved = (json.loads(STATE.read_text(encoding="utf-8")) or {}).get("saved") or {}
        except Exception:
            saved = {}

    def _restore_timeout(change_name: str, seconds: str | None) -> None:
        if seconds is None:
            return
        try:
            mins = max(0, int(int(seconds) // 60))
        except Exception:
            return
        _run(["powercfg", "/change", change_name, str(mins)])

    _restore_timeout("standby-timeout-ac", saved.get("standby_ac"))
    _restore_timeout("standby-timeout-dc", saved.get("standby_dc"))
    _restore_timeout("hibernate-timeout-ac", saved.get("hibernate_ac"))
    _restore_timeout("hibernate-timeout-dc", saved.get("hibernate_dc"))

    if saved.get("lid_ac") is not None:
        _run(
            [
                "powercfg",
                "/SETACVALUEINDEX",
                "SCHEME_CURRENT",
                "SUB_BUTTONS",
                "LIDACTION",
                str(saved["lid_ac"]),
            ]
        )
    if saved.get("lid_dc") is not None:
        _run(
            [
                "powercfg",
                "/SETDCVALUEINDEX",
                "SCHEME_CURRENT",
                "SUB_BUTTONS",
                "LIDACTION",
                str(saved["lid_dc"]),
            ]
        )
    _run(["powercfg", "/SETACTIVE", "SCHEME_CURRENT"])
    try:
        STATE.unlink(missing_ok=True)
    except Exception:
        pass
    return {"armed": False, "restored": saved}


if __name__ == "__main__":
    cmd = (sys.argv[1] if len(sys.argv) > 1 else "arm").lower()
    if cmd == "disarm":
        print(json.dumps(disarm_overnight_power(), indent=2))
    else:
        print(json.dumps(arm_overnight_power(), indent=2))
