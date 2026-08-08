from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

from agent.models import (
    AccountSnapshot,
    AdvisorDecision,
    CreditSpreadCandidate,
    DecisionAction,
)

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """You are a conservative options trading advisor for a defined-risk credit-spread bot.
You may ONLY choose among the provided candidate spreads by index, or pass.
You must NEVER invent new strikes, symbols, sizes, or strategies.
You must NEVER suggest naked options.
Respond with JSON only:
{"action":"trade"|"pass","candidate_index":<int or null>,"rationale":"<short>"}
"""


class ClaudeAdvisor:
    def __init__(self, cfg: dict[str, Any]):
        self.cfg = cfg
        self.enabled = bool(cfg.get("advisor", {}).get("enabled", True))
        self.model = cfg.get("advisor", {}).get("model", "claude-sonnet-4-20250514")
        self.max_tokens = int(cfg.get("advisor", {}).get("max_tokens", 1024))
        self.require_claude = bool(cfg.get("advisor", {}).get("require_claude", False))

    def decide(
        self,
        candidates: list[CreditSpreadCandidate],
        account: AccountSnapshot,
    ) -> AdvisorDecision:
        if not candidates:
            return AdvisorDecision(action=DecisionAction.PASS, rationale="no candidates")

        if not self.enabled:
            return AdvisorDecision(
                action=DecisionAction.TRADE,
                candidate_index=0,
                rationale="advisor disabled; taking top-scored candidate",
            )

        api_key = os.getenv("ANTHROPIC_API_KEY", "")
        if not api_key:
            if self.require_claude:
                return AdvisorDecision(
                    action=DecisionAction.PASS,
                    rationale="ANTHROPIC_API_KEY missing and require_claude=true",
                )
            return AdvisorDecision(
                action=DecisionAction.TRADE,
                candidate_index=0,
                rationale="no API key; fallback to top-scored candidate",
            )

        payload = {
            "account": {
                "equity": account.equity,
                "open_underlyings": account.open_underlyings,
                "realized_pnl_today": account.realized_pnl_today,
            },
            "candidates": [
                {
                    "index": i,
                    "underlying": c.underlying,
                    "spread_type": c.spread_type.value,
                    "short_strike": c.short_leg.strike,
                    "long_strike": c.long_leg.strike,
                    "expiry": c.short_leg.expiry.isoformat(),
                    "credit": c.credit,
                    "width": c.width,
                    "max_loss": c.max_loss,
                    "dte": c.dte,
                    "score": c.score,
                    "iv_rank": c.iv_rank,
                    "tags": c.rationale_tags,
                }
                for i, c in enumerate(candidates)
            ],
        }

        try:
            import anthropic

            client = anthropic.Anthropic(api_key=api_key)
            msg = client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=SYSTEM_PROMPT,
                messages=[
                    {
                        "role": "user",
                        "content": (
                            "Select at most one candidate or pass.\n"
                            + json.dumps(payload)
                        ),
                    }
                ],
            )
            text = "".join(
                block.text for block in msg.content if getattr(block, "type", "") == "text"
            )
            parsed = self._parse_json(text)
            action = str(parsed.get("action", "pass")).lower()
            idx = parsed.get("candidate_index")
            if action == "trade":
                if idx is None or not isinstance(idx, int) or idx < 0 or idx >= len(candidates):
                    return AdvisorDecision(
                        action=DecisionAction.PASS,
                        rationale="Claude returned invalid candidate_index",
                        raw=parsed,
                    )
                return AdvisorDecision(
                    action=DecisionAction.TRADE,
                    candidate_index=idx,
                    rationale=str(parsed.get("rationale", "")),
                    raw=parsed,
                )
            return AdvisorDecision(
                action=DecisionAction.PASS,
                rationale=str(parsed.get("rationale", "pass")),
                raw=parsed,
            )
        except Exception as exc:
            logger.exception("Claude advisor failed: %s", exc)
            if self.require_claude:
                return AdvisorDecision(
                    action=DecisionAction.PASS,
                    rationale=f"advisor error: {exc}",
                )
            return AdvisorDecision(
                action=DecisionAction.TRADE,
                candidate_index=0,
                rationale=f"advisor error fallback to top candidate: {exc}",
            )

    @staticmethod
    def _parse_json(text: str) -> dict[str, Any]:
        text = text.strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if not match:
                raise
            return json.loads(match.group(0))
