"""Shadow exit-model research — never modifies actual paper positions."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


EXIT_MODELS = (
    "FIXED_1_5R",
    "FIXED_2R",
    "FIXED_3R",
    "ATR_TRAIL",
    "EMA20_TRAIL",
    "SWING_TRAIL",
    "VWAP_INVALIDATION",
    "TIME_STOP",
    "TP1_1R_RUNNER_2R",
)


def evaluate_fixed_r(
    *,
    side: str,
    entry: float,
    stop: float,
    path_high: float,
    path_low: float,
    r_mult: float,
) -> dict[str, Any]:
    """Did price touch +R target before stop along observed path extremes?"""
    risk = abs(entry - stop) or 1e-9
    if side.upper() == "BUY":
        target = entry + r_mult * risk
        hit_stop = path_low <= stop
        hit_tgt = path_high >= target
    else:
        target = entry - r_mult * risk
        hit_stop = path_high >= stop
        hit_tgt = path_low <= target
    if hit_tgt and not hit_stop:
        result = "WIN"
        exit_px = target
    elif hit_stop and not hit_tgt:
        result = "LOSS"
        exit_px = stop
    elif hit_tgt and hit_stop:
        # Ambiguous on bar extremes — mark limitation
        result = "AMBIGUOUS"
        exit_px = stop
    else:
        result = "OPEN"
        exit_px = None
    return {
        "model": f"FIXED_{r_mult}R".replace(".", "_"),
        "result": result,
        "exit": exit_px,
        "target": target,
        "fill_model_limitation": result == "AMBIGUOUS",
    }


def evaluate_exit_suite(trade: dict[str, Any], path: dict[str, float]) -> list[dict[str, Any]]:
    """path: high/low since entry (from marks)."""
    side = str(trade.get("side", "BUY"))
    entry = float(trade["entry"])
    stop = float(trade["stop"])
    hi = float(path.get("high", entry))
    lo = float(path.get("low", entry))
    out = []
    for r in (1.5, 2.0, 3.0):
        row = evaluate_fixed_r(
            side=side, entry=entry, stop=stop, path_high=hi, path_low=lo, r_mult=r
        )
        row["trade_id"] = trade.get("id")
        row["symbol"] = trade.get("symbol")
        out.append(row)
    # Placeholder markers for trail models (require more path data)
    for name in (
        "ATR_TRAIL",
        "EMA20_TRAIL",
        "SWING_TRAIL",
        "VWAP_INVALIDATION",
        "TIME_STOP",
        "TP1_1R_RUNNER_2R",
    ):
        out.append(
            {
                "model": name,
                "trade_id": trade.get("id"),
                "symbol": trade.get("symbol"),
                "result": "NOT_COMPUTED",
                "fill_model_limitation": True,
                "note": "FILL_MODEL_LIMITATION — needs denser path / indicators",
            }
        )
    return out


class ExitModelJournal:
    def __init__(self, path: str | Path = "data/exit_model_research.jsonl"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, rows: list[dict[str, Any]]) -> None:
        with self.path.open("a", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, default=str) + "\n")
