"""Terminal execution decisions for A/A+ — never silent disappear."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


TERMINAL_EXECUTED = "EXECUTED"
TERMINAL_REJECTED = "REJECTED"


@dataclass
class ExecutionDecision:
    symbol: str
    strategy: str
    direction: str
    tier: str
    local_score: Any
    global_score: Any
    setup_id: str
    market_timestamp: str
    decision: str  # EXECUTED | REJECTED
    reason: str
    order_id: Optional[str] = None
    cycle_ts: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    config_version: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ExecutionDecisionLedger:
    def __init__(self, path: str | Path = "data/execution_decisions.jsonl"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._cycle: list[ExecutionDecision] = []

    def begin_cycle(self) -> None:
        self._cycle = []

    def record(self, d: ExecutionDecision) -> ExecutionDecision:
        self._cycle.append(d)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(d.to_dict(), default=str) + "\n")
        return d

    def reject(
        self,
        setup: Any,
        reason: str,
        *,
        config_version: str | None = None,
    ) -> ExecutionDecision:
        meta = getattr(setup, "metadata", None) or {}
        return self.record(
            ExecutionDecision(
                symbol=str(getattr(setup, "symbol", "")),
                strategy=str(
                    getattr(setup, "strategy_name", None)
                    or getattr(setup, "strategy", "")
                    or ""
                ),
                direction=str(
                    getattr(setup, "direction", None)
                    or getattr(setup, "side", "")
                    or ""
                ),
                tier=str(getattr(setup, "setup_tier", "") or ""),
                local_score=meta.get("strategy_local_score"),
                global_score=meta.get("global_score"),
                setup_id=str(meta.get("setup_id") or meta.get("setup_fingerprint") or ""),
                market_timestamp=str(getattr(setup, "market_timestamp", "") or ""),
                decision=TERMINAL_REJECTED,
                reason=reason,
                config_version=config_version or meta.get("config_version"),
            )
        )

    def executed(
        self,
        setup: Any,
        order_id: str,
        *,
        config_version: str | None = None,
    ) -> ExecutionDecision:
        meta = getattr(setup, "metadata", None) or {}
        return self.record(
            ExecutionDecision(
                symbol=str(getattr(setup, "symbol", "")),
                strategy=str(getattr(setup, "strategy_name", "") or ""),
                direction=str(
                    getattr(setup, "direction", None)
                    or getattr(setup, "side", "")
                    or ""
                ),
                tier=str(getattr(setup, "setup_tier", "") or ""),
                local_score=meta.get("strategy_local_score"),
                global_score=meta.get("global_score"),
                setup_id=str(meta.get("setup_id") or meta.get("setup_fingerprint") or ""),
                market_timestamp=str(getattr(setup, "market_timestamp", "") or ""),
                decision=TERMINAL_EXECUTED,
                reason="EXECUTED",
                order_id=order_id,
                config_version=config_version or meta.get("config_version"),
            )
        )

    def unresolved(self, setups: list[Any]) -> list[Any]:
        """Return A/A+ setups in this cycle without a terminal decision."""
        resolved = {
            (
                d.symbol.upper(),
                d.strategy,
                d.direction.upper(),
                d.setup_id,
            )
            for d in self._cycle
        }
        missing = []
        for s in setups:
            tier = str(getattr(s, "setup_tier", "") or "").upper()
            if tier not in {"A", "A+"}:
                continue
            meta = getattr(s, "metadata", None) or {}
            key = (
                str(s.symbol).upper(),
                str(s.strategy_name),
                str(s.direction).upper(),
                str(meta.get("setup_id") or meta.get("setup_fingerprint") or ""),
            )
            if key not in resolved:
                missing.append(s)
        return missing

    def assert_all_resolved(self, setups: list[Any]) -> None:
        missing = self.unresolved(setups)
        if missing:
            detail = ", ".join(
                f"{s.symbol}/{s.strategy_name}/{s.setup_tier}" for s in missing
            )
            raise RuntimeError(f"UNRESOLVED_EXECUTABLE_CANDIDATE: {detail}")

    def latest(self, n: int = 40) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        rows = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
        return list(reversed(rows[-n:]))
