from __future__ import annotations

import argparse
import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any

import numpy as np
import pandas as pd

from agent.config import load_settings
from agent.management.exits import estimate_close_debit, evaluate_exits
from agent.models import OpenPosition, SpreadType


@dataclass
class TradeResult:
    symbol: str
    spread_type: str
    entry_date: date
    exit_date: date
    entry_credit: float
    exit_debit: float
    pnl: float
    reason: str
    short_strike: float
    long_strike: float


def _fetch_history(symbol: str, years: float = 3.0) -> pd.DataFrame:
    import yfinance as yf

    period = f"{max(1, int(math.ceil(years)))}y"
    df = yf.download(symbol, period=period, auto_adjust=True, progress=False)
    if df is None or df.empty:
        raise RuntimeError(f"No data for {symbol}")
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] for c in df.columns]
    df = df.rename(columns=str.title)
    df = df.dropna(subset=["Close"]).copy()
    df.index = pd.to_datetime(df.index).tz_localize(None)
    return df


def _sma(series: pd.Series, n: int) -> pd.Series:
    return series.rolling(n).mean()


def _realized_vol_rank(closes: pd.Series, lookback: int = 20, hist: int = 252) -> float:
    rets = closes.pct_change().abs().dropna()
    if len(rets) < lookback + 10:
        return 50.0
    latest = float(rets.iloc[-lookback:].mean())
    window = rets.iloc[-hist:] if len(rets) >= hist else rets
    # percentile of latest among rolling means
    roll = window.rolling(lookback).mean().dropna()
    if roll.empty:
        return 50.0
    return float(100.0 * (roll <= latest).mean())


def _width_for(spot: float, configured: float) -> float:
    if spot < 50:
        return min(configured, 1.0)
    if spot < 200:
        return min(configured, 2.0)
    return configured


def _round_strike(spot: float, width: float, otm_pct: float, put: bool) -> tuple[float, float]:
    step = 1.0 if spot < 50 else (2.0 if spot < 200 else 5.0)
    if put:
        short = math.floor((spot * (1 - otm_pct)) / step) * step
        long = short - width
    else:
        short = math.ceil((spot * (1 + otm_pct)) / step) * step
        long = short + width
    return float(short), float(long)


def _entry_credit(spot: float, width: float, otm_pct: float, iv_rank: float) -> float:
    """Synthetic credit: higher when IV rank high and width larger; decays with OTM."""
    base = width * (0.18 + 0.12 * (iv_rank / 100.0))
    # Further OTM slightly less credit
    base *= max(0.55, 1.0 - otm_pct * 4)
    return round(max(0.15, min(width * 0.45, base)), 2)


