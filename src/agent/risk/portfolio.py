"""Portfolio-level risk coordination across agents and symbols."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class ExposureIntent:
    agent_id: str
    symbol: str
    direction: str  # BUY | SELL
    quantity: int
    strategy: str
    setup_tier: str
    allow_duplicate: bool = False


@dataclass
class PortfolioState:
    """Open exposure from all agents sharing an account."""

    opens: list[dict[str, Any]] = field(default_factory=list)
    claimed: list[ExposureIntent] = field(default_factory=list)


class PortfolioCoordinator:
    """Prevent conflicting / duplicate exposure unless explicitly allowed.

    product_families: micro + full-size of same underlying (MES/ES, etc.)
    correlation_groups: cross-index opposite-direction blocks
    """

    def __init__(self, cfg: dict[str, Any]):
        self.cfg = cfg
        pc = cfg.get("portfolio", {})
        risk = cfg.get("risk", {})
        self.allow_opposite = bool(pc.get("allow_opposite_same_symbol", False))
        self.allow_duplicate = bool(pc.get("allow_duplicate_same_trade", False))
        self.block_opposite_correlated = bool(
            risk.get("block_opposite_correlated", True)
        )
        self.correlation_groups = list(
            risk.get("correlation_groups")
            or [["MES", "MNQ", "MYM", "M2K", "ES", "NQ"]]
        )
        # Named product families (micro ↔ full size = same opportunity)
        families = risk.get("product_families") or {
            "SP500": ["MES", "ES"],
            "NASDAQ": ["MNQ", "NQ"],
            "GOLD": ["MGC", "GC"],
            "CRUDE": ["MCL", "CL"],
        }
        self.product_families: list[set[str]] = [
            {str(x).upper() for x in members}
            for members in (families.values() if isinstance(families, dict) else families)
        ]
        self.max_same_direction_per_family = int(
            risk.get("max_same_direction_per_family", 1)
        )

    def _group_for(self, symbol: str) -> Optional[set[str]]:
        su = symbol.upper()
        for g in self.correlation_groups:
            gs = {str(x).upper() for x in g}
            if su in gs:
                return gs
        return None

    def _family_for(self, symbol: str) -> Optional[set[str]]:
        su = symbol.upper()
        for f in self.product_families:
            if su in f:
                return f
        return None

    def _all_exposures(self, state: PortfolioState) -> list[dict[str, Any]]:
        rows = list(state.opens)
        for c in state.claimed:
            rows.append(
                {
                    "symbol": c.symbol,
                    "side": c.direction,
                    "agent_id": c.agent_id,
                }
            )
        return rows

    def check(self, intent: ExposureIntent, state: PortfolioState) -> tuple[bool, str]:
        sym = intent.symbol.upper()
        side = intent.direction.upper()

        for p in state.opens:
            if str(p.get("symbol", "")).upper() != sym:
                continue
            open_side = str(p.get("side", "")).upper()
            if open_side == side and not (
                intent.allow_duplicate or self.allow_duplicate
            ):
                return False, f"duplicate exposure {sym} {side} already open"
            if open_side != side and not self.allow_opposite:
                return False, f"opposite exposure {sym} {open_side} vs {side}"

        for c in state.claimed:
            if c.symbol.upper() != sym:
                continue
            if c.direction.upper() == side and not (
                intent.allow_duplicate or self.allow_duplicate
            ):
                return False, f"duplicate same-cycle claim {sym} {side}"
            if c.direction.upper() != side and not self.allow_opposite:
                return False, f"opposite same-cycle claim {sym}"

        # Product family: MES long + ES long = same underlying opportunity
        family = self._family_for(sym)
        if family and not (intent.allow_duplicate or self.allow_duplicate):
            same_dir = 0
            for p in self._all_exposures(state):
                ps = str(p.get("symbol", "")).upper()
                if ps in family and str(p.get("side", "")).upper() == side:
                    same_dir += 1
            if same_dir >= self.max_same_direction_per_family:
                return (
                    False,
                    f"product family limit: {sorted(family)} already has "
                    f"{same_dir} {side} (max {self.max_same_direction_per_family})",
                )

        if self.block_opposite_correlated:
            group = self._group_for(sym)
            if group:
                for p in self._all_exposures(state):
                    ps = str(p.get("symbol", "")).upper()
                    if ps in group and ps != sym:
                        if str(p.get("side", "")).upper() != side:
                            return (
                                False,
                                f"opposite correlated {ps} {p.get('side')} vs {sym} {side}",
                            )

        return True, "ok"

    def claim(self, intent: ExposureIntent, state: PortfolioState) -> None:
        state.claimed.append(intent)
