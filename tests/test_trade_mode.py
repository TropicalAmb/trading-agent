from agent.trade_mode import apply_trade_mode, current_trade_mode


def test_active_until_unlock():
    cfg = {
        "growth_plan": {
            "default_mode": "active",
            "swing_unlock_realized_pnl": 2000,
            "active": {
                "max_hold_minutes": 90,
                "target_dollars": 120,
                "time_stop_only_if_losing": True,
            },
            "swing": {"max_hold_minutes": 480, "target_dollars": 200},
        },
        "schedule": {},
        "vwap_acceptance": {},
    }
    assert current_trade_mode(cfg, 100) == "active"
    apply_trade_mode(cfg, 100)
    assert cfg["schedule"]["max_hold_minutes"] == 90
    assert cfg["schedule"]["time_stop_only_if_losing"] is True
    assert cfg["vwap_acceptance"]["target_dollars"] == 120

    assert current_trade_mode(cfg, 2500) == "swing"
    apply_trade_mode(cfg, 2500)
    assert cfg["schedule"]["max_hold_minutes"] == 480
    assert cfg["vwap_acceptance"]["target_dollars"] == 200
