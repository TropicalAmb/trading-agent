"""Unified high-confidence futures research harness (research-only; not paper config)."""

from agent.research.harness.engine import ResearchEngine
from agent.research.harness.metrics import GATES, meets_gates, trade_stats

__all__ = ["ResearchEngine", "GATES", "meets_gates", "trade_stats"]
