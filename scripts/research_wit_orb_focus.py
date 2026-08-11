"""Focused precision pass: only ORB5/15 × retest/first_break × Friday filter.

Uses walk-forward OOS + friction + bootstrap CI.
Also reports combined multi-symbol OOS book.
"""

from __future__ import annotations

import json
from pathlib import Path

from research_wit_precise_backtest import (
    _fetch,
    evaluate_config,
    orb_trades,
    stats,
    walk_forward_folds,
)

OUT = Path("data/research_wit_orb_focus.json")


def main() -> int:
    frames = {
        "NQ": _fetch("NQ=F", "5m", "60d"),
        "ES": _fetch("ES=F", "5m", "60d"),
        "GC": _fetch("GC=F", "5m", "60d"),
    }
    configs = []
    for orb_m in (5, 15):
        for mode in ("retest", "first_break"):
            for skip_fri in (False, True):
                configs.append(
                    {
                        "orb_minutes": orb_m,
                        "mode": mode,
                        "skip_friday": skip_fri,
                        "after_10": False,  # ORB is at the open; after-10 kills the setup
                        "target_r": 1.5,
                    }
                )

    by_sym = {}
    book = {json.dumps(c, sort_keys=True): [] for c in configs}
    for sym, df in frames.items():
        rows = []
        for c in configs:
            r = evaluate_config(
                df,
                symbol=sym,
                strategy=f"ORB_{c['orb_minutes']}m_{c['mode']}",
                params=c,
            )
            rows.append(
                {
                    "params": c,
                    "oos": r["oos"],
                    "positive_oos_folds": r["positive_oos_folds"],
                    "stable": r["stable"],
                }
            )
            # Collect raw OOS trades for book-level stats
            oos_trades = []
            for name, _train, test in walk_forward_folds(df, n_folds=4):
                oos_trades.extend(
                    orb_trades(
                        test,
                        symbol=sym,
                        orb_minutes=c["orb_minutes"],
                        mode=c["mode"],
                        target_r=c["target_r"],
                        skip_friday=c["skip_friday"],
                        after_10=False,
                        fold=f"{name}-test",
                    )
                )
            book[json.dumps(c, sort_keys=True)].extend(oos_trades)
        rows.sort(key=lambda x: (x["oos"]["expectancy_r"], x["oos"]["pf"]), reverse=True)
        by_sym[sym] = {
            "bars": len(df),
            "from": str(df.index.min()) if len(df) else None,
            "to": str(df.index.max()) if len(df) else None,
            "ranked": rows,
        }

    book_stats = []
    for k, trades in book.items():
        st = stats(trades)
        book_stats.append({"params": json.loads(k), "combined_oos": st, "n_symbols_traded": len({t.symbol for t in trades})})
    book_stats.sort(key=lambda x: (x["combined_oos"]["expectancy_r"], x["combined_oos"]["pf"]), reverse=True)

    out = {
        "note": "Focused ORB precision; after_10 forced false (conflicts with NY ORB)",
        "by_symbol": by_sym,
        "combined_book_ranked": book_stats,
        "recommendation": book_stats[0] if book_stats else None,
    }
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps({"top_combined": book_stats[:5], "nq_top": by_sym.get("NQ", {}).get("ranked", [])[:3], "es_top": by_sym.get("ES", {}).get("ranked", [])[:3]}, indent=2))
    print("Wrote", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
