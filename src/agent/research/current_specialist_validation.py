"""Locked-rule validation for only the currently papered specialists.

This module keeps three evidence lanes separate:
1. a corrected Databento volume-continuous replay with frozen parameters;
2. an independent chronological Yahoo replay with the same frozen parameters; and
3. the true paper-forward cohort under one exact config stamp.

No retired/research-only strategy is loaded or reported here.
"""

from __future__ import annotations

from math import sqrt
from pathlib import Path
from typing import Any, Iterable
import json
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from agent.research.harness.datasets import fetch_yahoo
from agent.research.hc_strategies import gen_vwap_rejection
from agent.research.momentum_deep import build_feature_frame, collect_momentum_signals
from agent.research.nq_context_entry import (
    FRICTION_NQ,
    build_context_5m,
    enrich_context_5m_bars,
    generate_candidates,
    realize_trades,
)
from agent.research.harness.metrics import GATES

ACTIVE_SPECIALISTS = (
    "nq_context_entry",
)


def _wilson(wins: int, n: int, z: float = 1.96) -> list[float] | None:
    if n <= 0:
        return None
    p = wins / n
    denom = 1.0 + z * z / n
    center = (p + z * z / (2.0 * n)) / denom
    margin = z * sqrt((p * (1.0 - p) + z * z / (4.0 * n)) / n) / denom
    return [max(0.0, center - margin), min(1.0, center + margin)]


