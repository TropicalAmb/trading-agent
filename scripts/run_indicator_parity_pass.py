"""Indicator parity pass: 1:1 TV MTF Sweep Retest on 1-minute data + challengers."""

from __future__ import annotations

import json
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent.research.harness.datasets import fetch_yahoo
from agent.strategy.indicator_parity import compute_parity_frame, state_at

OUT = ROOT / "data" / "indicator_parity"
SYMBOLS = {
    "NQ": ("NQ=F", 20.0),
    "MNQ": ("MNQ=F", 2.0),
    "ES": ("ES=F", 50.0),
    "MES": ("MES=F", 5.0),
}

CFG = {
    "indicator_parity": {
        "enabled": True,
        "use_vwap": True,
        "fast_ema": 20,
        "slow_ema": 50,
        "retest_zone_atr": 0.15,
        "sweep_valid_bars": 240,
        "stop_atr_mult": 1.0,
        "target_r_multiple": 2.0,
        "overext_atr": 1.8,
        "min_confidence": 0,
    }
}


def _session_label(ts: pd.Timestamp) -> str:
    if getattr(ts, "tzinfo", None) is not None:
        ts = ts.tz_convert("America/New_York")
    m = ts.hour * 60 + ts.minute
    if m >= 18 * 60 or m < 3 * 60:
        return "asia"
    if 3 * 60 <= m < 9 * 60 + 30:
        return "london"
    if 9 * 60 + 30 <= m < 17 * 60:
        return "ny"
    return "globex"


def _sample_label(n: int) -> str:
    if n < 30:
        return "VERY PRELIMINARY"
    if n < 100:
        return "PROMISING / NOT CONFIRMED"
    return "STRONGER SAMPLE"


def load_bars(yahoo_sym: str, interval: str, period: str) -> pd.DataFrame:
    """Load native Yahoo bars. Never upsample lower TF from higher TF OHLC."""
    df = fetch_yahoo(yahoo_sym, interval, period)
    if df is None or df.empty:
        return pd.DataFrame()
    return df


# Chart-TF runs: HTF 15m/1h/4h always derived from the base series (live as-of).
# Yahoo depth: 1m≈7d, 5m≈60d, 1h/4h≈2y. Delay ≠ discarded — longer HTF history is used.
BASE_RUNS = (
    {"tag": "1m_7d", "interval": "1m", "period": "7d", "cooldown_bars": 30, "min_bars": 200},
    {"tag": "5m_60d", "interval": "5m", "period": "60d", "cooldown_bars": 12, "min_bars": 500},
)


