"""Explicit scan / agent health states — never bundle unrelated conditions."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class ScanState(str, Enum):
    NO_NEW_BAR = "NO_NEW_BAR"
    DATA_STALE = "DATA_STALE"
    DATA_TIMEOUT = "DATA_TIMEOUT"
    DATA_ERROR = "DATA_ERROR"
    MARKET_CLOSED = "MARKET_CLOSED"
    BAR_PROCESSED = "BAR_PROCESSED"
    AGENT_PAUSED = "AGENT_PAUSED"
    AGENT_HEALTHY_WAITING = "AGENT_HEALTHY_WAITING"
    PASS_NO_CANDIDATE = "PASS_NO_CANDIDATE"
    EXECUTED = "EXECUTED"


@dataclass(frozen=True)
class CycleStatus:
    primary: str
    detail: str
    scan_state: str
    reasons: tuple[str, ...]


def parse_interval_seconds(interval: str) -> int:
    s = str(interval or "5m").strip().lower()
    if s.endswith("m"):
        return max(60, int(float(s[:-1]) * 60))
    if s.endswith("h"):
        return max(60, int(float(s[:-1]) * 3600))
    if s.endswith("d"):
        return max(60, int(float(s[:-1]) * 86400))
    try:
        return max(60, int(float(s)))
    except Exception:
        return 300


def stale_threshold_seconds(cfg: dict[str, Any], *, bar_interval: str | None = None) -> float:
    """Stale = beyond expected provider delay + bar cadence + tolerance."""
    md = cfg.get("market_data") or {}
    if md.get("stale_after_seconds") is not None:
        # Explicit override (tests / ops) wins
        return float(md["stale_after_seconds"])
    expected = float(md.get("expected_delay_seconds", md.get("estimated_delay_seconds", 900)))
    tol = float(md.get("stale_extra_tolerance_seconds", 420))
    interval = bar_interval or md.get("bar_interval") or "5m"
    return expected + float(parse_interval_seconds(interval)) + tol


def classify_cycle(
    symbol_reports: dict[str, Any],
    *,
    executable_count: int = 0,
    market_closed: bool = False,
    agent_paused: bool = False,
) -> CycleStatus:
    if agent_paused:
        return CycleStatus(
            "AGENT_PAUSED",
            "Agent paused / halted for new entries",
            ScanState.AGENT_PAUSED.value,
            ("AGENT_PAUSED",),
        )
    if market_closed:
        return CycleStatus(
            "MARKET CLOSED",
            "Session gate closed; scheduler still ticking",
            ScanState.MARKET_CLOSED.value,
            ("MARKET_CLOSED",),
        )

    reasons = [str(r.get("reason") or "") for r in symbol_reports.values()]
    if not reasons and executable_count == 0:
        return CycleStatus(
            "AGENT HEALTHY — WAITING FOR NEW MARKET BAR",
            "No symbol reports yet this cycle",
            ScanState.AGENT_HEALTHY_WAITING.value,
            (),
        )

    timeouts = [x for x in reasons if "DATA_TIMEOUT" in x or "timeout" in x.lower()]
    errors = [x for x in reasons if x.startswith("DATA_ERROR") or x == "DATA_EMPTY"]
    stales = [x for x in reasons if x == "DATA_STALE"]
    no_new = [x for x in reasons if x == "NO_NEW_BAR"]
    processed = [
        x
        for x in reasons
        if x
        and x
        not in {"NO_NEW_BAR", "DATA_STALE", "DATA_EMPTY", "MARKET_CLOSED"}
        and not x.startswith("DATA_ERROR")
        and "DATA_TIMEOUT" not in x
    ]

    if timeouts and len(timeouts) == len(reasons):
        return CycleStatus(
            "ERROR — MARKET DATA TIMEOUT",
            f"Provider timeout on {len(timeouts)} symbol(s)",
            ScanState.DATA_TIMEOUT.value,
            tuple(timeouts[:6]),
        )
    if errors and len(errors) == len(reasons):
        return CycleStatus(
            "ERROR — PROVIDER FAILURE",
            f"Provider failure on {len(errors)} symbol(s): {errors[0][:120]}",
            ScanState.DATA_ERROR.value,
            tuple(errors[:6]),
        )
    if stales and len(stales) == len(reasons):
        return CycleStatus(
            "BLOCKED — DATA STALE",
            "All symbols beyond expected Yahoo delay + bar cadence + tolerance",
            ScanState.DATA_STALE.value,
            ("DATA_STALE",),
        )
    if no_new and len(no_new) == len(reasons):
        # Extract latest market bar from reports if present
        bars = [
            str(r.get("market_time") or r.get("last_evaluated_market_bar") or "")
            for r in symbol_reports.values()
            if r.get("market_time") or r.get("last_evaluated_market_bar")
        ]
        bar_s = bars[0] if bars else "unknown"
        return CycleStatus(
            "AGENT HEALTHY — NO NEW MARKET BAR",
            f"Yahoo returned same completed bar ({bar_s}). Scheduler tick OK — waiting for next bar.",
            ScanState.NO_NEW_BAR.value,
            ("NO_NEW_BAR",),
        )
    if executable_count > 0:
        return CycleStatus(
            "AGENT HEALTHY — BAR PROCESSED",
            f"Executable setups: {executable_count}",
            ScanState.EXECUTED.value if False else ScanState.BAR_PROCESSED.value,
            tuple(processed[:6]) or ("BAR_PROCESSED",),
        )
    if processed or any(
        r.get("decision") == "CANDIDATE" or (r.get("candidates") or r.get("last_candidates"))
        for r in symbol_reports.values()
    ):
        # Bar evaluated but nothing >= minimum tier
        n_cands = sum(
            len(r.get("candidates") or r.get("last_candidates") or [])
            for r in symbol_reports.values()
        )
        return CycleStatus(
            "PASS — NO CANDIDATE >= A",
            f"Bar processed; {n_cands} candidate(s) below minimum_trade_tier or filtered",
            ScanState.PASS_NO_CANDIDATE.value,
            tuple(processed[:6]) or ("PASS_NO_CANDIDATE",),
        )
    # Mixed
    if no_new and not processed:
        return CycleStatus(
            "AGENT HEALTHY — NO NEW MARKET BAR",
            "Most symbols waiting; no bar processed this tick",
            ScanState.AGENT_HEALTHY_WAITING.value,
            ("NO_NEW_BAR",),
        )
    return CycleStatus(
        "AGENT HEALTHY — BAR PROCESSED",
        "Cycle completed with mixed symbol states",
        ScanState.BAR_PROCESSED.value,
        tuple(reasons[:6]),
    )
