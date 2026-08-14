"""Paid Databento cache + current Yahoo-tail provider tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from agent.config import load_settings
from agent.data.base import Bar, ProviderHealth
from agent.data.databento_cache_yahoo import DatabentoCacheYahooProvider
from agent.data.databento_historical import DatabentoHistoricalProvider
from agent.data.yahoo_delayed import make_provider

ROOT = Path(__file__).resolve().parents[1]
ET = ZoneInfo("America/New_York")


class _FakeYahoo:
    def __init__(self, bars: list[Bar]):
        self.bars = bars
        self.calls = 0

    def get_bars(self, symbol: str, *, interval: str = "5m", period: str = "10d"):
        self.calls += 1
        return list(self.bars)

    def get_latest_bar(self, symbol: str, *, interval: str = "5m", period: str = "10d"):
        return self.get_bars(symbol, interval=interval, period=period)[-1]

    def health(self):
        return ProviderHealth("yahoo_delayed", datetime.now(timezone.utc), None, 0, True)


def _bar(ts: datetime, close: float) -> Bar:
    return Bar(
        symbol="NQ",
        timestamp=ts,
        open=close - 0.25,
        high=close + 0.5,
        low=close - 0.5,
        close=close,
        volume=10.0,
        source="yahoo_delayed",
        is_realtime=False,
        estimated_delay_seconds=780.0,
        is_stale=False,
        received_time=datetime.now(timezone.utc),
        metadata={"bar_interval": "5m", "bar_interval_seconds": 300},
    )


def test_paid_cache_overrides_overlap_and_yahoo_supplies_current_tail(tmp_path):
    base_aware = datetime.now(ET).replace(minute=0, second=0, microsecond=0) - timedelta(days=1)
    idx = pd.date_range(base_aware, periods=16, freq="1min")
    close = [100.0 + (i * 0.01) for i in range(len(idx))]
    frame = pd.DataFrame(
        {
            "open": close,
            "high": [x + 0.1 for x in close],
            "low": [x - 0.1 for x in close],
            "close": close,
            "volume": [2.0] * len(idx),
        },
        index=idx,
    )
    frame.to_parquet(tmp_path / "NQ_1m_cache.parquet")
    (tmp_path / "NQ_1m_cache_meta.json").write_text(
        '{"end":"paid-cache-end","databento":"NQ.v.0",'
        '"stype_in":"continuous",'
        '"cache_format_version":"databento_continuous_v1"}',
        encoding="utf-8",
    )

    base = base_aware.replace(tzinfo=None)
    yahoo = _FakeYahoo(
        [
            _bar(base + timedelta(minutes=5), 100.55),
            _bar(base + timedelta(minutes=10), 100.60),
            _bar(base + timedelta(minutes=15), 100.75),
        ]
    )
    provider = DatabentoCacheYahooProvider(
        yahoo,
        cache_dir=tmp_path,
        cache_roots=["NQ"],
        max_relative_basis_gap=0.02,
    )

    bars = provider.get_bars("NQ", interval="5m", period="10d")
    by_ts = {b.timestamp: b for b in bars}
    assert by_ts[base + timedelta(minutes=10)].source == "databento_cache"
    assert by_ts[base + timedelta(minutes=10)].close != 100.60
    assert bars[-1].timestamp == base + timedelta(minutes=15)
    assert bars[-1].source == "databento_cache+yahoo_delayed"
    assert bars[-1].metadata["paid_databento_bars"] >= 3
    assert bars[-1].metadata["databento_api_called"] is False

    # Hybrid cache prevents management + pipeline from repeating work.
    provider.get_bars("NQ", interval="5m", period="10d")
    assert yahoo.calls == 1


def test_live_settings_construct_zero_spend_hybrid_provider():
    cfg = load_settings(ROOT / "config" / "settings.yaml")
    provider = make_provider(cfg)
    assert isinstance(provider, DatabentoCacheYahooProvider)
    assert cfg["market_data"]["databento_allow_api_refresh"] is False
    assert set(cfg["market_data"]["databento_cache_roots"]) == {"NQ", "ES", "CL", "GC"}


def test_unstable_basis_falls_back_to_exact_yahoo_and_caches_result(tmp_path):
    base_aware = datetime.now(ET).replace(minute=0, second=0, microsecond=0) - timedelta(days=1)
    idx = pd.date_range(base_aware, periods=16, freq="1min")
    frame = pd.DataFrame(
        {
            "open": [200.0] * len(idx),
            "high": [201.0] * len(idx),
            "low": [199.0] * len(idx),
            "close": [200.0] * len(idx),
            "volume": [2.0] * len(idx),
        },
        index=idx,
    )
    frame.to_parquet(tmp_path / "NQ_1m_cache.parquet")
    (tmp_path / "NQ_1m_cache_meta.json").write_text(
        '{"databento":"NQ.v.0","stype_in":"continuous",'
        '"cache_format_version":"databento_continuous_v1"}',
        encoding="utf-8",
    )
    base = base_aware.replace(tzinfo=None)
    exact = [
        _bar(base + timedelta(minutes=5), 100.0),
        _bar(base + timedelta(minutes=10), 100.0),
        _bar(base + timedelta(minutes=15), 100.0),
    ]
    yahoo = _FakeYahoo(exact)
    provider = DatabentoCacheYahooProvider(yahoo, cache_dir=tmp_path, cache_roots=["NQ"])

    bars = provider.get_bars("NQ")
    assert bars[-1].source == "yahoo_delayed"
    assert [b.close for b in bars] == [100.0, 100.0, 100.0]
    provider.get_bars("NQ")
    assert yahoo.calls == 1


def test_legacy_parent_cache_is_rejected_even_when_median_basis_looks_close(tmp_path):
    base_aware = datetime.now(ET).replace(minute=0, second=0, microsecond=0) - timedelta(days=1)
    idx = pd.date_range(base_aware, periods=16, freq="1min")
    close = [100.0 + i * 0.01 for i in range(len(idx))]
    pd.DataFrame(
        {
            "open": close,
            "high": [x + 0.1 for x in close],
            "low": [x - 0.1 for x in close],
            "close": close,
            "volume": [2.0] * len(idx),
        },
        index=idx,
    ).to_parquet(tmp_path / "NQ_1m_cache.parquet")
    (tmp_path / "NQ_1m_cache_meta.json").write_text(
        '{"databento":"NQ.FUT","stype_in":"parent"}', encoding="utf-8"
    )
    base = base_aware.replace(tzinfo=None)
    yahoo = _FakeYahoo([_bar(base + timedelta(minutes=5), 100.05)])
    bars = DatabentoCacheYahooProvider(
        yahoo, cache_dir=tmp_path, cache_roots=["NQ"]
    ).get_bars("NQ")
    assert bars[-1].source == "yahoo_delayed"
    assert bars[-1].metadata["databento_cache_status"] == "rejected"
    assert "parent-symbol" in bars[-1].metadata["databento_cache_reject_reason"]


def test_continuous_symbol_resolution_never_uses_parent_for_single_series():
    provider = DatabentoHistoricalProvider(api_key="test")
    assert provider._resolve_symbol("CL", "continuous") == "CL.v.0"
    assert provider._resolve_symbol("NQ", "continuous") == "NQ.v.0"
    assert provider._resolve_symbol("CL", "parent") == "CL.FUT"