def simulate_trades(
    frame: pd.DataFrame,
    *,
    buy_col: str,
    sell_col: str,
    symbol: str,
    point_value: float,
    target_r: float = 2.0,
    stop_atr_mult: float = 1.0,
    cooldown_bars: int = 30,
) -> list[dict]:
    trades = []
    i = 80
    n = len(frame)
    while i < n - 2:
        buy = bool(frame[buy_col].iloc[i])
        sell = bool(frame[sell_col].iloc[i])
        if not buy and not sell:
            i += 1
            continue
        side = "BUY" if buy else "SELL"
        entry = float(frame["close"].iloc[i])
        atr = float(frame["atr"].iloc[i] or 0) or abs(entry) * 0.001
        pdh_raw = frame["pdh"].iloc[i]
        pdl_raw = frame["pdl"].iloc[i]
        pdh = float(pdh_raw) if pd.notna(pdh_raw) else float("nan")
        pdl = float(pdl_raw) if pd.notna(pdl_raw) else float("nan")
        if side == "BUY":
            atr_stop = entry - atr * stop_atr_mult
            stop = min(pdl, atr_stop) if np.isfinite(pdl) else atr_stop
            risk = max(entry - stop, atr * 0.5)
            target = entry + risk * target_r
        else:
            atr_stop = entry + atr * stop_atr_mult
            stop = max(pdh, atr_stop) if np.isfinite(pdh) else atr_stop
            risk = max(stop - entry, atr * 0.5)
            target = entry - risk * target_r
        if not np.isfinite(risk) or risk <= 0:
            i += 1
            continue
        # Path exit
        pnl_r = -1.0
        exit_px = stop
        exit_reason = "stop"
        exit_i = i
        for j in range(i + 1, min(i + 240, n)):
            hi = float(frame["high"].iloc[j])
            lo = float(frame["low"].iloc[j])
            if side == "BUY":
                if lo <= stop:
                    pnl_r, exit_px, exit_reason, exit_i = -1.0, stop, "stop", j
                    break
                if hi >= target:
                    pnl_r, exit_px, exit_reason, exit_i = target_r, target, "target", j
                    break
            else:
                if hi >= stop:
                    pnl_r, exit_px, exit_reason, exit_i = -1.0, stop, "stop", j
                    break
                if lo <= target:
                    pnl_r, exit_px, exit_reason, exit_i = target_r, target, "target", j
                    break
        else:
            # time exit at last close
            exit_i = min(i + 239, n - 1)
            exit_px = float(frame["close"].iloc[exit_i])
            pnl_r = (exit_px - entry) / risk if side == "BUY" else (entry - exit_px) / risk
            exit_reason = "time"

        ts = frame.index[i]
        pnl_1 = pnl_r * risk * point_value  # 1 contract $
        trades.append(
            {
                "symbol": symbol,
                "side": side,
                "entry_ts": str(ts),
                "exit_ts": str(frame.index[exit_i]),
                "session": _session_label(pd.Timestamp(ts)),
                "entry": entry,
                "stop": stop,
                "target": target,
                "exit": exit_px,
                "exit_reason": exit_reason,
                "pnl_r": float(pnl_r),
                "risk_pts": float(risk),
                "pnl_dollars_1": float(pnl_1),
                "win": int(pnl_r > 0),
            }
        )
        i = max(exit_i, i + cooldown_bars)
    return trades


def key_level_filter(frame: pd.DataFrame) -> pd.DataFrame:
    """Challenger: exact signal + rejection/hold at PDH/PDL or session H/L."""
    out = frame.copy()
    # session high/low rolling within day
    if getattr(out.index, "tz", None) is not None:
        day = out.index.tz_convert("America/New_York").date
    else:
        day = out.index.date
    sess_hi = out["high"].groupby(day).cummax()
    sess_lo = out["low"].groupby(day).cummin()
    atr = out["atr"].replace(0, np.nan)
    near_pdh = (out["high"] - out["pdh"]).abs() <= 0.25 * atr
    near_pdl = (out["low"] - out["pdl"]).abs() <= 0.25 * atr
    near_sh = (out["high"] - sess_hi).abs() <= 0.25 * atr
    near_sl = (out["low"] - sess_lo).abs() <= 0.25 * atr
    # rejection/hold: bearish at highs / bullish at lows
    reject_short = (out["close"] < out["open"]) & (near_pdh | near_sh)
    reject_long = (out["close"] > out["open"]) & (near_pdl | near_sl)
    out["buy_keylevel"] = out["buy_now"] & reject_long
    out["sell_keylevel"] = out["sell_now"] & reject_short
    return out


def vwap_ema_volume_signals(df: pd.DataFrame) -> pd.DataFrame:
    """Simple challenger: 15m/1h align, EMA stack, VWAP side, pullback, volume, confirm."""
    work = df.copy()
    work.columns = [str(c).lower() for c in work.columns]
    if "volume" not in work.columns:
        work["volume"] = 1.0
    frame = compute_parity_frame(work, CFG)
    vol_ma = work["volume"].rolling(20).mean()
    vol_ok = work["volume"] >= 1.1 * vol_ma
    # 15m+1h aligned (not requiring 4h)
    bull_htf = (frame["dir_15m"] == 1) & (frame["dir_1h"] == 1)
    bear_htf = (frame["dir_15m"] == -1) & (frame["dir_1h"] == -1)
    ema_bull = (frame["ema20"] > frame["ema50"]) & (frame["close"] > frame["ema20"])
    ema_bear = (frame["ema20"] < frame["ema50"]) & (frame["close"] < frame["ema20"])
    above_vwap = frame["close"] > frame["vwap"]
    below_vwap = frame["close"] < frame["vwap"]
    # pullback toward EMA20/VWAP then confirm
    pb_long = (frame["low"] <= frame[["ema20", "vwap"]].max(axis=1) + 0.15 * frame["atr"]) & (
        frame["close"] > frame["open"]
    )
    pb_short = (frame["high"] >= frame[["ema20", "vwap"]].min(axis=1) - 0.15 * frame["atr"]) & (
        frame["close"] < frame["open"]
    )
    frame["buy_vwapema"] = bull_htf & ema_bull & above_vwap & pb_long & vol_ok
    frame["sell_vwapema"] = bear_htf & ema_bear & below_vwap & pb_short & vol_ok
    # reuse atr/pdh for stops
    return frame


