"""Simple specialists vs existing engines — OOS + missed-move coverage (research only)."""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent.research.harness.datasets import assign_period, fetch_yahoo, freeze_splits, save_split_lock
from agent.research.harness.metrics import trade_stats
from agent.research.harness.strategy_registry import gen_breakout_retest
from agent.research.hc_strategies import RTrade, gen_ema_pullback, gen_vwap_reclaim
from agent.research.missed_moves import scan_missed_moves

OUT = ROOT / "data" / "router_specialist_compare"
SYMBOLS = {
    "NQ": "NQ=F",
    "ES": "ES=F",
    "GC": "GC=F",
    "CL": "CL=F",
    "MNQ": "MNQ=F",
    "MES": "MES=F",
}


def _simple_trend_pullback(df, symbol: str, *, target_r: float = 1.5) -> list[RTrade]:
    if df is None or len(df) < 60:
        return []
    ema20 = df["close"].ewm(span=20, adjust=False).mean()
    ema50 = df["close"].ewm(span=50, adjust=False).mean()
    prev = df["close"].shift(1)
    tr = pd.concat(
        [
            (df["high"] - df["low"]).abs(),
            (df["high"] - prev).abs(),
            (df["low"] - prev).abs(),
        ],
        axis=1,
    ).max(axis=1)
    atr = tr.rolling(14).mean()
    out: list[RTrade] = []
    i = 50
    while i < len(df) - 8:
        a = float(atr.iloc[i] or 0)
        if a <= 0:
            i += 1
            continue
        e20, e50 = float(ema20.iloc[i]), float(ema50.iloc[i])
        c = float(df["close"].iloc[i])
        o = float(df["open"].iloc[i])
        h = float(df["high"].iloc[i])
        l = float(df["low"].iloc[i])
        window = df.iloc[i - 6 : i]
        side = None
        if e20 > e50 and c > e50:
            touched = bool((window["low"] <= e20 + 0.4 * a).any())
            if touched and c > e20 and c > o and l <= e20 + 0.4 * a:
                side = "BUY"
        elif e20 < e50 and c < e50:
            touched = bool((window["high"] >= e20 - 0.4 * a).any())
            if touched and c < e20 and c < o and h >= e20 - 0.4 * a:
                side = "SELL"
        if side is None:
            i += 1
            continue
        entry = c
        stop = (min(l, e20) - 0.35 * a) if side == "BUY" else (max(h, e20) + 0.35 * a)
        risk = abs(entry - stop)
        tgt = entry + risk * target_r if side == "BUY" else entry - risk * target_r
        pnl = -1.0
        for j in range(i + 1, min(i + 24, len(df))):
            hi, lo = float(df["high"].iloc[j]), float(df["low"].iloc[j])
            if side == "BUY":
                if lo <= stop:
                    pnl = -1.0
                    break
                if hi >= tgt:
                    pnl = target_r
                    break
            else:
                if hi >= stop:
                    pnl = -1.0
                    break
                if lo <= tgt:
                    pnl = target_r
                    break
        out.append(
            RTrade(
                symbol=symbol,
                strategy=f"simple_trend_pullback_R{target_r}",
                family="trend_pullback",
                side=side,
                entry_ts=str(df.index[i]),
                pnl_r=pnl,
                session=str(getattr(df.index[i], "hour", 0)),
                regime="UNK",
                confirmation="close",
                exit_style=f"{target_r}R",
                target_r=target_r,
            )
        )
        i += 12
    return out


def _simple_liquidity_reversal(df, symbol: str, *, target_r: float = 1.5) -> list[RTrade]:
    if df is None or len(df) < 40:
        return []
    prev = df["close"].shift(1)
    tr = pd.concat(
        [
            (df["high"] - df["low"]).abs(),
            (df["high"] - prev).abs(),
            (df["low"] - prev).abs(),
        ],
        axis=1,
    ).max(axis=1)
    atr = tr.rolling(14).mean()
    out: list[RTrade] = []
    i = 20
    while i < len(df) - 8:
        a = float(atr.iloc[i] or 0)
        if a <= 0:
            i += 1
            continue
        hist = df.iloc[i - 12 : i]
        swing_hi = float(hist["high"].max())
        swing_lo = float(hist["low"].min())
        c = float(df["close"].iloc[i])
        o = float(df["open"].iloc[i])
        h = float(df["high"].iloc[i])
        l = float(df["low"].iloc[i])
        side = None
        if h > swing_hi and c < swing_hi and c < o:
            side, stop = "SELL", max(h, swing_hi) + 0.3 * a
        elif l < swing_lo and c > swing_lo and c > o:
            side, stop = "BUY", min(l, swing_lo) - 0.3 * a
        else:
            i += 1
            continue
        entry = c
        risk = abs(entry - stop)
        tgt = entry + risk * target_r if side == "BUY" else entry - risk * target_r
        pnl = -1.0
        for j in range(i + 1, min(i + 24, len(df))):
            hi, lo = float(df["high"].iloc[j]), float(df["low"].iloc[j])
            if side == "BUY":
                if lo <= stop:
                    pnl = -1.0
                    break
                if hi >= tgt:
                    pnl = target_r
                    break
            else:
                if hi >= stop:
                    pnl = -1.0
                    break
                if lo <= tgt:
                    pnl = target_r
                    break
        out.append(
            RTrade(
                symbol=symbol,
                strategy=f"simple_liquidity_reversal_R{target_r}",
                family="liquidity_reversal",
                side=side,
                entry_ts=str(df.index[i]),
                pnl_r=pnl,
                session=str(getattr(df.index[i], "hour", 0)),
                regime="UNK",
                confirmation="reject",
                exit_style=f"{target_r}R",
                target_r=target_r,
            )
        )
        i += 12
    return out


