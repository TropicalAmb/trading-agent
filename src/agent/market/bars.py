from __future__ import annotations

import logging
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


def fetch_bars_yfinance(symbol: str, interval: str = "5m", period: str = "10d") -> pd.DataFrame:
    """Free intraday bars for sweep logic. Futures: use MES=F, MNQ=F, ES=F, etc."""
    import time
    from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout

    import yfinance as yf

    ticker = symbol
    yahoo_map = {
        "MES": "MES=F",
        "MNQ": "MNQ=F",
        "ES": "ES=F",
        "NQ": "NQ=F",
        "MGC": "MGC=F",
        "MYM": "MYM=F",
        "M2K": "M2K=F",
        "MCL": "MCL=F",
        "CL": "CL=F",
        "GC": "GC=F",
        "YM": "YM=F",
        "RTY": "RTY=F",
    }
    ticker = yahoo_map.get(symbol.upper(), symbol)

    def _download(per: str) -> pd.DataFrame:
        df = yf.download(
            ticker,
            interval=interval,
            period=per,
            auto_adjust=True,
            progress=False,
        )
        if df is None or df.empty:
            raise RuntimeError(f"No bars for {ticker}")
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [c[0] for c in df.columns]
        df = df.rename(columns=str.lower)
        df = df.dropna(subset=["open", "high", "low", "close"]).copy()
        df.index = pd.to_datetime(df.index)
        if df.index.tz is not None:
            df.index = df.index.tz_convert("America/New_York").tz_localize(None)
        return df[["open", "high", "low", "close", "volume"]]

    last_err: Exception | None = None
    for attempt, per in enumerate((period, "5d", "10d")):
        try:
            with ThreadPoolExecutor(max_workers=1) as pool:
                fut = pool.submit(_download, per)
                return fut.result(timeout=40)
        except FuturesTimeout as exc:
            last_err = RuntimeError(f"Yahoo timeout for {ticker}")
            logger.warning("Yahoo fetch %s attempt %s timed out", ticker, attempt + 1)
        except Exception as exc:
            last_err = exc
            logger.warning("Yahoo fetch %s attempt %s failed: %s", ticker, attempt + 1, exc)
            time.sleep(1.2 * (attempt + 1))
    raise RuntimeError(f"No bars for {ticker}: {last_err}")


def make_bar_source(cfg: dict[str, Any]):
    interval = cfg.get("sweep_retest", {}).get("bar_interval", "5m")
    period = cfg.get("sweep_retest", {}).get("bar_period", "10d")

    def _src(symbol: str) -> pd.DataFrame:
        return fetch_bars_yfinance(symbol, interval=interval, period=period)

    return _src


def probe_market_data(symbols: list[str], *, interval: str = "5m", period: str = "5d") -> list[dict[str, Any]]:
    """Fetch latest Yahoo bars and return a status row per symbol (for startup proof)."""
    rows: list[dict[str, Any]] = []
    for symbol in symbols:
        df = fetch_bars_yfinance(symbol, interval=interval, period=period)
        last = df.iloc[-1]
        rows.append(
            {
                "symbol": symbol.upper(),
                "source": "yahoo_finance",
                "ticker": {
                    "MES": "MES=F",
                    "MNQ": "MNQ=F",
                    "ES": "ES=F",
                    "NQ": "NQ=F",
                    "MGC": "MGC=F",
                    "MYM": "MYM=F",
                    "M2K": "M2K=F",
                    "MCL": "MCL=F",
                    "CL": "CL=F",
                    "GC": "GC=F",
                }.get(symbol.upper(), symbol),
                "bars": len(df),
                "last_bar_time": str(df.index[-1]),
                "last_close": float(last["close"]),
                "last_high": float(last["high"]),
                "last_low": float(last["low"]),
            }
        )
    return rows


def log_market_data_status(symbols: list[str], log: logging.Logger | None = None) -> None:
    """Print clear proof that strategy data is live Yahoo, not dummy prices."""
    log = log or logger
    log.info("=== MARKET DATA CHECK (Yahoo Finance — free, ~10–15m delayed CME) ===")
    for row in probe_market_data(symbols):
        log.info(
            "LIVE DATA %s (%s): last_close=%.2f  bar_time=%s  bars=%d",
            row["symbol"],
            row["ticker"],
            row["last_close"],
            row["last_bar_time"],
            row["bars"],
        )
    log.info(
        "Note: mock/dry_run only affects ORDER ROUTING — strategy bars above are real market prints."
    )
