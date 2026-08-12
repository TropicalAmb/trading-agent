"""Rank and select TradeSetups across symbols — multi-trade when risk allows.

Empirical StrategyPerformanceRouter evidence ranks among executable tiers.
Global score remains metadata / secondary. Hard gates stay elsewhere.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Optional

from agent.decision.performance_router import (
    StrategyPerformanceRouter,
    empirical_rank_tuple,
    router_from_cfg,
)
from agent.decision.setup import TradeSetup
from agent.decision.tiering import assign_tier_for_setup, can_execute, tier_rank


def _rank_key(setup: TradeSetup, cfg: dict[str, Any]) -> tuple:
    profile = str(cfg.get("execution_profile") or "balanced").lower()
    v2 = bool((cfg.get("performance_router_v2") or {}).get("enabled", False))
    if v2:
        from agent.decision.performance_router_v2 import empirical_rank_tuple_v2

        return (empirical_rank_tuple_v2(setup, profile=profile), tier_rank(setup.setup_tier))
    return (empirical_rank_tuple(setup), tier_rank(setup.setup_tier))


def _is_research_only_setup(setup: TradeSetup, cfg: dict[str, Any]) -> bool:
    meta = setup.metadata or {}
    if meta.get("research_only"):
        return True
    research = {str(x) for x in (cfg.get("research_only_engines") or [])}
    if setup.strategy_name in research:
        return True
    # Lifecycle / cell SHADOW is not a research engine, but still non-paper
    if meta.get("execution_mode") == "SHADOW":
        return True
    return False


def _is_paper_agreement_candidate(setup: TradeSetup, cfg: dict[str, Any]) -> bool:
    """Tier/research gate for agreement winners — before execution_quality dollars/thesis.

    Full can_execute (reward/thesis/etc.) runs after sizing in the pipeline so
    quality rejects are ledgered instead of vanishing as 'NO CANDIDATE'.
    """
    if _is_research_only_setup(setup, cfg):
        return False
    meta = setup.metadata or {}
    if meta.get("hard_invalidations"):
        return False
    life = str(meta.get("lifecycle_state") or "ACTIVE")
    if life in {"SHADOW_ONLY", "HARD_PAUSED"}:
        return False
    health = str(
        meta.get("cell_health")
        or (meta.get("router_evidence") or {}).get("cell_health")
        or "ACTIVE"
    )
    if health in {"SHADOW_ONLY", "PAUSED_FOR_REVIEW", "HARD_PAUSED"}:
        return False
    minimum = str(cfg.get("tiering", {}).get("minimum_trade_tier", "A")).upper()
    allowed = {
        "A+": {"A+"},
        "A": {"A+", "A"},
        "B": {"A+", "A", "B"},
        "C": {"A+", "A", "B", "C"},
    }.get(minimum, {"A+", "A"})
    return setup.setup_tier in allowed


def boost_for_agreement(
    setups: list[TradeSetup],
    cfg: dict[str, Any] | None = None,
) -> tuple[list[TradeSetup], list[tuple[TradeSetup, TradeSetup]]]:
    """Keep best per symbol+side. Returns (kept, superseded pairs (loser, winner)).

    Research/shadow engines may agree (bonus) but must not steal the paper slot
    from an executable competitor — that produced zero fills after EMA went shadow.
    """
    cfg = cfg or {}
    groups: dict[tuple[str, str], list[TradeSetup]] = defaultdict(list)
    for s in setups:
        groups[(s.symbol.upper(), s.direction.upper())].append(s)

    out: list[TradeSetup] = []
    superseded: list[tuple[TradeSetup, TradeSetup]] = []
    for (_sym, _side), lst in groups.items():
        if len(lst) == 1:
            out.append(lst[0])
            continue
        names = [x.strategy_name for x in lst]
        paperable = [x for x in lst if not _is_research_only_setup(x, cfg)]
        pool = paperable if paperable else lst
        best = max(pool, key=lambda x: _rank_key(x, cfg))
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
                    "vwap_acceptance",
                    "liquidity_reversal",
                    "vwap_reclaim",
                    "vwap_mss",
                    "vwap_orb",
                    "cl_vwap_prox_momentum",
                    "nq_context_entry",
                }
                for n in names
            )
            meta["competitor_count"] = len(lst)
            best.metadata = meta
        out.append(best)
        for x in lst:
            if x is best:
                continue
            m = dict(x.metadata or {})
            m["nonselected_reason"] = f"AGREEMENT_SUPERSEDED_BY_{best.strategy_name}"
            m["selected_competitor"] = best.strategy_name
            x.metadata = m
            superseded.append((x, best))
    return out, superseded


def rank_setups(setups: list[TradeSetup], cfg: dict[str, Any] | None = None) -> list[TradeSetup]:
    cfg = cfg or {}
    return sorted(setups, key=lambda s: _rank_key(s, cfg), reverse=True)


def attach_router_evidence(
    setups: list[TradeSetup],
    cfg: dict[str, Any],
    router: StrategyPerformanceRouter | None = None,
) -> StrategyPerformanceRouter | None:
    rcfg = cfg.get("performance_router") or {}
    if not bool(rcfg.get("enabled", True)):
        return router
    v2cfg = cfg.get("performance_router_v2") or {}
    if bool(v2cfg.get("enabled", False)):
        from agent.decision.performance_router_v2 import router_v2_from_cfg
        from agent.learning.model import AdaptiveTradeQualityModel

        qm = None
        if bool((cfg.get("trade_quality_model") or {}).get("enabled", True)):
            qm = AdaptiveTradeQualityModel(
                models_dir=(cfg.get("trade_quality_model") or {}).get(
                    "models_dir", "data/learning/models"
                )
            )
        router = router or router_v2_from_cfg(cfg, quality_model=qm)
        # Optional cell health
        try:
            from agent.learning.health import StrategyHealthStore, cell_key

            hs = StrategyHealthStore(
                (cfg.get("trade_quality_model") or {}).get(
                    "health_path", "data/learning/strategy_cell_health.json"
                )
            )
            for s in setups:
                meta = dict(s.metadata or {})
                key = cell_key(
                    s.strategy_name,
                    s.symbol,
                    str(s.session or ""),
                    str(meta.get("regime") or ""),
                    s.direction,
                )
                meta["cell_health"] = hs.get(key)
                s.metadata = meta
                router.attach_v2(s, cfg)
        except Exception:
            for s in setups:
                router.attach_v2(s, cfg)
        return router

    router = router or router_from_cfg(cfg)
    for s in setups:
        router.attach(s, cfg)
    return router


def select_executable(
    setups: list[TradeSetup], cfg: dict[str, Any]
) -> list[TradeSetup]:
    attach_router_evidence(setups, cfg)
    kept, _superseded = boost_for_agreement(setups, cfg)
    for s in kept:
        s.setup_tier = assign_tier_for_setup(s, cfg)
    # Pre-quality paper candidates; caller must apply can_execute after sizing
    executable = [s for s in kept if _is_paper_agreement_candidate(s, cfg)]
    return rank_setups([s for s in executable if can_execute(s, cfg)], cfg)


def select_executable_detailed(
    setups: list[TradeSetup],
    cfg: dict[str, Any],
    *,
    router: Optional[StrategyPerformanceRouter] = None,
) -> tuple[list[TradeSetup], list[tuple[TradeSetup, TradeSetup]]]:
    for s in setups:
        s.setup_tier = assign_tier_for_setup(s, cfg)
    attach_router_evidence(setups, cfg, router=router)
    # Shadow-only v2 evidence + HC decisions (does not change paper ranking while v2 off)
    try:
        from agent.decision.hc_shadow import (
            attach_high_confidence_shadow_decisions,
            attach_model_evidence_shadow,
        )

        attach_model_evidence_shadow(setups, cfg)
    except Exception:
        pass
    kept, superseded = boost_for_agreement(setups, cfg)
    for s in kept:
        s.setup_tier = assign_tier_for_setup(s, cfg)
    # Return paper agreement winners before execution_quality so pipeline can
    # size then ledger EXECUTION_QUALITY:* rejects (thesis/reward/etc.).
    executable = rank_setups(
        [s for s in kept if _is_paper_agreement_candidate(s, cfg)], cfg
    )
    try:
        from agent.decision.hc_shadow import attach_high_confidence_shadow_decisions

        selected_ids = {
            str((s.metadata or {}).get("setup_id") or "")
            for s in executable
            if can_execute(s, cfg)
        }
        attach_high_confidence_shadow_decisions(
            kept, cfg, router_v1_selected_ids=selected_ids
        )
    except Exception:
        pass
    aa_superseded = [
        (loser, winner)
        for loser, winner in superseded
        if _is_paper_agreement_candidate(loser, cfg)
        or str(loser.setup_tier).upper() in {"A", "A+"}
    ]
    return executable, aa_superseded


def select_journal_only(setups: list[TradeSetup], cfg: dict[str, Any]) -> list[TradeSetup]:
    return [s for s in setups if not can_execute(s, cfg)]
