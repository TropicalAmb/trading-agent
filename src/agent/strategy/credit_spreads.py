from __future__ import annotations

import logging
from datetime import date
from typing import Any

from agent.management.scoring import score_candidate
from agent.market_data import MarketDataService
from agent.models import CreditSpreadCandidate, OptionLeg, Side, SpreadType

logger = logging.getLogger(__name__)


def _spread_width(spot: float, configured: float) -> float:
    """Use tighter widths on cheaper underlyings (e.g. SLV) while honoring config cap."""
    if spot < 50:
        return min(configured, 1.0)
    if spot < 200:
        return min(configured, 2.0)
    return configured


def _mids_by_strike(chain: list[dict[str, Any]], right: str) -> dict[float, float]:
    out: dict[float, float] = {}
    for row in chain:
        if row.get("right") != right:
            continue
        mid = row.get("mid")
        if mid is None or mid <= 0:
            continue
        out[float(row["strike"])] = float(mid)
    return out


def _nearest_strike(strikes: list[float], target: float) -> float | None:
    if not strikes:
        return None
    return min(strikes, key=lambda s: abs(s - target))


class CreditSpreadScanner:
    """Rule-based scanner producing defined-risk vertical credit spreads."""

    def __init__(self, market: MarketDataService, cfg: dict[str, Any]):
        self.market = market
        self.cfg = cfg

    def scan_symbol(self, symbol: str) -> list[CreditSpreadCandidate]:
        strat = self.cfg["strategy"]
        ctx = self.market.underlying_context(symbol)
        expiry, chain = self.market.chain_for_window(symbol)
        if expiry is None or not chain:
            return []

        min_iv = float(strat.get("min_iv_rank", 0))
        if ctx["iv_rank"] < min_iv:
            logger.info(
                "%s IV rank %.1f below min %.1f — skip",
                symbol,
                ctx["iv_rank"],
                min_iv,
            )
            return []

        candidates: list[CreditSpreadCandidate] = []
        use_trend = bool(strat.get("use_trend_filter", True))

        if strat.get("allow_put_credit", True):
            if not use_trend or ctx["bullish"]:
                candidates.extend(
                    self._build_put_credits(symbol, ctx, expiry, chain)
                )
        if strat.get("allow_call_credit", True):
            if not use_trend or ctx["bearish"]:
                candidates.extend(
                    self._build_call_credits(symbol, ctx, expiry, chain)
                )

        candidates.sort(key=lambda c: c.score, reverse=True)
        limit = int(strat.get("max_candidates_per_symbol", 3))
        return candidates[:limit]

    def scan_universe(self) -> list[CreditSpreadCandidate]:
        symbols = list(self.cfg.get("universe", {}).get("symbols", []))
        all_c: list[CreditSpreadCandidate] = []
        for symbol in symbols:
            try:
                found = self.scan_symbol(symbol)
                all_c.extend(found)
                logger.info("%s → %d candidates", symbol, len(found))
            except Exception:
                logger.exception("Scan failed for %s", symbol)
        all_c.sort(key=lambda c: c.score, reverse=True)
        return all_c

    def _build_put_credits(
        self,
        symbol: str,
        ctx: dict[str, Any],
        expiry: date,
        chain: list[dict[str, Any]],
    ) -> list[CreditSpreadCandidate]:
        strat = self.cfg["strategy"]
        spot = float(ctx["spot"])
        width = _spread_width(spot, float(strat["spread_width"]))
        otm_pct = float(strat["short_otm_pct"])
        min_credit = width * float(strat["min_credit_pct_of_width"])

        puts = _mids_by_strike(chain, "P")
        strikes = sorted(puts.keys())
        short_target = spot * (1 - otm_pct)
        short_strike = _nearest_strike([s for s in strikes if s < spot], short_target)
        if short_strike is None:
            return []
        long_strike = _nearest_strike(
            [s for s in strikes if s <= short_strike - width + 1e-9],
            short_strike - width,
        )
        if long_strike is None or long_strike >= short_strike:
            return []

        short_mid = puts[short_strike]
        long_mid = puts[long_strike]
        credit = short_mid - long_mid
        actual_width = short_strike - long_strike
        if credit < min_credit * (actual_width / width if width else 1):
            return []
        if credit <= 0 or actual_width <= 0:
            return []

        max_loss = (actual_width - credit) * 100
        dte = (expiry - date.today()).days
        cand = CreditSpreadCandidate(
            underlying=symbol,
            spread_type=SpreadType.PUT_CREDIT,
            short_leg=OptionLeg(
                symbol=symbol,
                expiry=expiry,
                strike=short_strike,
                right="P",
                action=Side.SELL,
                quantity=1,
            ),
            long_leg=OptionLeg(
                symbol=symbol,
                expiry=expiry,
                strike=long_strike,
                right="P",
                action=Side.BUY,
                quantity=1,
            ),
            width=actual_width,
            credit=credit,
            max_loss=max_loss,
            dte=dte,
            spot=spot,
            iv_rank=ctx["iv_rank"],
            trend_ok=bool(ctx["bullish"]),
            score=0.0,
            rationale_tags=["put_credit", "bullish_trend" if ctx["bullish"] else "no_trend"],
            quote_ts=ctx["quote_ts"],
        )
        cand.score = score_candidate(cand)
        if cand.score < float(strat.get("min_score", -1e5)):
            return []
        return [cand]

    def _build_call_credits(
        self,
        symbol: str,
        ctx: dict[str, Any],
        expiry: date,
        chain: list[dict[str, Any]],
    ) -> list[CreditSpreadCandidate]:
        strat = self.cfg["strategy"]
        spot = float(ctx["spot"])
        width = _spread_width(spot, float(strat["spread_width"]))
        otm_pct = float(strat["short_otm_pct"])
        min_credit = width * float(strat["min_credit_pct_of_width"])

        calls = _mids_by_strike(chain, "C")
        strikes = sorted(calls.keys())
        short_target = spot * (1 + otm_pct)
        short_strike = _nearest_strike([s for s in strikes if s > spot], short_target)
        if short_strike is None:
            return []
        long_strike = _nearest_strike(
            [s for s in strikes if s >= short_strike + width - 1e-9],
            short_strike + width,
        )
        if long_strike is None or long_strike <= short_strike:
            return []

        short_mid = calls[short_strike]
        long_mid = calls[long_strike]
        credit = short_mid - long_mid
        actual_width = long_strike - short_strike
        if credit < min_credit * (actual_width / width if width else 1):
            return []
        if credit <= 0 or actual_width <= 0:
            return []

        max_loss = (actual_width - credit) * 100
        dte = (expiry - date.today()).days
        cand = CreditSpreadCandidate(
            underlying=symbol,
            spread_type=SpreadType.CALL_CREDIT,
            short_leg=OptionLeg(
                symbol=symbol,
                expiry=expiry,
                strike=short_strike,
                right="C",
                action=Side.SELL,
                quantity=1,
            ),
            long_leg=OptionLeg(
                symbol=symbol,
                expiry=expiry,
                strike=long_strike,
                right="C",
                action=Side.BUY,
                quantity=1,
            ),
            width=actual_width,
            credit=credit,
            max_loss=max_loss,
            dte=dte,
            spot=spot,
            iv_rank=ctx["iv_rank"],
            trend_ok=bool(ctx["bearish"]),
            score=0.0,
            rationale_tags=["call_credit", "bearish_trend" if ctx["bearish"] else "no_trend"],
            quote_ts=ctx["quote_ts"],
        )
        cand.score = score_candidate(cand)
        if cand.score < float(strat.get("min_score", -1e5)):
            return []
        return [cand]
