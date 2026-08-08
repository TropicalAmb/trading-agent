from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from agent.strategy.ema_pullback import evaluate_ema_pullback
from agent.strategy.liquidity_sweep import evaluate_liquidity_sweep
from agent.strategy.sweep_retest import evaluate_sweep_retest
from agent.strategy.vwap_acceptance import evaluate_vwap_acceptance
from agent.strategy.vwap_orb import evaluate_vwap_orb

logger = logging.getLogger(__name__)


@dataclass
class ConfluenceSignal:
    symbol: str
    side: str
    entry: float
    stop: float
    target: float
    confidence: int
    reason: str
    ts: datetime
    risk_dollars: float
    reward_dollars: float
    voters: list[str]


class ConfluenceScanner:
    """August-2026 style: only trade when multiple engines agree on the same side.

    Raises selectivity (fewer trades, higher intended win rate) vs any single engine.
    """

    def __init__(self, cfg: dict[str, Any], bar_source):
        self.cfg = cfg
        self.bar_source = bar_source
        conf = cfg.get("confluence", {})
        self.min_agree = int(conf.get("min_engines_agree", 2))
        self.engines = list(
            conf.get(
                "engines",
                ["vwap_acceptance", "vwap_orb", "sweep_retest"],
            )
        )

    def _eval_one(self, name: str, symbol: str, bars, point_value: float):
        if name == "vwap_acceptance":
            return evaluate_vwap_acceptance(symbol, bars, self.cfg, point_value=point_value)
        if name == "vwap_orb":
            return evaluate_vwap_orb(symbol, bars, self.cfg, point_value=point_value)
        if name == "sweep_retest":
            return evaluate_sweep_retest(symbol, bars, self.cfg, point_value=point_value)
        if name == "liquidity_sweep":
            return evaluate_liquidity_sweep(symbol, bars, self.cfg, point_value=point_value)
        if name == "ema_pullback":
            return evaluate_ema_pullback(symbol, bars, self.cfg, point_value=point_value)
        return None

    def diagnose_votes(self) -> dict[str, list[str]]:
        """Per-symbol engine vote lines for the paper-view scan tape."""
        out: dict[str, list[str]] = {}
        for symbol in self.cfg.get("universe", {}).get("symbols", []):
            meta = self.cfg.get("instruments", {}).get(symbol, {})
            pv = float(meta.get("point_value", 5.0))
            try:
                bars = self.bar_source(symbol)
            except Exception as exc:
                out[symbol] = [f"data_error:{exc}"]
                continue
            lines: list[str] = []
            for name in self.engines:
                try:
                    sig = self._eval_one(name, symbol, bars, pv)
                except Exception as exc:
                    lines.append(f"{name}:ERR")
                    logger.exception("engine %s failed on %s", name, symbol)
                    continue
                if sig is None:
                    lines.append(f"{name}:—")
                else:
                    lines.append(f"{name}:{sig.side}@{sig.confidence}")
            out[symbol] = lines
        return out

    def scan_symbol(self, symbol: str) -> Optional[ConfluenceSignal]:
        meta = self.cfg.get("instruments", {}).get(symbol, {})
        pv = float(meta.get("point_value", 5.0))
        bars = self.bar_source(symbol)

        votes: dict[str, list[Any]] = {"BUY": [], "SELL": []}
        for name in self.engines:
            try:
                sig = self._eval_one(name, symbol, bars, pv)
            except Exception:
                logger.exception("engine %s failed on %s", name, symbol)
                continue
            if sig is None:
                continue
            votes[sig.side].append((name, sig))
            logger.info("confluence vote %s %s via %s conf=%s", symbol, sig.side, name, sig.confidence)

        best_side = None
        best_list: list[Any] = []
        for side, lst in votes.items():
            if len(lst) > len(best_list):
                best_side, best_list = side, lst

        if best_side is None or len(best_list) < self.min_agree:
            return None

        # Location/trend-first: at least one voter must be a real setup engine
        must_one = [
            str(x)
            for x in self.cfg.get("confluence", {}).get("must_include_one_of", [])
            or []
        ]
        if must_one:
            voters_tmp = [n for n, _ in best_list]
            if not any(v in must_one for v in voters_tmp):
                logger.info(
                    "%s confluence skipped — no core engine in %s (need one of %s)",
                    symbol,
                    voters_tmp,
                    must_one,
                )
                return None

        # Use the strictest (worst) stop and most conservative target among voters
        entries = [s.entry for _, s in best_list]
        stops = [s.stop for _, s in best_list]
        targets = [s.target for _, s in best_list]
        entry = float(sum(entries) / len(entries))
        if best_side == "BUY":
            stop = min(stops)
            target = min(targets)  # nearest target among bulls = conservative
            if target <= entry:
                target = entry + abs(entry - stop) * 2
        else:
            stop = max(stops)
            target = max(targets)
            if target >= entry:
                target = entry - abs(stop - entry) * 2

        risk_pts = abs(entry - stop)
        reward_pts = abs(target - entry)
        risk_dollars = risk_pts * pv
        reward_dollars = reward_pts * pv
        max_risk = float(self.cfg.get("confluence", {}).get("max_risk_dollars", 100))
        min_reward = float(self.cfg.get("confluence", {}).get("min_reward_dollars", 100))
        if risk_dollars > max_risk or reward_dollars < min_reward:
            logger.info(
                "%s confluence rejected sizing risk=$%.0f reward=$%.0f",
                symbol,
                risk_dollars,
                reward_dollars,
            )
            return None

        min_rr = float(self.cfg.get("confluence", {}).get("min_rr", 1.4))
        if risk_pts > 0 and (reward_pts / risk_pts) < min_rr:
            logger.info(
                "%s confluence rejected R:R %.2f < %.2f",
                symbol,
                reward_pts / risk_pts,
                min_rr,
            )
            return None

        confs = [s.confidence for _, s in best_list]
        # Bonus for agreement count
        confidence = min(98, int(sum(confs) / len(confs) + 8 * (len(best_list) - 1)))
        voters = [n for n, _ in best_list]
        # Extra confidence if location engine voted
        if any(v in {"liquidity_sweep", "sweep_retest", "ema_pullback"} for v in voters):
            confidence = min(98, confidence + 4)
        reason = f"{best_side} CONFLUENCE x{len(voters)} [{', '.join(voters)}] conf={confidence}"
        return ConfluenceSignal(
            symbol=symbol,
            side=best_side,
            entry=entry,
            stop=float(stop),
            target=float(target),
            confidence=confidence,
            reason=reason,
            ts=datetime.now(timezone.utc),
            risk_dollars=float(risk_dollars),
            reward_dollars=float(reward_dollars),
            voters=voters,
        )

    def scan_universe(self) -> list[ConfluenceSignal]:
        out: list[ConfluenceSignal] = []
        for sym in self.cfg.get("universe", {}).get("symbols", []):
            try:
                sig = self.scan_symbol(sym)
                if sig:
                    out.append(sig)
                    logger.info("%s", sig.reason)
            except Exception:
                logger.exception("confluence scan failed %s", sym)
        out.sort(key=lambda s: (len(s.voters), s.confidence), reverse=True)
        return out
