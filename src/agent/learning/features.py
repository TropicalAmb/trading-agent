"""Entry-time feature snapshots from TradeSetup + MarketContext (no lookahead)."""

from __future__ import annotations

from typing import Any, Optional


def snapshot_entry_features(
    setup: Any,
    ctx: Any | None = None,
    *,
    atr: float | None = None,
    agreeing_n: int | None = None,
) -> dict[str, Any]:
    meta = dict(getattr(setup, "metadata", None) or {})
    direction = str(getattr(setup, "direction", "") or "").upper()
    sign = 1 if direction in {"BUY", "LONG"} else -1
    feats: dict[str, Any] = {
        "symbol": str(getattr(setup, "symbol", "")).upper(),
        "strategy": str(getattr(setup, "strategy_name", "")),
        "direction": "LONG" if sign > 0 else "SHORT",
        "session": getattr(setup, "session", None) or meta.get("session"),
        "regime": meta.get("regime"),
        "local_score": meta.get("strategy_local_score"),
        "global_score": meta.get("global_score"),
        "tier_rank": {"A+": 4, "A": 3, "B": 2, "C": 1}.get(str(getattr(setup, "setup_tier", "")), 0),
        "agreeing_n": agreeing_n
        if agreeing_n is not None
        else len(list(meta.get("agreeing_engines") or [])),
        "target_r": float(getattr(setup, "expected_r", 0) or 0),
    }
    if ctx is not None:
        mtf = 0
        if sign > 0:
            mtf = int(getattr(ctx, "direction_15m", 0) > 0) + int(getattr(ctx, "direction_1h", 0) > 0) + int(
                getattr(ctx, "direction_4h", 0) > 0
            )
        else:
            mtf = int(getattr(ctx, "direction_15m", 0) < 0) + int(getattr(ctx, "direction_1h", 0) < 0) + int(
                getattr(ctx, "direction_4h", 0) < 0
            )
        feats.update(
            {
                "dir_15m": int(getattr(ctx, "direction_15m", 0)),
                "dir_1h": int(getattr(ctx, "direction_1h", 0)),
                "dir_4h": int(getattr(ctx, "direction_4h", 0)),
                "mtf_aligned": int(mtf),
                "above_vwap": int(bool(getattr(ctx, "above_vwap", False))),
                "below_vwap": int(bool(getattr(ctx, "below_vwap", False))),
                "ema_bull": int(bool(getattr(ctx, "ema_bull", False))),
                "ema_bear": int(bool(getattr(ctx, "ema_bear", False))),
                "overextended": int(
                    bool(getattr(ctx, "overextended_long", False) or getattr(ctx, "overextended_short", False))
                ),
                "near_pdh": int(bool(getattr(ctx, "near_pdh", False))),
                "near_pdl": int(bool(getattr(ctx, "near_pdl", False))),
                "momentum_aligned": int(
                    (sign > 0 and getattr(ctx, "momentum_up", False))
                    or (sign < 0 and getattr(ctx, "momentum_down", False))
                ),
                "regime": str(getattr(getattr(ctx, "regime", None), "value", getattr(ctx, "regime", meta.get("regime")))),
            }
        )
    if atr and atr > 0:
        entry = float(getattr(setup, "entry", 0) or 0)
        stop = float(getattr(setup, "stop", 0) or 0)
        feats["atr"] = float(atr)
        feats["stop_dist_atr"] = abs(entry - stop) / atr
    # Optional extras from cascade / strategy metadata (entry-time only)
    cas = meta.get("cascade") or {}
    if isinstance(cas, dict):
        if cas.get("location") is not None:
            feats["cascade_location"] = str(cas.get("location"))
        if cas.get("thesis") is not None:
            feats["cascade_thesis"] = str(cas.get("thesis"))
        if cas.get("mss") is not None:
            feats["mss"] = int(bool(cas.get("mss")))
        if cas.get("bos") is not None:
            feats["break_of_structure"] = int(bool(cas.get("bos")))
    for k in (
        "vwap_dist_atr",
        "abs_dist_vwap_atr",
        "price_vs_ema20_atr",
        "price_vs_ema50_atr",
        "body_atr",
        "upper_wick_atr",
        "lower_wick_atr",
        "close_location",
        "atr_pctile",
        "sweep_magnitude_atr",
        "reclaim_quality",
        "pullback_depth_atr",
        "ema20_above_ema50",
        "near_session_high",
        "near_session_low",
        "engulfing",
        "rejection",
    ):
        if meta.get(k) is not None and k not in feats:
            feats[k] = meta.get(k)
        if ctx is not None and hasattr(ctx, k) and k not in feats:
            try:
                feats[k] = getattr(ctx, k)
            except Exception:
                pass
    if feats.get("vwap_dist_atr") is None and feats.get("abs_dist_vwap_atr") is not None:
        feats["vwap_dist_atr"] = feats["abs_dist_vwap_atr"]
    return feats


def top_traits_from_features(
    feats: dict[str, Any],
    *,
    coefficients: dict[str, float] | None = None,
    limit: int = 3,
) -> tuple[list[str], list[str]]:
    """Human-readable positive/negative traits for dashboard."""
    pos: list[str] = []
    neg: list[str] = []
    if int(feats.get("mtf_aligned") or 0) >= 3:
        pos.append("HTF alignment (MTF3)")
    elif int(feats.get("mtf_aligned") or 0) <= 1:
        neg.append("weak MTF alignment")
    if feats.get("above_vwap") and feats.get("direction") == "LONG":
        pos.append("above VWAP (long)")
    if feats.get("below_vwap") and feats.get("direction") == "SHORT":
        pos.append("below VWAP (short)")
    if feats.get("overextended"):
        neg.append("overextended")
    if feats.get("momentum_aligned"):
        pos.append("momentum aligned")
    if feats.get("near_pdh") and feats.get("direction") == "SHORT":
        pos.append("near PDH (short fade/ctx)")
    if feats.get("near_pdl") and feats.get("direction") == "LONG":
        pos.append("near PDL (long fade/ctx)")
    # Coefficient-driven extras
    if coefficients:
        scored = []
        for k, v in coefficients.items():
            if k.startswith(("strategy_", "symbol_", "session_", "regime_", "direction_")):
                continue
            val = feats.get(k)
            if val is None:
                continue
            try:
                contrib = float(v) * float(val)
            except Exception:
                continue
            scored.append((contrib, k, v))
        scored.sort(key=lambda x: x[0], reverse=True)
        for contrib, k, _v in scored[:limit]:
            if contrib > 0:
                pos.append(f"+ {k}")
            elif contrib < 0:
                neg.append(f"- {k}")
    return pos[:limit], neg[:limit]
