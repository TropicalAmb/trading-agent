from datetime import datetime
from zoneinfo import ZoneInfo

from agent.schedule.sessions import active_session_name, futures_market_open, session_ok


ALWAYS = {
    "schedule": {
        "timezone": "America/New_York",
        "entry_mode": "always_open",
        "weekend_open": "18:00",
        "weekend_close": "17:00",
        "maintenance_start": "17:00",
        "maintenance_end": "18:00",
    }
}

WINDOWS = {
    "schedule": {
        "timezone": "America/New_York",
        "entry_mode": "windows",
        "weekend_open": "18:00",
        "weekend_close": "17:00",
        "maintenance_start": "17:00",
        "maintenance_end": "18:00",
        "entry_windows": [
            {"name": "asia", "start": "18:00", "end": "02:00", "enabled": True},
            {"name": "london", "start": "03:00", "end": "09:30", "enabled": True},
            {"name": "ny_morning", "start": "09:35", "end": "11:30", "enabled": True},
            {"name": "ny_afternoon", "start": "11:30", "end": "16:55", "enabled": True},
        ],
    }
}


def _dt(y, m, d, hh, mm):
    return datetime(y, m, d, hh, mm, tzinfo=ZoneInfo("America/New_York"))


def test_always_open_midday():
    ok, label = session_ok(ALWAYS, _dt(2026, 8, 6, 15, 47))
    assert ok
    assert label == "ny"


def test_always_open_overnight_asia():
    ok, label = session_ok(ALWAYS, _dt(2026, 8, 5, 21, 0))
    assert ok
    assert label == "asia"


def test_maintenance_blocked():
    ok, reason = futures_market_open(ALWAYS, _dt(2026, 8, 6, 17, 30))
    assert not ok
    assert "exchange closed" in reason or "halt" in reason


def test_saturday_blocked():
    ok, _ = session_ok(ALWAYS, _dt(2026, 8, 8, 10, 0))
    assert not ok


def test_windows_mode_still_works():
    assert active_session_name(WINDOWS, _dt(2026, 8, 6, 13, 0)) == "ny_afternoon"
    assert active_session_name(WINDOWS, _dt(2026, 8, 6, 17, 30)) is None
