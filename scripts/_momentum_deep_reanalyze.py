"""Re-analyze saved momentum CSVs; rewrite report sections for parity_bias primary."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from agent.research.momentum_deep import sample_label, trade_stats, conditional_table  # noqa: E402
from run_momentum_deep_pass import (  # noqa: E402
    INTERACTIONS,
    fmt_st,
    interaction_scan,
    oos_eval,
    pareto_frontier,
    shallow_tree,
    single_condition_scan,
    winner_loser_report,
)

OUT = ROOT / "data" / "momentum_deep"


def main() -> int:
    b5p = pd.read_csv(OUT / "momentum_5m_parity_bias.csv")
    b1p = pd.read_csv(OUT / "momentum_1m_parity_bias.csv")
    b5t = pd.read_csv(OUT / "momentum_5m_trigger.csv")
    b1t = pd.read_csv(OUT / "momentum_1m_trigger.csv")

    # Primary: 5m parity_bias (same logic as prior interesting momentum_entry)
    primary = b5p
    base = trade_stats(primary)
    singles = single_condition_scan(primary)
    interactions = interaction_scan(primary)
    allc = singles + interactions
    s60 = sorted(
        [c for c in allc if c.get("n", 0) >= 30 and (c.get("wr") or 0) >= 0.60],
        key=lambda x: (-(x.get("wr") or 0), -(x.get("E") or 0)),
    )
    s65 = [c for c in s60 if (c.get("wr") or 0) >= 0.65]
    s70 = [c for c in s60 if (c.get("wr") or 0) >= 0.70]
    s75 = [c for c in s60 if (c.get("wr") or 0) >= 0.75]
    frontier = pareto_frontier(allc, {"conditions": "BASE", **base})
    wl = winner_loser_report(primary)
    predictors = sorted(
        [c for c in singles if c.get("n", 0) >= 30 and c["conditions"] != "BASE"],
        key=lambda x: (-(x.get("wr") or 0), -(x.get("E") or 0)),
    )[:20]

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
            ("not OE + 1H15m + VWAP", lambda d: (d["overextended"] == 0) & (d["agree_1h_15m"] == 1) & (d["vwap_side_ok"] == 1)),
            ("|VWAP|<=0.25", lambda d: d["abs_dist_vwap_atr"] <= 0.25),
            ("session ny_open", lambda d: d["session"] == "ny_open"),
        ]
        top = []
        if len(sub) >= 10:
            scanned = single_condition_scan(sub) + interaction_scan(sub)
            top = sorted(
                [c for c in scanned if c.get("n", 0) >= 20],
                key=lambda x: (-(x.get("wr") or 0), -(x.get("n") or 0)),
            )[:10]
        special[family] = {"baseline": trade_stats(sub), "top_conditions": top}

    sessions = {
        sess: trade_stats(primary[primary["session"] == sess])
        for sess in sorted(primary["session"].dropna().unique())
    }
    tree = shallow_tree(primary)

    d_sorted = primary.sort_values("timestamp")
    i1 = int(len(d_sorted) * 0.60)
    train_df = d_sorted.iloc[:i1]
    train_best = sorted(
        [
            c
            for c in single_condition_scan(train_df) + interaction_scan(train_df)
            if c.get("n", 0) >= 30 and (c.get("wr") or 0) >= 0.60
        ],
        key=lambda x: (-(x.get("wr") or 0), -(x.get("E") or 0)),
    )[:10]
    name_to_fn = {name: fn for name, fn in INTERACTIONS}
    name_to_fn.update(
        {
            "1H+15m agree": lambda d: d["agree_1h_15m"] == 1,
            "1H+15m+5m agree": lambda d: d["agree_1h_15m_5m"] == 1,
            "4H+1H agree": lambda d: d["agree_4h_1h"] == 1,
            "all 4 TF agree": lambda d: d["agree_all4"] == 1,
            "VWAP side OK": lambda d: d["vwap_side_ok"] == 1,
            "pullback before": lambda d: d["pullback_recent"] == 1,
            "rel_vol>1.15": lambda d: d["rel_volume"] > 1.15,
            "not overextended": lambda d: d["overextended"] == 0,
            "|VWAP|<=0.25ATR": lambda d: d["abs_dist_vwap_atr"] <= 0.25,
            "|VWAP| 0.25-0.75ATR": lambda d: (d["abs_dist_vwap_atr"] > 0.25)
            & (d["abs_dist_vwap_atr"] <= 0.75),
            "|VWAP|>0.75ATR": lambda d: d["abs_dist_vwap_atr"] > 0.75,
            "4H agrees": lambda d: d["agree_4h"] == 1,
            "5m agrees": lambda d: d["agree_5m"] == 1,
            "ema aligned": lambda d: d["ema_aligned"] == 1,
            "breakout": lambda d: d["breakout"] == 1,
            "retest": lambda d: d["retest"] == 1,
        }
    )
    oos_results = []
    for tb in train_best:
        fn = name_to_fn.get(tb["conditions"])
        if fn is None:
            continue
        oos_results.append(oos_eval(primary, fn, tb["conditions"]))

    multi_r = {f"{r}R": {"wr": float(primary[f"win_{r}R"].mean()), "n": int(len(primary))} for r in (1.0, 1.25, 1.5, 2.0)}
    mfe = {
        "mfe_winner_mean": float(primary.loc[primary.win == 1, "mfe_r"].mean()),
        "mfe_loser_mean": float(primary.loc[primary.win == 0, "mfe_r"].mean()),
        "mae_winner_mean": float(primary.loc[primary.win == 1, "mae_r"].mean()),
        "mae_loser_mean": float(primary.loc[primary.win == 0, "mae_r"].mean()),
    }

    # load prior pine funnel from existing json if present
    prev = {}
    prev_path = OUT / "MOMENTUM_DEEP_REPORT.json"
    if prev_path.exists():
        prev = json.loads(prev_path.read_text(encoding="utf-8"))

    paper = {
        "change_active_paper": False,
        "reason": "Diagnostic pass only; require stable OOS before any paper change.",
        "interesting": bool(any(o.get("stable") for o in oos_results)),
        "stable_rules": [o["name"] for o in oos_results if o.get("stable")],
    }

    report = {
        "generated": datetime.now(timezone.utc).isoformat(),
        "primary_book": "momentum_5m_parity_bias",
        "B_1m_parity_bias_baseline": trade_stats(b1p),
        "B2_1m_trigger_baseline": trade_stats(b1t),
        "C_5m_trigger_baseline": trade_stats(b5t),
        "C2_5m_parity_bias_baseline": base,
        "D_winner_loser": wl,
        "D2_mfe_mae": mfe,
        "E_strongest_single": predictors,
        "F_G_H_interactions": sorted(interactions, key=lambda x: (-(x.get("wr") or 0), -(x.get("n") or 0))),
        "I_wr_ge_65": s65,
        "J_wr_ge_70": s70,
        "J2_wr_ge_75": s75,
        "I0_wr_ge_60_n30": s60[:40],
        "K_pareto": frontier,
        "L_NQ": special["NQ"],
        "M_ES": special["ES"],
        "N_GC": special["GC"],
        "O_CL": special["CL"],
        "P_sessions": sessions,
        "Q_tree": tree,
        "R_oos": oos_results,
        "S_pine_boolean": prev.get("S_pine_boolean"),
        "T_funnel": prev.get("T_funnel"),
        "U_paper": paper,
        "multi_R": multi_r,
    }
    (OUT / "MOMENTUM_DEEP_REPORT.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")

    pine = report["S_pine_boolean"] or {}
    funnel = (report["T_funnel"] or {}).get("NQ") or {}

    lines = [
        "# Momentum Deep Diagnostic Report",
        "",
        f"Generated: {report['generated']}",
        "",
        "**Paper agent: NOT modified.**",
        "",
        "Primary discovery book: **5m parity_bias momentum** = strict 15m+1h+4h+VWAP bias + momentum confirmation candle (same construction as prior interesting momentum-only result). HTF agreement features still recorded; within this book 15m/1h/4h already agree by definition — **5m agreement and non-HTF features** are the discriminators.",
        "",
        "Open **trigger** book (no HTF gate) is reported for contrast; it is too loose alone (see C).",
        "",
        "## A. Historical data inventory",
        "",
        "See `data/momentum_deep/DATA_INVENTORY.md`.",
        "No local OHLC warehouse. Yahoo max: 1m≈7d, 5m/15m≈60d, 1h/4h≈2y. 1m not fabricated.",
        "",
        "## B. 1m momentum baselines",
        "",
        f"- **parity_bias**: {fmt_st(report['B_1m_parity_bias_baseline'])}",
        f"- **trigger**: {fmt_st(report['B2_1m_trigger_baseline'])}",
        "",
        "## C. 5m momentum baselines",
        "",
        f"- **parity_bias (PRIMARY)**: {fmt_st(base)}",
        f"- **trigger (open)**: {fmt_st(report['C_5m_trigger_baseline'])}",
        "",
        "### Multi-R (5m parity_bias, target before -1R stop)",
        "",
    ]
    for k, v in multi_r.items():
        lines.append(f"- {k}: WR={v['wr']:.1%} n={v['n']}")
    lines += [
        "",
        f"- MFE mean winners/losers: {mfe['mfe_winner_mean']:.2f} / {mfe['mfe_loser_mean']:.2f}",
        f"- MAE mean winners/losers: {mfe['mae_winner_mean']:.2f} / {mfe['mae_loser_mean']:.2f}",
        "",
        "## D. Winner vs loser (5m parity_bias)",
        "",
        f"Wins={wl.get('n_win')} Losses={wl.get('n_loss')}",
    ]
    for feat, stats in (wl.get("features") or {}).items():
        lines.append(f"- **{feat}**: {stats}")

    lines += ["", "## E. Strongest individual predictors (n≥30)", "", "| conditions | n | label | WR | PF | E | t/wk | retained |", "|---|---:|---|---:|---:|---:|---:|---:|"]
    for c in predictors:
        lines.append(
            f"| {c['conditions']} | {c['n']} | {sample_label(c['n'])} | {(c['wr'] or 0):.1%} | "
            f"{(c['pf'] or 0):.2f} | {(c['E'] or 0):+.3f} | {c.get('trades_per_week', 0):.1f} | "
            f"{c.get('pct_retained', 0):.0%} |"
        )

    lines += ["", "## F–H. Interactions (rationale-limited, depth≤4)", "", "| conditions | n | WR | PF | E | t/wk | retained |", "|---|---:|---:|---:|---:|---:|---:|"]
    for c in report["F_G_H_interactions"]:
        if c.get("n", 0) < 20:
            continue
        lines.append(
            f"| {c['conditions']} | {c['n']} | {(c['wr'] or 0):.1%} | {(c['pf'] or 0):.2f} | "
            f"{(c['E'] or 0):+.3f} | {c.get('trades_per_week', 0):.1f} | {c.get('pct_retained', 0):.0%} |"
        )

    lines += ["", "## I. Conditional WR ≥ 65% (n≥30)", ""]
    if not s65:
        lines.append("_None on 5m parity_bias with n≥30._")
    for c in s65:
        mark = " **≥75%**" if (c.get("wr") or 0) >= 0.75 else (" **≥70%**" if (c.get("wr") or 0) >= 0.70 else " **≥65%**")
        lines.append(f"- {c['conditions']}: {fmt_st(c)} retained={c.get('pct_retained', 0):.0%}{mark}")

    lines += ["", "## I0. Conditional WR ≥ 60% (n≥30) — ranked", ""]
    for c in s60[:30]:
        lines.append(f"- {c['conditions']}: {fmt_st(c)} retained={c.get('pct_retained', 0):.0%}")

    lines += ["", "## J. Conditional WR ≥ 70% (n≥30)", ""]
    if not s70:
        lines.append("_None on 5m parity_bias with n≥30._")
    for c in s70:
        lines.append(f"- {c['conditions']}: {fmt_st(c)}")

    lines += ["", "## K. WR / frequency Pareto frontier", "", "| conditions | n | WR | E | t/wk | retained |", "|---|---:|---:|---:|---:|---:|"]
    for c in frontier:
        lines.append(
            f"| {c.get('conditions')} | {c.get('n')} | {(c.get('wr') or 0):.1%} | "
            f"{(c.get('E') or 0):+.3f} | {c.get('trades_per_week', 0):.1f} | {c.get('pct_retained', 1):.0%} |"
        )

    for letter, key, title in [("L", "NQ", "NQ"), ("M", "ES", "ES"), ("N", "GC", "GC"), ("O", "CL", "CL")]:
        lines += ["", f"## {letter}. {title} specialization", ""]
        block = special[key]
        lines.append(f"Baseline: {fmt_st(block['baseline'])}")
        for c in block["top_conditions"]:
            lines.append(f"- {c.get('conditions')}: {fmt_st(c)} retained={c.get('pct_retained', 0):.0%}")

    lines += ["", "## P. Session specialization", ""]
    for sess, st in sessions.items():
        lines.append(f"- **{sess}**: {fmt_st(st)}")

    lines += ["", "## Q. Shallow tree (depth≤3)", ""]
    if tree.get("error"):
        lines.append(str(tree))
    else:
        lines.append(f"Train accuracy: {tree.get('train_accuracy')}")
        lines.append(f"Importances: {tree.get('feature_importances')}")
        lines.append("```")
        lines.append(tree.get("tree_text") or "")
        lines.append("```")

    lines += ["", "## R. Untouched OOS (freeze rules from TRAIN)", ""]
    for o in oos_results:
        lines.append(f"### {o.get('name')}")
        for split, st in (o.get("splits") or {}).items():
            lines.append(f"- {split}: {fmt_st(st)} retained={st.get('pct_retained', 0):.0%}")
        lines.append(f"- overfit_flag={o.get('overfit_flag')} stable={o.get('stable')}")

    lines += ["", "## S. Exact Pine BUY/SELL Boolean map", ""]
    if pine:
        lines.append(f"- BUY NOW = `{pine.get('BUY_NOW')}`")
        lines.append(f"- SELL NOW = `{pine.get('SELL_NOW')}`")
        lines.append(f"- longBias = `{pine.get('longBias')}`")
        lines.append(f"- longSetup = `{pine.get('longSetup')}`")
        for m in pine.get("mandatory_for_BUY_NOW") or []:
            lines.append(f"- mandatory: {m}")
    else:
        lines.append("See prior JSON / Pine file.")

    lines += ["", "## T. Why exact indicator_parity n≈5 on 1m/7d", ""]
    lines.append(json.dumps(funnel, indent=2))
    lines.append(str(funnel.get("why_n_collapsed", "")))

    lines += ["", "## U. Paper strategy change?", "", json.dumps(paper, indent=2), ""]
    (OUT / "MOMENTUM_DEEP_REPORT.md").write_text("\n".join(lines), encoding="utf-8")

    print("PRIMARY 5m parity", base)
    print("n60", len(s60), "n65", len(s65), "n70", len(s70))
    print("TOP10")
    for c in s60[:10]:
        print(c["conditions"], c["n"], round(c["wr"], 3), round(c["E"], 3), round(c["pct_retained"], 3))
    print("stable", paper["stable_rules"])
    print("Report written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
