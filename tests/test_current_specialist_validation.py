from agent.research.current_specialist_validation import summarize_true_forward


def test_true_forward_uses_exact_stamp_and_current_strategies_only():
    state = {
        "closed_trades": [
            {
                "strategy_name": "nq_context_entry",
                "config_version": "current",
                "pnl_dollars": 100,
                "risk_dollars": 100,
                "opened_at": "2026-08-14T10:00:00",
            },
            {
                "strategy_name": "nq_context_entry",
                "config_version": "old",
                "pnl_dollars": -100,
                "risk_dollars": 100,
            },
            {
                "strategy_name": "breakout_retest",
                "config_version": "current",
                "pnl_dollars": -100,
                "risk_dollars": 100,
            },
            {
                "strategy_name": "nq_context_entry",
                "config_version": "current",
                "exit_reason": "tp1",
                "pnl_dollars": 50,
                "risk_dollars": 100,
            },
        ]
    }
    report = summarize_true_forward(state, "current")
    assert report["overall"]["n"] == 1
    assert report["overall"]["win_rate"] == 1.0
    assert report["strategies"]["nq_context_entry"]["n"] == 1
    assert report["strategies"]["cl_vwap_prox_momentum"]["n"] == 0


def test_true_forward_can_be_limited_to_current_active_book():
    state = {
        "closed_trades": [
            {
                "strategy_name": "vwap_rejection",
                "config_version": "current",
                "pnl_dollars": 100,
                "risk_dollars": 100,
            }
        ]
    }
    report = summarize_true_forward(
        state,
        "current",
        ("nq_context_entry", "cl_vwap_prox_momentum"),
    )
    assert report["overall"]["n"] == 0
    assert "vwap_rejection" not in report["strategies"]