def trade_stats(trades: list[dict]) -> dict:
    if not trades:
        return {
            "n": 0,
            "wr": None,
            "pf": None,
            "expectancy_r": None,
            "net_r": 0.0,
            "max_dd_r": 0.0,
            "avg_win_r": None,
            "avg_loss_r": None,
            "trades_per_day": 0.0,
            "trades_per_week": 0.0,
            "sample_label": _sample_label(0),
        }
    rs = np.array([t["pnl_r"] for t in trades], dtype=float)
    rs = rs[np.isfinite(rs)]
    if len(rs) == 0:
        return trade_stats([])
    wins = rs[rs > 0]
    losses = rs[rs < 0]
    gw = float(wins.sum()) if len(wins) else 0.0
    gl = float(abs(losses.sum())) if len(losses) else 0.0
    eq = np.cumsum(rs)
    peak = np.maximum.accumulate(eq)
    dd = float((eq - peak).min()) if len(eq) else 0.0
    days = sorted({str(t["entry_ts"])[:10] for t in trades})
    n_days = max(len(days), 1)
    return {
        "n": int(len(rs)),
        "wr": float((rs > 0).mean()),
        "pf": (gw / gl) if gl > 1e-12 else (999.0 if gw > 0 else 0.0),
        "expectancy_r": float(rs.mean()),
        "net_r": float(rs.sum()),
        "max_dd_r": dd,
        "avg_win_r": float(wins.mean()) if len(wins) else None,
        "avg_loss_r": float(losses.mean()) if len(losses) else None,
        "trades_per_day": len(rs) / n_days,
        "trades_per_week": len(rs) / n_days * 5.0,
        "sample_label": _sample_label(len(rs)),
    }


def daily_pnl_report(
    trades: list[dict],
    *,
    contracts: tuple[int, ...] = (1, 2, 3),
    calendar_days: list[str] | None = None,
) -> dict:
    by_day: dict[str, float] = {}
    for t in trades:
        d = str(t["entry_ts"])[:10]
        px = t.get("pnl_dollars_1")
        if px is None or not np.isfinite(float(px)):
            continue
        by_day[d] = by_day.get(d, 0.0) + float(px)
    days = list(calendar_days) if calendar_days else sorted(by_day.keys())
    if not days and by_day:
        days = sorted(by_day.keys())
    if not days:
        return {"days": 0, "active_days": 0, "by_contracts": {}}
    vals = np.array([by_day.get(d, 0.0) for d in days], dtype=float)
    out = {
        "calendar_days": int(len(days)),
        "active_days": int(sum(1 for d in days if d in by_day)),
        "by_contracts": {},
    }
    for q in contracts:
        scaled = vals * q
        pos = scaled[scaled > 0]
        neg = scaled[scaled < 0]
        out["by_contracts"][str(q)] = {
            "avg_daily_pnl": float(scaled.mean()) if len(scaled) else 0.0,
            "profitable_day_median": float(np.median(pos)) if len(pos) else None,
            "profitable_day_p75": float(np.percentile(pos, 75)) if len(pos) else None,
            "losing_day_median": float(np.median(neg)) if len(neg) else None,
            "worst_day": float(scaled.min()) if len(scaled) else None,
            "pct_days_ge_500": float((scaled >= 500).mean()) if len(scaled) else 0.0,
            "pct_days_ge_1000": float((scaled >= 1000).mean()) if len(scaled) else 0.0,
            "pct_days_negative": float((scaled < 0).mean()) if len(scaled) else 0.0,
            "pct_days_zero_or_no_trade": float((scaled == 0).mean()) if len(scaled) else 0.0,
        }
    return out


