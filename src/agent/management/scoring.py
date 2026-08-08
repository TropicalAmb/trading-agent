from __future__ import annotations

from agent.models import CreditSpreadCandidate


def score_candidate(c: CreditSpreadCandidate, *, min_pop_proxy: float = 0.55) -> float:
    """Higher is better. Combines yield, cushion, IV, and a crude POP proxy.

    Not a guarantee of edge — used only to rank already-valid candidates.
    """
    if c.width <= 0 or c.credit <= 0:
        return -1e9

    yield_frac = c.credit / c.width  # e.g. 0.20 = keep 20% of width
    # Distance of short strike from spot as % (more OTM ≈ higher POP proxy)
    if c.spread_type.value == "put_credit":
        otm = max(0.0, (c.spot - c.short_leg.strike) / c.spot)
    else:
        otm = max(0.0, (c.short_leg.strike - c.spot) / c.spot)

    # Rough POP proxy: further OTM + decent yield; capped
    pop_proxy = min(0.90, 0.50 + otm * 6.0)
    if pop_proxy < min_pop_proxy:
        return -1e6 + pop_proxy

    iv = (c.iv_rank or 50.0) / 100.0
    # Prefer selling richer vol, with enough yield, not too close to expiry noise
    dte_factor = 1.0 if 14 <= c.dte <= 35 else 0.85
    trend_bonus = 0.05 if c.trend_ok else 0.0

    # Expected-value style proxy: win*credit - lose*(width-credit)
    # Using pop_proxy as P(win) under the crude model
    ev_per_share = pop_proxy * c.credit - (1 - pop_proxy) * (c.width - c.credit)
    ev_score = ev_per_share / c.width

    return (
        1.5 * yield_frac
        + 1.2 * ev_score
        + 0.4 * iv
        + 0.3 * otm
        + trend_bonus
    ) * dte_factor
