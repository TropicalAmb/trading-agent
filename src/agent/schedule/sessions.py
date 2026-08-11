"""CME micro session helpers (times in America/New_York).

Default: allow entries whenever Globex is open (nearly 24h),
except the daily maintenance break and the Fri–Sun weekend gap.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo


def _parse_hhmm(value: str) -> int:
    h, m = map(int, value.split(":"))
    return h * 60 + m


def _in_window(mins: int, start: str, end: str) -> bool:
    """Inclusive window. If start > end, window wraps midnight."""
    s = _parse_hhmm(start)
    e = _parse_hhmm(end)
    if s <= e:
        return s <= mins <= e
    return mins >= s or mins <= e


def _now_et(cfg: dict[str, Any], now: datetime | None) -> datetime:
    sched = cfg.get("schedule", {})
    tz = ZoneInfo(sched.get("timezone", "America/New_York"))
    now = now or datetime.now(tz)
    if now.tzinfo is None:
        return now.replace(tzinfo=tz)
    return now.astimezone(tz)


def futures_market_open(cfg: dict[str, Any], now: datetime | None = None) -> tuple[bool, str]:
    """True when CME micros (MES/MNQ) are in regular Globex hours."""
    sched = cfg.get("schedule", {})
    now = _now_et(cfg, now)
    mins = now.hour * 60 + now.minute
    weekend_open = sched.get("weekend_open", "18:00")
    weekend_close = sched.get("weekend_close", "17:00")
    maint_start = _parse_hhmm(sched.get("maintenance_start", "17:00"))
    maint_end = _parse_hhmm(sched.get("maintenance_end", "18:00"))

    # Saturday always closed
    if now.weekday() == 5:
        return False, "weekend (Saturday)"

    # Friday after weekend_close
    if now.weekday() == 4 and mins > _parse_hhmm(weekend_close):
        return False, "weekend gap (Fri close → Sun open)"

    # Sunday before weekend_open
    if now.weekday() == 6 and mins < _parse_hhmm(weekend_open):
        return False, "weekend gap (Fri close → Sun open)"

    # Daily maintenance ~17:00-18:00 ET (Sun-Thu evenings after open still apply after 18:00)
    if now.weekday() != 5 and maint_start <= mins < maint_end:
        return False, "CME exchange closed (daily halt ~5-6pm ET; resumes ~6pm Asia)"

    return True, "globex_open"


def active_session_name(cfg: dict[str, Any], now: datetime | None = None) -> str | None:
    """Label the cash-session region for journaling; None if market closed."""
    ok, reason = futures_market_open(cfg, now)
    if not ok:
        return None

    sched = cfg.get("schedule", {})
    mode = str(sched.get("entry_mode", "always_open")).lower()
    now = _now_et(cfg, now)
    mins = now.hour * 60 + now.minute

    # Optional named windows only if user switches entry_mode to "windows"
    if mode == "windows":
        windows = sched.get("entry_windows") or []
        for w in windows:
            if not w.get("enabled", True):
                continue
            if _in_window(mins, w["start"], w["end"]):
                return str(w.get("name", "session"))
        return None

    # always_open: still tag Asia / London / NY for the trade journal
    if _in_window(mins, "18:00", "02:59"):
        return "asia"
    if _in_window(mins, "03:00", "09:29"):
        return "london"
    if _in_window(mins, "09:30", "16:59"):
        return "ny"
    return "globex_open"


def session_ok(cfg: dict[str, Any], now: datetime | None = None) -> tuple[bool, str]:
    sched = cfg.get("schedule", {})
    mode = str(sched.get("entry_mode", "always_open")).lower()
    if mode == "windows":
        name = active_session_name(cfg, now)
        if name:
            return True, name
        return False, "outside enabled session windows"

    ok, info = futures_market_open(cfg, now)
    if not ok:
        return False, info

    now_et = _now_et(cfg, now)
    mins = now_et.hour * 60 + now_et.minute

    # Research-backed optional filters (Women in Day Trading group + our backtests).
    # Do not alter Globex weekend/maintenance logic above.
    if bool(sched.get("skip_friday_entries", False)) and now_et.weekday() == 4:
        # Still allow early Friday before weekend_close — but group evidence prefers no Fri entries
        return False, "skip_friday_entries (research filter)"

    delay = int(sched.get("ny_open_entry_delay_minutes", 0) or 0)
    if delay > 0:
        ny_open = _parse_hhmm("09:30")
        if ny_open <= mins < ny_open + delay:
            return False, f"ny_open_entry_delay ({delay}m after 09:30 ET)"

    label = active_session_name(cfg, now) or "globex_open"
    return True, label