def breakdown(trades: list[dict], key: str) -> dict[str, dict]:
    groups: dict[str, list] = {}
    for t in trades:
        groups.setdefault(str(t.get(key)), []).append(t)
    return {k: trade_stats(v) for k, v in groups.items()}


def _calendar_days(frames: dict[str, pd.DataFrame]) -> list[str]:
    cal: set[str] = set()
    for f in frames.values():
        idx = f.index
        if getattr(idx, "tz", None) is not None:
            cal.update(pd.Index(idx.tz_convert("America/New_York")).strftime("%Y-%m-%d"))
        else:
            cal.update(pd.Index(idx).strftime("%Y-%m-%d"))
    return sorted(cal)


def _fmt_cmp_row(name: str, st: dict) -> str:
    aw = st["avg_win_r"]
    al = st["avg_loss_r"]
    return (
        f"| {name} | {st['n']} | {st['sample_label']} | "
        f"{(st['wr'] if st['wr'] is not None else float('nan')):.1%} | "
        f"{(st['pf'] if st['pf'] is not None else float('nan')):.2f} | "
        f"{(st['expectancy_r'] if st['expectancy_r'] is not None else float('nan')):+.3f} | "
        f"{st['max_dd_r']:.2f} | {st['trades_per_day']:.2f} | {st['trades_per_week']:.2f} | "
        f"{(aw if aw is not None else float('nan')):.3f} | "
        f"{(al if al is not None else float('nan')):.3f} |"
    )


