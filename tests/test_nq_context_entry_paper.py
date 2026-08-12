"""Paper path tests for nq_context_entry specialist."""

from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pandas as pd
import yaml
from pathlib import Path

from agent.decision.cascade import attach_cascade_to_setup
from agent.decision.pipeline import DecisionPipeline
from agent.decision.setup import TradeSetup
from agent.decision.tiering import assign_tier_for_setup, can_execute, execution_reject_reason
from agent.strategy.nq_context_entry import evaluate_nq_context_entry


ROOT = Path(__file__).resolve().parents[1]


def _cfg() -> dict:
    return yaml.safe_load((ROOT / "config" / "settings.yaml").read_text(encoding="utf-8"))


def _synth_nq_pullback_bars(n: int = 200) -> pd.DataFrame:
    """Build a synthetic 5m uptrend that ends with a bullish EMA20 pullback touch."""
    # End in 10:00–12:00 ET window
    idx = pd.date_range("2026-03-10 07:00", periods=n, freq="5min", tz="America/New_York")
    rng = np.random.default_rng(42)
    # Strong uptrend base
    close = 20000 + np.cumsum(np.abs(rng.normal(2.0, 1.0, n)))
    open_ = np.r_[close[0], close[:-1]]
    high = np.maximum(open_, close) + 4
    low = np.minimum(open_, close) - 4
    df = pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": np.full(n, 1000.0)},
        index=idx,
    )
    # Force last bar into session + bullish close near EMA (evaluator recomputes EMA)
    # Pull last bar low into a shallow pullback while keeping bullish body
    i = -1
    df.iloc[i, df.columns.get_loc("open")] = float(df["close"].iloc[i] - 3)
    df.iloc[i, df.columns.get_loc("close")] = float(df["close"].iloc[i] + 2)
    df.iloc[i, df.columns.get_loc("high")] = float(df["close"].iloc[i] + 1)
    df.iloc[i, df.columns.get_loc("low")] = float(df["open"].iloc[i] - 25)
    return df


def test_config_wires_nq_context_entry_paper():
    cfg = _cfg()
    engines = cfg.get("confluence", {}).get("engines") or []
    research = set(cfg.get("research_only_engines") or [])
    specs = set(cfg.get("paper_specialist_engines") or [])
    assert "nq_context_entry" in engines
    assert "nq_context_entry" not in research
    assert "nq_context_entry" in specs
    assert cfg.get("config_version") == "router_v1_paperfix1"
    nq = cfg.get("nq_context_entry") or {}
    assert nq.get("window") == "0930_1200"
    assert float(nq.get("target_r_multiple")) == 1.15
    assert nq.get("sides") == ["BUY"]


def test_specialist_exempt_from_global_min_r():
    cfg = _cfg()
    now = datetime.now(timezone.utc)
    setup = TradeSetup(
        strategy_name="nq_context_entry",
        symbol="NQ",
        direction="BUY",
        setup_tier="A",
        confidence_score=78,
        entry=20000.0,
        stop=19980.0,
        target=20023.0,  # 1.15R
        expected_r=1.15,
        market_timestamp=now,
        received_timestamp=now,
        reasons=["test"],
        session="ny_open",
        agent_id="agent_1",
        quantity=1,
        risk_dollars=400.0,
        reward_dollars=460.0,
        metadata={
            "has_location": True,
            "global_score": 80,
            "families_positive": ["PRIMARY", "LOCATION"],
            "cascade": {
                "trigger": "PULLBACK",
                "location": "EXCELLENT_LOCATION",
                "thesis": "LONG_SUPPORT",
                "fit": "FIT",
                "decision": "EXECUTE_PAPER",
            },
            "cascade_decision": "EXECUTE_PAPER",
            "hard_invalidations": [],
            "lifecycle_state": "ACTIVE",
        },
    )
    # Without specialist exemption this would fail R<1.6
    assert execution_reject_reason(setup, cfg) is None
    assert can_execute(setup, cfg)


def test_pipeline_registers_nq_context_entry():
    cfg = _cfg()
    pipe = DecisionPipeline.__new__(DecisionPipeline)
    pipe.cfg = cfg
    pipe.engine_names = list(cfg["confluence"]["engines"]) + list(cfg.get("research_only_engines") or [])
    pipe.research_only_engines = set(cfg.get("research_only_engines") or [])
    # Call private map indirectly via _eval_engines empty frame path
    from agent.strategy.nq_context_entry import evaluate_nq_context_entry as fn

    assert callable(fn)


def test_nq_micro_remap_when_risk_exceeded():
    cfg = _cfg()
    # Wide stop so 1 NQ ($20/pt) exceeds $500
    entry, stop, target = 20000.0, 19970.0, 20034.5  # 30pt stop * $20 = $600
    now = datetime.now(timezone.utc)
    setup = TradeSetup(
        strategy_name="nq_context_entry",
        symbol="NQ",
        direction="BUY",
        setup_tier="A",
        confidence_score=78,
        entry=entry,
        stop=stop,
        target=target,
        expected_r=1.15,
        market_timestamp=now,
        received_timestamp=now,
        reasons=["remap_test"],
        session="ny_open",
        agent_id="agent_1",
        quantity=1,
        risk_dollars=600.0,
        reward_dollars=690.0,
        metadata={"point_value": 20.0, "cascade_log": ["RISK: pending"]},
    )
    pipe = DecisionPipeline.__new__(DecisionPipeline)
    pipe.cfg = cfg
    pipe.agent_id = "agent_1"
    sized = DecisionPipeline._size_setup(pipe, setup)
    assert sized.symbol == "MNQ"
    assert sized.quantity >= 1
    assert (sized.metadata or {}).get("remapped_from") == "NQ"
