from __future__ import annotations

from agent.research.long_history_strategy_validation import _current_gate, _long_gate


def _stats(n: int, wr: float, pf: float, expectancy: float) -> dict:
    return {
        "n": n,
        "wr": wr,
        "pf": pf,
        "expectancy_r": expectancy,
        "anti_cheat_ok": True,
    }


def test_long_gate_rejects_tiny_seventy_percent_sample() -> None:
    passing_headline = _stats(20, 0.80, 2.0, 0.5)
    passed, failures = _long_gate(passing_headline, passing_headline, passing_headline)
    assert not passed
    assert "all_n<100" in failures
    assert "holdout_n<30" in failures


def test_current_gate_requires_both_sources() -> None:
    paid = _stats(15, 0.80, 2.0, 0.4)
    yahoo = _stats(15, 0.60, 1.1, 0.05)
    passed, failures = _current_gate(paid, yahoo)
    assert not passed
    assert "independent_current_WR<70%" in failures


def test_current_gate_accepts_qualified_dual_source() -> None:
    qualified = _stats(15, 0.80, 2.0, 0.4)
    passed, failures = _current_gate(qualified, qualified)
    assert passed
    assert failures == []
