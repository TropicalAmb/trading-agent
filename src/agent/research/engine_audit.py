"""Per-engine selectivity audit (bars → pattern → candidates → tiers → rejects)."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Callable, Optional

import pandas as pd


def audit_engine_on_df(
    name: str,
    evaluate_fn: Callable[..., Any],
    df: pd.DataFrame,
    cfg: dict[str, Any],
    *,
    symbol: str = "MES",
    point_value: float = 5.0,
    step: int = 1,
    min_bars: int = 40,
) -> dict[str, Any]:
    """Walk completed bars and count detections / hard rejections (research only)."""
    bars_evaluated = 0
    raw_detections = 0
    candidates = 0
    rejects: Counter[str] = Counter()
    # Engines that expose present≠entry use optional attributes
    present_flags = 0

    if df is None or len(df) < min_bars:
        return {
            "strategy": name,
            "bars_evaluated": 0,
            "raw_pattern_detections": 0,
            "candidates_generated": 0,
            "top_rejection_reasons": [],
            "note": "insufficient bars",
        }

    for i in range(min_bars, len(df), max(1, step)):
        window = df.iloc[: i + 1]
        bars_evaluated += 1
        try:
            sig = evaluate_fn(symbol, window, cfg, point_value=point_value)
        except TypeError:
            try:
                sig = evaluate_fn(symbol, window, cfg)
            except Exception as exc:
                rejects[f"eval_error:{type(exc).__name__}"] += 1
                continue
        except Exception as exc:
            rejects[f"eval_error:{type(exc).__name__}"] += 1
            continue
        if sig is None:
            rejects["no_setup"] += 1
            continue
        raw_detections += 1
        if getattr(sig, "breakout_present", None) or getattr(sig, "momentum_present", None):
            present_flags += 1
        if getattr(sig, "entry_valid", True) is False:
            rejects["ENTRY_NOT_VALID"] += 1
            continue
        candidates += 1

    top = rejects.most_common(8)
    return {
        "strategy": name,
        "bars_evaluated": bars_evaluated,
        "raw_pattern_detections": raw_detections,
        "present_flags": present_flags,
        "candidates_generated": candidates,
        "hard_rejections": int(sum(rejects.values())),
        "top_rejection_reasons": [{"reason": r, "n": n} for r, n in top],
    }


def audit_from_last_evaluation(path: str = "data/last_evaluation.json") -> dict[str, Any]:
    """Summarize engine because-strings from persisted last evaluation."""
    import json
    from pathlib import Path

    p = Path(path)
    if not p.exists():
        return {"engines": {}, "note": "no last_evaluation.json"}
    data = json.loads(p.read_text(encoding="utf-8"))
    engines: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "symbols_seen": 0,
            "none": 0,
            "signals": 0,
            "tiers": Counter(),
            "because": Counter(),
        }
    )
    for sym, rep in (data.get("symbols") or {}).items():
        for ename, er in (rep.get("engines") or {}).items():
            e = engines[ename]
            e["symbols_seen"] += 1
            if er.get("result") in (None, "none", ""):
                e["none"] += 1
                e["because"][str(er.get("because") or "none")] += 1
            else:
                e["signals"] += 1
                e["tiers"][str(er.get("tier") or "?")] += 1
        for c in rep.get("candidates") or []:
            ename = str(c.get("strategy") or "")
            if ename:
                engines[ename]["tiers"][str(c.get("tier") or "?")] += 1

    out = {}
    for name, e in engines.items():
        out[name] = {
            "symbols_seen": e["symbols_seen"],
            "none": e["none"],
            "signals": e["signals"],
            "tier_counts": dict(e["tiers"]),
            "top_rejection_reasons": [
                {"reason": r, "n": n} for r, n in e["because"].most_common(8)
            ],
        }
    return {"engines": out}


def quiet_engine_notes(audit: dict[str, Any]) -> list[str]:
    notes = []
    for name, e in (audit.get("engines") or {}).items():
        if e.get("signals", 0) == 0 and e.get("none", 0) > 0:
            top = (e.get("top_rejection_reasons") or [{}])[0]
            notes.append(
                f"{name}: quiet — 0 signals / {e.get('none')} none; "
                f"top reject={top.get('reason')} (n={top.get('n')})"
            )
    return notes
