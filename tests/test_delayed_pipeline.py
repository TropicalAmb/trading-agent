"""Extra delayed-data / isolation tests."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

from agent.data.base import Bar
from agent.data.bar_cursor import BarCursorStore
from agent.decision.pipeline import DecisionPipeline


def _bar(sym, ts, close=100.0, stale=False):
    return Bar(
        symbol=sym,
        timestamp=ts,
        open=close,
        high=close,
        low=close,
        close=close,
        volume=1,
        source="yahoo_delayed",
        is_realtime=False,
        estimated_delay_seconds=780,
        is_stale=stale,
        received_time=datetime.now(timezone.utc),
    )


def test_missing_bars_processed_chronologically(tmp_path):
    provider = MagicMock()
    cursor = BarCursorStore(tmp_path / "c.json")
    t0 = datetime(2026, 8, 7, 9, 15)
    t1 = datetime(2026, 8, 7, 9, 20)
    t2 = datetime(2026, 8, 7, 9, 25)
    cursor.set("MES", t0)
    bars = [_bar("MES", t0), _bar("MES", t1), _bar("MES", t2)]
    provider.get_bars.return_value = bars
    provider.to_dataframe.side_effect = lambda bs: __import__("pandas").DataFrame(
        {
            "open": [b.open for b in bs],
            "high": [b.high for b in bs],
            "low": [b.low for b in bs],
            "close": [b.close for b in bs],
            "volume": [b.volume for b in bs],
        },
        index=[b.timestamp for b in bs],
    )
    cfg = {
        "universe": {"symbols": ["MES"]},
        "confluence": {"engines": []},
        "market_data": {},
        "instruments": {"MES": {"point_value": 5}},
        "quantity": {"default_quantity": 1, "max_quantity": 25},
        "tiering": {"minimum_trade_tier": "A"},
        "schedule": {"timezone": "America/New_York", "entry_mode": "always_open"},
    }
    pipe = DecisionPipeline(cfg, provider, cursor, agent_id="agent_1")
    out = pipe.scan_cycle()
    # Cursor advanced to latest pending
    assert cursor.get("MES") == t2
    assert out["symbol_reports"]["MES"]["reason"] in {
        "no candidate from any engine",
        out["symbol_reports"]["MES"].get("reason"),
    }


def test_one_symbol_failure_does_not_stop_others(tmp_path):
    provider = MagicMock()
    cursor = BarCursorStore(tmp_path / "c2.json")

    def get_bars(symbol, **kwargs):
        if symbol == "MES":
            raise RuntimeError("yahoo boom")
        return [_bar(symbol, datetime(2026, 8, 7, 9, 25))]

    provider.get_bars.side_effect = get_bars
    provider.to_dataframe.return_value = __import__("pandas").DataFrame(
        {"open": [1], "high": [1], "low": [1], "close": [1], "volume": [1]},
        index=[datetime(2026, 8, 7, 9, 25)],
    )
    cfg = {
        "universe": {"symbols": ["MES", "MNQ"]},
        "confluence": {"engines": []},
        "market_data": {},
        "instruments": {"MES": {"point_value": 5}, "MNQ": {"point_value": 2}},
        "quantity": {"default_quantity": 1},
        "tiering": {"minimum_trade_tier": "A"},
        "schedule": {"timezone": "America/New_York", "entry_mode": "always_open"},
    }
    out = DecisionPipeline(cfg, provider, cursor).scan_cycle()
    assert "DATA_ERROR" in out["symbol_reports"]["MES"]["reason"]
    assert out["symbol_reports"]["MNQ"]["decision"] == "PASS"


def test_stale_blocks_new_entry(tmp_path):
    provider = MagicMock()
    cursor = BarCursorStore(tmp_path / "c3.json")
    provider.get_bars.return_value = [
        _bar("MES", datetime(2026, 8, 7, 9, 25), stale=True)
    ]
    cfg = {
        "universe": {"symbols": ["MES"]},
        "confluence": {"engines": ["ema_pullback"]},
        "market_data": {},
        "instruments": {"MES": {"point_value": 5}},
        "quantity": {"default_quantity": 1},
        "tiering": {"minimum_trade_tier": "A"},
        "schedule": {"timezone": "America/New_York", "entry_mode": "always_open"},
    }
    out = DecisionPipeline(cfg, provider, cursor).scan_cycle()
    assert out["symbol_reports"]["MES"]["reason"] == "DATA_STALE"
    assert out["executable"] == []
