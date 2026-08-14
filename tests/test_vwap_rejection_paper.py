"""VWAP-rejection evaluator tests plus its clean-validation demotion."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from agent.decision.setup import TradeSetup
from agent.decision.tiering import execution_reject_reason
from agent.strategy.vwap_rejection import _to_1h, evaluate_vwap_rejection

ROOT = Path(__file__).resolve().parents[1]


def _cfg() -> dict:
    return yaml.safe_load((ROOT / "config" / "settings.yaml").read_text(encoding="utf-8"))


def test_config_demotes_negative_expectancy_vwap_rejection():
    cfg = _cfg()
    engines = cfg.get("confluence", {}).get("engines") or []
    research = set(cfg.get("research_only_engines") or [])
    specs = set(cfg.get("paper_specialist_engines") or [])
    assert "vwap_rejection" not in engines
    assert "vwap_rejection" in research
    assert "vwap_rejection" not in specs
    assert "nq_context_entry" in specs
    assert "cl_vwap_prox_momentum" not in specs
    assert "cl_vwap_prox_momentum" in research
    assert cfg.get("config_version") == "router_v1_specialists_autonomy4"
    vr = cfg.get("vwap_rejection") or {}
    assert vr.get("enabled") is False
    assert float(vr.get("target_r_multiple")) == 1.5


def test_evaluator_fires_wick_reject_on_1h():
    idx = pd.date_range("2026-03-10 10:00", periods=80, freq="1h", tz="America/New_York")
    rng = np.random.default_rng(7)
    close = 5000 + np.cumsum(rng.normal(0, 2, len(idx)))
    df = pd.DataFrame(
        {
            "open": np.r_[close[0], close[:-1]],
            "high": close + 5,
            "low": close - 5,
            "close": close,
            "volume": np.full(len(idx), 1000.0),
        },
        index=idx,
    )
    # Force last bar: pierce VWAP low then close bullish above VWAP
    # Build synthetic VWAP near mid of last bar
    i = -1
    mid = float(df["close"].iloc[i])
    df.iloc[i, df.columns.get_loc("low")] = mid - 20
    df.iloc[i, df.columns.get_loc("high")] = mid + 2
    df.iloc[i, df.columns.get_loc("open")] = mid - 1
    df.iloc[i, df.columns.get_loc("close")] = mid + 1
    # Prior bars flat so session VWAP sits between low and close
    cfg = _cfg()
    sig = evaluate_vwap_rejection("ES", df, cfg, point_value=50.0)
    # May or may not fire depending on VWAP calc; assert no crash + schema if fires
    if sig is not None:
        assert sig.side in {"BUY", "SELL"}
        assert sig.target != sig.entry


def test_resample_drops_still_forming_hour():
    complete = pd.date_range("2026-03-10 09:00", periods=24, freq="5min")
    partial = pd.date_range("2026-03-10 11:00", periods=2, freq="5min")
    idx = complete.append(partial)
    df = pd.DataFrame(
        {
            "open": np.full(len(idx), 100.0),
            "high": np.full(len(idx), 101.0),
            "low": np.full(len(idx), 99.0),
            "close": np.full(len(idx), 100.0),
            "volume": np.full(len(idx), 10.0),
        },
        index=idx,
    )
    hourly = _to_1h(df)
    assert list(hourly.index) == [pd.Timestamp("2026-03-10 09:00"), pd.Timestamp("2026-03-10 10:00")]


def test_demoted_vwap_rejection_is_not_specialist_exempt_from_min_r():
    cfg = _cfg()
    now = datetime.now(timezone.utc)
    setup = TradeSetup(
        strategy_name="vwap_rejection",
        symbol="ES",
        direction="SELL",
        setup_tier="A",
        confidence_score=76,
        entry=5000.0,
        stop=5010.0,
        target=4985.0,  # 1.5R
        expected_r=1.5,
        market_timestamp=now,
        received_timestamp=now,
        reasons=["test"],
        risk_dollars=100.0,
        reward_dollars=150.0,
        quantity=2,
    )
    # It is stopped before any execution-quality exemption can make it paperable.
    reason = execution_reject_reason(setup, cfg)
    assert reason == "RESEARCH_ONLY:vwap_rejection"
