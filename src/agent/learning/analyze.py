"""Winner/loser traits, interactions, high-accuracy cells, tier/score audits."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

import numpy as np
import pandas as pd

from agent.learning.shrink import shrink_rate


def feature_lift_table(df: pd.DataFrame, *, target: str = "win") -> dict[str, Any]:
    """Bin continuous features and report WR lifts vs baseline."""
    if df.empty or target not in df.columns:
        return {"baseline_wr": None, "lifts": []}
    base = float(df[target].mean())
    lifts = []
    binaryish = [
        "mtf_aligned",
        "above_vwap",
        "below_vwap",
        "ema_bull",
        "ema_bear",
        "overextended",
        "near_pdh",
        "near_pdl",
        "momentum_aligned",
        "ema20_above_ema50",
    ]
    for col in binaryish:
        if col not in df.columns:
            continue
        s = pd.to_numeric(df[col], errors="coerce")
        for val in [1, 0]:
            mask = s == val
            n = int(mask.sum())
            if n < 8:
                continue
            wr = float(df.loc[mask, target].mean())
            lifts.append(
                {
                    "feature": f"{col}={val}",
                    "n": n,
                    "wr": wr,
                    "lift_pp": (wr - base) * 100,
                }
            )
    continuous = [
        "vwap_dist_atr",
        "price_vs_ema20_atr",
        "price_vs_ema50_atr",
        "body_atr",
        "stop_dist_atr",
        "atr_pctile",
        "global_score",
        "local_score",
        "target_r",
    ]
    for col in continuous:
        if col not in df.columns:
            continue
        s = pd.to_numeric(df[col], errors="coerce")
        try:
            cats = pd.qcut(s, q=min(4, max(2, s.notna().sum() // 15)), duplicates="drop")
        except Exception:
            continue
        for cat in cats.dropna().unique():
            mask = cats == cat
            n = int(mask.sum())
            if n < 8:
                continue
            wr = float(df.loc[mask, target].mean())
            lifts.append(
                {
                    "feature": f"{col} in {cat}",
                    "n": n,
                    "wr": wr,
                    "lift_pp": (wr - base) * 100,
                }
            )
    lifts.sort(key=lambda x: x["lift_pp"], reverse=True)
    winners = [x for x in lifts if x["lift_pp"] > 0][:15]
    losers = sorted([x for x in lifts if x["lift_pp"] < 0], key=lambda x: x["lift_pp"])[:15]
    return {"baseline_wr": base, "winner_features": winners, "loser_features": losers, "all": lifts}


def interaction_table(df: pd.DataFrame, *, target: str = "win", min_n: int = 15) -> list[dict[str, Any]]:
    if df.empty:
        return []
    combos = [
        ("strategy", "symbol"),
        ("strategy", "session"),
        ("strategy", "regime"),
        ("mtf_aligned", "above_vwap"),
        ("mtf_aligned", "overextended"),
        ("momentum_aligned", "regime"),
        ("near_pdh", "session"),
        ("near_pdl", "session"),
    ]
    base = float(df[target].mean()) if target in df.columns else 0.0
    out = []
    for a, b in combos:
        if a not in df.columns or b not in df.columns:
            continue
        g = df.groupby([a, b], dropna=False)
        for key, part in g:
            n = len(part)
            if n < min_n:
                continue
            wr = float(part[target].mean())
            rs = pd.to_numeric(part.get("realized_r"), errors="coerce").dropna()
            e = float(rs.mean()) if len(rs) else None
            out.append(
                {
                    "interaction": f"{a}×{b}",
                    "values": key,
                    "n": n,
                    "wr": wr,
                    "lift_pp": (wr - base) * 100,
                    "expectancy_r": e,
                }
            )
    out.sort(key=lambda x: (x["wr"], x["n"]), reverse=True)
    return out[:40]


def high_accuracy_cells(
    df: pd.DataFrame,
    *,
    min_n_strong: int = 100,
    min_n_promising: int = 40,
    min_wr: float = 0.65,
    min_pf: float = 1.5,
) -> dict[str, list[dict[str, Any]]]:
    if df.empty:
        return {"strong": [], "promising": []}
    keys = ["strategy", "symbol", "session", "regime", "direction"]
    for k in keys:
        if k not in df.columns:
            return {"strong": [], "promising": []}
    strong, promising = [], []
    for key, part in df.groupby(keys, dropna=False):
        n = len(part)
        if n < min_n_promising:
            continue
        wins = int(part["win"].sum()) if "win" in part.columns else 0
        wr = wins / n
        rs = pd.to_numeric(part["realized_r"], errors="coerce").dropna().tolist()
        gw = sum(r for r in rs if r > 0)
        gl = abs(sum(r for r in rs if r < 0))
        pf = (gw / gl) if gl > 1e-12 else (999.0 if gw > 0 else 0.0)
        e = float(np.mean(rs)) if rs else 0.0
        shr = shrink_rate(wins, n, prior_mean=float(df["win"].mean()), prior_strength=20.0)
        row = {
            "cell": dict(zip(keys, key)),
            "n": n,
            "wr": wr,
            "shrunk_wr": shr.shrunk,
            "pf": pf,
            "expectancy_r": e,
            "label": "STRONG" if n >= min_n_strong else "PROMISING / INSUFFICIENT SAMPLE",
        }
        if wr >= min_wr and e > 0 and pf >= min_pf:
            if n >= min_n_strong:
                strong.append(row)
            else:
                promising.append(row)
    strong.sort(key=lambda x: (x["wr"], x["n"]), reverse=True)
    promising.sort(key=lambda x: (x["wr"], x["n"]), reverse=True)
    return {"strong": strong, "promising": promising}


def tier_calibration(df: pd.DataFrame) -> dict[str, Any]:
    out = {}
    if df.empty or "tier" not in df.columns:
        return {"tiers": {}, "flag": None}
    for tier, part in df.groupby(df["tier"].astype(str)):
        rs = pd.to_numeric(part["realized_r"], errors="coerce").dropna()
        n = len(part)
        wins = int(part["win"].sum()) if "win" in part.columns else int((rs > 0).sum())
        gw = float(rs[rs > 0].sum()) if len(rs) else 0.0
        gl = float(abs(rs[rs < 0].sum())) if len(rs) else 0.0
        out[str(tier)] = {
            "n": n,
            "wr": wins / max(n, 1),
            "pf": (gw / gl) if gl > 1e-12 else (999.0 if gw > 0 else 0.0),
            "expectancy_r": float(rs.mean()) if len(rs) else None,
        }
    # Monotonic A+ >= A >= B on expectancy?
    order = ["C", "B", "A", "A+"]
    es = [out.get(t, {}).get("expectancy_r") for t in order if t in out]
    flag = None
    finite = [e for e in es if e is not None]
    if len(finite) >= 2:
        # check non-decreasing along order present
        present = [(t, out[t]["expectancy_r"]) for t in order if t in out and out[t]["expectancy_r"] is not None]
        for i in range(1, len(present)):
            if present[i][1] + 1e-9 < present[i - 1][1]:
                flag = "TIER_CALIBRATION_FAILURE"
                break
    return {"tiers": out, "flag": flag}


def global_score_deciles(df: pd.DataFrame) -> list[dict[str, Any]]:
    if df.empty or "global_score" not in df.columns:
        return []
    s = pd.to_numeric(df["global_score"], errors="coerce")
    try:
        dec = pd.qcut(s, q=min(10, max(3, s.notna().sum() // 10)), duplicates="drop")
    except Exception:
        return []
    rows = []
    for cat, part in df.groupby(dec, observed=False):
        rs = pd.to_numeric(part["realized_r"], errors="coerce").dropna()
        rows.append(
            {
                "decile": str(cat),
                "n": len(part),
                "wr": float(part["win"].mean()) if "win" in part.columns else None,
                "expectancy_r": float(rs.mean()) if len(rs) else None,
                "score_mean": float(pd.to_numeric(part["global_score"], errors="coerce").mean()),
            }
        )
    return rows


def simulate_router_selection(
    df: pd.DataFrame,
    *,
    mode: str = "v1",
    profile: str = "balanced",
    probs: np.ndarray | None = None,
) -> dict[str, Any]:
    """Select top candidate per (timestamp, symbol, direction) using v1/v2 ranking."""
    if df.empty:
        return {"n": 0, "wr": None, "expectancy_r": None, "pf": None}
    d = df.copy()
    d["_ts"] = pd.to_datetime(d["market_timestamp"], errors="coerce")
    if probs is not None and len(probs) == len(d):
        d["_p"] = probs
    else:
        d["_p"] = pd.to_numeric(d.get("shrunk_win_rate", d.get("win")), errors="coerce").fillna(0.5)
    # Group competitors roughly by day+symbol+direction (proxy for same-bar competition)
    d["_day"] = d["_ts"].dt.floor("D")
    selected_idx = []
    for _, g in d.groupby(["_day", "symbol", "direction"], dropna=False):
        if g.empty:
            continue
        if mode == "v2" and str(profile).lower() == "high_confidence":
            # eligibility
            eg = g.copy()
            eg = eg[pd.to_numeric(eg.get("realized_r"), errors="coerce").notna()]
            # rank by predicted p then wr proxy
            eg = eg.sort_values(["_p"], ascending=False)
            # soft filters using historical cell stats unavailable → use row global_score as weak proxy skipped
            pick = eg.iloc[0]
        elif mode == "v2":
            # expectancy-first using realized_r as oracle stand-in is leakage — use feature score proxy
            # Use _p * sign of prior: for OOS comparison we use model prob only
            eg = g.sort_values(["_p"], ascending=False)
            pick = eg.iloc[0]
        else:
            # v1-like: global score first among rows
            eg = g.sort_values(
                [c for c in ["global_score", "local_score"] if c in g.columns],
                ascending=False,
            )
            pick = eg.iloc[0]
        selected_idx.append(pick.name)
    sel = d.loc[selected_idx]
    rs = pd.to_numeric(sel["realized_r"], errors="coerce").dropna()
    wins = int((rs > 0).sum())
    n = len(rs)
    gw = float(rs[rs > 0].sum()) if n else 0.0
    gl = float(abs(rs[rs < 0].sum())) if n else 0.0
    return {
        "n": n,
        "wr": wins / max(n, 1),
        "expectancy_r": float(rs.mean()) if n else None,
        "pf": (gw / gl) if gl > 1e-12 else (999.0 if gw > 0 else 0.0),
        "trades_per_week": None,
        "realized_rs": [float(x) for x in rs.tolist()],
        "selected_index": list(selected_idx),
    }
