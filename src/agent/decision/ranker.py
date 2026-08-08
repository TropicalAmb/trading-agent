"""Rank and select TradeSetups across symbols — multi-trade when risk allows."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from agent.decision.setup import TradeSetup
from agent.decision.tiering import assign_tier_for_setup, can_execute, tier_rank


def boost_for_agreement(
    setups: list[TradeSetup],
) -> tuple[list[TradeSetup], list[tuple[TradeSetup, TradeSetup]]]:
    """Keep best per symbol+side. Returns (kept, superseded pairs (loser, winner))."""
    groups: dict[tuple[str, str], list[TradeSetup]] = defaultdict(list)
    for s in setups:
        groups[(s.symbol.upper(), s.direction.upper())].append(s)

    out: list[TradeSetup] = []
    superseded: list[tuple[TradeSetup, TradeSetup]] = []
    for (_sym, _side), lst in groups.items():
        if len(lst) == 1:
            out.append(lst[0])
            continue
        best = max(lst, key=lambda x: (tier_rank(x.setup_tier), x.confidence_score))
        names = [x.strategy_name for x in lst]
        meta = dict(best.metadata or {})
        if meta.get("agreeing_engines") != names:
            if "agreement" not in " ".join(best.reasons):
                best.confidence_score = min(98, best.confidence_score + 4 * (len(lst) - 1))
                best.reasons = list(best.reasons) + [f"agreement:{','.join(names)}"]
            meta["agreeing_engines"] = names
            meta["has_location"] = meta.get("has_location") or any(
                n
                in {
                    "liquidity_sweep",
                    "sweep_retest",
                    "breakout_retest",
                    "opening_range",
                }
                for n in names
            )
            best.metadata = meta
        out.append(best)
        for x in lst:
            if x is best:
                continue
            superseded.append((x, best))
    return out, superseded


def rank_setups(setups: list[TradeSetup]) -> list[TradeSetup]:
    return sorted(
        setups,
        key=lambda s: (tier_rank(s.setup_tier), s.confidence_score, s.expected_r),
        reverse=True,
    )


def select_executable(
    setups: list[TradeSetup], cfg: dict[str, Any]
) -> list[TradeSetup]:
    """All A+/A (per config) setups after agreement merge — caller applies portfolio caps."""
    kept, _superseded = boost_for_agreement(setups)
    for s in kept:
        s.setup_tier = assign_tier_for_setup(s, cfg)
    executable = [s for s in kept if can_execute(s, cfg)]
    return rank_setups(executable)


def select_executable_detailed(
    setups: list[TradeSetup], cfg: dict[str, Any]
) -> tuple[list[TradeSetup], list[tuple[TradeSetup, TradeSetup]]]:
    """Like select_executable but also returns superseded (loser, winner) pairs."""
    # Re-tier all first for fair comparison
    for s in setups:
        s.setup_tier = assign_tier_for_setup(s, cfg)
    kept, superseded = boost_for_agreement(setups)
    for s in kept:
        s.setup_tier = assign_tier_for_setup(s, cfg)
    executable = rank_setups([s for s in kept if can_execute(s, cfg)])
    # Only report superseded when loser was itself executable-tier
    aa_superseded = [
        (loser, winner)
        for loser, winner in superseded
        if can_execute(loser, cfg) or str(loser.setup_tier).upper() in {"A", "A+"}
    ]
    return executable, aa_superseded


def select_journal_only(setups: list[TradeSetup], cfg: dict[str, Any]) -> list[TradeSetup]:
    return [s for s in setups if not can_execute(s, cfg)]
