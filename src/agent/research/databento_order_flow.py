"""Guarded Databento TBBO ingestion and deterministic order-flow aggregation.

TBBO is trade-space L1 data: every record is a trade plus the best bid and
offer immediately before that trade.  Databento's side convention is ``B``
for a buyer aggressor and ``A`` for a seller aggressor.  This module keeps
those semantics explicit and never substitutes an OHLCV pressure proxy.

Official references:
https://databento.com/docs/schemas-and-data-formats/cbbo
https://databento.com/docs/standards-and-conventions/common-fields-enums-types
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd


DATASET = "GLBX.MDP3"
SCHEMA = "tbbo"
STYPE_IN = "continuous"
APPROVAL_PHRASE = "USER_APPROVED"
CONTINUOUS_SYMBOLS = {"NQ": "NQ.v.0", "CL": "CL.v.0"}
REQUIRED_TBBO_COLUMNS = (
    "action",
    "side",
    "price",
    "size",
    "bid_px_00",
    "ask_px_00",
    "bid_sz_00",
    "ask_sz_00",
)


class TBBODataQualityError(ValueError):
    """Raised when records cannot safely be treated as Databento TBBO."""


class SpendGuardError(RuntimeError):
    """Raised before a paid request when an explicit spend guard fails."""


@dataclass(frozen=True)
class TBBORequest:
    symbols: tuple[str, ...]
    start: datetime
    end: datetime
    dataset: str = DATASET
    schema: str = SCHEMA
    stype_in: str = STYPE_IN

    def __post_init__(self) -> None:
        if self.dataset != DATASET or self.schema != SCHEMA or self.stype_in != STYPE_IN:
            raise ValueError("TBBO requests are fixed to GLBX.MDP3/tbbo/continuous")
        if not self.symbols:
            raise ValueError("At least one Databento symbol is required")
        unknown = sorted(set(self.symbols) - set(CONTINUOUS_SYMBOLS.values()))
        if unknown:
            raise ValueError(f"Unsupported continuous symbols: {unknown}")
        if self.start.tzinfo is None or self.end.tzinfo is None:
            raise ValueError("TBBO request timestamps must be timezone-aware")
        if self.start >= self.end:
            raise ValueError("TBBO request start must be before end")
        if self.end - self.start > timedelta(days=30):
            raise ValueError("TBBO request window cannot exceed 30 days")

    def api_kwargs(self) -> dict[str, Any]:
        return {
            "dataset": self.dataset,
            "symbols": list(self.symbols),
            "schema": self.schema,
            "stype_in": self.stype_in,
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
        }


@dataclass(frozen=True)
class SpendGuardResult:
    quoted_cost_usd: float
    downloaded: bool
    output_path: Path | None = None


def _normalized_text(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.upper()


def _event_timestamps(frame: pd.DataFrame) -> pd.DatetimeIndex:
    if "ts_event" in frame.columns:
        timestamps = pd.to_datetime(frame["ts_event"], utc=True, errors="coerce")
    elif str(frame.index.name or "").lower() == "ts_event":
        timestamps = pd.to_datetime(frame.index, utc=True, errors="coerce")
    else:
        raise TBBODataQualityError("missing_columns:ts_event")
    if pd.isna(timestamps).any():
        raise TBBODataQualityError("invalid_ts_event")
    return pd.DatetimeIndex(timestamps, name="ts_event")


def normalize_tbbo(frame: pd.DataFrame) -> pd.DataFrame:
    """Validate and normalize one or more decoded Databento TBBO streams.

    Prices are expected to have already been converted by ``DBNStore.to_df``
    to normal floating-point units.  The function fails closed instead of
    guessing missing side, quote, price, or event-time values.
    """

    if frame is None or frame.empty:
        raise TBBODataQualityError("empty_tbbo")
    work = frame.copy()
    work.columns = [str(column).lower() for column in work.columns]
    missing = [column for column in REQUIRED_TBBO_COLUMNS if column not in work.columns]
    if missing:
        raise TBBODataQualityError(f"missing_columns:{','.join(missing)}")

    timestamps = _event_timestamps(work)
    if not timestamps.is_monotonic_increasing:
        raise TBBODataQualityError("unsorted_ts_event")
    work.index = timestamps
    if "ts_event" in work.columns:
        work = work.drop(columns=["ts_event"])

    action = _normalized_text(work["action"])
    bad_action = ~action.isin({"T", "TRADE"})
    if bad_action.any():
        raise TBBODataQualityError(f"non_trade_actions:{int(bad_action.sum())}")

    side_raw = _normalized_text(work["side"])
    side = side_raw.map(
        {
            "B": "BUY",
            "BID": "BUY",
            "BUY": "BUY",
            "A": "SELL",
            "ASK": "SELL",
            "SELL": "SELL",
            "N": "UNKNOWN",
            "NONE": "UNKNOWN",
            "UNKNOWN": "UNKNOWN",
        }
    )
    if side.isna().any():
        values = sorted(side_raw.loc[side.isna()].unique().tolist())
        raise TBBODataQualityError(f"invalid_side_values:{values}")

    numeric_columns = (
        "price",
        "size",
        "bid_px_00",
        "ask_px_00",
        "bid_sz_00",
        "ask_sz_00",
    )
    numeric = work.loc[:, numeric_columns].apply(pd.to_numeric, errors="coerce")
    if not np.isfinite(numeric.to_numpy(dtype=float)).all():
        raise TBBODataQualityError("non_finite_required_values")
    bad_price = (
        (numeric["price"] <= 0)
        | (numeric["bid_px_00"] <= 0)
        | (numeric["ask_px_00"] <= 0)
    )
    if bad_price.any():
        raise TBBODataQualityError(f"nonpositive_price_rows:{int(bad_price.sum())}")
    bad_size = (
        (numeric["size"] <= 0)
        | (numeric["bid_sz_00"] < 0)
        | (numeric["ask_sz_00"] < 0)
    )
    if bad_size.any():
        raise TBBODataQualityError(f"invalid_size_rows:{int(bad_size.sum())}")
    locked_or_crossed = numeric["bid_px_00"] >= numeric["ask_px_00"]
    if locked_or_crossed.any():
        raise TBBODataQualityError(
            f"locked_or_crossed_quote_rows:{int(locked_or_crossed.sum())}"
        )

    depth_total = numeric["bid_sz_00"] + numeric["ask_sz_00"]
    work["aggressor_side"] = side.to_numpy()
    work["trade_price"] = numeric["price"].to_numpy(dtype=float)
    work["trade_size"] = numeric["size"].to_numpy(dtype=float)
    work["bid_price"] = numeric["bid_px_00"].to_numpy(dtype=float)
    work["ask_price"] = numeric["ask_px_00"].to_numpy(dtype=float)
    work["bid_size"] = numeric["bid_sz_00"].to_numpy(dtype=float)
    work["ask_size"] = numeric["ask_sz_00"].to_numpy(dtype=float)
    work["mid_price"] = (work["bid_price"] + work["ask_price"]) / 2.0
    work["spread"] = work["ask_price"] - work["bid_price"]
    work["book_imbalance"] = np.where(
        depth_total.to_numpy(dtype=float) > 0,
        (work["bid_size"] - work["ask_size"]) / depth_total.to_numpy(dtype=float),
        np.nan,
    )
    work["buy_volume"] = np.where(side.to_numpy() == "BUY", work["trade_size"], 0.0)
    work["sell_volume"] = np.where(side.to_numpy() == "SELL", work["trade_size"], 0.0)
    work["unknown_volume"] = np.where(
        side.to_numpy() == "UNKNOWN", work["trade_size"], 0.0
    )
    work["signed_volume"] = work["buy_volume"] - work["sell_volume"]
    work["price_volume"] = work["trade_price"] * work["trade_size"]
    if "symbol" not in work.columns:
        work["symbol"] = ""
    else:
        work["symbol"] = work["symbol"].astype(str)
    return work


def aggregate_tbbo(frame: pd.DataFrame, *, frequency: str = "1min") -> pd.DataFrame:
    """Aggregate validated TBBO records into leak-free completed-time buckets."""

    if frequency not in {"1min", "5min"}:
        raise ValueError("frequency must be '1min' or '5min'")
    work = normalize_tbbo(frame)
    grouped: Iterable[tuple[str, pd.DataFrame]]
    symbols = work["symbol"].drop_duplicates().tolist()
    grouped = ((symbol, work.loc[work["symbol"] == symbol]) for symbol in symbols)
    outputs: list[pd.DataFrame] = []
    for symbol, symbol_frame in grouped:
        bucket = symbol_frame.resample(frequency, label="left", closed="left")
        result = bucket.agg(
            open=("trade_price", "first"),
            high=("trade_price", "max"),
            low=("trade_price", "min"),
            close=("trade_price", "last"),
            trade_count=("trade_size", "size"),
            volume=("trade_size", "sum"),
            buy_volume=("buy_volume", "sum"),
            sell_volume=("sell_volume", "sum"),
            unknown_volume=("unknown_volume", "sum"),
            delta=("signed_volume", "sum"),
            price_volume=("price_volume", "sum"),
            mean_spread=("spread", "mean"),
            last_spread=("spread", "last"),
            mean_book_imbalance=("book_imbalance", "mean"),
            last_book_imbalance=("book_imbalance", "last"),
            last_mid_price=("mid_price", "last"),
        )
        result = result.loc[result["trade_count"] > 0].copy()
        result["vwap"] = result["price_volume"] / result["volume"]
        result["delta_ratio"] = result["delta"] / result["volume"]
        result["unknown_volume_ratio"] = result["unknown_volume"] / result["volume"]
        result["symbol"] = symbol
        result = result.drop(columns=["price_volume"])
        outputs.append(result)
    if not outputs:
        raise TBBODataQualityError("no_aggregated_tbbo_rows")
    out = pd.concat(outputs).sort_index(kind="stable")
    return out[
        [
            "symbol",
            "open",
            "high",
            "low",
            "close",
            "trade_count",
            "volume",
            "buy_volume",
            "sell_volume",
            "unknown_volume",
            "delta",
            "delta_ratio",
            "vwap",
            "mean_spread",
            "last_spread",
            "mean_book_imbalance",
            "last_book_imbalance",
            "last_mid_price",
            "unknown_volume_ratio",
        ]
    ]


def quote_tbbo_cost(client: Any, request: TBBORequest) -> float:
    """Use Databento's free metadata endpoint and validate its response."""

    cost = float(client.metadata.get_cost(**request.api_kwargs()))
    if not np.isfinite(cost) or cost < 0:
        raise SpendGuardError(f"Invalid Databento quote: {cost!r}")
    return cost