def trade_stats(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    clean = [r for r in rows if np.isfinite(float(r.get("pnl_r", np.nan)))]
    pnl = np.asarray([float(r["pnl_r"]) for r in clean], dtype=float)
    n = len(pnl)
    if not n:
        return {
            "n": 0,
            "wins": 0,
            "win_rate": None,
            "win_rate_95ci": None,
            "profit_factor": None,
            "expectancy_r": None,
            "max_drawdown_r": 0.0,
        }
    wins = int((pnl > 0).sum())
    gross_win = float(pnl[pnl > 0].sum())
    gross_loss = float(abs(pnl[pnl < 0].sum()))
    equity = pnl.cumsum()
    drawdown = equity - np.maximum.accumulate(np.r_[0.0, equity])[-len(equity) :]
    return {
        "n": n,
        "wins": wins,
        "win_rate": wins / n,
        "win_rate_95ci": _wilson(wins, n),
        "profit_factor": gross_win / gross_loss if gross_loss > 1e-12 else None,
        "expectancy_r": float(pnl.mean()),
        "max_drawdown_r": float(drawdown.min()) if len(drawdown) else 0.0,
    }


def chronological_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    ordered = sorted(rows, key=lambda r: str(r.get("entry_ts") or ""))
    cut = int(len(ordered) * 0.8)
    return {
        "all": trade_stats(ordered),
        "development_80pct": trade_stats(ordered[:cut]),
        "latest_20pct": trade_stats(ordered[cut:]),
        "latest_20pct_start": (
            str(ordered[cut].get("entry_ts")) if cut < len(ordered) else None
        ),
    }


def _generate_nq_candidates(frame: pd.DataFrame) -> list[dict[str, Any]]:
    return generate_candidates(
        frame,
        trigger="PULLBACK",
        window="0930_1200",
        confirmation="signal_close",
        zone_atr=0.30,
        stop_atr=0.55,
        vwap_buffer_atr=0.20,
        sides=("BUY",),
        cooldown_bars=2,
        min_stop_atr=0.385,
    )


def _nq_candidates(df5: pd.DataFrame) -> list[dict[str, Any]]:
    return _generate_nq_candidates(enrich_context_5m_bars(df5))


def replay_nq(
    df5: pd.DataFrame,
    *,
    execution_bars: pd.DataFrame | None = None,
) -> list[dict[str, Any]]:
    candidates = _nq_candidates(df5)
    return realize_configured_management(
        candidates,
        df5 if execution_bars is None else execution_bars,
        strategy="nq_context_entry",
        symbol="NQ",
        target_r=1.15,
        friction_points=FRICTION_NQ,
    )


def realize_configured_management(
    candidates: Iterable[dict[str, Any]],
    bars: pd.DataFrame,
    *,
    strategy: str,
    symbol: str,
    target_r: float,
    tp1_r: float = 1.0,
    entry_bar_minutes: int = 5,
    time_stop_minutes: int = 120,
    friction_points: float = 0.0,
    friction_r: float = 0.0,
    move_be_at_r: float = 0.75,
    near_target_frac: float = 0.70,
    lock_profit_frac: float = 0.50,
    trail_after_r: float = 1.0,
    trail_giveback_r: float = 0.35,
) -> list[dict[str, Any]]:
    """Replay the configured two-lot paper manager with next-bar stop tightening."""
    idx = bars.index
    open_ = bars["open"].to_numpy(dtype=float)
    high = bars["high"].to_numpy(dtype=float)
    low = bars["low"].to_numpy(dtype=float)
    close = bars["close"].to_numpy(dtype=float)
    rows: list[dict[str, Any]] = []
    for cand in candidates:
        entry = float(cand["entry"])
        initial_stop = float(cand["stop"])
        side = str(cand.get("side") or cand.get("direction") or "").upper()
        risk = abs(entry - initial_stop)
        if risk <= 1e-12 or side not in {"BUY", "SELL"}:
            continue
        entry_ts = pd.Timestamp(cand["entry_ts"])
        ready_ts = entry_ts + pd.Timedelta(minutes=int(entry_bar_minutes))
        start = int(idx.searchsorted(ready_ts, side="left"))
        if start >= len(idx):
            continue
        target = entry + target_r * risk if side == "BUY" else entry - target_r * risk
        tp1 = entry + tp1_r * risk if side == "BUY" else entry - tp1_r * risk
        stop = initial_stop
        remaining = 1.0
        banked_r = 0.0
        tp1_done = False
        peak_r = 0.0
        raw_r: float | None = None
        exit_ts = entry_ts
        # The live time stop only exits losers. Winners keep running until a
        # barrier; cap research at 24h to avoid carrying across unrelated weeks.
        hard_end = int(idx.searchsorted(ready_ts + pd.Timedelta(hours=24), side="left"))
        hard_end = min(len(idx), max(start, hard_end))
        for j in range(start, hard_end):
            h, l, o, c = float(high[j]), float(low[j]), float(open_[j]), float(close[j])
            stop_hit = (l <= stop) if side == "BUY" else (h >= stop)
            target_hit = (h >= target) if side == "BUY" else (l <= target)
            if stop_hit:
                # Match paper gap handling: a gap through the stop fills at open.
                exit_px = min(stop, o) if side == "BUY" else max(stop, o)
                runner_r = ((exit_px - entry) / risk) if side == "BUY" else ((entry - exit_px) / risk)
                raw_r = banked_r + remaining * runner_r
                exit_ts = idx[j]
                break
            if target_hit:
                raw_r = banked_r + remaining * target_r
                exit_ts = idx[j]
                break
            if not tp1_done:
                tp1_hit = (h >= tp1) if side == "BUY" else (l <= tp1)
                if tp1_hit:
                    banked_r += 0.5 * tp1_r
                    remaining = 0.5
                    tp1_done = True
                    stop = entry
                    exit_ts = idx[j]
                    continue

            favorable_r = ((h - entry) / risk) if side == "BUY" else ((entry - l) / risk)
            peak_r = max(peak_r, favorable_r)
            stop_r = ((stop - entry) / risk) if side == "BUY" else ((entry - stop) / risk)
            new_stop_r = stop_r
            if favorable_r >= move_be_at_r:
                new_stop_r = max(new_stop_r, 0.0)
            if target_r > 0 and favorable_r / target_r >= near_target_frac:
                new_stop_r = max(new_stop_r, target_r * lock_profit_frac)
            if peak_r >= trail_after_r:
                new_stop_r = max(new_stop_r, peak_r - trail_giveback_r)
            if new_stop_r > stop_r:
                stop = entry + new_stop_r * risk if side == "BUY" else entry - new_stop_r * risk

            held_minutes = (pd.Timestamp(idx[j]) - ready_ts).total_seconds() / 60.0
            mark_r = ((c - entry) / risk) if side == "BUY" else ((entry - c) / risk)
            if held_minutes >= time_stop_minutes and mark_r < 0:
                raw_r = banked_r + remaining * mark_r
                exit_ts = idx[j]
                break
        if raw_r is None:
            j = max(start, hard_end - 1)
            mark_r = ((float(close[j]) - entry) / risk) if side == "BUY" else ((entry - float(close[j])) / risk)
            raw_r = banked_r + remaining * mark_r
            exit_ts = idx[j]
        pnl_r = float(raw_r - friction_r - friction_points / risk)
        rows.append(
            {
                "strategy": strategy,
                "symbol": symbol,
                "entry_ts": str(entry_ts),
                "exit_ts": str(exit_ts),
                "pnl_r": pnl_r,
                "tp1_done": tp1_done,
            }
        )
    return rows


def realize_nq_scaled_exit(
    candidates: Iterable[dict[str, Any]],
    bars: pd.DataFrame,
    *,
    tp1_r: float,
    target_r: float = 1.15,
    entry_bar_minutes: int = 5,
    max_hold_minutes: int = 180,
) -> list[dict[str, Any]]:
    """Two-lot outcome: half at TP1, runner to target/BE, stop-first OHLC ordering."""
    idx = bars.index
    high = bars["high"].to_numpy(dtype=float)
    low = bars["low"].to_numpy(dtype=float)
    close = bars["close"].to_numpy(dtype=float)
    rows: list[dict[str, Any]] = []
    for cand in candidates:
        entry = float(cand["entry"])
        stop = float(cand["stop"])
        side = str(cand["side"])
        risk = abs(entry - stop)
        if risk <= 1e-12:
            continue
        target = entry + target_r * risk if side == "BUY" else entry - target_r * risk
        tp1 = entry + tp1_r * risk if side == "BUY" else entry - tp1_r * risk
        entry_ts = pd.Timestamp(cand["entry_ts"])
        ready_ts = entry_ts + pd.Timedelta(minutes=int(entry_bar_minutes))
        start = int(idx.searchsorted(ready_ts, side="left"))
        end_ts = ready_ts + pd.Timedelta(minutes=int(max_hold_minutes))
        end = min(len(idx), max(start, int(idx.searchsorted(end_ts, side="left"))))
        tp1_done = False
        raw_r: float | None = None
        exit_ts = entry_ts
        for j in range(start, end):
            h, l = float(high[j]), float(low[j])
            initial_stop_hit = (l <= stop) if side == "BUY" else (h >= stop)
            target_hit = (h >= target) if side == "BUY" else (l <= target)
            tp1_hit = (h >= tp1) if side == "BUY" else (l <= tp1)
            if not tp1_done:
                # Conservative same-bar ordering: original stop wins ambiguity.
                if initial_stop_hit:
                    raw_r = -1.0
                    exit_ts = idx[j]
                    break
                if target_hit:
                    raw_r = 0.5 * tp1_r + 0.5 * target_r
                    exit_ts = idx[j]
                    break
                if tp1_hit:
                    tp1_done = True
                    continue
            else:
                be_hit = (l <= entry) if side == "BUY" else (h >= entry)
                if be_hit and target_hit:
                    raw_r = 0.5 * tp1_r
                    exit_ts = idx[j]
                    break
                if be_hit:
                    raw_r = 0.5 * tp1_r
                    exit_ts = idx[j]
                    break
                if target_hit:
                    raw_r = 0.5 * tp1_r + 0.5 * target_r
                    exit_ts = idx[j]
                    break
        if raw_r is None:
            if start >= len(idx):
                runner_r = 0.0
            else:
                j = max(start, end - 1)
                exit_ts = idx[j]
                runner_r = (
                    (float(close[j]) - entry) / risk
                    if side == "BUY"
                    else (entry - float(close[j])) / risk
                )
            raw_r = (
                0.5 * tp1_r + 0.5 * runner_r if tp1_done else runner_r
            )
        # Same per-contract point friction assumption as the locked baseline.
        pnl_r = float(raw_r - FRICTION_NQ / risk)
        rows.append(
            {
                "strategy": "nq_context_entry",
                "symbol": "NQ",
                "entry_ts": str(entry_ts),
                "exit_ts": str(exit_ts),
                "tp1_r": float(tp1_r),
                "target_r": float(target_r),
                "pnl_r": pnl_r,
            }
        )
    return rows


def replay_nq_exit_sensitivity(
    df5: pd.DataFrame,
    *,
    execution_bars: pd.DataFrame | None = None,
) -> dict[str, Any]:
    candidates = _nq_candidates(df5)
    bars = df5 if execution_bars is None else execution_bars
    baseline_trades = realize_trades(
        candidates,
        bars,
        target_r=1.15,
        symbol="NQ",
        entry_bar_minutes=5,
        max_hold_minutes=180,
    )
    baseline = [
        {
            "strategy": "nq_context_entry",
            "symbol": "NQ",
            "entry_ts": t.entry_ts,
            "pnl_r": float(t.pnl_r),
        }
        for t in baseline_trades
    ]
    return {
        "method": (
            "two contracts; half at TP1; runner stop moves to breakeven on the next bar; "
            "same-bar stop wins; identical NQ point-friction haircut"
        ),
        "configured_management": chronological_summary(
            replay_nq(df5, execution_bars=bars)
        ),
        "baseline_no_scale": chronological_summary(baseline),
        "scale_out": {
            f"{tp1:.2f}R": chronological_summary(
                realize_nq_scaled_exit(candidates, bars, tp1_r=tp1)
            )
            for tp1 in (0.30, 0.50, 0.75, 1.00)
        },
    }


def replay_cl(df5: pd.DataFrame) -> list[dict[str, Any]]:
    frame = build_feature_frame(df5)
    rows = collect_momentum_signals(
        frame,
        symbol="CL",
        chart_tf="5m",
        mode="parity_bias",
        cooldown=12,
        stop_atr_mult=1.0,
        point_value=1000.0,
    )
    candidates = [
        {
            "entry_ts": row["timestamp"],
            "entry": row["entry"],
            "stop": row["stop"],
            "side": row["direction"],
        }
        for row in rows
        if float(row.get("abs_dist_vwap_atr", 999.0)) <= 0.25
    ]
    # One underlying only: do not pool CL and MCL as independent observations.
    return realize_configured_management(
        candidates,
        df5,
        strategy="cl_vwap_prox_momentum",
        symbol="CL",
        target_r=2.0,
        friction_r=0.07,
    )


def replay_vwap(frames_1h: dict[str, pd.DataFrame]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for symbol, frame in frames_1h.items():
        for trade in gen_vwap_rejection(frame, symbol, target_r=1.5):
            out.append(
                {
                    "strategy": "vwap_rejection",
                    "symbol": symbol,
                    "entry_ts": trade.entry_ts,
                    "pnl_r": float(trade.pnl_r),
                }
            )
    return out


def run_yahoo_locked_replay() -> dict[str, Any]:
    nq = fetch_yahoo("NQ=F", "5m", "60d")
    cl = fetch_yahoo("CL=F", "5m", "60d")
    hourly = {
        symbol: fetch_yahoo(ticker, "1h", "365d")
        for symbol, ticker in {
            "NQ": "NQ=F",
            "ES": "ES=F",
            "CL": "CL=F",
            "GC": "GC=F",
        }.items()
    }
    rows = {
        "nq_context_entry": replay_nq(nq) if len(nq) else [],
        "cl_vwap_prox_momentum": replay_cl(cl) if len(cl) else [],
        "vwap_rejection": replay_vwap(hourly),
    }
    return {
        "source": "Yahoo independent screening; frozen current rules; no optimization",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "windows": {
            "NQ_5m": [str(nq.index.min()), str(nq.index.max())] if len(nq) else None,
            "CL_5m": [str(cl.index.min()), str(cl.index.max())] if len(cl) else None,
            "VWAP_1h": {
                s: [str(d.index.min()), str(d.index.max())] if len(d) else None
                for s, d in hourly.items()
            },
        },
        "strategies": {name: chronological_summary(part) for name, part in rows.items()},
        "nq_exit_sensitivity": replay_nq_exit_sensitivity(nq) if len(nq) else {},
        "paper_promotion_gate": {
            "min_n": GATES["min_n"],
            "min_win_rate": GATES["min_wr"],
            "min_profit_factor": GATES["min_pf"],
            "min_expectancy_r": GATES["min_expectancy_r"],
        },
    }


def _verified_continuous_cache(cache_dir: Path, root: str) -> tuple[pd.DataFrame, dict[str, Any]]:
    path = cache_dir / f"{root}_1m_cache.parquet"
    meta_path = cache_dir / f"{root}_1m_cache_meta.json"
    frame = pd.read_parquet(path).sort_index()
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    expected = f"{root}.v.0"
    quality = meta.get("quality_audit") or {}
    if (
        str(meta.get("databento") or "").lower() != expected.lower()
        or str(meta.get("stype_in") or "").lower() != "continuous"
        or str(meta.get("cache_format_version") or "") != "databento_continuous_v1"
        or str(quality.get("status") or "").upper() == "FAIL"
    ):
        raise RuntimeError(f"Databento cache failed identity/quality preflight: {root}")
    return frame, meta


def _completed_5m(frame_1m: pd.DataFrame) -> pd.DataFrame:
    counts = frame_1m["close"].resample("5min", label="left", closed="left").count()
    bars = frame_1m.resample("5min", label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    )
    return bars.loc[counts >= 4].dropna(subset=["open", "high", "low", "close"])


def run_databento_locked_replay(cache_dir: Path) -> dict[str, Any]:
    """Run frozen strategies on paid, audited `.v.0` one-minute history."""
    nq_1m, nq_meta = _verified_continuous_cache(cache_dir, "NQ")
    cl_1m, cl_meta = _verified_continuous_cache(cache_dir, "CL")
    nq_5m = build_context_5m(nq_1m)
    cl_5m = _completed_5m(cl_1m)
    nq_candidates = _generate_nq_candidates(nq_5m)
    nq_rows = realize_configured_management(
        nq_candidates,
        nq_1m,
        strategy="nq_context_entry",
        symbol="NQ",
        target_r=1.15,
        friction_points=FRICTION_NQ,
    )
    nq_baseline = [
        {
            "strategy": "nq_context_entry",
            "symbol": "NQ",
            "entry_ts": t.entry_ts,
            "pnl_r": float(t.pnl_r),
        }
        for t in realize_trades(
            nq_candidates,
            nq_1m,
            target_r=1.15,
            symbol="NQ",
            entry_bar_minutes=5,
            max_hold_minutes=180,
        )
    ]
    cl_rows = replay_cl(cl_5m)
    return {
        "source": "Databento GLBX.MDP3 audited volume-continuous `.v.0`; frozen current rules; no optimization",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "windows": {
            "NQ_1m": [str(nq_1m.index.min()), str(nq_1m.index.max())],
            "CL_1m": [str(cl_1m.index.min()), str(cl_1m.index.max())],
        },
        "cache_quality": {
            "NQ": nq_meta.get("quality_audit") or {},
            "CL": cl_meta.get("quality_audit") or {},
        },
        "strategies": {
            "nq_context_entry": chronological_summary(nq_rows),
            "cl_vwap_prox_momentum": chronological_summary(cl_rows),
        },
        "nq_exit_sensitivity": {
            "method": (
                "two contracts; half at TP1; runner stop moves to breakeven on the next bar; "
                "same-bar stop wins; signal bar must close before 1m execution; identical NQ friction"
            ),
            "baseline_no_scale": chronological_summary(nq_baseline),
            "configured_management": chronological_summary(nq_rows),
            "scale_out": {
                f"{tp1:.2f}R": chronological_summary(
                    realize_nq_scaled_exit(nq_candidates, nq_1m, tp1_r=tp1)
                )
                for tp1 in (0.30, 0.50, 0.75, 1.00)
            },
        },
        "paper_promotion_gate": {
            "min_n": GATES["min_n"],
            "min_win_rate": GATES["min_wr"],
            "min_profit_factor": GATES["min_pf"],
            "min_expectancy_r": GATES["min_expectancy_r"],
        },
    }


def _forward_rows(
    state: dict[str, Any],
    config_version: str,
    active_specialists: Iterable[str] = ACTIVE_SPECIALISTS,
) -> list[dict[str, Any]]:
    active = set(active_specialists)
    out: list[dict[str, Any]] = []
    for row in state.get("closed_trades") or []:
        strategy = str(row.get("strategy_name") or "")
        stamp = str(
            row.get("config_version")
            or (row.get("metadata") or {}).get("config_version")
            or ""
        )
        if strategy not in active or stamp != config_version:
            continue
        reason = str(row.get("exit_reason") or "").lower()
        if reason in {"tp1", "universe_prune", "correlation_prune", "demo"}:
            continue
        pnl = row.get("pnl_dollars")
        risk = row.get("risk_dollars")
        try:
            pnl_f = float(pnl)
            risk_f = abs(float(risk))
        except (TypeError, ValueError):
            continue
        if risk_f <= 1e-12:
            continue
        out.append(
            {
                "strategy": strategy,
                "symbol": row.get("symbol"),
                "entry_ts": row.get("opened_at") or row.get("market_timestamp"),
                "pnl_r": pnl_f / risk_f,
                "pnl_dollars": pnl_f,
                "feed_source": row.get("feed_source"),
            }
        )
    return out


def summarize_true_forward(
    state: dict[str, Any],
    config_version: str,
    active_specialists: Iterable[str] = ACTIVE_SPECIALISTS,
) -> dict[str, Any]:
    active = tuple(active_specialists)
    rows = _forward_rows(state, config_version, active)
    return {
        "config_version": config_version,
        "definition": "closed paper trades under this exact stamp only",
        "overall": trade_stats(rows),
        "strategies": {
            name: trade_stats([r for r in rows if r["strategy"] == name])
            for name in active
        },
    }


def write_report(payload: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "CURRENT_SPECIALIST_VALIDATION.json").write_text(
        json.dumps(payload, indent=2, default=str), encoding="utf-8"
    )
    active = set(payload.get("active_specialists") or [])
    metric_rows: list[dict[str, Any]] = []
    lanes = (
        ("databento_locked_replay", "Databento corrected .v.0"),
        ("yahoo_locked_replay", "Yahoo independent"),
    )
    for lane_key, lane_label in lanes:
        for name, result in (payload.get(lane_key, {}).get("strategies") or {}).items():
            for cohort_key, cohort_label in (
                ("all", "All"),
                ("latest_20pct", "Latest 20%"),
            ):
                stats = result[cohort_key]
                metric_rows.append(
                    {
                        "source": lane_label,
                        "strategy": name,
                        "cohort": cohort_label,
                        "deployment": "active_forward" if name in active else "research_only",
                        **stats,
                    }
                )
    pd.DataFrame(metric_rows).to_csv(output_dir / "strategy_metrics.csv", index=False)

    def fmt(st: dict[str, Any]) -> str:
        if not st or not st.get("n"):
            return "n=0 — no measured win rate"
        pf = st.get("profit_factor")
        return (
            f"n={st['n']} · WR={st['win_rate']:.1%} · "
            f"PF={pf:.2f} · E={st['expectancy_r']:+.3f}R · "
            f"maxDD={st['max_drawdown_r']:+.2f}R"
            if pf is not None
            else f"n={st['n']} · WR={st['win_rate']:.1%} · PF=∞ · "
            f"E={st['expectancy_r']:+.3f}R · maxDD={st['max_drawdown_r']:+.2f}R"
        )

    active_label = ", ".join(payload["active_specialists"]) or "none"
    lines = [
        "# Current Specialist Validation",
        "",
        "## Executive decision",
        "",
        "No strategy currently passes every frozen threshold on both the corrected paid Databento lane and the independent Yahoo lane using the bot's configured management. Paper entry is therefore fail-closed; this is not a profitability claim.",
        "",
        "## True forward paper cohort",
        "",
        f"Config: `{payload['true_forward']['config_version']}`",
        f"Active: `{active_label}`",
        "",
        f"- Overall: {fmt(payload['true_forward']['overall'])}",
    ]
    for name, st in payload["true_forward"]["strategies"].items():
        lines.append(f"- `{name}`: {fmt(st)}")
    lines += [
        "",
    ]
    for lane_key, lane_label in lanes:
        lane = payload.get(lane_key) or {}
        lines += [
            "",
            f"## {lane_label} frozen replay",
            "",
            str(lane.get("source") or ""),
            "",
        ]
        for name, result in (lane.get("strategies") or {}).items():
            lines += [
                f"### `{name}`",
                "",
                f"- All: {fmt(result['all'])}",
                f"- Latest chronological 20%: {fmt(result['latest_20pct'])}",
                f"- Holdout start: {result['latest_20pct_start']}",
                "",
            ]
        sensitivity = lane.get("nq_exit_sensitivity") or {}
        if sensitivity:
            lines += [
                "### NQ exit architecture",
                "",
                sensitivity.get("method", ""),
                "",
                f"- Configured manager: {fmt((sensitivity.get('configured_management') or {}).get('all') or {})}",
                f"- No scale-out: {fmt((sensitivity.get('baseline_no_scale') or {}).get('all') or {})}",
            ]
            for label, cohorts in (sensitivity.get("scale_out") or {}).items():
                lines.append(f"- TP1 `{label}` without pre-TP1 protection: {fmt((cohorts or {}).get('all') or {})}")
            lines.append("")
    lines += [
        "## Methodology and reproducibility",
        "",
        "- Rules and thresholds were frozen before this replay; this run performed no parameter search.",
        "- Primary metrics simulate configured quantity-two management: 1R half exit, next-bar breakeven/profit-stop tightening, stop-first same-bar ordering, 120-minute losing-only time stop, and friction.",
        "- A five-minute signal cannot execute until its signal bar has closed; one-minute Databento paths begin at the next tradable minute.",
        "- Every higher-timeframe feature is point-in-time. Automated prefix-invariance tests verify that appending future bars cannot change an earlier feature or signal.",
        "- CL and MCL are one underlying and are not counted as independent observations.",
        "- The current-stamp cohort excludes partial TP1 rows, prune/demo exits, different config stamps, and research-only strategies.",
        "- Reproduce with `python scripts/run_current_specialist_validation.py`.",
        "",
        "## Limitations",
        "",
        "Neither replay is a fill-perfect simulator or proof of future returns. Databento marks six source dates degraded; CL also has an elevated 2–30 minute gap rate. Those warnings are retained in `CORRECTED_CACHE_QUALITY.md`. Latest Yahoo NQ has only 10 trades.",
        "",
        "## Decision rule",
        "",
        "Historical promotion requires both lanes to meet n≥40, WR≥55%, PF≥1.3, E≥0.15R, plus non-negative latest-slice expectancy and PF≥1.0. Forward profitability still requires at least 40 resolved current-stamp paper trades with PF≥1.3 and positive expectancy after friction.",
        "",
        "## Sources",
        "",
        "- [Databento symbology conventions](https://databento.com/docs/standards-and-conventions/symbology)",
        "- [Databento parent symbology](https://databento.com/docs/examples/symbology/parent-symbology)",
        "- [Databento continuous symbology](https://databento.com/docs/examples/symbology/continuous)",
        "- [r/algotrading: paper-to-live mistakes](https://www.reddit.com/r/algotrading/comments/1vmdce4/paper_2_live_what_mistakes_did_your_trading_bot/)",
        "- [r/algotrading: walk-forward, holdout, and paper validation](https://www.reddit.com/r/algotrading/comments/1u4dcdp/progress_on_my_custom_algo_trading_bot_from_the/)",
        "- [r/algotrading: implementation bugs can manufacture edge](https://www.reddit.com/r/algotrading/comments/1v06g8t/a_bug_in_my_code_accidentally_made_my_strategy/)",
    ]
    (output_dir / "CURRENT_SPECIALIST_VALIDATION.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
