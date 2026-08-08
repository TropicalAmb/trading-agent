"""Walk-forward research tooling — never auto-applies to production config."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class WalkForwardResult:
    params: dict[str, Any]
    training_metrics: dict[str, float]
    validation_metrics: dict[str, float]
    overfit_warning: bool
    note: str


def walk_forward(
    *,
    param_grid: list[dict[str, Any]],
    train_fn: Callable[[dict[str, Any]], dict[str, float]],
    valid_fn: Callable[[dict[str, Any]], dict[str, float]],
    train_metric: str = "expectancy",
) -> WalkForwardResult:
    """Pick best training params, score on validation; never writes settings.yaml."""
    if not param_grid:
        return WalkForwardResult({}, {}, {}, False, "empty grid")
    best = None
    best_train = None
    for p in param_grid:
        m = train_fn(p)
        if best is None or float(m.get(train_metric, -1e18)) > float(
            best_train.get(train_metric, -1e18)  # type: ignore[union-attr]
        ):
            best, best_train = p, m
    assert best is not None and best_train is not None
    val = valid_fn(best)
    overfit = float(best_train.get(train_metric, 0)) > float(val.get(train_metric, 0)) * 1.5 + 1e-9
    return WalkForwardResult(
        params=best,
        training_metrics=best_train,
        validation_metrics=val,
        overfit_warning=overfit,
        note="NOT APPLIED TO PRODUCTION — manual review required",
    )
