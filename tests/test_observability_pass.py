"""Observability / runtime status pass — does not change strategy thresholds."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd
import pytest

from agent.config import load_settings
from agent.context.market_context import _resample_ohlc, build_market_context
from agent.data.base import Bar
from agent.data.bar_cursor import BarCursorStore
from agent.data.yahoo_delayed import YahooDelayedFuturesProvider
from agent.decision.pipeline import DecisionPipeline
from agent.decision.setup_identity import structural_setup_key
from agent.journal.filter_calibration import build_filter_calibration
from agent.journal.shadow import ShadowTracker
from agent.runtime.observability_store import LastEvaluationStore
from agent.runtime.scan_status import (
    ScanState,
    classify_cycle,
    parse_interval_seconds,
    stale_threshold_seconds,
)

ROOT = Path(__file__).resolve().parents[1]


def test_thresholds_unlocked_not_changed():
    cfg = load_settings(ROOT / "config" / "settings.yaml")
    assert cfg["tiering"]["minimum_trade_tier"] == "A"
    assert cfg["tiering"]["tier_thresholds"]["A"] == 72
    assert cfg["tiering"]["tier_thresholds"]["A_PLUS"] == 85
    assert cfg["quantity"]["default_quantity"] == 1
    assert cfg["risk"]["max_risk_dollars_per_trade"] == 250


def test_no_new_bar_is_healthy_waiting_not_stale_bundle():
    st = classify_cycle(
        {
            "MES": {"reason": "NO_NEW_BAR", "market_time": "2026-08-07T11:10:00"},
            "MNQ": {"reason": "NO_NEW_BAR", "market_time": "2026-08-07T11:10:00"},
        }
    )
    assert st.scan_state == ScanState.NO_NEW_BAR.value
    assert "HEALTHY" in st.primary
    assert "stale" not in st.primary.lower()


def test_stale_and_timeout_are_distinct():
    assert classify_cycle({"MES": {"reason": "DATA_STALE"}}).scan_state == "DATA_STALE"
    assert "TIMEOUT" in classify_cycle(
        {"MES": {"reason": "DATA_TIMEOUT:boom"}}
    ).primary


def test_expected_yahoo_delay_not_automatically_stale():
    cfg = {
        "market_data": {
            "expected_delay_seconds": 900,
            "stale_extra_tolerance_seconds": 420,
            "bar_interval": "5m",
            # no stale_after override → formula
        }
    }
    thr = stale_threshold_seconds(cfg)
    # 900 + 300 + 420 = 1620s (~27m). 13–15m Yahoo delay is fine.
    assert thr == 1620
    delay_typical = 14 * 60
    assert delay_typical < thr


def test_provider_bar_interval_metadata():
    p = YahooDelayedFuturesProvider(default_bar_interval="5m")
    meta = p.provider_meta()
    assert meta["bar_interval"] == "5m"
    assert meta["bar_interval_seconds"] == 300


def test_context_persists_across_no_new_bar(tmp_path):
    store = LastEvaluationStore(tmp_path / "le.json")
    store.update_symbol(
        "MES",
        {
            "market_bar": "2026-08-07T11:10:00",
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
            "regime": {"regime": "TREND_UP", "confidence": 78},
            "market_context": {
                "direction_15m": 1,
                "direction_1h": 1,
                "direction_4h": -1,
                "above_vwap": True,
                "ema_bull": True,
            },
            "candidates": [
                {
                    "symbol": "MES",
                    "strategy": "ema_pullback",
                    "local_score": 87,
                    "global_score": 64,
                    "tier": "B",
                }
            ],
            "engines": {},
        },
    )
    store.set_last_candidates(store.get_symbol("MES")["candidates"], market_bar="2026-08-07T11:10:00")

    provider = MagicMock()
    cursor = BarCursorStore(tmp_path / "c.json")
    ts = datetime(2026, 8, 7, 11, 10)
    cursor.set("MES", ts)
    bar = Bar(
        symbol="MES",
        timestamp=ts,
        open=100,
        high=101,
        low=99,
        close=100.5,
        volume=1,
        source="yahoo_delayed",
        is_realtime=False,
        estimated_delay_seconds=780,
        is_stale=False,
        received_time=datetime.now(timezone.utc),
        metadata={"bar_interval": "5m", "bar_interval_seconds": 300},
    )
    provider.get_bars.return_value = [bar]
    provider.to_dataframe.return_value = pd.DataFrame(
        {"open": [100], "high": [101], "low": [99], "close": [100.5], "volume": [1]},
        index=[ts],
    )
    class _H:
        def __init__(self):
            self.source = "yahoo_delayed"
            self.is_healthy = True
            self.last_success_utc = None
            self.last_error = None
            self.consecutive_failures = 0

        @property
        def __dict__(self):
            return {
                "source": self.source,
                "is_healthy": self.is_healthy,
                "last_success_utc": self.last_success_utc,
                "last_error": self.last_error,
                "consecutive_failures": self.consecutive_failures,
            }

    provider.health.return_value = _H()
    cfg = {
        "universe": {"symbols": ["MES"]},
        "confluence": {"engines": []},
        "market_data": {"last_evaluation_path": str(tmp_path / "le.json")},
        "instruments": {"MES": {"point_value": 5}},
        "quantity": {"default_quantity": 1},
        "tiering": {"minimum_trade_tier": "A", "tier_thresholds": {"A": 72, "A_PLUS": 85, "B": 58}},
        "schedule": {"timezone": "America/New_York", "entry_mode": "always_open"},
        "config_version": "opt_v1",
    }
    pipe = DecisionPipeline(cfg, provider, cursor, agent_id="agent_1")
    pipe.last_eval = store
    out = pipe.scan_cycle()
    rep = out["symbol_reports"]["MES"]
    assert rep["reason"] == "NO_NEW_BAR"
    assert rep["regime"]["regime"] == "TREND_UP"
    assert rep["market_context"]["direction_15m"] == 1
    assert rep["last_candidates"]
    assert out["cycle_status"]["scan_state"] == "NO_NEW_BAR"
    assert out["last_evaluated_candidates"]


def test_htf_aggregation_from_5m_no_lookahead():
    idx = pd.date_range("2026-08-07 09:00", periods=48, freq="5min")
    open_ = [100.0] * 48
    close = [100.0] * 48
    # Each completed 15m bucket = 3×5m bars
    for i in range(0, 48, 3):
        open_[i] = 100.0
        close[i + 2] = 101.0 if i == 0 else 99.0
    df = pd.DataFrame(
        {
            "open": open_,
            "high": [102] * 48,
            "low": [98] * 48,
            "close": close,
            "volume": [1] * 48,
        },
        index=idx,
    )
    r15 = _resample_ohlc(df, "15min")
    r1h = _resample_ohlc(df, "1h")
    r4h = _resample_ohlc(df, "4h")
    assert len(r15) >= 1
    # 48 five-minute bars → 16 raw 15m buckets; last dropped as incomplete ⇒ ≤15
    assert len(r15) <= 15
    assert len(r1h) <= 3
    assert len(r4h) <= 1
    assert r15.index[-1] <= df.index[-1]
    # Direction uses candle close vs open, not EMA
    ctx = build_market_context(df)
    assert ctx.direction_15m in (-1, 0, 1)
    assert isinstance(ctx.ema_bull, bool)


def test_shadow_resolves_stop_target_horizon_and_dedupes(tmp_path):
    path = tmp_path / "shadow.json"
    st = ShadowTracker(path)
    row = {
        "symbol": "MES",
        "side": "BUY",
        "entry": 100,
        "stop": 99,
        "target": 102,
        "point_value": 5,
        "tier": "B",
        "strategy": "ema_pullback",
        "structural_key": "MES|ema_pullback|BUY|l100.0",
        "setup_id": "MES|ema_pullback|BUY|2026-08-07T11:05|e100.0|l100.0",
        "market_timestamp": "2026-08-07T11:05:00",
    }
    assert st.open_shadow(row) is not None
    assert st.open_shadow(row) is None  # duplicate structural
    # Stop via bar low
    st.mark_bars(
        {"MES": {"high": 100.2, "low": 98.9, "close": 99.5}},
        cfg={"shadow": {"research_horizon_bars": 36}},
        bar_interval_minutes=5,
    )
    assert st.summary()["count"] == 1
    assert st.summary()["open"] == 0

    # Horizon close
    st2 = ShadowTracker(tmp_path / "s2.json")
    st2.open_shadow({**row, "structural_key": "MES|ema_pullback|BUY|l101.0", "setup_id": "x2"})
    for _ in range(3):
        st2.mark_bars(
            {"MES": {"high": 100.1, "low": 99.9, "close": 100.0}},
            cfg={"shadow": {"research_horizon_bars": 2}},
            bar_interval_minutes=5,
        )
    assert st2.summary()["count"] >= 1


def test_filter_calibration_insufficient_data():
    cal = build_filter_calibration(actual_trades=[], shadow_trades=[], min_b_sample=30)
    assert cal["FILTER_ASSESSMENT"] == "INSUFFICIENT_DATA"


def test_parse_interval():
    assert parse_interval_seconds("5m") == 300
    assert parse_interval_seconds("1h") == 3600


def test_structural_key_ignores_bar_time():
    a = structural_setup_key(symbol="MYM", strategy="ema_pullback", direction="BUY", level=54112.0)
    b = structural_setup_key(symbol="MYM", strategy="ema_pullback", direction="BUY", level=54112.04)
    assert a == b
