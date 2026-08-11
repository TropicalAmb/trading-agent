"""Validate CL VWAP-prox momentum + NQ NY-open leads. Research only."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent.research.harness.datasets import fetch_yahoo
from agent.research.harness.monte_carlo import monte_carlo
from agent.research.momentum_deep import (
    build_feature_frame,
    collect_momentum_signals,
    sample_label,
    trade_stats,
)
from agent.risk.strategy_lifecycle import (
    StrategyCellState,
    StrategyLifecycleStore,
    compute_kill_thresholds,
)

OUT = ROOT / "data" / "specialist_validation"


def _stats(df: pd.DataFrame) -> dict:
    return trade_stats(df) if len(df) else trade_stats(pd.DataFrame())


def load_parity_book(symbols: list[str], chart_tf: str = "5m", period: str = "60d") -> pd.DataFrame:
    yahoo = {
        "NQ": ("NQ=F", 20.0),
        "MNQ": ("MNQ=F", 2.0),
        "CL": ("CL=F", 1000.0),
        "MCL": ("MCL=F", 100.0),
    }
    rows = []
    for sym in symbols:
        ysym, pv = yahoo[sym]
        print(f"load {chart_tf} {sym}", flush=True)
        df = fetch_yahoo(ysym, chart_tf, period)
        if df is None or len(df) < 200:
            continue
        frame = build_feature_frame(df)
        part = collect_momentum_signals(
            frame, symbol=sym, chart_tf=chart_tf, mode="parity_bias", cooldown=12, point_value=pv
        )
        rows.extend(part)
        print(f"  parity signals={len(part)}", flush=True)
    return pd.DataFrame(rows)


def filter_cl(df: pd.DataFrame) -> pd.DataFrame:
    return df[(df["symbol"].isin(["CL", "MCL"])) & (df["abs_dist_vwap_atr"] <= 0.25)].copy()


def filter_nq_open(df: pd.DataFrame) -> pd.DataFrame:
    return df[(df["symbol"].isin(["NQ", "MNQ"])) & (df["session"] == "ny_open")].copy()


def walk_forward(df: pd.DataFrame, n_folds: int = 5) -> list[dict]:
    d = df.sort_values("timestamp")
    n = len(d)
    if n < n_folds * 10:
        return [{"error": "insufficient", "n": n}]
    folds = []
    edges = np.linspace(0, n, n_folds + 1).astype(int)
    for i in range(n_folds):
        # train = all before fold i test segment; test = fold segment
        te0, te1 = edges[i], edges[i + 1]
        # expanding train before test
        train = d.iloc[:te0] if te0 > 0 else d.iloc[: max(1, te1 // 5)]
        test = d.iloc[te0:te1]
        if len(test) < 5:
            continue
        folds.append(
            {
                "fold": i + 1,
                "train_n": len(train),
                "test": _stats(test),
                "test_range": [str(test["timestamp"].iloc[0]), str(test["timestamp"].iloc[-1])],
            }
        )
    return folds


def holdout(df: pd.DataFrame, frac: float = 0.20) -> dict:
    d = df.sort_values("timestamp")
    cut = int(len(d) * (1 - frac))
    return {
        "train": _stats(d.iloc[:cut]),
        "holdout": _stats(d.iloc[cut:]),
        "cut_ts": str(d.iloc[cut]["timestamp"]) if cut < len(d) else None,
    }


def monthly(df: pd.DataFrame) -> list[dict]:
    d = df.copy()
    d["month"] = pd.to_datetime(d["timestamp"], utc=True).dt.tz_convert("America/New_York").dt.strftime("%Y-%m")
    out = []
    for m, g in d.groupby("month"):
        st = _stats(g)
        st["month"] = m
        out.append(st)
    return out


def by_col(df: pd.DataFrame, col: str) -> dict[str, dict]:
    return {str(k): _stats(g) for k, g in df.groupby(col)}


def vol_regime(df: pd.DataFrame) -> dict[str, dict]:
    d = df.copy()

    def bucket(p):
        if pd.isna(p):
            return "UNKNOWN"
        if p < 0.25:
            return "LOW"
        if p < 0.70:
            return "NORMAL"
        if p < 0.90:
            return "HIGH"
        return "EXTREME"

    d["vol_regime"] = d["atr_pctile"].map(bucket)
    return by_col(d, "vol_regime")


def stress(df: pd.DataFrame, slip_r: float = 0.05, fee_r: float = 0.02) -> dict:
    """Haircut each trade by slip+fee in R units both sides approx."""
    d = df.copy()
    pen = slip_r + fee_r
    d["pnl_r_stress"] = d["pnl_r"].astype(float) - pen
    # recompute win under stress for 2R target model: winners become 2-pen, losers -1-pen
    st = _stats(d.rename(columns={"pnl_r": "_old"}).assign(pnl_r=d["pnl_r_stress"]))
    st["penalty_r"] = pen
    return st


def validate_candidate(name: str, df: pd.DataFrame) -> dict:
    base = _stats(df)
    rs = df["pnl_r"].astype(float).tolist() if len(df) else []
    thr = compute_kill_thresholds(rs)
    mc = monte_carlo(rs, n_sims=5000, seed=11) if len(rs) >= 5 else {"status": "INSUFFICIENT"}
    return {
        "name": name,
        "n": len(df),
        "sample_label": sample_label(len(df)),
        "baseline": base,
        "walk_forward": walk_forward(df),
        "holdout": holdout(df),
        "monthly": monthly(df),
        "by_session": by_col(df, "session") if len(df) else {},
        "by_side": by_col(df, "direction") if len(df) else {},
        "by_symbol": by_col(df, "symbol") if len(df) else {},
        "vol_regime": vol_regime(df) if len(df) else {},
        "monte_carlo": mc,
        "stress_slip_fee": stress(df),
        "kill_thresholds": thr,
        "mfe_mae": {
            "mfe_win": float(df.loc[df.win == 1, "mfe_r"].mean()) if len(df[df.win == 1]) else None,
            "mfe_loss": float(df.loc[df.win == 0, "mfe_r"].mean()) if len(df[df.win == 0]) else None,
            "mae_win": float(df.loc[df.win == 1, "mae_r"].mean()) if len(df[df.win == 1]) else None,
            "mae_loss": float(df.loc[df.win == 0, "mae_r"].mean()) if len(df[df.win == 0]) else None,
        },
    }


def _fmt(st: dict) -> str:
    if not st or not st.get("n"):
        return "n=0"
    return (
        f"n={st['n']} ({sample_label(st['n'])}) WR={(st.get('wr') or 0):.1%} "
        f"PF={(st.get('pf') or 0):.2f} E={(st.get('E') or 0):+.3f} "
        f"DD={st.get('max_dd', 0):.2f} t/wk={st.get('trades_per_week', 0):.1f}"
    )


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    book = load_parity_book(["CL", "MCL", "NQ", "MNQ"], "5m", "60d")
    book.to_csv(OUT / "parity_bias_5m_book.csv", index=False)
    cl = filter_cl(book)
    nq = filter_nq_open(book)
    cl.to_csv(OUT / "cl_vwap_prox_momentum_v1_trades.csv", index=False)
    nq.to_csv(OUT / "nq_ny_open_momentum_v1_trades.csv", index=False)

    cl_rep = validate_candidate("cl_vwap_prox_momentum_v1", cl)
    nq_rep = validate_candidate("nq_ny_open_momentum_v1", nq)

    # Seed lifecycle thresholds (does not activate paper)
    store = StrategyLifecycleStore(OUT / "lifecycle_seed.json")
    for sym in ("CL", "MCL"):
        sub = cl[cl.symbol == sym]
        if len(sub):
            store.seed_thresholds(
                "cl_vwap_prox_momentum",
                sym,
                sub["pnl_r"].astype(float).tolist(),
                expected_wr=cl_rep["baseline"].get("wr"),
                expected_e=cl_rep["baseline"].get("E"),
            )
    for sym in ("NQ", "MNQ"):
        sub = nq[nq.symbol == sym]
        if len(sub):
            store.seed_thresholds(
                "nq_ny_open_momentum",
                sym,
                sub["pnl_r"].astype(float).tolist(),
                expected_wr=nq_rep["baseline"].get("wr"),
                expected_e=nq_rep["baseline"].get("E"),
            )
    # Also seed into runtime path for dashboard
    runtime = StrategyLifecycleStore(ROOT / "data" / "strategy_lifecycle.json")
    for cell in store.snapshot():
        payload = {k: v for k, v in cell.items() if k != "key"}
        runtime.put_cell(StrategyCellState(**payload))

    # Paper decision: keep research_only unless holdout stays strong
    cl_h = cl_rep["holdout"]["holdout"]
    paper = {
        "cl_vwap_prox_momentum": {
            "activate_paper_executable": False,
            "reason": (
                f"holdout WR={(cl_h.get('wr') or 0):.1%} n={cl_h.get('n')} — "
                "keep research_only/shadow until holdout WR>=60% and n>=30 with stable WF"
            ),
            "add_as_research_engine": True,
        },
        "nq_ny_open_momentum": {
            "activate_paper_executable": False,
            "reason": "PROMISING / NOT CONFIRMED — remain research_only",
            "add_as_research_engine": True,
        },
    }
    if (
        (cl_h.get("n") or 0) >= 25
        and (cl_h.get("wr") or 0) >= 0.60
        and (cl_h.get("E") or 0) > 0.4
    ):
        paper["cl_vwap_prox_momentum"]["activate_paper_executable"] = False  # still not sole champion
        paper["cl_vwap_prox_momentum"]["recommend_paper_shadow_track"] = True
        paper["cl_vwap_prox_momentum"]["reason"] = (
            "Holdout remains interesting — add research engine + lifecycle tracking; "
            "do NOT make sole paper champion (n still limited)."
        )

    report = {
        "generated": datetime.now(timezone.utc).isoformat(),
        "cl": cl_rep,
        "nq": nq_rep,
        "paper": paper,
        "lifecycle_seed": store.snapshot(),
    }
    (OUT / "SPECIALIST_VALIDATION_REPORT.json").write_text(
        json.dumps(report, indent=2, default=str), encoding="utf-8"
    )

    lines = [
        "# Specialist Validation Report",
        "",
        f"Generated: {report['generated']}",
        "",
        "**Paper agent not replaced. Candidates added as research engines only.**",
        "",
        "## 1. CL — cl_vwap_prox_momentum_v1",
        "",
        f"Definition: 5m parity-bias momentum + `|VWAP|<=0.25 ATR` on CL/MCL.",
        f"Baseline: {_fmt(cl_rep['baseline'])}",
        "",
        "### Holdout",
        f"- train: {_fmt(cl_rep['holdout']['train'])}",
        f"- holdout: {_fmt(cl_rep['holdout']['holdout'])}",
        "",
        "### Walk-forward folds",
    ]
    for f in cl_rep["walk_forward"]:
        if "error" in f:
            lines.append(str(f))
        else:
            lines.append(f"- fold {f['fold']}: {_fmt(f['test'])} range={f['test_range']}")
    lines += ["", "### Monthly"]
    for m in cl_rep["monthly"]:
        lines.append(f"- {m.get('month')}: {_fmt(m)}")
    lines += ["", "### Session / side / symbol / vol regime"]
    for title, block in [
        ("session", cl_rep["by_session"]),
        ("side", cl_rep["by_side"]),
        ("symbol", cl_rep["by_symbol"]),
        ("vol", cl_rep["vol_regime"]),
    ]:
        lines.append(f"**{title}**")
        for k, st in block.items():
            lines.append(f"- {k}: {_fmt(st)}")
    lines += [
        "",
        "### Monte Carlo",
        json.dumps(cl_rep["monte_carlo"], indent=2),
        "",
        f"### Stress (slip+fee): {_fmt(cl_rep['stress_slip_fee'])}",
        "",
        "### Kill thresholds (pre-deploy)",
        json.dumps(cl_rep["kill_thresholds"], indent=2),
        "",
        "## 2. NQ — nq_ny_open_momentum_v1",
        "",
        f"Definition: 5m parity-bias momentum + session=ny_open on NQ/MNQ.",
        f"Baseline: {_fmt(nq_rep['baseline'])}",
        "",
        "### Holdout",
        f"- train: {_fmt(nq_rep['holdout']['train'])}",
        f"- holdout: {_fmt(nq_rep['holdout']['holdout'])}",
        "",
        "### Walk-forward",
    ]
    for f in nq_rep["walk_forward"]:
        if "error" in f:
            lines.append(str(f))
        else:
            lines.append(f"- fold {f['fold']}: {_fmt(f['test'])}")
    lines += ["", "### Monthly"]
    for m in nq_rep["monthly"]:
        lines.append(f"- {m.get('month')}: {_fmt(m)}")
    lines += ["", "### Session / side / vol"]
    for title, block in [
        ("side", nq_rep["by_side"]),
        ("symbol", nq_rep["by_symbol"]),
        ("vol", nq_rep["vol_regime"]),
    ]:
        lines.append(f"**{title}**")
        for k, st in block.items():
            lines.append(f"- {k}: {_fmt(st)}")
    lines += [
        "",
        "### Monte Carlo",
        json.dumps(nq_rep["monte_carlo"], indent=2),
        "",
        f"### Stress: {_fmt(nq_rep['stress_slip_fee'])}",
        "",
        "### Kill thresholds",
        json.dumps(nq_rep["kill_thresholds"], indent=2),
        "",
        "## Paper changes",
        json.dumps(paper, indent=2),
        "",
    ]
    (OUT / "SPECIALIST_VALIDATION_REPORT.md").write_text("\n".join(lines), encoding="utf-8")
    print("CL", cl_rep["baseline"])
    print("NQ", nq_rep["baseline"])
    print("CL holdout", cl_rep["holdout"]["holdout"])
    print("NQ holdout", nq_rep["holdout"]["holdout"])
    print("Report:", OUT / "SPECIALIST_VALIDATION_REPORT.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
