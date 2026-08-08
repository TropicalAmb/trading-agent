"""Champion / challenger strategy versioning — no automatic promotion."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class VersionVerdict:
    strategy: str
    champion: str
    challenger: str
    challenger_trades: int
    promotion_candidate: bool
    reason: str


def resolve_execution_mode(
    cfg: dict[str, Any], strategy: str, version: str | None = None
) -> str:
    """Return ACTUAL or SHADOW for a strategy version."""
    sv = (cfg.get("strategy_versions") or {}).get(strategy) or {}
    champion = str(sv.get("champion") or f"{strategy}_v1")
    ver = version or champion
    if ver == champion:
        return "ACTUAL"
    challengers = [str(x) for x in (sv.get("challengers") or [])]
    if ver in challengers:
        return "SHADOW"
    return "ACTUAL"


def champion_name(cfg: dict[str, Any], strategy: str) -> str:
    sv = (cfg.get("strategy_versions") or {}).get(strategy) or {}
    return str(sv.get("champion") or f"{strategy}_v1")


def evaluate_promotion(
    cfg: dict[str, Any],
    *,
    strategy: str,
    champion_stats: dict[str, Any],
    challenger_stats: dict[str, Any],
) -> VersionVerdict:
    acfg = cfg.get("adaptive_analysis") or {}
    min_n = int(acfg.get("min_challenger_trades", 50))
    champ = champion_name(cfg, strategy)
    chall_list = (cfg.get("strategy_versions") or {}).get(strategy, {}).get("challengers") or []
    chall = str(chall_list[0]) if chall_list else f"{strategy}_v2"
    n = int(challenger_stats.get("trade_count") or 0)
    if n < min_n:
        return VersionVerdict(
            strategy, champ, chall, n, False, f"need {min_n} trades (have {n})"
        )
    ok = (
        float(challenger_stats.get("expectancy") or 0)
        > float(champion_stats.get("expectancy") or 0)
        and float(challenger_stats.get("profit_factor") or 0)
        > float(champion_stats.get("profit_factor") or 0)
        and float(challenger_stats.get("max_drawdown") or 0)
        <= float(champion_stats.get("max_drawdown") or 0) * 1.25 + 1e-9
    )
    return VersionVerdict(
        strategy,
        champ,
        chall,
        n,
        ok,
        "PROMOTION_CANDIDATE" if ok else "challenger not superior on PF/expectancy/DD",
    )
