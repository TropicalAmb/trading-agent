"""Tier quantity + fit-to-risk hard cap."""

from __future__ import annotations

import yaml
from pathlib import Path

from agent.execution.sizing import fit_quantity_to_risk, resolve_trade_quantity

ROOT = Path(__file__).resolve().parents[1]


def _cfg() -> dict:
    return yaml.safe_load((ROOT / "config" / "settings.yaml").read_text(encoding="utf-8"))


def test_settings_multi_lot_targets():
    cfg = _cfg()
    assert cfg["quantity"]["default_quantity"] == 2
    assert cfg["quantity"]["quantity_by_tier"]["A+"] == 3
    assert cfg["quantity"]["quantity_by_tier"]["A"] == 2


def test_resolve_by_tier():
    cfg = _cfg()
    assert resolve_trade_quantity(cfg, symbol="MES", tier="A+") == 3
    assert resolve_trade_quantity(cfg, symbol="MES", tier="A") == 2


def test_fit_shrinks_under_hard_cap():
    # MES $5/pt, 20pt stop = $100/contract → 5 lots = $500 under $500; 6 would be $600
    assert (
        fit_quantity_to_risk(
            desired_qty=6,
            entry=100,
            stop=80,
            point_value=5.0,
            hard_cap_dollars=500,
        )
        == 5
    )


def test_fit_zero_when_one_contract_too_large():
    # ES $50/pt, 12pt stop = $600/contract > $500
    assert (
        fit_quantity_to_risk(
            desired_qty=2,
            entry=5000,
            stop=4988,
            point_value=50.0,
            hard_cap_dollars=500,
        )
        == 0
    )


def test_fit_allows_multi_on_micro_tight_stop():
    # MNQ $2/pt, 25pt = $50/contract → 5 lots under $500
    assert (
        fit_quantity_to_risk(
            desired_qty=5,
            entry=20000,
            stop=19975,
            point_value=2.0,
            hard_cap_dollars=500,
        )
        == 5
    )


def test_live_hard_cap_finite():
    from agent.execution.risk_budget import effective_max_risk_dollars

    cfg = _cfg()
    assert float(cfg["risk"]["max_risk_dollars_per_trade"]) > 0
    assert effective_max_risk_dollars(cfg) > 0
    assert effective_max_risk_dollars(cfg) <= float(cfg["risk"]["max_account_risk_per_trade"])


def test_fit_zero_cap_never_unlimited():
    # Misconfig hard_cap<=0 must NOT size unlimited — forces floor behavior
    q = fit_quantity_to_risk(
        desired_qty=3,
        entry=100,
        stop=99,
        point_value=5.0,
        hard_cap_dollars=0,
    )
    assert q >= 1  # $5 risk/contract under $250 floor → affordable
