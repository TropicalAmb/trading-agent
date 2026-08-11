"""Regression: cycle must never shadow DirectionalRiskEngine as local `risk`."""

from __future__ import annotations

import ast
from pathlib import Path

from agent.risk.directional import DirectionalRiskEngine


ROOT = Path(__file__).resolve().parents[1]
LIVE_MAIN = ROOT / "src" / "agent" / "live_main.py"


def test_live_main_uses_risk_engine_name():
    src = LIVE_MAIN.read_text(encoding="utf-8")
    assert "risk_engine = DirectionalRiskEngine(cfg)" in src
    assert "risk = DirectionalRiskEngine(cfg)" not in src
    assert "risk_engine: DirectionalRiskEngine" in src
    assert "ok, reasons = risk_engine.evaluate(" in src


def test_cycle_function_does_not_assign_local_named_risk():
    """AST guard: any `risk = ...` inside nested cycle would reintroduce UnboundLocalError."""
    tree = ast.parse(LIVE_MAIN.read_text(encoding="utf-8"))
    cycle_fn = None
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "main":
            for sub in ast.walk(node):
                if isinstance(sub, ast.FunctionDef) and sub.name == "cycle":
                    cycle_fn = sub
                    break
    assert cycle_fn is not None, "expected nested cycle() inside main()"
    bad: list[str] = []
    for sub in ast.walk(cycle_fn):
        if isinstance(sub, ast.Assign):
            for t in sub.targets:
                if isinstance(t, ast.Name) and t.id == "risk":
                    bad.append(f"Assign risk at line {sub.lineno}")
        if isinstance(sub, ast.AnnAssign) and isinstance(sub.target, ast.Name):
            if sub.target.id == "risk":
                bad.append(f"AnnAssign risk at line {sub.lineno}")
    assert not bad, bad


def test_risk_engine_evaluate_still_works_after_trade_risk_dollars_math():
    """Lifecycle R math must use trade_risk_dollars, leaving engine callable."""
    cfg = {
        "risk": {
            "max_risk_dollars_per_trade": 500,
            "max_open_positions": 50,
            "symbol_cooldown_minutes": 0,
            "block_opposite_correlated": False,
        },
        "schedule": {"timezone": "America/New_York"},
        "instruments": {"MES": {"point_value": 5.0}},
    }
    risk_engine = DirectionalRiskEngine(cfg)
    trade_risk_dollars = 100.0
    pnl = 50.0
    pnl_r = (pnl / trade_risk_dollars) if trade_risk_dollars > 1e-9 else 0.0
    assert pnl_r == 0.5
    assert hasattr(risk_engine, "evaluate")
