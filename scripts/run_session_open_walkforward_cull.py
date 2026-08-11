"""Session-open momentum walk-forward + strategy cull board.

Research only. Does not change paper execution or risk.
Uses Yahoo 5m (~60d) until Databento/Kaggle-quality CME history is wired.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent.learning.dataset import build_unified_dataset
from agent.learning.shrink import shrink_rate
from agent.research.harness.datasets import fetch_yahoo
from agent.research.momentum_deep import (
    build_feature_frame,
    collect_momentum_signals,
    trade_stats,
)

OUT = ROOT / "data" / "session_open_walkforward"

YAHOO = {
    "NQ": ("NQ=F", 20.0),
    "MNQ": ("MNQ=F", 2.0),
    "ES": ("ES=F", 50.0),
    "MES": ("MES=F", 5.0),
    "CL": ("CL=F", 1000.0),
    "MCL": ("MCL=F", 100.0),
}

OPEN_SESSIONS = ("asia", "london", "ny_open")


def _norm_stats(st: dict) -> dict:
    """Normalize momentum_deep.trade_stats keys to expectancy_r / max_dd_r."""
    out = dict(st or {})
    if "expectancy_r" not in out and "E" in out:
        out["expectancy_r"] = out.get("E")
    if "max_dd_r" not in out and "max_dd" in out:
        out["max_dd_r"] = out.get("max_dd")
    return out


def walk_forward(df: pd.DataFrame, n_folds: int = 5) -> list[dict]:
    d = df.sort_values("timestamp")
    n = len(d)
    if n < max(25, n_folds * 5):
        return [{"error": "insufficient", "n": n}]
    folds = []
    edges = np.linspace(0, n, n_folds + 1).astype(int)
    for i in range(n_folds):
        te0, te1 = int(edges[i]), int(edges[i + 1])
        test = d.iloc[te0:te1]
        if len(test) < 5:
            continue
        st = _norm_stats(trade_stats(test))
        folds.append(
            {
                "fold": i + 1,
                "n": int(st.get("n") or 0),
                "wr": st.get("wr"),
                "pf": st.get("pf"),
                "expectancy_r": st.get("expectancy_r"),
                "max_dd_r": st.get("max_dd_r"),
                "label": sample_label(st),
            }
        )
    return folds


def sample_label(st: dict) -> str:
    n = int(st.get("n") or 0)
    if n >= 100:
        return "VALIDATED"
    if n >= 40:
        return "DEVELOPING"
    if n >= 20:
        return "EARLY"
    return "ANECDOTAL"


def verdict_for(st: dict, folds: list[dict]) -> str:
    """KEEP / WATCH / X_OUT for research board (not paper promotion)."""
    n = int(st.get("n") or 0)
    wr = float(st.get("wr") or 0)
    e = float(st.get("expectancy_r") or 0)
    pf = float(st.get("pf") or 0)
    if n < 20:
        return "ANECDOTAL_WATCH"
    # Walk-forward: require majority folds with E>0 when enough folds
    good_folds = [f for f in folds if f.get("expectancy_r") is not None and f["expectancy_r"] > 0]
    fold_ok = (len(good_folds) >= max(2, len(folds) // 2)) if folds and "error" not in (folds[0] or {}) else False
    if e > 0 and pf >= 1.2 and wr >= 0.55 and fold_ok:
        return "KEEP_RESEARCH"
    if e > 0 and pf >= 1.0 and wr >= 0.50:
        return "WATCH"
    return "X_OUT"


def load_parity(symbols: list[str], period: str = "60d") -> pd.DataFrame:
    rows = []
    for sym in symbols:
        ysym, pv = YAHOO[sym]
        print(f"load 5m {sym}", flush=True)
        df = fetch_yahoo(ysym, "5m", period)
        if df is None or len(df) < 200:
            print(f"  skip {sym} (short)", flush=True)
            continue
        frame = build_feature_frame(df)
        part = collect_momentum_signals(
            frame, symbol=sym, chart_tf="5m", mode="parity_bias", cooldown=12, point_value=pv
        )
        rows.extend(part)
        print(f"  signals={len(part)}", flush=True)
    return pd.DataFrame(rows)


def cull_from_learning_store() -> list[dict]:
    df, _ = build_unified_dataset(backfill_bars=False)
    if df.empty or "strategy" not in df.columns:
        return []
    out = []
    for strat, part in df.groupby(df["strategy"].astype(str)):
        rs = pd.to_numeric(part["realized_r"], errors="coerce").dropna()
        n = len(rs)
        if n < 8:
            continue
        wins = int((rs > 0).sum())
        wr = wins / n
        gw = float(rs[rs > 0].sum())
        gl = float(abs(rs[rs < 0].sum()))
        pf = (gw / gl) if gl > 1e-12 else (999.0 if gw > 0 else 0.0)
        e = float(rs.mean())
        shr = shrink_rate(wins, n, prior_mean=0.5, prior_strength=20.0)
        st = {
            "n": n,
            "wr": wr,
            "shrunk_wr": shr.shrunk,
            "pf": pf,
            "expectancy_r": e,
            "max_dd_r": float((np.cumsum(rs) - np.maximum.accumulate(np.cumsum(rs))).min()) if n else 0,
        }
        # No folds here — use simple cull
        if n < 20:
            v = "ANECDOTAL_WATCH"
        elif e > 0 and pf >= 1.2 and wr >= 0.50:
            v = "KEEP_RESEARCH"
        elif e > -0.05 and pf >= 0.9:
            v = "WATCH"
        else:
            v = "X_OUT"
        out.append({"strategy": strat, "source": "learning_store_unified", "verdict": v, **st})
    out.sort(key=lambda x: (x.get("expectancy_r") or -9, x.get("n") or 0), reverse=True)
    return out


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    print("Loading parity-bias momentum book (Yahoo 5m 60d)...", flush=True)
    book = load_parity(["NQ", "MNQ", "ES", "MES", "CL", "MCL"], period="60d")
    cells = []
    for sess in OPEN_SESSIONS:
        for family, symbols in (
            ("NQ_FAMILY", ["NQ", "MNQ"]),
            ("ES_FAMILY", ["ES", "MES"]),
            ("CL_FAMILY", ["CL", "MCL"]),
        ):
            part = book[(book["symbol"].isin(symbols)) & (book["session"] == sess)].copy()
            st = _norm_stats(trade_stats(part) if len(part) else trade_stats(pd.DataFrame()))
            folds = walk_forward(part) if len(part) else [{"error": "empty"}]
            v = verdict_for(st, folds if isinstance(folds, list) else [])
            cells.append(
                {
                    "cell": f"{family}|{sess}|parity_mom",
                    "session": sess,
                    "family": family,
                    "symbols": symbols,
                    "verdict": v,
                    "evidence": sample_label(st),
                    "stats": st,
                    "walk_forward": folds,
                    "n": int(st.get("n") or 0),
                    "wr": st.get("wr"),
                    "pf": st.get("pf"),
                    "expectancy_r": st.get("expectancy_r"),
                    "max_dd_r": st.get("max_dd_r"),
                    "trades_per_week": st.get("trades_per_week"),
                }
            )
            print(
                f"{family} {sess}: n={st.get('n')} WR={st.get('wr')} E={st.get('expectancy_r')} -> {v}",
                flush=True,
            )

    # Explicit NQ NY open (existing specialist)
    nq_ny = book[(book["symbol"].isin(["NQ", "MNQ"])) & (book["session"] == "ny_open")].copy()
    nq_st = _norm_stats(trade_stats(nq_ny) if len(nq_ny) else trade_stats(pd.DataFrame()))
    nq_folds = walk_forward(nq_ny) if len(nq_ny) else []
    nq_cell = {
        "cell": "nq_ny_open_momentum_v1",
        "session": "ny_open",
        "family": "NQ_FAMILY",
        "verdict": verdict_for(nq_st, nq_folds),
        "evidence": sample_label(nq_st),
        "stats": nq_st,
        "walk_forward": nq_folds,
        "n": int(nq_st.get("n") or 0),
        "wr": nq_st.get("wr"),
        "pf": nq_st.get("pf"),
        "expectancy_r": nq_st.get("expectancy_r"),
        "max_dd_r": nq_st.get("max_dd_r"),
        "trades_per_week": nq_st.get("trades_per_week"),
    }

    learning_cull = cull_from_learning_store()

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "data_note": (
            "Yahoo 5m ~60d only — NOT Databento. Results are directional research, "
            "not live-proof. Prefer Databento for multi-month CME bars when ready."
        ),
        "nq_ny_open_specialist": nq_cell,
        "session_open_cells": cells,
        "learning_store_strategy_cull": learning_cull,
        "x_out": [c for c in cells if c["verdict"] == "X_OUT"]
        + [c for c in learning_cull if c["verdict"] == "X_OUT"],
        "keep_research": [c for c in cells if c["verdict"] == "KEEP_RESEARCH"]
        + [c for c in learning_cull if c["verdict"] == "KEEP_RESEARCH"],
        "watch": [c for c in cells if c["verdict"] in {"WATCH", "ANECDOTAL_WATCH"}]
        + [c for c in learning_cull if c["verdict"] in {"WATCH", "ANECDOTAL_WATCH"}],
    }
    (OUT / "SESSION_OPEN_WALKFORWARD_REPORT.json").write_text(
        json.dumps(report, indent=2, default=str), encoding="utf-8"
    )

    lines = [
        "# Session Open Momentum + Strategy Cull",
        "",
        f"Generated: {report['generated_at']}",
        "",
        f"**Data caveat:** {report['data_note']}",
        "",
        "## NQ NY-open specialist (existing)",
        f"- verdict: **{nq_cell['verdict']}** ({nq_cell['evidence']})",
        f"- n={nq_st.get('n')} WR={nq_st.get('wr')} PF={nq_st.get('pf')} E={nq_st.get('expectancy_r')} DD={nq_st.get('max_dd_r')} t/wk={nq_st.get('trades_per_week')}",
        "",
        "## Session-open cells (Asia / London / NY open)",
        "",
        "| Cell | n | WR | PF | E[R] | DD | Verdict |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for c in cells:
        lines.append(
            f"| {c['cell']} | {c['n']} | {c.get('wr')} | {c.get('pf')} | {c.get('expectancy_r')} | {c.get('max_dd_r')} | **{c['verdict']}** |"
        )
    lines += ["", "## Learning-store strategy cull (paper/shadow outcomes)", ""]
    for r in learning_cull:
        lines.append(
            f"- **{r['verdict']}** `{r['strategy']}`: n={r['n']} WR={r['wr']:.1%} shrunk={r['shrunk_wr']:.1%} "
            f"PF={r['pf']:.2f} E={r['expectancy_r']:+.3f}R"
        )
    lines += [
        "",
        "## X_OUT (stop spending research time)",
        "",
    ]
    for x in report["x_out"]:
        name = x.get("cell") or x.get("strategy")
        lines.append(f"- {name}")
    lines += ["", "## KEEP_RESEARCH", ""]
    for x in report["keep_research"]:
        name = x.get("cell") or x.get("strategy")
        lines.append(f"- {name}")
    (OUT / "SESSION_OPEN_WALKFORWARD_REPORT.md").write_text("\n".join(lines), encoding="utf-8")
    print("Wrote", OUT / "SESSION_OPEN_WALKFORWARD_REPORT.md", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
