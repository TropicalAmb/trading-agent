import pandas as pd
import pytest

from agent.research.current_specialist_validation import (
    realize_configured_management,
    realize_nq_scaled_exit,
    summarize_true_forward,
)
from agent.research.nq_context_entry import realize_trades


def test_true_forward_uses_exact_stamp_and_current_strategies_only():
    state = {
        "closed_trades": [
            {
                "strategy_name": "nq_context_entry",
                "config_version": "current",
                "pnl_dollars": 100,
                "risk_dollars": 100,
                "opened_at": "2026-08-14T10:00:00",
            },
            {
                "strategy_name": "nq_context_entry",
                "config_version": "old",
                "pnl_dollars": -100,
                "risk_dollars": 100,
            },
            {
                "strategy_name": "breakout_retest",
                "config_version": "current",
                "pnl_dollars": -100,
                "risk_dollars": 100,
            },
            {
                "strategy_name": "nq_context_entry",
                "config_version": "current",
                "exit_reason": "tp1",
                "pnl_dollars": 50,
                "risk_dollars": 100,
            },
        ]
    }
    report = summarize_true_forward(state, "current")
    assert report["overall"]["n"] == 1
    assert report["overall"]["win_rate"] == 1.0
    assert report["strategies"]["nq_context_entry"]["n"] == 1
    assert "cl_vwap_prox_momentum" not in report["strategies"]


def test_true_forward_can_be_limited_to_current_active_book():
    state = {
        "closed_trades": [
            {
                "strategy_name": "vwap_rejection",
                "config_version": "current",
                "pnl_dollars": 100,
                "risk_dollars": 100,
            }
        ]
    }
    report = summarize_true_forward(
        state,
        "current",
        ("nq_context_entry", "cl_vwap_prox_momentum"),
    )
    assert report["overall"]["n"] == 0
    assert "vwap_rejection" not in report["strategies"]


def test_scaled_exit_banks_half_then_runner_breakeven_next_bar():
    idx = pd.date_range("2026-08-14 10:00", periods=3, freq="5min", tz="America/New_York")
    bars = pd.DataFrame(
        {
            "open": [100, 100, 101],
            "high": [101, 104, 101],
            "low": [99, 99, 100],
            "close": [100, 102, 100],
            "volume": [1, 1, 1],
        },
        index=idx,
    )
    rows = realize_nq_scaled_exit(
        [{"entry": 100, "stop": 90, "side": "BUY", "entry_ts": idx[0]}],
        bars,
        tp1_r=0.30,
    )
    # Half earns +0.30R; half scratches. Then subtract 0.75pt / 10pt risk.
    assert rows[0]["pnl_r"] == pytest.approx(0.075)


def test_scaled_exit_uses_stop_when_same_bar_also_contains_target():
    idx = pd.date_range("2026-08-14 10:00", periods=2, freq="5min", tz="America/New_York")
    bars = pd.DataFrame(
        {
            "open": [100, 100],
            "high": [101, 112],
            "low": [99, 89],
            "close": [100, 105],
            "volume": [1, 1],
        },
        index=idx,
    )
    rows = realize_nq_scaled_exit(
        [{"entry": 100, "stop": 90, "side": "BUY", "entry_ts": idx[0]}],
        bars,
        tp1_r=0.30,
    )
    assert rows[0]["pnl_r"] == pytest.approx(-1.075)


def test_one_minute_realizer_waits_until_five_minute_signal_bar_closes():
    idx = pd.date_range("2026-08-14 10:00", periods=7, freq="1min", tz="America/New_York")
    bars = pd.DataFrame(
        {
            "open": [100] * 7,
            "high": [101, 112, 101, 101, 101, 101, 101],
            "low": [99, 99, 99, 99, 99, 89, 99],
            "close": [100] * 7,
            "volume": [1] * 7,
        },
        index=idx,
    )
    candidate = {
        "entry": 100,
        "stop": 90,
        "side": "BUY",
        "entry_ts": idx[0],
        "trigger": "PULLBACK",
        "session_window": "0930_1200",
        "confirmation": "signal_close",
        "swing_high": 110,
        "swing_low": 90,
        "dir_15m": 1,
        "dir_1h": 1,
        "above_vwap": 1,
        "ema_aligned": 1,
    }
    rows = realize_trades([candidate], bars, target_r=1.0)
    # The apparent target at 10:01 occurred inside the 10:00–10:04 signal bar.
    assert rows[0].pnl_r < -1.0


def test_configured_manager_tightens_from_one_bar_and_uses_stop_next_bar():
    idx = pd.date_range("2026-08-14 10:00", periods=3, freq="5min", tz="America/New_York")
    bars = pd.DataFrame(
        {
            "open": [100, 100, 106],
            "high": [101, 108.1, 106],
            "low": [99, 99, 105],
            "close": [100, 107, 105.5],
            "volume": [1, 1, 1],
        },
        index=idx,
    )
    rows = realize_configured_management(
        [{"entry": 100, "stop": 90, "side": "BUY", "entry_ts": idx[0]}],
        bars,
        strategy="test",
        symbol="NQ",
        target_r=1.15,
    )
    # 70% target progress locks half the 1.15R target: +0.575R.
    assert rows[0]["pnl_r"] == pytest.approx(0.575)


def test_configured_manager_banks_half_at_one_r_then_runner_breakeven():
    idx = pd.date_range("2026-08-14 10:00", periods=3, freq="5min", tz="America/New_York")
    bars = pd.DataFrame(
        {
            "open": [100, 100, 100],
            "high": [101, 110, 101],
            "low": [99, 99, 99],
            "close": [100, 105, 100],
            "volume": [1, 1, 1],
        },
        index=idx,
    )
    rows = realize_configured_management(
        [{"entry": 100, "stop": 90, "side": "BUY", "entry_ts": idx[0]}],
        bars,
        strategy="test",
        symbol="CL",
        target_r=2.0,
    )
    assert rows[0]["pnl_r"] == pytest.approx(0.5)
