from __future__ import annotations

import logging
from typing import Any

from agent.broker.ibkr import BrokerClient
from agent.models import CreditSpreadCandidate, OrderResult

logger = logging.getLogger(__name__)


class ExecutionService:
    def __init__(self, broker: BrokerClient, cfg: dict[str, Any]):
        self.broker = broker
        self.cfg = cfg

    def execute(self, candidate: CreditSpreadCandidate) -> OrderResult:
        exec_cfg = self.cfg.get("execution", {})
        dry_run = bool(exec_cfg.get("dry_run", True))
        mode = self.cfg.get("mode", "paper")

        # Extra safety: never send live orders unless both flags allow
        if mode == "live" and not self.cfg.get("allow_live_trading"):
            return OrderResult(
                dry_run=True,
                submitted=False,
                status="BLOCKED",
                detail="live trading not allowed by env flag",
                candidate=candidate,
            )

        # In paper mode we may still dry_run depending on config
        force_dry = dry_run
        logger.info(
            "Executing %s %s qty=%s dry_run=%s",
            candidate.spread_type.value,
            candidate.underlying,
            candidate.contracts,
            force_dry,
        )
        raw = self.broker.place_credit_spread(candidate, dry_run=force_dry)
        return OrderResult(
            dry_run=bool(raw.get("dry_run", force_dry)),
            submitted=bool(raw.get("submitted")),
            order_id=raw.get("order_id"),
            status=str(raw.get("status", "")),
            detail=str(raw.get("detail", "")),
            candidate=candidate,
        )