def run_backtest(cfg: dict[str, Any], *, years: float = 3.0) -> dict[str, Any]:
    strat = cfg["strategy"]
    mgmt = cfg.get("management", {})
    symbols = list(cfg.get("universe", {}).get("symbols", ["SPY"]))
    otm = float(strat.get("short_otm_pct", 0.03))
    width_cfg = float(strat.get("spread_width", 5.0))
    min_iv = float(strat.get("min_iv_rank", 0))
    sma_n = int(strat.get("trend_sma_period", 20))
    hold_dte = int(strat.get("backtest_hold_dte", 35))
    entry_weekday = int(strat.get("backtest_entry_weekday", 0))  # Monday=0

    trades: list[TradeResult] = []
    equity = 100_000.0
    peak = equity
    max_dd = 0.0
    curve = []

    for symbol in symbols:
        df = _fetch_history(symbol, years=years)
        df["SMA"] = _sma(df["Close"], sma_n)
        i = sma_n + 5
        open_trade: dict[str, Any] | None = None

        while i < len(df) - 2:
            row = df.iloc[i]
            dt: date = df.index[i].date()
            spot = float(row["Close"])
            sma = row["SMA"]
            if pd.isna(sma):
                i += 1
                continue

            # Manage open
            if open_trade is not None:
                pos: OpenPosition = open_trade["pos"]
                entry_i = open_trade["entry_i"]
                days_passed = i - entry_i
                entry_dte = hold_dte
                mark = estimate_close_debit(
                    pos, spot, days_passed=days_passed, entry_dte=entry_dte
                )
                # Build a one-off evaluate using current dte
                pos.expiry = dt + timedelta(days=max(0, entry_dte - days_passed))
                signals = evaluate_exits([pos], {symbol: spot}, cfg, today=dt)
                # Also force exit at original expiry index
                force = days_passed >= entry_dte
                if signals or force:
                    reason = signals[0].reason.value if signals else "expiry"
                    debit = signals[0].mark_debit if signals else mark
                    pnl = (pos.entry_credit - debit) * 100 * pos.quantity
                    # Cap loss at max loss
                    max_loss = (pos.width - pos.entry_credit) * 100 * pos.quantity
                    pnl = max(-max_loss, pnl)
                    trades.append(
                        TradeResult(
                            symbol=symbol,
                            spread_type=pos.spread_type.value,
                            entry_date=open_trade["entry_date"],
                            exit_date=dt,
                            entry_credit=pos.entry_credit,
                            exit_debit=debit,
                            pnl=pnl,
                            reason=reason,
                            short_strike=pos.short_strike,
                            long_strike=pos.long_strike,
                        )
                    )
                    equity += pnl
                    peak = max(peak, equity)
                    max_dd = max(max_dd, (peak - equity) / peak if peak else 0)
                    curve.append({"date": dt.isoformat(), "equity": equity, "symbol": symbol})
                    open_trade = None
                    i += 1
                    continue

            # Entries: one at a time per symbol, chosen weekday, RTH proxy = daily bar
            if open_trade is None and dt.weekday() == entry_weekday:
                closes = df["Close"].iloc[: i + 1]
                iv_rank = _realized_vol_rank(closes)
                bullish = spot >= float(sma)
                bearish = spot < float(sma)
                put_ok = bool(strat.get("allow_put_credit", True)) and (
                    not strat.get("use_trend_filter", True) or bullish
                )
                call_ok = bool(strat.get("allow_call_credit", True)) and (
                    not strat.get("use_trend_filter", True) or bearish
                )
                if iv_rank >= min_iv and (put_ok or call_ok):
                    width = _width_for(spot, width_cfg)
                    if put_ok:
                        st = SpreadType.PUT_CREDIT
                        short_k, long_k = _round_strike(spot, width, otm, put=True)
                        right = "P"
                    else:
                        st = SpreadType.CALL_CREDIT
                        short_k, long_k = _round_strike(spot, width, otm, put=False)
                        right = "C"
                    credit = _entry_credit(spot, width, otm, iv_rank)
                    if credit / width >= float(strat.get("min_credit_pct_of_width", 0.15)):
                        pos = OpenPosition(
                            id=f"{symbol}-{dt}",
                            underlying=symbol,
                            spread_type=st,
                            short_strike=short_k,
                            long_strike=long_k,
                            right=right,
                            expiry=dt + timedelta(days=hold_dte),
                            width=width,
                            entry_credit=credit,
                            quantity=1,
                            entry_spot=spot,
                            entry_ts=datetime(dt.year, dt.month, dt.day, tzinfo=timezone.utc),
                        )
                        open_trade = {
                            "pos": pos,
                            "entry_i": i,
                            "entry_date": dt,
                        }
            i += 1

    pnls = [t.pnl for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    win_rate = len(wins) / len(pnls) if pnls else 0.0
    avg_win = float(np.mean(wins)) if wins else 0.0
    avg_loss = float(np.mean(losses)) if losses else 0.0
    expectancy = float(np.mean(pnls)) if pnls else 0.0
    gross_profit = float(sum(wins))
    gross_loss = float(abs(sum(losses)))
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else float("inf") if gross_profit else 0.0

    return {
        "trades": trades,
        "stats": {
            "symbols": symbols,
            "years": years,
            "n_trades": len(trades),
            "win_rate": win_rate,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "expectancy_per_trade": expectancy,
            "total_pnl": float(sum(pnls)) if pnls else 0.0,
            "profit_factor": profit_factor,
            "max_drawdown_pct": max_dd,
            "ending_equity": equity,
            "management": {
                "profit_take_frac_of_credit": mgmt.get("profit_take_frac_of_credit", 0.5),
                "stop_loss_mult_of_credit": mgmt.get("stop_loss_mult_of_credit", 2.0),
                "time_exit_dte": mgmt.get("time_exit_dte", 21),
            },
        },
        "curve": curve,
    }


def _print_report(result: dict[str, Any]) -> None:
    s = result["stats"]
    print("\n========== BACKTEST REPORT ==========")
    print(f"Symbols:        {', '.join(s['symbols'])}")
    print(f"Lookback:       {s['years']}y")
    print(f"Trades:         {s['n_trades']}")
    print(f"Win rate:       {s['win_rate']:.1%}")
    print(f"Avg win:        ${s['avg_win']:.2f}")
    print(f"Avg loss:       ${s['avg_loss']:.2f}")
    print(f"Expectancy:     ${s['expectancy_per_trade']:.2f} / trade")
    print(f"Total P&L:      ${s['total_pnl']:.2f}")
    print(f"Profit factor:  {s['profit_factor']:.2f}")
    print(f"Max drawdown:   {s['max_drawdown_pct']:.1%}")
    print(f"Ending equity:  ${s['ending_equity']:.2f}  (start $100,000)")
    print("Management:", s["management"])
    print("=====================================")
    if s["expectancy_per_trade"] <= 0 or s["profit_factor"] < 1.0:
        print(
            "\nVERDICT: Rules do NOT show a clear edge in this simulation.\n"
            "Do NOT go live. We should tighten filters or change parameters.\n"
        )
    else:
        print(
            "\nVERDICT: Positive expectancy in this simulation - still PAPER TRADE next.\n"
            "Not a guarantee. Assumes stop orders fill near the stop (gaps can be worse).\n"
        )
    # Show last 8 trades
    trades: list[TradeResult] = result["trades"]
    if trades:
        print("Recent trades:")
        for t in trades[-8:]:
            print(
                f"  {t.entry_date} -> {t.exit_date} {t.symbol:4} {t.spread_type:12} "
                f"pnl=${t.pnl:8.2f}  {t.reason}"
            )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Backtest credit-spread rules")
    parser.add_argument("--years", type=float, default=3.0)
    parser.add_argument("--config", default=None)
    parser.add_argument(
        "--csv",
        default="data/backtest_trades.csv",
        help="Optional trade export path",
    )
    args = parser.parse_args(argv)

    cfg = load_settings(args.config)
    # Ensure management defaults exist
    cfg.setdefault(
        "management",
        {
            "profit_take_frac_of_credit": 0.50,
            "stop_loss_mult_of_credit": 2.0,
            "time_exit_dte": 21,
            "force_close_dte": 7,
        },
    )

    print("Downloading history and simulating (may take ~30s)...")
    result = run_backtest(cfg, years=args.years)
    _print_report(result)

    trades: list[TradeResult] = result["trades"]
    if trades and args.csv:
        out = pd.DataFrame([t.__dict__ for t in trades])
        from pathlib import Path

        path = Path(args.csv)
        path.parent.mkdir(parents=True, exist_ok=True)
        out.to_csv(path, index=False)
        print(f"\nSaved trades -> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