def run_base(base: dict) -> dict:
    """One chart-TF run. HTF 15m/1h/4h always derived from this base (no lookahead)."""
    tag = base["tag"]
    interval = base["interval"]
    period = base["period"]
    cooldown = int(base["cooldown_bars"])
    min_bars = int(base["min_bars"])
    data_note = {
        "base_tag": tag,
        "chart_interval": interval,
        "period": period,
        "htf": "15m + 1h + 4h derived live-asof from base (Pine useLiveHTF)",
        "source": f"Yahoo Finance native {interval} (period={period})",
        "local_1m_archive": False,
        "fabricated_from_higher_tf": False,
        "delay_note": (
            "Yahoo delay does not discard HTF state — same delayed bars still carry "
            "15m/1h/4h direction, EMA, VWAP, PDH/PDL."
        ),
    }
    print(f"\n=== BASE {tag} ===", flush=True)
    print("DATA:", json.dumps(data_note), flush=True)

    systems = {
        "exact_tv_indicator": ("buy_now", "sell_now"),
        "pullback_entry": ("buy_pullback", "sell_pullback"),
        "momentum_entry": ("buy_momentum", "sell_momentum"),
        "indicator_plus_keylevel": ("buy_keylevel", "sell_keylevel"),
        "vwap_ema_volume": ("buy_vwapema", "sell_vwapema"),
    }
    trades_by_system: dict[str, list] = {k: [] for k in systems}
    frames: dict[str, pd.DataFrame] = {}
    parity_samples: list[dict] = []

    for sym, (ysym, pv) in SYMBOLS.items():
        print(f"load {interval} {sym}", flush=True)
        df = load_bars(ysym, interval, period)
        if df is None or len(df) < min_bars:
            print(f"  SKIP {sym}: insufficient {interval} bars ({0 if df is None else len(df)})", flush=True)
            continue
        frames[sym] = df
        print(f"  bars={len(df)} {df.index.min()} -> {df.index.max()}", flush=True)

        frame = compute_parity_frame(df, CFG)
        frame = key_level_filter(frame)
        sig_idx = np.where(frame["buy_now"] | frame["sell_now"])[0]
        for i in list(sig_idx[:3]) + list(sig_idx[-2:] if len(sig_idx) > 3 else []):
            st = state_at(frame, int(i), symbol=sym, entry_mode="exact", cfg=CFG)
            row = asdict(st)
            row["base_tag"] = tag
            parity_samples.append(row)
        for i in range(200, len(frame), max(len(frame) // 8, 1)):
            st = state_at(frame, i, symbol=sym, entry_mode="exact", cfg=CFG)
            row = asdict(st)
            row["base_tag"] = tag
            parity_samples.append(row)

        vframe = vwap_ema_volume_signals(df)
        for name, (bcol, scol) in systems.items():
            src = vframe if name == "vwap_ema_volume" else frame
            if bcol not in src.columns:
                continue
            tr = simulate_trades(
                src,
                buy_col=bcol,
                sell_col=scol,
                symbol=sym,
                point_value=pv,
                cooldown_bars=cooldown,
            )
            for t in tr:
                t["system"] = name
                t["base_tag"] = tag
                t["chart_interval"] = interval
            trades_by_system[name].extend(tr)
            print(f"  {name}: trades={len(tr)}", flush=True)

    calendar_days = _calendar_days(frames)
    comparison = {}
    for name, trades in trades_by_system.items():
        st = trade_stats(trades)
        st["by_symbol"] = breakdown(trades, "symbol")
        st["by_session"] = breakdown(trades, "session")
        st["daily_pnl"] = daily_pnl_report(trades, calendar_days=calendar_days)
        comparison[name] = st

    for name, trades in trades_by_system.items():
        pd.DataFrame(trades).to_csv(OUT / f"trades_{tag}_{name}.csv", index=False)
    if parity_samples:
        pd.DataFrame(parity_samples).to_csv(OUT / f"parity_state_sample_{tag}.csv", index=False)

    return {
        "base_tag": tag,
        "data": data_note,
        "symbols_loaded": {s: int(len(f)) for s, f in frames.items()},
        "date_range": {s: [str(f.index.min()), str(f.index.max())] for s, f in frames.items()},
        "exact_trades": len(trades_by_system["exact_tv_indicator"]),
        "comparison": comparison,
        "parity_sample_rows": parity_samples[:40],
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    by_base = {}
    for base in BASE_RUNS:
        by_base[base["tag"]] = run_base(base)

    report = {
        "generated": datetime.now(timezone.utc).isoformat(),
        "indicator_source": "MTF Sweep Retest Assistant (//@version=6)",
        "pine_path": str(OUT / "MTF_Sweep_Retest_Assistant.pine"),
        "parity_status": (
            "LOGIC_PORTED_1_1 from Pine BUY NOW/SELL NOW; "
            "strict all-3 HTF (15m/1h/4h) live-asof on every base bar; "
            "chart TF runs: 1m_7d and 5m_60d; "
            "stops/targets are execution overlay (not in Pine overlay)."
        ),
        "htf_clarification": (
            "15m/1h/4h were never ignored — they gate longBias/shortBias on every signal. "
            "Prior pass only lacked a long chart-TF history window (Yahoo 1m≈7d). "
            "This pass adds native 5m×60d while keeping the same HTF logic."
        ),
        "by_base": by_base,
        # Convenience: primary longer window for headline table
        "primary_base": "5m_60d",
        "comparison": (by_base.get("5m_60d") or {}).get("comparison") or {},
        "data": (by_base.get("5m_60d") or {}).get("data") or {},
    }
    (OUT / "INDICATOR_PARITY_REPORT.json").write_text(
        json.dumps(report, indent=2, default=str), encoding="utf-8"
    )

    lines = [
        "# Indicator Parity Report",
        "",
        f"Generated: {report['generated']}",
        "",
        f"**Parity status:** {report['parity_status']}",
        "",
        f"**HTF note:** {report['htf_clarification']}",
        "",
    ]
    for tag, block in by_base.items():
        data = block.get("data") or {}
        cmp = block.get("comparison") or {}
        lines += [
            f"## Base: `{tag}` (chart={data.get('chart_interval')}, period={data.get('period')})",
            "",
            f"- Source: `{data.get('source')}`",
            f"- HTF: `{data.get('htf')}`",
            f"- Range: `{block.get('date_range')}`",
            f"- Exact trades: **{block.get('exact_trades')}**",
            "",
            "| system | n | label | WR | PF | E[R] | maxDD R | trades/day | trades/week | avg win R | avg loss R |",
            "|---|---|---|---|---|---|---|---|---|---|---|",
        ]
        for name, st in cmp.items():
            lines.append(_fmt_cmp_row(name, st))

        exact = cmp.get("exact_tv_indicator") or {}
        lines += ["", f"### Exact indicator — by symbol ({tag})", ""]
        for sym, st in (exact.get("by_symbol") or {}).items():
            lines.append(
                f"- **{sym}**: n={st['n']} ({st['sample_label']}) WR={st['wr']} "
                f"PF={st['pf']} E={st['expectancy_r']} DD={st['max_dd_r']}"
            )
        lines += ["", f"### Exact indicator — by session ({tag})", ""]
        for sess, st in (exact.get("by_session") or {}).items():
            lines.append(
                f"- **{sess}**: n={st['n']} WR={st['wr']} PF={st['pf']} E={st['expectancy_r']}"
            )
        lines += ["", f"### Pullback vs momentum ({tag})", ""]
        for name in ("pullback_entry", "momentum_entry"):
            st = cmp.get(name) or {}
            lines.append(
                f"- **{name}**: n={st.get('n')} ({st.get('sample_label')}) WR={st.get('wr')} "
                f"PF={st.get('pf')} E={st.get('expectancy_r')} DD={st.get('max_dd_r')}"
            )

        lines += ["", f"### Daily P&L ({tag}, calendar days)", ""]
        for sys_name in (
            "exact_tv_indicator",
            "indicator_plus_keylevel",
            "vwap_ema_volume",
            "pullback_entry",
            "momentum_entry",
        ):
            st = cmp.get(sys_name) or {}
            dp = (st.get("daily_pnl") or {}).get("by_contracts") or {}
            lines.append(f"#### {sys_name}")
            lines.append(
                f"- calendar days={ (st.get('daily_pnl') or {}).get('calendar_days') } "
                f"active={ (st.get('daily_pnl') or {}).get('active_days') }"
            )
            for q, dblock in dp.items():
                lines.append(
                    f"- **{q}c**: avg={dblock.get('avg_daily_pnl')}; "
                    f"win med/p75={dblock.get('profitable_day_median')}/"
                    f"{dblock.get('profitable_day_p75')}; "
                    f"lose med/worst={dblock.get('losing_day_median')}/"
                    f"{dblock.get('worst_day')}; "
                    f"≥500/≥1000/neg/zero="
                    f"{dblock.get('pct_days_ge_500'):.0%}/"
                    f"{dblock.get('pct_days_ge_1000'):.0%}/"
                    f"{dblock.get('pct_days_negative'):.0%}/"
                    f"{dblock.get('pct_days_zero_or_no_trade'):.0%}"
                )
        lines.append("")

    lines += [
        "## Notes",
        "- Chart TF = when BUY/SELL fires (1m vs 5m). HTF bias always uses 15m/1h/4h.",
        "- Pine `sweepValidBars=240` is in **chart bars** (same as TV when you change chart TF).",
        "- Delay is not used as a reason to skip HTF — only Yahoo history depth differs by interval.",
        "- Stops/targets are execution assumptions (Pine is overlay-only).",
        "",
    ]
    (OUT / "INDICATOR_PARITY_REPORT.md").write_text("\n".join(lines), encoding="utf-8")
    print("Report:", OUT / "INDICATOR_PARITY_REPORT.md", flush=True)
    summary = {
        tag: {
            k: {
                "n": v["n"],
                "wr": v["wr"],
                "pf": v["pf"],
                "E": v["expectancy_r"],
                "label": v["sample_label"],
            }
            for k, v in (block.get("comparison") or {}).items()
        }
        for tag, block in by_base.items()
    }
    print(json.dumps(summary, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
