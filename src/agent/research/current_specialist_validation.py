"""Locked-rule validation for only the currently papered specialists.

This module keeps two evidence lanes separate:
1. an independent chronological Yahoo replay with frozen parameters; and
2. the true paper-forward cohort under one exact config stamp.

No retired/research-only strategy is loaded or reported here.
"""

from __future__ import annotations

from math import sqrt
from pathlib import Path
from typing import Any, Iterable
import json

import numpy as np
import pandas as pd

from agent.research.harness.datasets import fetch_yahoo
from agent.research.hc_strategies import gen_vwap_rejection
from agent.research.momentum_deep import build_feature_frame, collect_momentum_signals
from agent.research.nq_context_entry import (
    enrich_context_5m_bars,
    generate_candidates,
    realize_trades,
)

ACTIVE_SPECIALISTS = (
    "nq_context_entry",
    "cl_vwap_prox_momentum",
    "vwap_rejection",
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


def replay_nq(df5: pd.DataFrame) -> list[dict[str, Any]]:
    frame = enrich_context_5m_bars(df5)
    candidates = generate_candidates(
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
    trades = realize_trades(candidates, df5, target_r=1.15, symbol="NQ")
    return [
        {
            "strategy": "nq_context_entry",
            "symbol": "NQ",
            "entry_ts": t.entry_ts,
            "pnl_r": float(t.pnl_r),
        }
        for t in trades
    ]


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
    # One underlying only: do not pool CL and MCL as independent observations.
    return [
        {
            "strategy": "cl_vwap_prox_momentum",
            "symbol": "CL",
            "entry_ts": str(row["timestamp"]),
            # Same stress used by the specialist report: 0.05R slippage + 0.02R fees.
            "pnl_r": float(row["pnl_r"]) - 0.07,
        }
        for row in rows
        if float(row.get("abs_dist_vwap_atr", 999.0)) <= 0.25
    ]


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
        "windows": {
            "NQ_5m": [str(nq.index.min()), str(nq.index.max())] if len(nq) else None,
            "CL_5m": [str(cl.index.min()), str(cl.index.max())] if len(cl) else None,
            "VWAP_1h": {
                s: [str(d.index.min()), str(d.index.max())] if len(d) else None
                for s, d in hourly.items()
            },
        },
        "strategies": {name: chronological_summary(part) for name, part in rows.items()},
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
    for name, result in payload["yahoo_locked_replay"]["strategies"].items():
        for cohort_key, cohort_label in (
            ("all", "All"),
            ("latest_20pct", "Latest 20%"),
        ):
            stats = result[cohort_key]
            metric_rows.append(
                {
                    "strategy": name,
                    "cohort": cohort_label,
                    "deployment": "active_forward" if name in active else "disabled",
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

    lines = [
        "# Current Specialist Validation",
        "",
        "## Executive decision",
        "",
        "The old Databento parent-symbol cache is excluded. Only `nq_context_entry` and `cl_vwap_prox_momentum` remain active for clean paper-forward measurement. `vwap_rejection` is disabled after a large negative-expectancy replay. No strategy is called forward-profitable yet.",
        "",
        "## True forward paper cohort",
        "",
        f"Config: `{payload['true_forward']['config_version']}`",
        f"Active: `{', '.join(payload['active_specialists'])}`",
        "",
        f"- Overall: {fmt(payload['true_forward']['overall'])}",
    ]
    for name, st in payload["true_forward"]["strategies"].items():
        lines.append(f"- `{name}`: {fmt(st)}")
    lines += [
        "",
        "## Frozen-rule independent Yahoo replay",
        "",
        "This is chronological historical replay, not future data. The latest 20% was not used to retune parameters in this run. NQ includes a 3-tick point haircut, CL includes a 0.07R fee/slippage haircut, and VWAP uses a 3-tick haircut.",
        "",
    ]
    for name, result in payload["yahoo_locked_replay"]["strategies"].items():
        lines.append(f"### `{name}`")
        lines.append("")
        lines.append(f"- All: {fmt(result['all'])}")
        lines.append(f"- Latest chronological 20%: {fmt(result['latest_20pct'])}")
        lines.append(f"- Holdout start: {result['latest_20pct_start']}")
        lines.append("")
    lines += [
        "## Methodology and reproducibility",
        "",
        "- Rules and thresholds were frozen before this replay; this run performed no parameter search.",
        "- Every higher-timeframe feature is point-in-time. Automated prefix-invariance tests verify that appending future bars cannot change an earlier feature or signal.",
        "- CL and MCL are one underlying and are not counted as independent observations.",
        "- The current-stamp cohort excludes partial TP1 rows, prune/demo exits, different config stamps, and research-only strategies.",
        "- Reproduce with `python scripts/run_current_specialist_validation.py`.",
        "",
        "## Limitations",
        "",
        "Yahoo replay is an independent screen, not a fill-perfect simulator or proof of future returns. Confidence intervals are wide for the latest NQ and CL slices. Corrected Databento `.v.0` validation remains pending explicit download approval.",
        "",
        "## Decision rule",
        "",
        "Do not claim forward profitability until a strategy has at least 40 resolved current-stamp trades with PF≥1.3 and positive expectancy after friction. A backtest or Yahoo screen cannot substitute for that cohort.",
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
