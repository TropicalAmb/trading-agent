"""Supply/demand + price-action research pass (Yahoo 5m, R-space, frozen splits).

Does not modify paper config. Honest READY / WATCH / FAIL verdict vs research gates.
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable

import pandas as pd

from agent.research.features_ict import atr
from agent.research.harness.datasets import (
    SplitSpec,
    assign_period,
    fetch_yahoo,
    freeze_splits,
    save_split_lock,
)
from agent.research.harness.metrics import GATES, meets_gates, trade_stats
from agent.research.hc_strategies import (
    RTrade,
    _exit_r,
    _friction,
    _regime_label,
    _session_label,
)

# Full-size Yahoo continuous; micros share the same underlying path for this screen.
SYMBOLS_5M = {
    "NQ": "NQ=F",
    "ES": "ES=F",
    "GC": "GC=F",
    "CL": "CL=F",
}

FRICTION_NOTE = (
    "Friction: 2 ticks slip + 1 tick buffer per side; fixed-R targets; "
    "no lookahead on entry bar; 60/20/20 chronological freeze before selection."
)


def gen_supply_demand_v2(
    df: pd.DataFrame,
    symbol: str,
    *,
    target_r: float,
    impulse_atr: float = 1.2,
    base_bars: int = 6,
    return_bars: int = 16,
    allow_all_sessions: bool = True,
) -> list[RTrade]:
    """Base consolidation → impulse departure → return to zone → confirmation candle."""
    if len(df) < 100:
        return []
    a = atr(df)
    fr = _friction(symbol)
    out: list[RTrade] = []
    i = 50
    while i < len(df) - 15:
        ts = df.index[i]
        if not allow_all_sessions and not (9 <= ts.hour < 16):
            i += 1
            continue
        av = float(a.iloc[i] or 0)
        if av <= 0:
            i += 1
            continue
        base = df.iloc[i - base_bars : i - 2]
        impulse = df.iloc[i - 2 : i + 1]
        base_hi, base_lo = float(base["high"].max()), float(base["low"].min())
        base_w = base_hi - base_lo
        if base_w <= 0 or base_w > 1.8 * av:
            i += 1
            continue
        imp_move = float(impulse["close"].iloc[-1] - impulse["close"].iloc[0])
        if abs(imp_move) < impulse_atr * av:
            i += 1
            continue
        side = "BUY" if imp_move > 0 else "SELL"
        entered = False
        for j in range(i + 1, min(len(df) - 6, i + return_bars)):
            cj = float(df["close"].iloc[j])
            oj = float(df["open"].iloc[j])
            lj = float(df["low"].iloc[j])
            hj = float(df["high"].iloc[j])
            if side == "BUY" and lj <= base_hi and cj >= base_lo and cj > oj:
                stop = base_lo - 0.3 * av
            elif side == "SELL" and hj >= base_lo and cj <= base_hi and cj < oj:
                stop = base_hi + 0.3 * av
            else:
                continue
            entry = cj
            risk = abs(entry - stop)
            if risk <= 1e-9 or risk > 2.5 * av:
                continue
            tgt = entry + risk * target_r if side == "BUY" else entry - risk * target_r
            pnl = _exit_r(df, j, side, entry, stop, tgt, fr)
            out.append(
                RTrade(
                    symbol=symbol,
                    strategy=f"SupplyDemand_v2_R{target_r}_imp{impulse_atr}",
                    family="supply_demand",
                    side=side,
                    entry_ts=str(df.index[j]),
                    pnl_r=pnl,
                    session=_session_label(df.index[j]),
                    regime=_regime_label(df, j, a),
                    confirmation="zone_retest",
                    exit_style=f"{target_r}R",
                    target_r=target_r,
                )
            )
            entered = True
            i = j + 12
            break
        if not entered:
            i += 1
    return out


def gen_price_action_sweep_reclaim(
    df: pd.DataFrame,
    symbol: str,
    *,
    target_r: float,
    lookback: int = 12,
    displace_atr: float = 0.8,
    allow_all_sessions: bool = True,
) -> list[RTrade]:
    """Sweep prior swing high/low + displacement + reclaim/reject (PA, not chase breakout)."""
    if len(df) < 80:
        return []
    a = atr(df)
    fr = _friction(symbol)
    out: list[RTrade] = []
    i = 40
    while i < len(df) - 12:
        ts = df.index[i]
        if not allow_all_sessions and not (9 <= ts.hour < 16):
            i += 1
            continue
        av = float(a.iloc[i] or 0)
        if av <= 0:
            i += 1
            continue
        look = df.iloc[i - lookback : i]
        level_hi = float(look["high"].max())
        level_lo = float(look["low"].min())
        c = float(df["close"].iloc[i])
        o = float(df["open"].iloc[i])
        h = float(df["high"].iloc[i])
        l = float(df["low"].iloc[i])
        body = abs(c - o)
        # Sweep high then close back below (SELL) or sweep low then close back above (BUY)
        side = None
        level = None
        if h > level_hi and c < level_hi and c < o and body >= 0.35 * av:
            # liquidity grab above + rejection
            side, level = "SELL", level_hi
        elif l < level_lo and c > level_lo and c > o and body >= 0.35 * av:
            side, level = "BUY", level_lo
        else:
            i += 1
            continue
        # Require displacement away from level within next 2 bars (not immediate chase through)
        ok_disp = False
        for k in range(i, min(len(df) - 6, i + 3)):
            ck = float(df["close"].iloc[k])
            if side == "SELL" and (level - ck) >= displace_atr * 0.5 * av:
                ok_disp = True
                break
            if side == "BUY" and (ck - level) >= displace_atr * 0.5 * av:
                ok_disp = True
                break
        if not ok_disp:
            i += 1
            continue
        # Entry on reclaim/reject confirmation at/near level within next 6 bars
        entered = False
        for j in range(i + 1, min(len(df) - 6, i + 7)):
            cj = float(df["close"].iloc[j])
            oj = float(df["open"].iloc[j])
            lj = float(df["low"].iloc[j])
            hj = float(df["high"].iloc[j])
            if side == "BUY" and lj <= level + 0.2 * av and cj >= level and cj > oj:
                stop = min(l, level_lo) - 0.35 * av
            elif side == "SELL" and hj >= level - 0.2 * av and cj <= level and cj < oj:
                stop = max(h, level_hi) + 0.35 * av
            else:
                continue
            entry = cj
            risk = abs(entry - stop)
            if risk <= 1e-9 or risk > 2.5 * av:
                continue
            # Mild displacement filter on entry bar
            if body < 0.2 * av:
                continue
            tgt = entry + risk * target_r if side == "BUY" else entry - risk * target_r
            pnl = _exit_r(df, j, side, entry, stop, tgt, fr)
            out.append(
                RTrade(
                    symbol=symbol,
                    strategy=f"PriceAction_SweepReclaim_R{target_r}_lb{lookback}",
                    family="price_action",
                    side=side,
                    entry_ts=str(df.index[j]),
                    pnl_r=pnl,
                    session=_session_label(df.index[j]),
                    regime=_regime_label(df, j, a),
                    confirmation="sweep_reclaim",
                    exit_style=f"{target_r}R",
                    target_r=target_r,
                )
            )
            entered = True
            i = j + 10
            break
        if not entered:
            i += 1
    return out


def _stress_pnls(pnls: list[float], slip_r: float = 0.08) -> list[float]:
    return [float(x) - slip_r for x in pnls]


def _cell_key(t: RTrade) -> str:
    return f"{t.family}|{t.strategy}|{t.symbol}|{t.session}|{t.side}"


def _stats_from_trades(trades: list[RTrade]) -> dict[str, Any]:
    return trade_stats(
        [t.pnl_r for t in trades],
        [t.entry_ts for t in trades],
    )


def _walk_forward_folds(trades: list[RTrade], n_folds: int = 4) -> list[dict[str, Any]]:
    if len(trades) < n_folds * 8:
        return []
    ordered = sorted(trades, key=lambda t: t.entry_ts)
    folds: list[dict[str, Any]] = []
    chunk = max(len(ordered) // n_folds, 1)
    for f in range(n_folds):
        part = ordered[f * chunk : (f + 1) * chunk if f < n_folds - 1 else len(ordered)]
        if len(part) < 5:
            continue
        st = _stats_from_trades(part)
        folds.append({"fold": f + 1, "n": st["n"], "wr": st["wr"], "expectancy_r": st["expectancy_r"], "pf": st["pf"]})
    return folds


def build_param_grid() -> list[tuple[str, str, Callable[..., list[RTrade]], dict[str, Any]]]:
    """family, strategy_id, generator, kwargs."""
    grid: list[tuple[str, str, Callable[..., list[RTrade]], dict[str, Any]]] = []
    for tr in (1.5, 1.6, 2.0):
        for imp in (1.2, 1.5):
            grid.append(
                (
                    "supply_demand",
                    f"sd_v2_R{tr}_imp{imp}",
                    gen_supply_demand_v2,
                    {"target_r": tr, "impulse_atr": imp, "allow_all_sessions": True},
                )
            )
        for lb in (12, 20):
            grid.append(
                (
                    "price_action",
                    f"pa_sweep_R{tr}_lb{lb}",
                    gen_price_action_sweep_reclaim,
                    {"target_r": tr, "lookback": lb, "allow_all_sessions": True},
                )
            )
    return grid


def run_sd_pa_research(out_dir: Path) -> dict[str, Any]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    frames: dict[str, pd.DataFrame] = {}
    splits: dict[str, SplitSpec] = {}
    print("Loading Yahoo 5m (60d)...", flush=True)
    for name, ysym in SYMBOLS_5M.items():
        df = fetch_yahoo(ysym, "5m", "60d")
        frames[name] = df
        print(f"  {name}: {len(df)} bars", flush=True)
        if len(df) >= 80:
            splits[name] = freeze_splits(df)
    lock = {
        "frozen_at_rule": "60/20/20 chronological by trading day",
        "splits_5m": {k: asdict(v) for k, v in splits.items()},
        "friction": FRICTION_NOTE,
        "gates": GATES,
        "symbols": SYMBOLS_5M,
    }
    save_split_lock(out_dir / "split_lock.json", lock)

    grid = build_param_grid()
    print(f"Param grid: {len(grid)} configs", flush=True)

    # Aggregate trades per config across symbols
    all_rows: list[dict[str, Any]] = []
    by_config: dict[str, list[RTrade]] = defaultdict(list)
    by_config_period: dict[str, dict[str, list[RTrade]]] = defaultdict(
        lambda: {"train": [], "val": [], "final": []}
    )

    for ci, (family, sid, gen, kwargs) in enumerate(grid, 1):
        n_cfg = 0
        for sym, df in frames.items():
            if sym not in splits or df.empty:
                continue
            trades = gen(df, sym, **kwargs)
            split = splits[sym]
            for t in trades:
                period = assign_period(t.entry_ts, split)
                by_config[sid].append(t)
                by_config_period[sid][period].append(t)
                all_rows.append(
                    {
                        "family": family,
                        "strategy_id": sid,
                        "symbol": t.symbol,
                        "side": t.side,
                        "session": t.session,
                        "regime": t.regime,
                        "entry_ts": t.entry_ts,
                        "pnl_r": t.pnl_r,
                        "target_r": t.target_r,
                        "period": period,
                        "strategy": t.strategy,
                    }
                )
                n_cfg += 1
        print(f"  [{ci}/{len(grid)}] {sid}: {n_cfg} trades", flush=True)

    # Score configs on train, pick best per family, evaluate val/final
    family_best: dict[str, dict[str, Any]] = {}
    config_scores: list[dict[str, Any]] = []
    for family, sid, _, kwargs in grid:
        train = by_config_period[sid]["train"]
        val = by_config_period[sid]["val"]
        final = by_config_period[sid]["final"]
        all_t = by_config[sid]
        st_train = _stats_from_trades(train)
        st_val = _stats_from_trades(val)
        st_final = _stats_from_trades(final)
        st_all = _stats_from_trades(all_t)
        st_stress = trade_stats(_stress_pnls([t.pnl_r for t in all_t]), [t.entry_ts for t in all_t])
        folds = _walk_forward_folds(all_t)
        score = {
            "family": family,
            "strategy_id": sid,
            "params": kwargs,
            "train": st_train,
            "val": st_val,
            "final": st_final,
            "all": st_all,
            "stress": st_stress,
            "folds": folds,
            "meets_hard_gates_final": meets_gates(st_final),
            "meets_hard_gates_all": meets_gates(st_all),
            "meets_hard_gates_val": meets_gates(st_val),
        }
        config_scores.append(score)
        prev = family_best.get(family)
        # Select on train expectancy with n floor, break ties by WR
        rank = (st_train["n"] >= 20, st_train["expectancy_r"], st_train["wr"], st_train["n"])
        if prev is None or rank > (
            prev["train"]["n"] >= 20,
            prev["train"]["expectancy_r"],
            prev["train"]["wr"],
            prev["train"]["n"],
        ):
            family_best[family] = score

    # Session / symbol cells for best configs
    cell_report: list[dict[str, Any]] = []
    for fam, best in family_best.items():
        sid = best["strategy_id"]
        cells: dict[str, list[RTrade]] = defaultdict(list)
        for t in by_config[sid]:
            cells[f"{t.symbol}|{t.session}|{t.side}"].append(t)
            cells[f"{t.symbol}|ALL|{t.side}"].append(t)
            cells[f"ALL|{t.session}|{t.side}"].append(t)
        for key, trs in sorted(cells.items(), key=lambda kv: -len(kv[1])):
            st = _stats_from_trades(trs)
            if st["n"] < 15:
                continue
            cell_report.append(
                {
                    "family": fam,
                    "strategy_id": sid,
                    "cell": key,
                    **st,
                    "meets_hard_gates": meets_gates(st),
                }
            )

    ready_cells = [c for c in cell_report if c.get("meets_hard_gates")]
    ready_configs = [
        s
        for s in family_best.values()
        if s.get("meets_hard_gates_final") or s.get("meets_hard_gates_val")
    ]

    # Soft holdout bar used in NQ WR65 (n>=40, wr>=65, E>0)
    soft_ready = []
    for s in family_best.values():
        fin = s["final"]
        if (
            fin["n"] >= 40
            and fin["wr"] >= 0.65
            and fin["expectancy_r"] > 0
            and fin["pf"] >= 1.5
            and fin.get("anti_cheat_ok", False)
        ):
            soft_ready.append(s)

    if ready_configs or soft_ready or ready_cells:
        # Prefer hard gates; soft holdout still WATCH not auto-paper
        if ready_configs or ready_cells:
            verdict = "READY"
            note = "At least one config/cell meets hard research gates (WR≥65, n≥100, PF, E)."
        else:
            verdict = "WATCH"
            note = "Holdout soft bar (n≥40 WR≥65 E>0) met but hard n≥100 not cleared — do not auto-paper."
    else:
        # Any positive expectancy with n>=30?
        watch = [
            s
            for s in family_best.values()
            if s["final"]["n"] >= 30 and s["final"]["expectancy_r"] > 0 and s["final"]["pf"] >= 1.2
        ]
        if watch:
            verdict = "WATCH"
            note = "Positive expectancy OOS cells exist but WR/n gates failed — leave specialists-only."
        else:
            verdict = "FAIL"
            note = "No supply_demand or price_action config cleared promotion gates."

    summary = {
        "verdict": verdict,
        "note": note,
        "gates": GATES,
        "friction": FRICTION_NOTE,
        "n_trades_total": len(all_rows),
        "n_configs": len(grid),
        "family_best": family_best,
        "ready_cells": ready_cells[:40],
        "soft_ready": soft_ready,
        "top_cells": sorted(cell_report, key=lambda c: (-c["wr"], -c["n"]))[:40],
        "config_scores_top": sorted(
            config_scores,
            key=lambda s: (-s["final"]["expectancy_r"], -s["final"]["wr"], -s["final"]["n"]),
        )[:30],
    }

    (out_dir / "sd_pa_research.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    (out_dir / "sd_pa_trades.jsonl").write_text(
        "\n".join(json.dumps(r) for r in all_rows) + ("\n" if all_rows else ""),
        encoding="utf-8",
    )
    write_sd_pa_report(summary, out_dir / "SD_PA_RESEARCH_REPORT.md")
    return summary


def write_sd_pa_report(summary: dict[str, Any], path: Path) -> None:
    lines: list[str] = []
    lines.append("# Supply/Demand + Price Action Research Report")
    lines.append("")
    lines.append(f"**Verdict:** `{summary['verdict']}`")
    lines.append("")
    lines.append(summary.get("note") or "")
    lines.append("")
    lines.append("## Gates")
    lines.append("```")
    lines.append(json.dumps(summary.get("gates") or {}, indent=2))
    lines.append("```")
    lines.append("")
    lines.append(f"Friction: {summary.get('friction')}")
    lines.append(f"Total trades generated: {summary.get('n_trades_total')}")
    lines.append(f"Configs tried: {summary.get('n_configs')}")
    lines.append("")
    lines.append("## Best config per family (selected on TRAIN expectancy)")
    for fam, best in (summary.get("family_best") or {}).items():
        lines.append(f"### {fam} — `{best.get('strategy_id')}`")
        lines.append(f"Params: `{best.get('params')}`")
        for period in ("train", "val", "final", "all", "stress"):
            st = best.get(period) or {}
            lines.append(
                f"- **{period}**: n={st.get('n')} WR={st.get('wr')} PF={st.get('pf')} "
                f"E={st.get('expectancy_r')} DD={st.get('max_dd_r')} "
                f"gates_ok={meets_gates(st) if st else False}"
            )
        folds = best.get("folds") or []
        if folds:
            lines.append("- folds: " + ", ".join(
                f"f{f['fold']}:n={f['n']} wr={f['wr']} E={f['expectancy_r']}" for f in folds
            ))
        lines.append("")
    lines.append("## Top cells by WR (n≥15)")
    lines.append("| family | strategy | cell | n | WR | PF | E | gates |")
    lines.append("|---|---|---|---:|---:|---:|---:|---|")
    for c in summary.get("top_cells") or []:
        lines.append(
            f"| {c.get('family')} | `{c.get('strategy_id')}` | {c.get('cell')} | "
            f"{c.get('n')} | {c.get('wr')} | {c.get('pf')} | {c.get('expectancy_r')} | "
            f"{c.get('meets_hard_gates')} |"
        )
    lines.append("")
    lines.append("## Promotion rule")
    lines.append(
        "- **READY** → may wire one locked paper engine (manual). "
        "- **WATCH/FAIL** → keep `router_v1_specialists_only`; do not re-enable location spray."
    )
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