def _oos_stats(trades: list[RTrade], split) -> dict:
    oos = []
    for t in trades:
        try:
            ts = pd.Timestamp(t.entry_ts)
        except Exception:
            continue
        if assign_period(ts, split) == "final":
            oos.append(float(t.pnl_r))
    st = trade_stats(oos)
    st["n_all"] = len(trades)
    st["n_oos"] = len(oos)
    return st


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    gens = [
        ("complex_ema_pullback", "existing", lambda d, s: gen_ema_pullback(d, s, target_r=1.5)),
        ("complex_breakout_retest", "existing", lambda d, s: gen_breakout_retest(d, s, target_r=1.5)),
        ("complex_vwap_reclaim_hc", "existing", lambda d, s: gen_vwap_reclaim(d, s, target_r=1.5)),
        ("simple_trend_pullback", "simple", lambda d, s: _simple_trend_pullback(d, s, target_r=1.5)),
        ("simple_liquidity_reversal", "simple", lambda d, s: _simple_liquidity_reversal(d, s, target_r=1.5)),
        ("simple_vwap_reclaim", "simple", lambda d, s: gen_vwap_reclaim(d, s, target_r=1.5, confirm="close")),
    ]

    rows: list[dict] = []
    missed_rows: list[dict] = []
    aggregate = {
        "missed_existing": 0,
        "missed_simple": 0,
        "missed_either": 0,
        "symbols": 0,
    }

    for sym, ysym in SYMBOLS.items():
        print(f"load {sym}", flush=True)
        df = fetch_yahoo(ysym, "1h", "730d")
        if df is None or df.empty or len(df) < 200:
            print(f"  skip {sym}: insufficient bars", flush=True)
            continue
        split = freeze_splits(df)
        save_split_lock(
            OUT / f"split_{sym}.json",
            {
                "symbol": sym,
                "train_end": split.train_end,
                "val_end": split.val_end,
                "final_start": split.final_start,
                "n_days_final": split.n_days_final,
            },
        )

        existing_map: dict[str, list] = defaultdict(list)
        simple_map: dict[str, list] = defaultdict(list)
        either_map: dict[str, list] = defaultdict(list)

        for name, kind, gen in gens:
            trades = gen(df, sym)
            st = _oos_stats(trades, split)
            st.update({"symbol": sym, "name": name, "kind": kind})
            rows.append(st)
            print(
                f"  {name}: OOS n={st.get('n')} WR={float(st.get('wr') or 0):.1%} "
                f"PF={float(st.get('pf') or 0):.2f} E={float(st.get('expectancy_r') or 0):+.3f}",
                flush=True,
            )
            for t in trades:
                bar = str(t.entry_ts)
                row = {"tier": "A", "strategy": name, "symbol": sym}
                either_map[bar].append(row)
                if kind == "existing":
                    existing_map[bar].append(row)
                else:
                    simple_map[bar].append(row)

        mm_exist = scan_missed_moves(df, symbol=sym, candidates_by_bar=existing_map, stride=3)
        mm_simple = scan_missed_moves(df, symbol=sym, candidates_by_bar=simple_map, stride=3)
        mm_either = scan_missed_moves(df, symbol=sym, candidates_by_bar=either_map, stride=3)
        missed_rows.append(
            {
                "symbol": sym,
                "missed_existing": len(mm_exist),
                "missed_simple": len(mm_simple),
                "missed_either": len(mm_either),
                "capture_lift_vs_existing": len(mm_exist) - len(mm_either),
            }
        )
        aggregate["missed_existing"] += len(mm_exist)
        aggregate["missed_simple"] += len(mm_simple)
        aggregate["missed_either"] += len(mm_either)
        aggregate["symbols"] += 1
        print(
            f"  missed_moves existing={len(mm_exist)} simple={len(mm_simple)} either={len(mm_either)}",
            flush=True,
        )

    payload = {
        "generated": datetime.now(timezone.utc).isoformat(),
        "config_version": "router_v1",
        "strategy_version": "performance_router_v1",
        "rows": rows,
        "missed_moves": missed_rows,
        "missed_move_aggregate": aggregate,
    }
    (OUT / "router_specialist_compare.json").write_text(
        json.dumps(payload, indent=2, default=str), encoding="utf-8"
    )

    lines = [
        "# Router specialist comparison (OOS)",
        "",
        f"Generated: {payload['generated']}",
        "",
        "## Strategy OOS (FINAL holdout)",
        "",
        "| name | kind | symbol | n | WR | PF | E[R] | max_dd_r |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r.get('name')} | {r.get('kind')} | {r.get('symbol')} | "
            f"{r.get('n')} | {float(r.get('wr') or 0):.1%} | {float(r.get('pf') or 0):.2f} | "
            f"{float(r.get('expectancy_r') or 0):+.3f} | {float(r.get('max_dd_r') or 0):.2f} |"
        )
    lines += [
        "",
        "## Missed-move coverage",
        "",
        "| symbol | missed existing | missed simple | missed either | lift |",
        "|---|---|---|---|---|",
    ]
    for m in missed_rows:
        lines.append(
            f"| {m['symbol']} | {m['missed_existing']} | {m['missed_simple']} | "
            f"{m['missed_either']} | {m['capture_lift_vs_existing']} |"
        )
    lines += [
        "",
        f"Aggregate: `{aggregate}`",
        "",
        "Note: `missed_*` counts large moves with no matching candidate in that set. "
        "Positive lift means specialists reduced misses vs existing-only.",
        "",
    ]
    (OUT / "ROUTER_SPECIALIST_REPORT.md").write_text("\n".join(lines), encoding="utf-8")
    print("Report:", OUT / "ROUTER_SPECIALIST_REPORT.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
