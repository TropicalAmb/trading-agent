"""Live readiness: kill switch, sim broker, providers, learning schema, persistence."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from agent.data.broker_realtime import BrokerRealtimeProvider
from agent.data.historical import HistoricalProvider
from agent.data.yahoo_delayed import make_provider
from agent.execution.kill_switch import ExecutionKillSwitch
from agent.execution.order_state import OrderState
from agent.execution.sim_broker import SimulatedBroker
from agent.learning.schema import SCHEMA_VERSION, strip_post_entry_leakage
from agent.learning.store import LearningStore
from agent.learning.shrink import shrink_rate
import pandas as pd


def test_schema_strips_outcome_from_features():
    row = strip_post_entry_leakage(
        {
            "symbol": "MES",
            "features": {"mtf_aligned": 2, "realized_r": 1.2, "win": 1},
            "final_result": "OPEN",
        }
    )
    assert row["schema_version"] == SCHEMA_VERSION
    assert "realized_r" not in row["features"]
    assert "win" not in row["features"]


def test_shrinkage_hierarchy_demo():
    shr = shrink_rate(8, 10, prior_mean=0.5, prior_strength=20.0)
    assert shr.raw == 0.8
    assert shr.shrunk < 0.65


def test_kill_switch_arm_disarm(tmp_path: Path):
    ks = ExecutionKillSwitch(tmp_path / "ks.json")
    assert not ks.is_armed()
    ks.arm(reason="test", existing_position_mode="MANAGE_EXISTING")
    assert ks.is_armed()
    assert ks.reject_new_orders_reason().startswith("KILL_SWITCH")
    ks.disarm()
    assert not ks.is_armed()


def test_sim_broker_state_machine():
    b = SimulatedBroker()
    b.connect()
    sig = SimpleNamespace(symbol="MES", side="BUY", entry=100.0, stop=99.0, target=102.0, market_timestamp="a")
    r = b.place_bracket_order(sig, qty=1)
    assert r["order_state"] == OrderState.FILLED.value
    assert r["stop_order_id"]
    r2 = b.place_bracket_order(sig, qty=1)
    assert r2["reason"] == "DUPLICATE_ORDER"
    b.disconnect()
    sig2 = SimpleNamespace(symbol="MNQ", side="SELL", entry=1.0, stop=2.0, target=0.5, market_timestamp="b")
    assert b.place_bracket_order(sig2, qty=1)["reason"] == "BROKER_DISCONNECT"


def test_historical_and_realtime_providers():
    df = pd.DataFrame(
        {
            "open": [1, 2],
            "high": [1.5, 2.5],
            "low": [0.5, 1.5],
            "close": [1.2, 2.2],
            "volume": [10, 11],
        },
        index=pd.to_datetime(["2026-08-01", "2026-08-02"], utc=True),
    )
    hist = HistoricalProvider({"MES": df})
    bars = hist.get_bars("MES")
    assert len(bars) == 2
    assert hist.health().is_healthy
    rt = BrokerRealtimeProvider({})
    assert rt.health().is_healthy is False
    assert len(rt.external_dependencies()) >= 4
    cfg = {"market_data": {"provider": "yahoo_delayed"}}
    assert type(make_provider(cfg)).__name__ == "YahooDelayedFuturesProvider"


def test_learning_store_persists(tmp_path: Path):
    store = LearningStore(tmp_path / "c.jsonl")
    store.append({"setup_id": "x", "symbol": "MES", "final_result": "OPEN", "features": {"mtf_aligned": 2}})
    store2 = LearningStore(tmp_path / "c.jsonl")
    assert len(store2.all_rows()) == 1
    assert store2.all_rows()[0].get("schema_version") == SCHEMA_VERSION


def test_live_pilot_config_exists_and_is_inactive():
    import yaml
    from pathlib import Path

    p = Path("config/live_pilot.yaml")
    assert p.exists()
    cfg = yaml.safe_load(p.read_text(encoding="utf-8"))
    assert cfg.get("activation_status") == "NOT_ACTIVATED"
    assert cfg.get("quantity", {}).get("max_quantity") == 1
    assert set(cfg.get("universe") or {}) == {"MES", "MNQ", "MGC", "MCL"}
    assert (cfg.get("trade_quality_model") or {}).get("allow_live_auto_promote") is False


def test_databento_provider_requires_key(monkeypatch):
    monkeypatch.delenv("DATABENTO_API_KEY", raising=False)
    from agent.data.databento_historical import DatabentoHistoricalProvider

    p = DatabentoHistoricalProvider(api_key="")
    assert p.health().is_healthy is False
    try:
        p.get_bars("NQ", interval="5m", period="7d")
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        assert "DATABENTO_API_KEY" in str(exc)


def test_make_provider_databento_name():
    from agent.data.yahoo_delayed import make_provider

    p = make_provider({"market_data": {"provider": "databento"}})
    assert type(p).__name__ == "DatabentoHistoricalProvider"