def guarded_tbbo_download(
    client: Any,
    request: TBBORequest,
    *,
    output_path: Path,
    download: bool = False,
    confirmation: str = "",
    max_cost_usd: float = 0.0,
) -> SpendGuardResult:
    """Quote first; download only after all explicit spend gates pass."""

    quoted_cost = quote_tbbo_cost(client, request)
    if not download:
        return SpendGuardResult(quoted_cost_usd=quoted_cost, downloaded=False)
    if confirmation != APPROVAL_PHRASE:
        raise SpendGuardError(
            f"Paid TBBO download requires --confirm-spend {APPROVAL_PHRASE}"
        )
    if not np.isfinite(max_cost_usd) or max_cost_usd <= 0:
        raise SpendGuardError("Paid TBBO download requires a positive --max-cost-usd")
    if quoted_cost > float(max_cost_usd):
        raise SpendGuardError(
            f"Quoted cost ${quoted_cost:.6f} exceeds cap ${float(max_cost_usd):.6f}"
        )
    output_path = Path(output_path)
    if output_path.exists():
        raise SpendGuardError(f"Refusing to overwrite existing TBBO file: {output_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    client.timeseries.get_range(**request.api_kwargs(), path=str(output_path))
    if not output_path.exists() or output_path.stat().st_size <= 0:
        raise RuntimeError("Databento returned without creating a non-empty TBBO file")
    return SpendGuardResult(
        quoted_cost_usd=quoted_cost,
        downloaded=True,
        output_path=output_path,
    )
