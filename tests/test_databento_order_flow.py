from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import pytest

from agent.research.databento_order_flow import (
    SpendGuardError,
    TBBODataQualityError,
    TBBORequest,
    aggregate_tbbo,
    guarded_tbbo_download,
    normalize_tbbo,
)


def _tbbo_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "ts_event": pd.to_datetime(
                [
                    "2026-08-14T13:30:00Z",
                    "2026-08-14T13:30:30Z",
                    "2026-08-14T13:31:00Z",
                ]
            ),
            "action": ["T", "Trade", "T"],
            "side": ["B", "Ask", "None"],
            "price": [100.25, 100.00, 100.25],
            "size": [2, 1, 3],
            "bid_px_00": [100.00, 100.00, 100.00],
            "ask_px_00": [100.25, 100.25, 100.25],
            "bid_sz_00": [6, 4, 5],
            "ask_sz_00": [4, 6, 5],
            "symbol": ["NQ.v.0", "NQ.v.0", "NQ.v.0"],
        }
    )


def _request() -> TBBORequest:
    return TBBORequest(
        symbols=("NQ.v.0", "CL.v.0"),
        start=datetime(2026, 7, 15, tzinfo=timezone.utc),
        end=datetime(2026, 8, 14, tzinfo=timezone.utc),
    )


class _Metadata:
    def __init__(self, cost: float):
        self.cost = cost
        self.calls: list[dict] = []

    def get_cost(self, **kwargs):
        self.calls.append(kwargs)
        return self.cost


class _Timeseries:
    def __init__(self):
        self.calls: list[dict] = []

    def get_range(self, **kwargs):
        self.calls.append(kwargs)
        Path(kwargs["path"]).write_bytes(b"DBN")


class _Client:
    def __init__(self, cost: float):
        self.metadata = _Metadata(cost)
        self.timeseries = _Timeseries()


def test_tbbo_side_semantics_and_one_minute_aggregation():
    normalized = normalize_tbbo(_tbbo_frame())
    assert normalized["aggressor_side"].tolist() == ["BUY", "SELL", "UNKNOWN"]
    assert normalized["signed_volume"].tolist() == [2.0, -1.0, 0.0]

    bars = aggregate_tbbo(_tbbo_frame(), frequency="1min")
    first = bars.iloc[0]
    assert first["trade_count"] == 2
    assert first["volume"] == 3
    assert first["buy_volume"] == 2
    assert first["sell_volume"] == 1
    assert first["unknown_volume"] == 0
    assert first["delta"] == 1
    assert first["delta_ratio"] == pytest.approx(1 / 3)
    assert first["vwap"] == pytest.approx((100.25 * 2 + 100.00) / 3)
    assert first["mean_spread"] == pytest.approx(0.25)
    assert first["mean_book_imbalance"] == pytest.approx(0.0)
    assert bars.iloc[1]["unknown_volume_ratio"] == pytest.approx(1.0)


def test_tbbo_fails_closed_on_missing_fields():
    frame = _tbbo_frame().drop(columns=["bid_px_00"])
    with pytest.raises(TBBODataQualityError, match="missing_columns:bid_px_00"):
        normalize_tbbo(frame)


@pytest.mark.parametrize(
    ("column", "value", "error"),
    [
        ("price", 0, "nonpositive_price_rows"),
        ("size", 0, "invalid_size_rows"),
        ("action", "A", "non_trade_actions"),
        ("side", "?", "invalid_side_values"),
    ],
)
def test_tbbo_fails_closed_on_invalid_trade_values(column, value, error):
    frame = _tbbo_frame()
    frame.loc[0, column] = value
    with pytest.raises(TBBODataQualityError, match=error):
        normalize_tbbo(frame)


def test_tbbo_fails_closed_on_locked_or_crossed_quotes():
    frame = _tbbo_frame()
    frame.loc[0, "bid_px_00"] = frame.loc[0, "ask_px_00"]
    with pytest.raises(TBBODataQualityError, match="locked_or_crossed_quote_rows:1"):
        normalize_tbbo(frame)


def test_tbbo_fails_closed_on_unsorted_event_time():
    frame = _tbbo_frame().iloc[[1, 0, 2]].reset_index(drop=True)
    with pytest.raises(TBBODataQualityError, match="unsorted_ts_event"):
        normalize_tbbo(frame)


def test_quote_only_never_calls_paid_timeseries(tmp_path):
    client = _Client(23.170063)
    result = guarded_tbbo_download(
        client,
        _request(),
        output_path=tmp_path / "would_be_paid.dbn.zst",
    )
    assert result.quoted_cost_usd == pytest.approx(23.170063)
    assert result.downloaded is False
    assert len(client.metadata.calls) == 1
    assert client.timeseries.calls == []
    assert not (tmp_path / "would_be_paid.dbn.zst").exists()


def test_request_cannot_bypass_fixed_schema_or_thirty_day_cap():
    with pytest.raises(ValueError, match="fixed to GLBX.MDP3/tbbo/continuous"):
        TBBORequest(
            symbols=("NQ.v.0",),
            start=datetime(2026, 8, 1, tzinfo=timezone.utc),
            end=datetime(2026, 8, 2, tzinfo=timezone.utc),
            schema="mbp-1",
        )
    with pytest.raises(ValueError, match="cannot exceed 30 days"):
        TBBORequest(
            symbols=("NQ.v.0",),
            start=datetime(2026, 7, 1, tzinfo=timezone.utc),
            end=datetime(2026, 7, 1, tzinfo=timezone.utc) + timedelta(days=31),
        )


def test_download_refuses_without_exact_confirmation(tmp_path):
    client = _Client(23.170063)
    with pytest.raises(SpendGuardError, match="USER_APPROVED"):
        guarded_tbbo_download(
            client,
            _request(),
            output_path=tmp_path / "tbbo.dbn.zst",
            download=True,
            confirmation="yes",
            max_cost_usd=24,
        )
    assert client.timeseries.calls == []


def test_download_refuses_when_quote_exceeds_cost_cap(tmp_path):
    client = _Client(23.170063)
    with pytest.raises(SpendGuardError, match="exceeds cap"):
        guarded_tbbo_download(
            client,
            _request(),
            output_path=tmp_path / "tbbo.dbn.zst",
            download=True,
            confirmation="USER_APPROVED",
            max_cost_usd=23.0,
        )
    assert client.timeseries.calls == []


def test_approved_download_streams_directly_to_file(tmp_path):
    client = _Client(23.170063)
    output = tmp_path / "tbbo.dbn.zst"
    result = guarded_tbbo_download(
        client,
        _request(),
        output_path=output,
        download=True,
        confirmation="USER_APPROVED",
        max_cost_usd=23.18,
    )
    assert result.downloaded is True
    assert result.output_path == output
    assert output.read_bytes() == b"DBN"
    assert client.timeseries.calls[0]["schema"] == "tbbo"
    assert client.timeseries.calls[0]["stype_in"] == "continuous"
    assert client.timeseries.calls[0]["symbols"] == ["NQ.v.0", "CL.v.0"]


def test_spend_guard_never_prints_api_credentials(tmp_path, capsys):
    client = _Client(1.0)
    guarded_tbbo_download(
        client,
        _request(),
        output_path=tmp_path / "unused.dbn.zst",
    )
    assert capsys.readouterr().out == ""
