"""Empirical-Bayes style shrinkage for small performance cells."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


@dataclass
class ShrunkRate:
    raw: float
    shrunk: float
    n: int
    prior_mean: float
    prior_strength: float


def shrink_rate(
    wins: int,
    n: int,
    *,
    prior_mean: float,
    prior_strength: float = 20.0,
) -> ShrunkRate:
    """Beta-binomial style shrink of win rate toward parent/global mean.

    An 8/10 cell is NOT treated as 80% when prior_strength is large.
    """
    n = max(int(n), 0)
    wins = max(0, min(int(wins), n))
    raw = (wins / n) if n else prior_mean
    ps = max(float(prior_strength), 1e-9)
    pm = min(max(float(prior_mean), 0.0), 1.0)
    shrunk = (wins + ps * pm) / (n + ps) if (n + ps) > 0 else pm
    return ShrunkRate(raw=raw, shrunk=shrunk, n=n, prior_mean=pm, prior_strength=ps)


def shrink_expectancy(
    rs: Sequence[float],
    *,
    prior_mean: float,
    prior_strength: float = 20.0,
) -> float:
    n = len(rs)
    if n <= 0:
        return float(prior_mean)
    raw = sum(rs) / n
    ps = max(float(prior_strength), 1e-9)
    return (n * raw + ps * prior_mean) / (n + ps)
