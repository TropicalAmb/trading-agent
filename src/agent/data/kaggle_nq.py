"""Kaggle NQ 1-minute historical loader (research primary source).

Preferred dataset: tgtanalytics/nq-futures-1min-bar-2022-2025
File: Dataset_NQ_1min_2022_2025.csv (~Dec 2022–Dec 2025, America/New_York stamps).

Yahoo remains paper delayed diagnostics only — not the research primary feed.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

DEFAULT_SLUG = "tgtanalytics/nq-futures-1min-bar-2022-2025"
DEFAULT_FILENAME = "Dataset_NQ_1min_2022_2025.csv"
FALLBACK_SLUG = "youneseloiarm/nasdaq-cme-future-nq"


def default_local_paths(repo_root: Path | None = None) -> list[Path]:
    root = repo_root or Path(__file__).resolve().parents[3]
    return [
        root / "data" / "kaggle" / DEFAULT_FILENAME,
        root / "data" / "raw" / DEFAULT_FILENAME,
        Path.home()
        / ".cache"
        / "kagglehub"
        / "datasets"
        / "tgtanalytics"
        / "nq-futures-1min-bar-2022-2025"
        / "versions"
        / "1"
        / DEFAULT_FILENAME,
    ]


def download_kaggle_nq(
    *,
    slug: str = DEFAULT_SLUG,
    dest_dir: Path | None = None,
    filename: str = DEFAULT_FILENAME,
) -> Path:
    """Download via kagglehub and copy primary CSV into data/kaggle/."""
    import kagglehub

    cache = Path(kagglehub.dataset_download(slug))
    src = cache / filename
    if not src.exists():
        matches = list(cache.rglob(filename))
        if not matches:
            # fall back: any 1-minute CSV in the cache
            matches = list(cache.rglob("*1*min*.csv")) + list(cache.rglob("*1_minute*.csv"))
        if not matches:
            raise FileNotFoundError(f"No NQ 1m CSV found under {cache}")
        src = matches[0]
    dest_dir = dest_dir or Path(__file__).resolve().parents[3] / "data" / "kaggle"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / src.name
    if not dest.exists() or dest.stat().st_size != src.stat().st_size:
        dest.write_bytes(src.read_bytes())
    logger.info("Kaggle NQ cached at %s (%s bytes)", dest, dest.stat().st_size)
    return dest


def resolve_nq_1m_csv(path: str | Path | None = None, *, auto_download: bool = True) -> Path:
    if path:
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(p)
        return p
    env = os.getenv("KAGGLE_NQ_1M_CSV", "").strip()
    if env and Path(env).exists():
        return Path(env)
    for candidate in default_local_paths():
        if candidate.exists():
            return candidate
    if auto_download:
        try:
            return download_kaggle_nq()
        except Exception as exc:
            logger.warning("Kaggle auto-download failed: %s", exc)
    raise FileNotFoundError(
        "NQ 1m CSV not found. Place Dataset_NQ_1min_2022_2025.csv under data/kaggle/ "
        "or set KAGGLE_NQ_1M_CSV, or install kagglehub and retry."
    )


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    work = df.copy()
    work.columns = [str(c).strip() for c in work.columns]
    rename = {
        "timestamp ET": "timestamp",
        "timestamp_et": "timestamp",
        "datetime": "timestamp",
        "Date": "timestamp",
        "time": "timestamp",
        "Vwap_RTH": "vwap_rth",
        "Vwap_ETH": "vwap_eth",
        "VWAP_RTH": "vwap_rth",
        "VWAP_ETH": "vwap_eth",
        "Open": "open",
        "High": "high",
        "Low": "low",
        "Close": "close",
        "Volume": "volume",
    }
    work = work.rename(columns={k: v for k, v in rename.items() if k in work.columns})
    lower = {c: c.lower() for c in work.columns}
    work = work.rename(columns=lower)
    return work


def load_nq_1m_csv(
    path: str | Path | None = None,
    *,
    auto_download: bool = True,
    assume_tz: str = "America/New_York",
) -> pd.DataFrame:
    """Load NQ 1-minute OHLCV (+ optional VWAP columns) as tz-aware ET index."""
    csv_path = resolve_nq_1m_csv(path, auto_download=auto_download)
    df = pd.read_csv(csv_path)
    df = _normalize_columns(df)
    if "timestamp" not in df.columns:
        raise ValueError(f"Missing timestamp column in {csv_path}; cols={list(df.columns)}")
    for need in ("open", "high", "low", "close"):
        if need not in df.columns:
            raise ValueError(f"Missing {need} in {csv_path}")
    if "volume" not in df.columns:
        df["volume"] = 0.0
    ts = pd.to_datetime(df["timestamp"], errors="coerce")
    if getattr(ts.dt, "tz", None) is None:
        ts = ts.dt.tz_localize(assume_tz, ambiguous="infer", nonexistent="shift_forward")
    else:
        ts = ts.dt.tz_convert(assume_tz)
    out = pd.DataFrame(
        {
            "open": pd.to_numeric(df["open"], errors="coerce").to_numpy(),
            "high": pd.to_numeric(df["high"], errors="coerce").to_numpy(),
            "low": pd.to_numeric(df["low"], errors="coerce").to_numpy(),
            "close": pd.to_numeric(df["close"], errors="coerce").to_numpy(),
            "volume": pd.to_numeric(df["volume"], errors="coerce").fillna(0.0).to_numpy(),
        },
        index=ts,
    )
    if "vwap_rth" in df.columns:
        out["vwap_rth"] = pd.to_numeric(df["vwap_rth"], errors="coerce").to_numpy()
    if "vwap_eth" in df.columns:
        out["vwap_eth"] = pd.to_numeric(df["vwap_eth"], errors="coerce").to_numpy()
    out = out[~out.index.isna()].sort_index()
    out = out.dropna(subset=["open", "high", "low", "close"])
    out = out[~out.index.duplicated(keep="last")]
    out.attrs["source"] = "kaggle"
    out.attrs["path"] = str(csv_path)
    out.attrs["symbol"] = "NQ"
    return out


def resample_ohlcv(df_1m: pd.DataFrame, rule: str = "5min") -> pd.DataFrame:
    """Build higher-TF OHLCV from 1m (label=left, closed=left)."""
    agg: dict[str, Any] = {
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    }
    for col in ("vwap_rth", "vwap_eth"):
        if col in df_1m.columns:
            agg[col] = "last"
    out = df_1m.resample(rule, label="left", closed="left").agg(agg)
    return out.dropna(subset=["open", "high", "low", "close"])
