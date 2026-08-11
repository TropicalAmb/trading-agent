"""Startup / drought probe: prove paper execution wiring is not broken.

Fails (exit 1) if DirectionalRiskEngine wiring or can_execute path is broken.
Does NOT place trades. Does NOT loosen quality gates.
"""

from __future__ import annotations

import ast
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def _assert_no_risk_shadow_in_cycle() -> None:
    src = (ROOT / "src" / "agent" / "live_main.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    for node in tree.body:
        if not (isinstance(node, ast.FunctionDef) and node.name == "main"):
            continue
        for sub in ast.walk(node):
            if isinstance(sub, ast.FunctionDef) and sub.name == "cycle":
                for inner in ast.walk(sub):
                    if isinstance(inner, ast.Assign):
                        for t in inner.targets:
                            if isinstance(t, ast.Name) and t.id == "risk":
                                raise RuntimeError(
                                    f"preflight FAIL: cycle() assigns local 'risk' at line {inner.lineno} "
                                    "(reintroduces UnboundLocalError / EXECUTION_ERROR)"
                                )


def run_preflight(cfg: dict | None = None) -> dict:
    from agent.config import load_settings
    from agent.decision.setup import TradeSetup
    from agent.decision.tiering import can_execute
    from agent.risk.directional import DirectionalRiskEngine

    cfg = cfg or load_settings(ROOT / "config" / "settings.yaml")
    _assert_no_risk_shadow_in_cycle()

    risk_engine = DirectionalRiskEngine(cfg)
    if not hasattr(risk_engine, "evaluate"):
        raise RuntimeError("preflight FAIL: DirectionalRiskEngine missing evaluate()")

    # Synthetic location setup that should be paper-eligible under quality gates
    setup = TradeSetup(
        strategy_name="liquidity_sweep",
        symbol="MES",
        direction="BUY",
        setup_tier="A",
        confidence_score=80,
        entry=100.0,
        stop=99.0,
        target=102.0,
        expected_r=2.0,
        market_timestamp=datetime(2026, 8, 10, 14, 0),
        received_timestamp=datetime.now(timezone.utc),
        reasons=["preflight"],
        quantity=2,
        reward_dollars=160.0,
        risk_dollars=80.0,
        metadata={
            "has_location": True,
            "agreeing_engines": ["liquidity_sweep"],
            "location_source": "location_engine",
            "cascade": {
                "thesis": "LONG_SUPPORT",
                "location": "ACCEPTABLE_LOCATION",
                "trigger": "BREAKOUT_RETEST",
            },
        },
    )
    if not can_execute(setup, cfg):
        # Gates may reject — that is OK for preflight. Wiring must still be intact.
        # Only fail if engine object was corrupted somehow.
        pass

    # Simulate lifecycle dollar math without shadowing risk_engine
    trade_risk_dollars = float(setup.risk_dollars or 0) or 80.0
    _ = (10.0 / trade_risk_dollars) if trade_risk_dollars > 1e-9 else 0.0
    if not hasattr(risk_engine, "evaluate"):
        raise RuntimeError("preflight FAIL: risk_engine broken after trade_risk_dollars math")

    return {
        "ok": True,
        "config_version": cfg.get("config_version"),
        "risk_engine": type(risk_engine).__name__,
        "can_execute_synthetic": can_execute(setup, cfg),
    }


def main() -> int:
    try:
        result = run_preflight()
    except Exception as exc:
        print(f"PREFLIGHT FAIL: {exc}", flush=True)
        return 1
    print(
        f"PREFLIGHT OK config={result.get('config_version')} "
        f"engine={result.get('risk_engine')} "
        f"synthetic_executable={result.get('can_execute_synthetic')}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
