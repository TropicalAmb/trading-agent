"""Momentum deep diagnostic pass — research only. Does not touch paper agent."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.tree import DecisionTreeClassifier, export_text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent.research.harness.datasets import fetch_yahoo
from agent.research.momentum_deep import (
    R_TARGETS,
    build_feature_frame,
    collect_momentum_signals,
    conditional_table,
    sample_label,
    trade_stats,
)
from agent.strategy.indicator_parity import compute_parity_frame

OUT = ROOT / "data" / "momentum_deep"

SYMBOLS = {
    "NQ": ("NQ=F", 20.0),
    "MNQ": ("MNQ=F", 2.0),
    "ES": ("ES=F", 50.0),
    "MES": ("MES=F", 5.0),
    "GC": ("GC=F", 100.0),
    "MGC": ("MGC=F", 10.0),
    "CL": ("CL=F", 1000.0),
    "MCL": ("MCL=F", 100.0),
}

# Yahoo practical max depths by interval
TF_PERIODS = {
    "1m": "7d",
    "5m": "60d",
    "15m": "60d",
    "60m": "730d",
    "1h": "730d",
    "4h": "730d",
}

INTERACTIONS = [
    ("agree_1h_15m==1", lambda d: d["agree_1h_15m"] == 1),
    ("agree_1h_15m==1 & vwap_side_ok", lambda d: (d["agree_1h_15m"] == 1) & (d["vwap_side_ok"] == 1)),
    ("agree_1h_15m==1 & pullback_recent", lambda d: (d["agree_1h_15m"] == 1) & (d["pullback_recent"] == 1)),
    ("agree_4h_1h==1 & abs_vwap<=0.6", lambda d: (d["agree_4h_1h"] == 1) & (d["abs_dist_vwap_atr"] <= 0.6)),
    ("agree_15m_5m==1 & rel_vol>1.15", lambda d: (d["agree_15m_5m"] == 1) & (d["rel_volume"] > 1.15)),
    ("pullback_recent & body_range>0.5", lambda d: (d["pullback_recent"] == 1) & (d["body_range"] > 0.5)),
    ("agree_1h_15m_5m==1 & vwap_side_ok", lambda d: (d["agree_1h_15m_5m"] == 1) & (d["vwap_side_ok"] == 1)),
    ("agree_4h_1h_15m==1 & vwap_side_ok & pullback", lambda d: (d["agree_4h_1h_15m"] == 1) & (d["vwap_side_ok"] == 1) & (d["pullback_recent"] == 1)),
    ("agree_all4==1 & abs_vwap<=0.75", lambda d: (d["agree_all4"] == 1) & (d["abs_dist_vwap_atr"] <= 0.75)),
    ("vwap_side_ok & abs_vwap<=0.25", lambda d: (d["vwap_side_ok"] == 1) & (d["abs_dist_vwap_atr"] <= 0.25)),
    ("vwap_side_ok & abs_vwap 0.25-0.75", lambda d: (d["vwap_side_ok"] == 1) & (d["abs_dist_vwap_atr"] > 0.25) & (d["abs_dist_vwap_atr"] <= 0.75)),
    ("agree_1h==1 & ema_aligned & rel_vol>1.15", lambda d: (d["agree_1h"] == 1) & (d["ema_aligned"] == 1) & (d["rel_volume"] > 1.15)),
    ("not overextended & agree_1h_15m & vwap_ok", lambda d: (d["overextended"] == 0) & (d["agree_1h_15m"] == 1) & (d["vwap_side_ok"] == 1)),
    ("breakout==1 & agree_1h_15m", lambda d: (d["breakout"] == 1) & (d["agree_1h_15m"] == 1)),
    ("retest==1 & agree_1h_15m", lambda d: (d["retest"] == 1) & (d["agree_1h_15m"] == 1)),
]


def inventory() -> pd.DataFrame:
    rows = []
    for sym, (ysym, _) in SYMBOLS.items():
        for tf, period in TF_PERIODS.items():
            if tf == "60m":
                continue  # alias of 1h
            print(f"inventory {sym} {tf} {period}", flush=True)
            try:
                df = fetch_yahoo(ysym, tf, period)
            except Exception as e:
                rows.append(
                    {
                        "symbol": sym,
                        "timeframe": tf,
                        "source": f"Yahoo {ysym}",
                        "period_requested": period,
                        "start": None,
                        "end": None,
                        "bars": 0,
                        "gaps": f"ERROR:{e}",
                    }
                )
                continue
            if df is None or df.empty:
                rows.append(
                    {
                        "symbol": sym,
                        "timeframe": tf,
                        "source": f"Yahoo {ysym}",
                        "period_requested": period,
                        "start": None,
                        "end": None,
                        "bars": 0,
                        "gaps": "EMPTY",
                    }
                )
                continue
            # gap estimate: median bar delta vs large gaps
            deltas = df.index.to_series().diff().dt.total_seconds().dropna()
            med = float(deltas.median()) if len(deltas) else np.nan
            gap_n = int((deltas > 3 * med).sum()) if med and med > 0 else 0
            rows.append(
                {
                    "symbol": sym,
                    "timeframe": tf,
                    "source": f"Yahoo {ysym}",
                    "period_requested": period,
                    "start": str(df.index.min()),
                    "end": str(df.index.max()),
                    "bars": int(len(df)),
                    "gaps": f"median_dt_s={med:.0f}; gaps>3x_median={gap_n}",
                }
            )
    inv = pd.DataFrame(rows)
    OUT.mkdir(parents=True, exist_ok=True)
    inv.to_csv(OUT / "data_inventory.csv", index=False)
    lines = [
        "# Momentum Deep — Data Inventory",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        "Local multi-month 1m archive: **not present** in repo.",
        "Source: Yahoo Finance native intervals (no fabrication of 1m from higher TF).",
        "",
        "| symbol | timeframe | source | period | start | end | bars | gaps |",
        "|---|---|---|---|---|---|---:|---|",
    ]
    for _, r in inv.iterrows():
        lines.append(
            f"| {r['symbol']} | {r['timeframe']} | {r['source']} | {r['period_requested']} | "
            f"{r['start']} | {r['end']} | {r['bars']} | {r['gaps']} |"
        )
    lines += [
        "",
        "## Practical max history (Yahoo)",
        "- 1m: ~7 days",
        "- 5m / 15m: ~60 days",
        "- 1h / 4h: ~2 years (730d request)",
        "",
        "Repo also has trade journals / research CSVs under `data/` but **no OHLC bar warehouse**.",
        "",
    ]
    (OUT / "DATA_INVENTORY.md").write_text("\n".join(lines), encoding="utf-8")
    return inv


def pine_boolean_map() -> dict:
    return {
        "source": "data/indicator_parity/MTF_Sweep_Retest_Assistant.pine",
        "BUY_NOW": (
            "longBias AND longSetup AND (close > open) AND (close > high[1])"
        ),
        "SELL_NOW": (
            "shortBias AND shortSetup AND (close < open) AND (close < low[1])"
        ),
        "longBias": "allBullNow AND (useVWAP ? close > vwap : TRUE)  "
        "where allBullNow = (s15==1 AND s1h==1 AND s4h==1)",
        "shortBias": "allBearNow AND (useVWAP ? close < vwap : TRUE)",
        "longSetup": "longSweepActive AND longRetestZone AND close > pdl",
        "shortSetup": "shortSweepActive AND shortRetestZone AND close < pdh",
        "longSweep": "low < pdl AND close > pdl",
        "shortSweep": "high > pdh AND close < pdh",
        "longSweepActive": "bars_since_longSweep <= sweepValidBars (default 240)",
        "longRetestZone": "low in [pdl - atr*retestZoneATR, pdl + atr*retestZoneATR]",
        "mandatory_for_BUY_NOW": [
            "all three HTF bullish (15/60/240)",
            "VWAP filter when useVWAP=true (default)",
            "PDL sweep then retest zone active",
            "close > pdl",
            "bullish confirmation candle vs prior high",
        ],
        "confidence_score_NOT_required_for_BUY_NOW": True,
        "ema_stack_NOT_required_for_BUY_NOW": True,
    }


def pine_rejection_funnel(symbol: str = "NQ") -> dict:
    ysym, _ = SYMBOLS[symbol]
    df = fetch_yahoo(ysym, "1m", "7d")
    if df is None or len(df) < 200:
        return {"error": "insufficient 1m"}
    frame = compute_parity_frame(df, {"indicator_parity": {"use_vwap": True}})
    n = len(frame)
    # candidate = every bar after warmup
    warmup = 80
    cand = n - warmup
    # progressive gates for long side (counts are bars failing that stage among remaining)
    all_bull = (frame["dir_15m"] == 1) & (frame["dir_1h"] == 1) & (frame["dir_4h"] == 1)
    vwap_ok = frame["close"] > frame["vwap"]
    long_bias = all_bull & vwap_ok
    # reconstruct setup pieces from parity frame
    buy = frame["buy_now"].astype(bool)
    sell = frame["sell_now"].astype(bool)
    # use intermediate columns if present
    long_setup = frame["pullback"] & (frame["dir_15m"] == 1)  # approx; better from exact
    # More precise funnel from compute internals via signal columns
    mom_long = (frame["close"] > frame["open"]) & (frame["close"] > frame["high"].shift(1))
    # From parity: buy_now already final
    # Stage counts for BUY path on all bars
    after_htf = int(all_bull.iloc[warmup:].sum())
    after_vwap = int(long_bias.iloc[warmup:].sum())
    # long_setup from frame columns
    # compute_parity_frame stores long_setup? It stores pullback = long|short setup
    # Use buy_pullback / buy_now
    after_setup = int((long_bias & frame.get("buy_pullback", buy)).iloc[warmup:].sum()) if "buy_pullback" in frame else None
    # Direct: bars with long_bias & pullback flag & close>pdl style via buy_pullback
    buy_pb = frame["buy_pullback"] if "buy_pullback" in frame.columns else buy
    buy_mom = frame["buy_momentum"] if "buy_momentum" in frame.columns else (long_bias & mom_long)
    final_buy = int(buy.iloc[warmup:].sum())
    final_sell = int(sell.iloc[warmup:].sum())
    return {
        "symbol": symbol,
        "interval": "1m",
        "period": "7d",
        "bars_total": n,
        "candidate_bars_after_warmup": cand,
        "long_all3_htf": after_htf,
        "long_htf_and_vwap": after_vwap,
        "long_parity_momentum_bias_trigger": int(buy_mom.iloc[warmup:].sum()),
        "long_pullback_entry_bars": int(buy_pb.iloc[warmup:].sum()),
        "final_BUY_NOW": final_buy,
        "final_SELL_NOW": final_sell,
        "final_signals_either": final_buy + final_sell,
        "why_n_collapsed": (
            "BUY NOW requires ALL of: allBullNow(15+1h+4h) AND VWAP AND "
            "longSweepActive+retestZone+close>pdl AND bullish break of prior high. "
            "On ~7d of 1m data that intersection is rare (often single-digit per symbol)."
        ),
    }


def build_book(chart_tf: str, period: str, mode: str, cooldown: int) -> pd.DataFrame:
    all_rows = []
    for sym, (ysym, pv) in SYMBOLS.items():
        print(f"book {mode} {chart_tf} {sym}", flush=True)
        df = fetch_yahoo(ysym, chart_tf, period)
        if df is None or len(df) < 200:
            print(f"  skip {sym}", flush=True)
            continue
        frame = build_feature_frame(df)
        rows = collect_momentum_signals(
            frame,
            symbol=sym,
            chart_tf=chart_tf,
            mode=mode,
            cooldown=cooldown,
            point_value=pv,
        )
        print(f"  signals={len(rows)}", flush=True)
        all_rows.extend(rows)
    return pd.DataFrame(all_rows)


def winner_loser_report(df: pd.DataFrame) -> dict:
    if df.empty:
        return {}
    wins = df[df["win"] == 1]
    losses = df[df["win"] == 0]
    feats = [
        "agree_4h",
        "agree_1h",
        "agree_15m",
        "agree_5m",
        "agree_1h_15m",
        "agree_1h_15m_5m",
        "agree_4h_1h",
        "agree_all4",
        "vwap_side_ok",
        "pullback_recent",
        "ema_aligned",
        "overextended",
        "breakout",
        "retest",
        "rel_volume",
        "abs_dist_vwap_atr",
        "body_range",
        "atr_pctile",
        "htf_agree_count",
    ]
    out = {"n_win": int(len(wins)), "n_loss": int(len(losses)), "features": {}}
    for f in feats:
        if f not in df.columns:
            continue
        if df[f].dtype == float or f in {"rel_volume", "abs_dist_vwap_atr", "body_range", "atr_pctile"}:
            out["features"][f] = {
                "winner_mean": float(wins[f].mean()) if len(wins) else None,
                "loser_mean": float(losses[f].mean()) if len(losses) else None,
                "winner_median": float(wins[f].median()) if len(wins) else None,
                "loser_median": float(losses[f].median()) if len(losses) else None,
            }
        else:
            out["features"][f] = {
                "winner_rate": float(wins[f].mean()) if len(wins) else None,
                "loser_rate": float(losses[f].mean()) if len(losses) else None,
            }
    return out


def single_condition_scan(df: pd.DataFrame) -> list[dict]:
    conds = []
    specs = [
        ("BASE", lambda d: pd.Series(True, index=d.index)),
        ("4H agrees", lambda d: d["agree_4h"] == 1),
        ("4H conflicts", lambda d: d["agree_4h"] == 0),
        ("1H agrees", lambda d: d["agree_1h"] == 1),
        ("1H conflicts", lambda d: d["agree_1h"] == 0),
        ("15m agrees", lambda d: d["agree_15m"] == 1),
        ("5m agrees", lambda d: d["agree_5m"] == 1),
        ("1H+15m agree", lambda d: d["agree_1h_15m"] == 1),
        ("1H+15m+5m agree", lambda d: d["agree_1h_15m_5m"] == 1),
        ("4H+1H agree", lambda d: d["agree_4h_1h"] == 1),
        ("4H+1H+15m agree", lambda d: d["agree_4h_1h_15m"] == 1),
        ("all 4 TF agree", lambda d: d["agree_all4"] == 1),
        ("VWAP side OK", lambda d: d["vwap_side_ok"] == 1),
        ("VWAP side BAD", lambda d: d["vwap_side_ok"] == 0),
        ("|VWAP|<=0.25ATR", lambda d: d["abs_dist_vwap_atr"] <= 0.25),
        ("|VWAP| 0.25-0.75ATR", lambda d: (d["abs_dist_vwap_atr"] > 0.25) & (d["abs_dist_vwap_atr"] <= 0.75)),
        ("|VWAP|>0.75ATR", lambda d: d["abs_dist_vwap_atr"] > 0.75),
        ("pullback before", lambda d: d["pullback_recent"] == 1),
        ("no pullback", lambda d: d["pullback_recent"] == 0),
        ("rel_vol>1.15", lambda d: d["rel_volume"] > 1.15),
        ("rel_vol<=1.15", lambda d: d["rel_volume"] <= 1.15),
        ("ema aligned", lambda d: d["ema_aligned"] == 1),
        ("not overextended", lambda d: d["overextended"] == 0),
        ("overextended", lambda d: d["overextended"] == 1),
        ("breakout", lambda d: d["breakout"] == 1),
        ("retest", lambda d: d["retest"] == 1),
    ]
    for name, fn in specs:
        try:
            mask = fn(df)
            conds.append(conditional_table(df, mask, name))
        except Exception:
            continue
    # sessions
    for sess in sorted(df["session"].dropna().unique()):
        conds.append(conditional_table(df, df["session"] == sess, f"session={sess}"))
    return conds


def interaction_scan(df: pd.DataFrame) -> list[dict]:
    out = []
    for name, fn in INTERACTIONS:
        try:
            mask = fn(df)
            out.append(conditional_table(df, mask, name))
        except Exception:
            continue
    return out


def pareto_frontier(candidates: list[dict], base: dict) -> list[dict]:
    """Keep non-dominated on WR↑ and trades/week↑ (and E as soft)."""
    pts = [base] + [c for c in candidates if c.get("n", 0) >= 30 and c.get("wr") is not None]
    # sort by wr desc
    pts = sorted(pts, key=lambda x: (x.get("wr") or 0), reverse=True)
    frontier = []
    best_tw = -1.0
    # Actually Pareto: maximize WR and trades/week — walk by increasing WR, keep if tw not dominated
    # Collect all, filter dominated
    for p in pts:
        dominated = False
        for q in pts:
            if q is p:
                continue
            if (q.get("wr") or 0) >= (p.get("wr") or 0) and (q.get("trades_per_week") or 0) >= (
                p.get("trades_per_week") or 0
            ) and (
                (q.get("wr") or 0) > (p.get("wr") or 0)
                or (q.get("trades_per_week") or 0) > (p.get("trades_per_week") or 0)
            ):
                dominated = True
                break
        if not dominated:
            frontier.append(p)
    frontier = sorted(frontier, key=lambda x: (x.get("wr") or 0), reverse=True)
    return frontier[:20]


def shallow_tree(df: pd.DataFrame) -> dict:
    if len(df) < 80:
        return {"error": "too few rows"}
    feature_cols = [
        "agree_4h",
        "agree_1h",
        "agree_15m",
        "agree_5m",
        "agree_1h_15m",
        "vwap_side_ok",
        "abs_dist_vwap_atr",
        "pullback_recent",
        "rel_volume",
        "ema_aligned",
        "overextended",
        "body_range",
        "htf_agree_count",
        "breakout",
    ]
    X = df[feature_cols].replace([np.inf, -np.inf], np.nan).fillna(0.0)
    y = df["win"].astype(int)
    clf = DecisionTreeClassifier(max_depth=3, min_samples_leaf=30, random_state=42)
    clf.fit(X, y)
    text = export_text(clf, feature_names=feature_cols)
    # evaluate leaf-like rules manually via top paths — report tree text + overall train score
    return {
        "max_depth": 3,
        "min_samples_leaf": 30,
        "train_accuracy": float(clf.score(X, y)),
        "tree_text": text,
        "feature_importances": dict(zip(feature_cols, [float(x) for x in clf.feature_importances_])),
    }


def oos_eval(df: pd.DataFrame, rule_fn, name: str) -> dict:
    """Chronological 60/20/20 on timestamps."""
    d = df.sort_values("timestamp").copy()
    n = len(d)
    if n < 60:
        return {"name": name, "error": "too few"}
    i1 = int(n * 0.60)
    i2 = int(n * 0.80)
    parts = {
        "TRAIN": d.iloc[:i1],
        "VALIDATION": d.iloc[i1:i2],
        "FINAL": d.iloc[i2:],
    }
    out = {"name": name, "splits": {}}
    for k, part in parts.items():
        mask = rule_fn(part)
        sub = part.loc[mask]
        st = trade_stats(sub)
        st["n_universe"] = len(part)
        st["pct_retained"] = len(sub) / len(part) if len(part) else 0
        out["splits"][k] = st
    # reject if FINAL WR collapses >20pp vs TRAIN
    tr = out["splits"]["TRAIN"].get("wr")
    fi = out["splits"]["FINAL"].get("wr")
    if tr is not None and fi is not None:
        out["overfit_flag"] = bool(tr - fi > 0.20)
        out["stable"] = bool(fi >= 0.55 and (tr - fi) <= 0.15)
    else:
        out["overfit_flag"] = True
        out["stable"] = False
    return out


def fmt_st(st: dict) -> str:
    if not st or st.get("n", 0) == 0:
        return "n=0"
    return (
        f"n={st['n']} ({st.get('label') or sample_label(st['n'])}) "
        f"WR={(st['wr'] or 0):.1%} PF={(st['pf'] or 0):.2f} "
        f"E={st['E']:+.3f} DD={st.get('max_dd', 0):.2f} "
        f"t/wk={st.get('trades_per_week', 0):.1f}"
    )


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    print("=== DATA INVENTORY ===", flush=True)
    inv = inventory()

    pine = pine_boolean_map()
    funnel = pine_rejection_funnel("NQ")
    # multi-symbol funnel totals on 1m
    funnel_all = []
    for sym in ("NQ", "ES", "MNQ", "MES"):
        f = pine_rejection_funnel(sym)
        funnel_all.append(f)

    print("=== BUILD BOOKS ===", flush=True)
    # Primary research: open trigger so HTF features vary
    book_1m = build_book("1m", "7d", mode="trigger", cooldown=30)
    book_5m = build_book("5m", "60d", mode="trigger", cooldown=12)
    # Continuity baseline: parity bias momentum (reproduces prior interesting set)
    book_1m_parity = build_book("1m", "7d", mode="parity_bias", cooldown=30)
    book_5m_parity = build_book("5m", "60d", mode="parity_bias", cooldown=12)

    for name, df in [
        ("momentum_1m_trigger", book_1m),
        ("momentum_5m_trigger", book_5m),
        ("momentum_1m_parity_bias", book_1m_parity),
        ("momentum_5m_parity_bias", book_5m_parity),
    ]:
        df.to_csv(OUT / f"{name}.csv", index=False)

    # Focus analysis on 5m trigger (adequate history) + report 1m parity for continuity
    primary = book_5m
    secondary = book_1m_parity

    print("=== ANALYSIS 5m trigger ===", flush=True)
    base_5m = trade_stats(primary)
    base_1m_parity = trade_stats(secondary)
    base_1m_trig = trade_stats(book_1m)
    base_5m_parity = trade_stats(book_5m_parity)

    wl = winner_loser_report(primary)
    singles = single_condition_scan(primary)
    interactions = interaction_scan(primary)
    all_cand = singles + interactions
    strong_60 = [c for c in all_cand if c.get("n", 0) >= 30 and (c.get("wr") or 0) >= 0.60]
    strong_65 = [c for c in all_cand if c.get("n", 0) >= 30 and (c.get("wr") or 0) >= 0.65]
    strong_70 = [c for c in all_cand if c.get("n", 0) >= 30 and (c.get("wr") or 0) >= 0.70]
    strong_75 = [c for c in all_cand if c.get("n", 0) >= 30 and (c.get("wr") or 0) >= 0.75]
    strong_60 = sorted(strong_60, key=lambda x: (-(x.get("wr") or 0), -(x.get("E") or 0)))
    frontier = pareto_frontier(all_cand, {"conditions": "BASE", **base_5m})

    # specialization
    special = {}
    for family, members in {
        "NQ": ["NQ", "MNQ"],
        "ES": ["ES", "MES"],
        "GC": ["GC", "MGC"],
        "CL": ["CL", "MCL"],
    }.items():
        sub = primary[primary["symbol"].isin(members)]
        fam_conds = [
            ("1H+15m", lambda d: d["agree_1h_15m"] == 1),
            ("1H+15m+VWAP", lambda d: (d["agree_1h_15m"] == 1) & (d["vwap_side_ok"] == 1)),
            ("pullback+1H15m", lambda d: (d["pullback_recent"] == 1) & (d["agree_1h_15m"] == 1)),
            ("VWAP proximal", lambda d: (d["vwap_side_ok"] == 1) & (d["abs_dist_vwap_atr"] <= 0.6)),
            ("breakout+1H15m", lambda d: (d["breakout"] == 1) & (d["agree_1h_15m"] == 1)),
            ("rel_vol>1.15+1H15m", lambda d: (d["rel_volume"] > 1.15) & (d["agree_1h_15m"] == 1)),
        ]
        top = []
        if len(sub) >= 10:
            top = sorted(
                [conditional_table(sub, fn(sub), name) for name, fn in fam_conds],
                key=lambda x: (-(x.get("wr") or 0), -(x.get("n") or 0)),
            )[:8]
        special[family] = {"baseline": trade_stats(sub), "top_conditions": top}

    sessions = {}
    for sess in sorted(primary["session"].dropna().unique()):
        sessions[sess] = trade_stats(primary[primary["session"] == sess])

    tree = shallow_tree(primary)

    # OOS on top promising rules from train-discover on full then eval splits
    # Discover on TRAIN only
    d_sorted = primary.sort_values("timestamp")
    n = len(d_sorted)
    i1 = int(n * 0.60)
    train_df = d_sorted.iloc[:i1]
    train_singles = single_condition_scan(train_df)
    train_ix = interaction_scan(train_df)
    train_best = sorted(
        [c for c in train_singles + train_ix if c.get("n", 0) >= 30 and (c.get("wr") or 0) >= 0.62],
        key=lambda x: (-(x.get("wr") or 0), -(x.get("E") or 0)),
    )[:8]
    # map names back to INTERACTIONS + built-ins
    name_to_fn = {name: fn for name, fn in INTERACTIONS}
    name_to_fn.update({
        "1H+15m agree": lambda d: d["agree_1h_15m"] == 1,
        "1H+15m+5m agree": lambda d: d["agree_1h_15m_5m"] == 1,
        "4H+1H agree": lambda d: d["agree_4h_1h"] == 1,
        "all 4 TF agree": lambda d: d["agree_all4"] == 1,
        "VWAP side OK": lambda d: d["vwap_side_ok"] == 1,
        "pullback before": lambda d: d["pullback_recent"] == 1,
        "rel_vol>1.15": lambda d: d["rel_volume"] > 1.15,
        "not overextended": lambda d: d["overextended"] == 0,
        "|VWAP|<=0.25ATR": lambda d: d["abs_dist_vwap_atr"] <= 0.25,
        "|VWAP| 0.25-0.75ATR": lambda d: (d["abs_dist_vwap_atr"] > 0.25) & (d["abs_dist_vwap_atr"] <= 0.75),
    })
    oos_results = []
    for tb in train_best:
        nm = tb["conditions"]
        fn = name_to_fn.get(nm)
        if fn is None:
            continue
        oos_results.append(oos_eval(primary, fn, nm))

    # multi-R summary
    multi_r = {}
    for r in R_TARGETS:
        col = f"win_{r}R"
        if col in primary.columns:
            multi_r[f"{r}R"] = {
                "wr": float(primary[col].mean()),
                "n": int(len(primary)),
            }

    # strongest predictors by WR lift among n>=30
    predictors = sorted(
        [c for c in singles if c.get("n", 0) >= 30 and c["conditions"] != "BASE"],
        key=lambda x: (-(x.get("wr") or 0), -(x.get("E") or 0)),
    )[:15]

    paper_support = {
        "change_active_paper": False,
        "reason": (
            "Diagnostic only. Promote only if a rule shows stable TRAIN/VAL/FINAL "
            "with acceptable frequency; this pass does not modify paper."
        ),
        "interesting": bool(any(o.get("stable") for o in oos_results)),
        "stable_rules": [o["name"] for o in oos_results if o.get("stable")],
    }

    report = {
        "generated": datetime.now(timezone.utc).isoformat(),
        "A_inventory_rows": int(len(inv)),
        "B_1m_parity_bias_baseline": base_1m_parity,
        "B2_1m_trigger_baseline": base_1m_trig,
        "C_5m_trigger_baseline": base_5m,
        "C2_5m_parity_bias_baseline": base_5m_parity,
        "D_winner_loser": wl,
        "E_strongest_single": predictors,
        "F_G_H_interactions": sorted(interactions, key=lambda x: (-(x.get("wr") or 0), -(x.get("n") or 0))),
        "I_wr_ge_65": strong_65,
        "J_wr_ge_70": strong_70,
        "J2_wr_ge_75": strong_75,
        "I0_wr_ge_60_n30": strong_60[:40],
        "K_pareto": frontier,
        "L_NQ": special.get("NQ"),
        "M_ES": special.get("ES"),
        "N_GC": special.get("GC"),
        "O_CL": special.get("CL"),
        "P_sessions": sessions,
        "Q_tree": tree,
        "R_oos": oos_results,
        "S_pine_boolean": pine,
        "T_funnel": {"NQ": funnel, "all": funnel_all},
        "U_paper": paper_support,
        "multi_R_5m_trigger": multi_r,
        "note_signal_defs": {
            "trigger": "mom candle only (close>open & close>prior high) — HTF are features",
            "parity_bias": "strict all3 HTF + VWAP + mom candle (prior momentum_entry definition)",
        },
    }
    (OUT / "MOMENTUM_DEEP_REPORT.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")

    # Markdown A–U
    lines = [
        "# Momentum Deep Diagnostic Report",
        "",
        f"Generated: {report['generated']}",
        "",
        "**Paper agent: NOT modified.** Research/diagnostic only.",
        "",
        "## A. Historical data inventory",
        "",
        "See `data/momentum_deep/DATA_INVENTORY.md`.",
        f"Inventory rows: {len(inv)}. No local 1m warehouse; Yahoo native max: 1m≈7d, 5m/15m≈60d, 1h/4h≈2y.",
        "",
        "## B. 1m momentum baselines",
        "",
        f"- **parity_bias** (prior definition): {fmt_st(base_1m_parity)}",
        f"- **trigger** (open HTF features): {fmt_st(base_1m_trig)}",
        "",
        "## C. 5m momentum baselines",
        "",
        f"- **trigger** (primary research book): {fmt_st(base_5m)}",
        f"- **parity_bias**: {fmt_st(base_5m_parity)}",
        "",
        "### Multi-R hit rates (5m trigger, before -1R)",
        "",
    ]
    for k, v in multi_r.items():
        lines.append(f"- {k}: WR={v['wr']:.1%} (n={v['n']})")

    lines += ["", "## D. Winner vs loser feature analysis (5m trigger)", ""]
    lines.append(f"Wins={wl.get('n_win')} Losses={wl.get('n_loss')}")
    for feat, stats in (wl.get("features") or {}).items():
        lines.append(f"- **{feat}**: {stats}")

    lines += ["", "## E. Strongest individual predictors (n≥30)", ""]
    lines.append("| conditions | n | label | WR | PF | E | t/wk | retained |")
    lines.append("|---|---:|---|---:|---:|---:|---:|---:|")
    for c in predictors:
        lines.append(
            f"| {c['conditions']} | {c['n']} | {sample_label(c['n'])} | {(c['wr'] or 0):.1%} | "
            f"{(c['pf'] or 0):.2f} | {(c['E'] or 0):+.3f} | {c.get('trades_per_week', 0):.1f} | "
            f"{c.get('pct_retained', 0):.0%} |"
        )

    lines += ["", "## F–H. Interactions (2–4 vars, rationale-limited)", ""]
    lines.append("| conditions | n | WR | PF | E | t/wk | retained |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|")
    for c in sorted(interactions, key=lambda x: (-(x.get("wr") or 0), -(x.get("n") or 0))):
        if c.get("n", 0) < 10:
            continue
        lines.append(
            f"| {c['conditions']} | {c['n']} | {(c['wr'] or 0):.1%} | {(c['pf'] or 0):.2f} | "
            f"{(c['E'] or 0):+.3f} | {c.get('trades_per_week', 0):.1f} | {c.get('pct_retained', 0):.0%} |"
        )

    lines += ["", "## I. Conditional WR ≥ 65% (n≥30)", ""]
    if not strong_65:
        lines.append("_None with n≥30._")
    for c in strong_65:
        hl = ""
        if (c.get("wr") or 0) >= 0.75:
            hl = " **≥75%**"
        elif (c.get("wr") or 0) >= 0.70:
            hl = " **≥70%**"
        elif (c.get("wr") or 0) >= 0.65:
            hl = " **≥65%**"
        lines.append(f"- {c['conditions']}: {fmt_st(c)} retained={c.get('pct_retained', 0):.0%}{hl}")

    lines += ["", "## J. Conditional WR ≥ 70% (n≥30)", ""]
    if not strong_70:
        lines.append("_None with n≥30._")
    for c in strong_70:
        lines.append(f"- {c['conditions']}: {fmt_st(c)} retained={c.get('pct_retained', 0):.0%}")

    lines += ["", "## K. WR / frequency Pareto frontier (5m trigger)", ""]
    lines.append("| conditions | n | WR | E | t/wk | retained |")
    lines.append("|---|---:|---:|---:|---:|---:|")
    for c in frontier:
        lines.append(
            f"| {c.get('conditions')} | {c.get('n')} | {(c.get('wr') or 0):.1%} | "
            f"{(c.get('E') or 0):+.3f} | {c.get('trades_per_week', 0):.1f} | "
            f"{c.get('pct_retained', 1.0):.0%} |"
        )

    for letter, key, title in [
        ("L", "NQ", "NQ specialization"),
        ("M", "ES", "ES specialization"),
        ("N", "GC", "GC specialization"),
        ("O", "CL", "CL specialization"),
    ]:
        lines += ["", f"## {letter}. {title}", ""]
        block = special.get(key) or {}
        lines.append(f"Baseline: {fmt_st(block.get('baseline') or {})}")
        for c in block.get("top_conditions") or []:
            lines.append(f"- {c.get('conditions')}: {fmt_st(c)}")

    lines += ["", "## P. Session specialization (5m trigger)", ""]
    for sess, st in sessions.items():
        lines.append(f"- **{sess}**: {fmt_st(st)}")

    lines += ["", "## Q. Shallow tree (depth≤3, research only)", ""]
    if tree.get("error"):
        lines.append(str(tree))
    else:
        lines.append(f"Train accuracy: {tree.get('train_accuracy'):.3f}")
        lines.append(f"Importances: {tree.get('feature_importances')}")
        lines.append("```")
        lines.append(tree.get("tree_text") or "")
        lines.append("```")

    lines += ["", "## R. Untouched OOS (rules frozen from TRAIN discovery)", ""]
    for o in oos_results:
        lines.append(f"### {o.get('name')}")
        if o.get("error"):
            lines.append(str(o))
            continue
        for split, st in (o.get("splits") or {}).items():
            lines.append(f"- {split}: {fmt_st(st)} retained={st.get('pct_retained', 0):.0%}")
        lines.append(f"- overfit_flag={o.get('overfit_flag')} stable={o.get('stable')}")

    lines += ["", "## S. Exact Pine BUY/SELL Boolean dependency map", ""]
    lines.append(f"- BUY NOW = `{pine['BUY_NOW']}`")
    lines.append(f"- SELL NOW = `{pine['SELL_NOW']}`")
    lines.append(f"- longBias = `{pine['longBias']}`")
    lines.append(f"- longSetup = `{pine['longSetup']}`")
    lines.append("Mandatory for BUY NOW:")
    for m in pine["mandatory_for_BUY_NOW"]:
        lines.append(f"- {m}")
    lines.append(f"- Confidence/EMA stack required for BUY NOW? **No** (display only).")

    lines += ["", "## T. Why indicator_parity had ~5 signals on 1m/7d", ""]
    lines.append(json.dumps(funnel, indent=2))
    lines.append("")
    lines.append(str(funnel.get("why_n_collapsed", "")))
    lines.append("")
    for f in funnel_all:
        lines.append(
            f"- {f.get('symbol')}: candidates≈{f.get('candidate_bars_after_warmup')} "
            f"HTF+VWAP long={f.get('long_htf_and_vwap')} "
            f"BUY_NOW={f.get('final_BUY_NOW')} SELL_NOW={f.get('final_SELL_NOW')}"
        )

    lines += ["", "## U. Evidence for paper strategy change?", ""]
    lines.append(json.dumps(paper_support, indent=2))
    lines += [
        "",
        "## Notes",
        "- Active paper agent untouched.",
        "- 5m trigger is the primary discovery book (60d history, HTF as features).",
        "- 1m parity_bias book reproduces the earlier ~60%+ momentum-style definition on short history.",
        "",
    ]
    (OUT / "MOMENTUM_DEEP_REPORT.md").write_text("\n".join(lines), encoding="utf-8")
    print("Report:", OUT / "MOMENTUM_DEEP_REPORT.md", flush=True)
    print(
        json.dumps(
            {
                "1m_parity": base_1m_parity,
                "5m_trigger": base_5m,
                "n65": len(strong_65),
                "n70": len(strong_70),
                "stable_oos": paper_support["stable_rules"],
            },
            indent=2,
            default=str,
        ),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
