from __future__ import annotations

import json

from agent.decision.evidence_gate import evaluate_paper_evidence


def _summary(*, n=50, wr=0.60, pf=1.50, expectancy=0.20):
    return {
        "all": {
            "n": n,
            "win_rate": wr,
            "profit_factor": pf,
            "expectancy_r": expectancy,
        },
        "latest_20pct": {
            "n": 10,
            "win_rate": 0.60,
            "profit_factor": 1.20,
            "expectancy_r": 0.05,
        },
    }


def _cfg(path):
    return {
        "paper_evidence_gate": {
            "registry_path": str(path),
            "required_sources": ["databento_locked_replay", "yahoo_locked_replay"],
            "min_n": 40,
            "min_win_rate": 0.55,
            "min_profit_factor": 1.30,
            "min_expectancy_r": 0.15,
            "latest_min_profit_factor": 1.0,
            "latest_min_expectancy_r": 0.0,
        }
    }


def test_dual_source_gate_requires_every_source(tmp_path):
    path = tmp_path / "evidence.json"
    path.write_text(
        json.dumps(
            {
                "databento_locked_replay": {"strategies": {"s": _summary()}},
                "yahoo_locked_replay": {
                    "strategies": {"s": _summary(expectancy=0.10)}
                },
            }
        ),
        encoding="utf-8",
    )
    decision = evaluate_paper_evidence("s", _cfg(path))
    assert decision.eligible is False
    assert "yahoo_locked_replay:expectancy_r" in decision.reason
    assert set(decision.metrics["sources"]) == {
        "databento_locked_replay",
        "yahoo_locked_replay",
    }


def test_dual_source_gate_passes_only_when_both_pass(tmp_path):
    path = tmp_path / "evidence.json"
    path.write_text(
        json.dumps(
            {
                "databento_locked_replay": {"strategies": {"s": _summary()}},
                "yahoo_locked_replay": {"strategies": {"s": _summary()}},
            }
        ),
        encoding="utf-8",
    )
    decision = evaluate_paper_evidence("s", _cfg(path))
    assert decision.eligible is True
    assert decision.reason == "EVIDENCE_GATE:PASS"
