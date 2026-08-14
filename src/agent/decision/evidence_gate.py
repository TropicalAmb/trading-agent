"""Fail-closed paper eligibility from a frozen validation artifact."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class PaperEvidenceDecision:
    eligible: bool
    reason: str
    strategy: str
    cohort: str
    source_path: str
    metrics: dict[str, Any]
    thresholds: dict[str, float | int]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _resolve_path(raw: str) -> Path:
    path = Path(raw)
    if path.is_absolute():
        return path
    cwd_path = Path.cwd() / path
    if cwd_path.exists():
        return cwd_path
    # .../src/agent/decision/evidence_gate.py -> repository root
    return Path(__file__).resolve().parents[3] / path


def evaluate_paper_evidence(
    strategy: str,
    cfg: dict[str, Any],
) -> PaperEvidenceDecision:
    gate = cfg.get("paper_evidence_gate") or {}
    cohort = str(gate.get("cohort") or "all")
    source = _resolve_path(
        str(
            gate.get("registry_path")
            or "data/current_specialist_validation/CURRENT_SPECIALIST_VALIDATION.json"
        )
    )
    thresholds: dict[str, float | int] = {
        "min_n": int(gate.get("min_n", 40)),
        "min_win_rate": float(gate.get("min_win_rate", 0.55)),
        "min_profit_factor": float(gate.get("min_profit_factor", 1.30)),
        "min_expectancy_r": float(gate.get("min_expectancy_r", 0.15)),
        "latest_min_profit_factor": float(gate.get("latest_min_profit_factor", 1.0)),
        "latest_min_expectancy_r": float(gate.get("latest_min_expectancy_r", 0.0)),
    }

    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except Exception as exc:
        return PaperEvidenceDecision(
            False,
            f"EVIDENCE_GATE:registry_unavailable:{type(exc).__name__}",
            strategy,
            cohort,
            str(source),
            {},
            thresholds,
        )

    strategy_rows = (
        ((payload.get("yahoo_locked_replay") or {}).get("strategies") or {}).get(strategy)
        or {}
    )
    metrics = dict(strategy_rows.get(cohort) or {})
    latest = dict(strategy_rows.get("latest_20pct") or {})
    if not metrics:
        return PaperEvidenceDecision(
            False,
            f"EVIDENCE_GATE:no_frozen_metrics:{strategy}",
            strategy,
            cohort,
            str(source),
            {},
            thresholds,
        )

    checks = (
        ("n", int(metrics.get("n") or 0), int(thresholds["min_n"])),
        (
            "win_rate",
            float(metrics.get("win_rate") or 0.0),
            float(thresholds["min_win_rate"]),
        ),
        (
            "profit_factor",
            float(metrics.get("profit_factor") or 0.0),
            float(thresholds["min_profit_factor"]),
        ),
        (
            "expectancy_r",
            float(metrics.get("expectancy_r") or 0.0),
            float(thresholds["min_expectancy_r"]),
        ),
        (
            "latest_profit_factor",
            float(latest.get("profit_factor") or 0.0),
            float(thresholds["latest_min_profit_factor"]),
        ),
        (
            "latest_expectancy_r",
            float(latest.get("expectancy_r") or 0.0),
            float(thresholds["latest_min_expectancy_r"]),
        ),
    )
    for name, actual, required in checks:
        if actual < required:
            return PaperEvidenceDecision(
                False,
                f"EVIDENCE_GATE:{name}={actual:.4f}<{required:.4f}",
                strategy,
                cohort,
                str(source),
                {**metrics, "latest_20pct": latest},
                thresholds,
            )
    return PaperEvidenceDecision(
        True,
        "EVIDENCE_GATE:PASS",
        strategy,
        cohort,
        str(source),
        {**metrics, "latest_20pct": latest},
        thresholds,
    )
