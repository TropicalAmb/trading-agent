"""Account-level risk budget — finite hard caps, never unlimited."""

from __future__ import annotations

from typing import Any


# Full-size → preferred micro when stop risk exceeds budget
MICRO_OF: dict[str, str] = {
    "ES": "MES",
    "NQ": "MNQ",
    "GC": "MGC",
    "CL": "MCL",
    "YM": "MYM",
    "RTY": "M2K",
}


def effective_max_risk_dollars(
    cfg: dict[str, Any],
    *,
    equity: float | None = None,
) -> float:
    """Finite dollars at risk allowed for one new trade.

    Uses min(risk_per_trade_pct * equity, max_account_risk_per_trade,
    max_risk_dollars_per_trade) when those are set > 0.
    Always returns a positive finite value (defaults to 250 if misconfigured).
    """
    risk = cfg.get("risk") or {}
    hard = float(risk.get("max_risk_dollars_per_trade") or 0)
    acct = float(risk.get("max_account_risk_per_trade") or 0)
    pct = float(risk.get("risk_per_trade_pct") or 0)
    if equity is None:
        equity = float(
            (cfg.get("paper") or {}).get("starting_equity")
            or (cfg.get("account") or {}).get("equity")
            or 50_000
        )
    candidates: list[float] = []
    if hard > 0:
        candidates.append(hard)
    if acct > 0:
        candidates.append(acct)
    if pct > 0 and equity > 0:
        candidates.append(pct * float(equity))
    if not candidates:
        return 250.0  # never unlimited
    return float(min(candidates))


def suggest_micro_symbol(symbol: str) -> str | None:
    return MICRO_OF.get(str(symbol).upper())
