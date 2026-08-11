# VWAP + MSS Deep Research Report

Generated: 2026-08-09T17:23:17.165078+00:00

## A. RUNTIME
```json
{
  "config_version": "opt_v1",
  "paper_agent_running": true,
  "strategy_version": null,
  "risk": {
    "max_risk_dollars_per_trade": 500,
    "max_account_risk_per_trade": 500,
    "risk_per_trade_pct": 0.01
  },
  "quantity": {
    "default_quantity": 2,
    "max_quantity": 25,
    "quantity_by_tier": {
      "A+": 3,
      "A": 2
    },
    "quantity_by_symbol": {},
    "quantity_by_strategy": {},
    "quantity_by_agent_profile": {
      "balanced": 2,
      "momentum": 2,
      "liquidity": 2,
      "trend": 2
    }
  },
  "supervisor": {
    "ts": "2026-08-09T17:11:31.876804+00:00",
    "supervisor_pid": 60172,
    "agent_pid": 37872,
    "state": "running",
    "health": "healthy",
    "heartbeat_age_sec": 25.3,
    "supervisor_uptime_sec": 3403.4,
    "restart_count": 3,
    "restart_reason": "scheduler_heartbeat_stuck_4330s",
    "last_restart_timestamp": "2026-08-08T19:30:08.028087+00:00",
    "scheduler_warning_seconds": 90,
    "scheduler_stuck_seconds": 150
  },
  "supervisor_pid": 60172,
  "agent_pid": 37872,
  "latest_heartbeat_age_sec": 25.3,
  "blotter_heartbeat": "2026-08-09T17:11:06.624676+00:00",
  "last_paper_trade": {
    "id": "PAPER-00001",
    "ts": "2026-08-06T19:31:00.105104+00:00",
    "symbol": "MES",
    "side": "BUY",
    "qty": 1,
    "entry": 7740.0,
    "stop": 7720.0,
    "target": 7780.0,
    "status": "CLOSED",
    "source": "demo",
    "reason": "demo paper fill to verify Paper Trading View",
    "confidence": 99.0,
    "risk_dollars": 100.0,
    "reward_dollars": 200.0,
    "tv_price": null,
    "venue": "LOCAL_PAPER (not TradingView Paper Trading)",
    "opened_at": "2026-08-06T19:31:00.105104+00:00",
    "point_value": 5.0,
    "session": "unknown",
    "peak_favorable_pts": 0.0,
    "initial_stop": 7720.0,
    "closed_at": "2026-08-06T21:10:06.549609+00:00",
    "exit": 7731.75,
    "exit_reason": "time_stop",
    "pnl_dollars": -41.25,
    "hold_minutes": 99.11,
    "result": "LOSS"
  },
  "latest_paper_scan": "2026-08-08T17:02:28.750144+00:00"
}
```

## B. RESEARCH SCALE
```json
{
  "historical_range_1h": {
    "NQ": {
      "start": "2024-03-17 18:00:00-04:00",
      "end": "2026-08-07 16:00:00-04:00",
      "bars": 13681
    },
    "MNQ": {
      "start": "2024-03-17 18:00:00-04:00",
      "end": "2026-08-07 16:00:00-04:00",
      "bars": 13717
    },
    "ES": {
      "start": "2024-03-17 18:00:00-04:00",
      "end": "2026-08-07 16:00:00-04:00",
      "bars": 13683
    },
    "MES": {
      "start": "2024-03-17 18:00:00-04:00",
      "end": "2026-08-07 16:00:00-04:00",
      "bars": 13715
    },
    "GC": {
      "start": "2024-03-17 18:00:00-04:00",
      "end": "2026-08-07 16:00:00-04:00",
      "bars": 13718
    },
    "MGC": {
      "start": "2024-03-17 18:00:00-04:00",
      "end": "2026-08-07 16:00:00-04:00",
      "bars": 13720
    },
    "CL": {
      "start": "2024-03-17 18:00:00-04:00",
      "end": "2026-08-07 16:00:00-04:00",
      "bars": 13511
    },
    "MCL": {
      "start": "2024-03-17 18:00:00-04:00",
      "end": "2026-08-07 16:00:00-04:00",
      "bars": 13314
    }
  },
  "bars_total_approx": 217498,
  "strategy_variants_specified": 354,
  "configs_evaluated_after_prune": 258,
  "configs_pruned": 96,
  "train_trades_sum": 380256,
  "val_trades_sum": 161226,
  "final_oos_top": {
    "high_wr": 35,
    "balanced": 35,
    "high_exp": 35
  },
  "elapsed_sec": 698.9
}
```

## Q. FINAL VERDICT
**NO ROBUST >=65% CANDIDATE YET**

No FINAL holdout config met WR>=65%, PF>=1.5, E>=0.25R, n>=100, anti-cheat. Closest FINAL: {'n': 35, 'wins': 13, 'losses': 22, 'wr': 0.3714, 'wr_ci95': [0.2, 0.5429], 'pf': 0.589, 'expectancy_r': -0.2519, 'max_dd_r': -10.242, 'avg_win_r': 0.972, 'avg_loss_r': -0.975, 'med_win_r': 1.017, 'med_loss_r': -1.011, 'worst_r': -1.032, 'p95_loss_r': -1.019, 'trades_per_week': 1.41, 'longest_losing_streak': 5, 'anti_cheat_ok': True, 'anti_cheat_reasons': [], 'config': 'ny_1100_1200_mC_retest_R1.5'}

## C. VWAP+MSS RESULTS
### Baseline (DEV val)
```json
{
  "config": "base_mC_reclaim_R1.25",
  "train": {
    "n": 3035,
    "wins": 1294,
    "losses": 1741,
    "wr": 0.4264,
    "wr_ci95": [
      0.4082,
      0.4442
    ],
    "pf": 0.84,
    "expectancy_r": -0.089,
    "max_dd_r": -270.31,
    "avg_win_r": 1.1,
    "avg_loss_r": -0.973,
    "med_win_r": 1.221,
    "med_loss_r": -1.02,
    "worst_r": -1.224,
    "p95_loss_r": -1.077,
    "trades_per_week": 43.97,
    "longest_losing_streak": 14,
    "anti_cheat_ok": true,
    "anti_cheat_reasons": []
  },
  "val": {
    "n": 1301,
    "wins": 640,
    "losses": 661,
    "wr": 0.4919,
    "wr_ci95": [
      0.4672,
      0.5212
    ],
    "pf": 1.065,
    "expectancy_r": 0.0325,
    "max_dd_r": -44.568,
    "avg_win_r": 1.079,
    "avg_loss_r": -0.98,
    "med_win_r": 1.226,
    "med_loss_r": -1.019,
    "worst_r": -1.186,
    "p95_loss_r": -1.079,
    "trades_per_week": 42.69,
    "longest_losing_streak": 12,
    "anti_cheat_ok": true,
    "anti_cheat_reasons": []
  },
  "final": {
    "n": 1092,
    "wins": 500,
    "losses": 592,
    "wr": 0.4579,
    "wr_ci95": [
      0.4285,
      0.489
    ],
    "pf": 0.986,
    "expectancy_r": -0.0071,
    "max_dd_r": -58.289,
    "avg_win_r": 1.102,
    "avg_loss_r": -0.944,
    "med_win_r": 1.237,
    "med_loss_r": -1.009,
    "worst_r": -1.107,
    "p95_loss_r": -1.043,
    "trades_per_week": 43.22,
    "longest_losing_streak": 14,
    "anti_cheat_ok": true,
    "anti_cheat_reasons": []
  }
}
```
### Best high-WR (selected on VAL, FINAL metrics)
```json
{
  "config": "ny_1100_1200_mC_retest_R1.5",
  "spec": {
    "id": "ny_1100_1200_mC_retest_R1.5",
    "group": "ny_open",
    "mss_mode": "C",
    "vwap_mode": "retest",
    "target_r": 1.5,
    "entry_mode": "signal_close",
    "ny_window": "1100_1200",
    "need_disp": true
  },
  "train": {
    "n": 105,
    "wins": 45,
    "losses": 60,
    "wr": 0.4286,
    "wr_ci95": [
      0.3429,
      0.5333
    ],
    "pf": 0.891,
    "expectancy_r": -0.0553,
    "max_dd_r": -15.291,
    "avg_win_r": 1.056,
    "avg_loss_r": -0.889,
    "med_win_r": 1.052,
    "med_loss_r": -1.016,
    "worst_r": -1.053,
    "p95_loss_r": -1.039,
    "trades_per_week": 1.52,
    "longest_losing_streak": 9,
    "anti_cheat_ok": true,
    "anti_cheat_reasons": []
  },
  "val": {
    "n": 39,
    "wins": 24,
    "losses": 15,
    "wr": 0.6154,
    "wr_ci95": [
      0.4615,
      0.7436
    ],
    "pf": 2.122,
    "expectancy_r": 0.3468,
    "max_dd_r": -3.015,
    "avg_win_r": 1.066,
    "avg_loss_r": -0.804,
    "med_win_r": 1.156,
    "med_loss_r": -1.004,
    "worst_r": -1.03,
    "p95_loss_r": -1.029,
    "trades_per_week": 1.57,
    "longest_losing_streak": 3,
    "anti_cheat_ok": true,
    "anti_cheat_reasons": []
  },
  "final": {
    "n": 35,
    "wins": 13,
    "losses": 22,
    "wr": 0.3714,
    "wr_ci95": [
      0.2,
      0.5429
    ],
    "pf": 0.589,
    "expectancy_r": -0.2519,
    "max_dd_r": -10.242,
    "avg_win_r": 0.972,
    "avg_loss_r": -0.975,
    "med_win_r": 1.017,
    "med_loss_r": -1.011,
    "worst_r": -1.032,
    "p95_loss_r": -1.019,
    "trades_per_week": 1.41,
    "longest_losing_streak": 5,
    "anti_cheat_ok": true,
    "anti_cheat_reasons": []
  },
  "gates_met": false,
  "monte_carlo": {
    "n_sims": 10000,
    "status": "OK",
    "median_terminal_r": -9.01,
    "p05_terminal_r": -18.273,
    "p95_terminal_r": 0.996,
    "median_max_dd_r": -11.228,
    "p90_max_dd_r": -17.266,
    "p95_max_dd_r": -19.016,
    "prob_dd_ge_5r": 0.953,
    "prob_dd_ge_10r": 0.5982,
    "prob_dd_ge_15r": 0.2072,
    "prob_dd_ge_20r": 0.0306,
    "median_longest_losing_streak": 6,
    "p90_longest_losing_streak": 9,
    "p95_longest_losing_streak": 11
  },
  "by_symbol": {
    "NQ": {
      "n": 5,
      "wins": 3,
      "losses": 2,
      "wr": 0.6,
      "wr_ci95": [
        0.2,
        1.0
      ],
      "pf": 0.81,
      "expectancy_r": -0.0763,
      "max_dd_r": -1.628,
      "avg_win_r": 0.542,
      "avg_loss_r": -1.003,
      "med_win_r": 0.378,
      "med_loss_r": -1.003,
      "worst_r": -1.003,
      "p95_loss_r": -1.003,
      "trades_per_week": 0.28,
      "longest_losing_streak": 1,
      "anti_cheat_ok": true,
      "anti_cheat_reasons": []
    },
    "MNQ": {
      "n": 4,
      "wins": 2,
      "losses": 2,
      "wr": 0.5,
      "wr_ci95": [
        0.0,
        1.0
      ],
      "pf": 0.338,
      "expectancy_r": -0.332,
      "max_dd_r": -1.003,
      "avg_win_r": 0.339,
      "avg_loss_r": -1.003,
      "med_win_r": 0.339,
      "med_loss_r": -1.003,
      "worst_r": -1.003,
      "p95_loss_r": -1.003,
      "trades_per_week": 0.28,
      "longest_losing_streak": 1,
      "anti_cheat_ok": false,
      "anti_cheat_reasons": [
        "tiny_target_or_huge_stop"
      ]
    },
    "ES": {
      "n": 8,
      "wins": 3,
      "losses": 5,
      "wr": 0.375,
      "wr_ci95": [
        0.0,
        0.75
      ],
      "pf": 0.665,
      "expectancy_r": -0.2122,
      "max_dd_r": -3.043,
      "avg_win_r": 1.123,
      "avg_loss_r": -1.013,
      "med_win_r": 1.021,
      "med_loss_r": -1.013,
      "worst_r": -1.019,
      "p95_loss_r": -1.018,
      "trades_per_week": 0.32,
      "longest_losing_streak": 3,
      "anti_cheat_ok": true,
      "anti_cheat_reasons": []
    },
    "MES": {
      "n": 8,
      "wins": 2,
      "losses": 6,
      "wr": 0.25,
      "wr_ci95": [
        0.0,
        0.625
      ],
      "pf": 0.471,
      "expectancy_r": -0.3512,
      "max_dd_r": -4.294,
      "avg_win_r": 1.249,
      "avg_loss_r": -0.885,
      "med_win_r": 1.249,
      "med_loss_r": -1.013,
      "worst_r": -1.032,
      "p95_loss_r": -1.029,
      "trades_per_week": 0.38,
      "longest_losing_streak": 5,
      "anti_cheat_ok": true,
      "anti_cheat_reasons": []
    },
    "GC": {
      "n": 2,
      "wins": 1,
      "losses": 1,
      "wr": 0.5,
      "wr_ci95": [
        0.0,
        1.0
      ],
      "pf": 1.487,
      "expectancy_r": 0.245,
      "max_dd_r": -1.006,
      "avg_win_r": 1.496,
      "avg_loss_r": -1.006,
      "med_win_r": 1.496,
      "med_loss_r": -1.006,
      "worst_r": -1.006,
      "p95_loss_r": -1.006,
      "trades_per_week": 0.08,
      "longest_losing_streak": 1,
      "anti_cheat_ok": true,
      "anti_cheat_reasons": []
    },
    "MGC": {
      "n": 1,
      "wins": 0,
      "losses": 1,
      "wr": 0.0,
      "wr_ci95": [
        0.0,
        0.0
      ],
      "pf": 0.0,
      "expectancy_r": -1.0063,
      "max_dd_r": 0.0,
      "avg_win_r": 0.0,
      "avg_loss_r": -1.006,
      "med_win_r": 0.0,
      "med_loss_r": -1.006,
      "worst_r": -1.006,
      "p95_loss_r": -1.006,
      "trades_per_week": 1.0,
      "longest_losing_streak": 1,
      "anti_cheat_ok": true,
      "anti_cheat_reasons": []
    },
    "CL": {
      "n": 4,
      "wins": 1,
      "losses": 3,
      "wr": 0.25,
      "wr_ci95": [
        0.0,
        0.75
      ],
      "pf": 0.49,
      "expectancy_r": -0.3871,
      "max_dd_r": -1.014,
      "avg_win_r": 1.487,
      "avg_loss_r": -1.012,
      "med_win_r": 1.487,
      "med_loss_r": -1.013,
      "worst_r": -1.014,
      "p95_loss_r": -1.014,
      "trades_per_week": 1.56,
      "longest_losing_streak": 2,
      "anti_cheat_ok": true,
      "anti_cheat_reasons": []
    },
    "MCL": {
      "n": 3,
      "wins": 1,
      "losses": 2,
      "wr": 0.3333,
      "wr_ci95": [
        0.0,
        1.0
      ],
      "pf": 0.736,
      "expectancy_r": -0.1781,
      "max_dd_r": -1.008,
      "avg_win_r": 1.487,
      "avg_loss_r": -1.011,
      "med_win_r": 1.487,
      "med_loss_r": -1.011,
      "worst_r": -1.013,
      "p95_loss_r": -1.013,
      "trades_per_week": 1.17,
      "longest_losing_streak": 1,
      "anti_cheat_ok": true,
      "anti_cheat_reasons": []
    }
  },
  "by_session": {
    "NY_MID": {
      "n": 35,
      "wins": 13,
      "losses": 22,
      "wr": 0.3714,
      "wr_ci95": [
        0.2,
        0.5429
      ],
      "pf": 0.589,
      "expectancy_r": -0.2519,
      "max_dd_r": -10.242,
      "avg_win_r": 0.972,
      "avg_loss_r": -0.975,
      "med_win_r": 1.017,
      "med_loss_r": -1.011,
      "worst_r": -1.032,
      "p95_loss_r": -1.019,
      "trades_per_week": 1.41,
      "longest_losing_streak": 5,
      "anti_cheat_ok": true,
      "anti_cheat_reasons": []
    }
  },
  "final_trades_n": 35
}
```
### Best balanced
```json
{
  "config": "ny_1100_1200_mC_retest_R1.5",
  "spec": {
    "id": "ny_1100_1200_mC_retest_R1.5",
    "group": "ny_open",
    "mss_mode": "C",
    "vwap_mode": "retest",
    "target_r": 1.5,
    "entry_mode": "signal_close",
    "ny_window": "1100_1200",
    "need_disp": true
  },
  "train": {
    "n": 105,
    "wins": 45,
    "losses": 60,
    "wr": 0.4286,
    "wr_ci95": [
      0.3429,
      0.5333
    ],
    "pf": 0.891,
    "expectancy_r": -0.0553,
    "max_dd_r": -15.291,
    "avg_win_r": 1.056,
    "avg_loss_r": -0.889,
    "med_win_r": 1.052,
    "med_loss_r": -1.016,
    "worst_r": -1.053,
    "p95_loss_r": -1.039,
    "trades_per_week": 1.52,
    "longest_losing_streak": 9,
    "anti_cheat_ok": true,
    "anti_cheat_reasons": []
  },
  "val": {
    "n": 39,
    "wins": 24,
    "losses": 15,
    "wr": 0.6154,
    "wr_ci95": [
      0.4615,
      0.7436
    ],
    "pf": 2.122,
    "expectancy_r": 0.3468,
    "max_dd_r": -3.015,
    "avg_win_r": 1.066,
    "avg_loss_r": -0.804,
    "med_win_r": 1.156,
    "med_loss_r": -1.004,
    "worst_r": -1.03,
    "p95_loss_r": -1.029,
    "trades_per_week": 1.57,
    "longest_losing_streak": 3,
    "anti_cheat_ok": true,
    "anti_cheat_reasons": []
  },
  "final": {
    "n": 35,
    "wins": 13,
    "losses": 22,
    "wr": 0.3714,
    "wr_ci95": [
      0.2,
      0.5429
    ],
    "pf": 0.589,
    "expectancy_r": -0.2519,
    "max_dd_r": -10.242,
    "avg_win_r": 0.972,
    "avg_loss_r": -0.975,
    "med_win_r": 1.017,
    "med_loss_r": -1.011,
    "worst_r": -1.032,
    "p95_loss_r": -1.019,
    "trades_per_week": 1.41,
    "longest_losing_streak": 5,
    "anti_cheat_ok": true,
    "anti_cheat_reasons": []
  },
  "gates_met": false,
  "monte_carlo": {
    "n_sims": 10000,
    "status": "OK",
    "median_terminal_r": -9.01,
    "p05_terminal_r": -18.273,
    "p95_terminal_r": 0.996,
    "median_max_dd_r": -11.228,
    "p90_max_dd_r": -17.266,
    "p95_max_dd_r": -19.016,
    "prob_dd_ge_5r": 0.953,
    "prob_dd_ge_10r": 0.5982,
    "prob_dd_ge_15r": 0.2072,
    "prob_dd_ge_20r": 0.0306,
    "median_longest_losing_streak": 6,
    "p90_longest_losing_streak": 9,
    "p95_longest_losing_streak": 11
  },
  "by_symbol": {
    "NQ": {
      "n": 5,
      "wins": 3,
      "losses": 2,
      "wr": 0.6,
      "wr_ci95": [
        0.2,
        1.0
      ],
      "pf": 0.81,
      "expectancy_r": -0.0763,
      "max_dd_r": -1.628,
      "avg_win_r": 0.542,
      "avg_loss_r": -1.003,
      "med_win_r": 0.378,
      "med_loss_r": -1.003,
      "worst_r": -1.003,
      "p95_loss_r": -1.003,
      "trades_per_week": 0.28,
      "longest_losing_streak": 1,
      "anti_cheat_ok": true,
      "anti_cheat_reasons": []
    },
    "MNQ": {
      "n": 4,
      "wins": 2,
      "losses": 2,
      "wr": 0.5,
      "wr_ci95": [
        0.0,
        1.0
      ],
      "pf": 0.338,
      "expectancy_r": -0.332,
      "max_dd_r": -1.003,
      "avg_win_r": 0.339,
      "avg_loss_r": -1.003,
      "med_win_r": 0.339,
      "med_loss_r": -1.003,
      "worst_r": -1.003,
      "p95_loss_r": -1.003,
      "trades_per_week": 0.28,
      "longest_losing_streak": 1,
      "anti_cheat_ok": false,
      "anti_cheat_reasons": [
        "tiny_target_or_huge_stop"
      ]
    },
    "ES": {
      "n": 8,
      "wins": 3,
      "losses": 5,
      "wr": 0.375,
      "wr_ci95": [
        0.0,
        0.75
      ],
      "pf": 0.665,
      "expectancy_r": -0.2122,
      "max_dd_r": -3.043,
      "avg_win_r": 1.123,
      "avg_loss_r": -1.013,
      "med_win_r": 1.021,
      "med_loss_r": -1.013,
      "worst_r": -1.019,
      "p95_loss_r": -1.018,
      "trades_per_week": 0.32,
      "longest_losing_streak": 3,
      "anti_cheat_ok": true,
      "anti_cheat_reasons": []
    },
    "MES": {
      "n": 8,
      "wins": 2,
      "losses": 6,
      "wr": 0.25,
      "wr_ci95": [
        0.0,
        0.625
      ],
      "pf": 0.471,
      "expectancy_r": -0.3512,
      "max_dd_r": -4.294,
      "avg_win_r": 1.249,
      "avg_loss_r": -0.885,
      "med_win_r": 1.249,
      "med_loss_r": -1.013,
      "worst_r": -1.032,
      "p95_loss_r": -1.029,
      "trades_per_week": 0.38,
      "longest_losing_streak": 5,
      "anti_cheat_ok": true,
      "anti_cheat_reasons": []
    },
    "GC": {
      "n": 2,
      "wins": 1,
      "losses": 1,
      "wr": 0.5,
      "wr_ci95": [
        0.0,
        1.0
      ],
      "pf": 1.487,
      "expectancy_r": 0.245,
      "max_dd_r": -1.006,
      "avg_win_r": 1.496,
      "avg_loss_r": -1.006,
      "med_win_r": 1.496,
      "med_loss_r": -1.006,
      "worst_r": -1.006,
      "p95_loss_r": -1.006,
      "trades_per_week": 0.08,
      "longest_losing_streak": 1,
      "anti_cheat_ok": true,
      "anti_cheat_reasons": []
    },
    "MGC": {
      "n": 1,
      "wins": 0,
      "losses": 1,
      "wr": 0.0,
      "wr_ci95": [
        0.0,
        0.0
      ],
      "pf": 0.0,
      "expectancy_r": -1.0063,
      "max_dd_r": 0.0,
      "avg_win_r": 0.0,
      "avg_loss_r": -1.006,
      "med_win_r": 0.0,
      "med_loss_r": -1.006,
      "worst_r": -1.006,
      "p95_loss_r": -1.006,
      "trades_per_week": 1.0,
      "longest_losing_streak": 1,
      "anti_cheat_ok": true,
      "anti_cheat_reasons": []
    },
    "CL": {
      "n": 4,
      "wins": 1,
      "losses": 3,
      "wr": 0.25,
      "wr_ci95": [
        0.0,
        0.75
      ],
      "pf": 0.49,
      "expectancy_r": -0.3871,
      "max_dd_r": -1.014,
      "avg_win_r": 1.487,
      "avg_loss_r": -1.012,
      "med_win_r": 1.487,
      "med_loss_r": -1.013,
      "worst_r": -1.014,
      "p95_loss_r": -1.014,
      "trades_per_week": 1.56,
      "longest_losing_streak": 2,
      "anti_cheat_ok": true,
      "anti_cheat_reasons": []
    },
    "MCL": {
      "n": 3,
      "wins": 1,
      "losses": 2,
      "wr": 0.3333,
      "wr_ci95": [
        0.0,
        1.0
      ],
      "pf": 0.736,
      "expectancy_r": -0.1781,
      "max_dd_r": -1.008,
      "avg_win_r": 1.487,
      "avg_loss_r": -1.011,
      "med_win_r": 1.487,
      "med_loss_r": -1.011,
      "worst_r": -1.013,
      "p95_loss_r": -1.013,
      "trades_per_week": 1.17,
      "longest_losing_streak": 1,
      "anti_cheat_ok": true,
      "anti_cheat_reasons": []
    }
  },
  "by_session": {
    "NY_MID": {
      "n": 35,
      "wins": 13,
      "losses": 22,
      "wr": 0.3714,
      "wr_ci95": [
        0.2,
        0.5429
      ],
      "pf": 0.589,
      "expectancy_r": -0.2519,
      "max_dd_r": -10.242,
      "avg_win_r": 0.972,
      "avg_loss_r": -0.975,
      "med_win_r": 1.017,
      "med_loss_r": -1.011,
      "worst_r": -1.032,
      "p95_loss_r": -1.019,
      "trades_per_week": 1.41,
      "longest_losing_streak": 5,
      "anti_cheat_ok": true,
      "anti_cheat_reasons": []
    }
  },
  "final_trades_n": 35
}
```
### Best high-expectancy
```json
{
  "config": "ny_1100_1200_mC_retest_R1.5",
  "spec": {
    "id": "ny_1100_1200_mC_retest_R1.5",
    "group": "ny_open",
    "mss_mode": "C",
    "vwap_mode": "retest",
    "target_r": 1.5,
    "entry_mode": "signal_close",
    "ny_window": "1100_1200",
    "need_disp": true
  },
  "train": {
    "n": 105,
    "wins": 45,
    "losses": 60,
    "wr": 0.4286,
    "wr_ci95": [
      0.3429,
      0.5333
    ],
    "pf": 0.891,
    "expectancy_r": -0.0553,
    "max_dd_r": -15.291,
    "avg_win_r": 1.056,
    "avg_loss_r": -0.889,
    "med_win_r": 1.052,
    "med_loss_r": -1.016,
    "worst_r": -1.053,
    "p95_loss_r": -1.039,
    "trades_per_week": 1.52,
    "longest_losing_streak": 9,
    "anti_cheat_ok": true,
    "anti_cheat_reasons": []
  },
  "val": {
    "n": 39,
    "wins": 24,
    "losses": 15,
    "wr": 0.6154,
    "wr_ci95": [
      0.4615,
      0.7436
    ],
    "pf": 2.122,
    "expectancy_r": 0.3468,
    "max_dd_r": -3.015,
    "avg_win_r": 1.066,
    "avg_loss_r": -0.804,
    "med_win_r": 1.156,
    "med_loss_r": -1.004,
    "worst_r": -1.03,
    "p95_loss_r": -1.029,
    "trades_per_week": 1.57,
    "longest_losing_streak": 3,
    "anti_cheat_ok": true,
    "anti_cheat_reasons": []
  },
  "final": {
    "n": 35,
    "wins": 13,
    "losses": 22,
    "wr": 0.3714,
    "wr_ci95": [
      0.2,
      0.5429
    ],
    "pf": 0.589,
    "expectancy_r": -0.2519,
    "max_dd_r": -10.242,
    "avg_win_r": 0.972,
    "avg_loss_r": -0.975,
    "med_win_r": 1.017,
    "med_loss_r": -1.011,
    "worst_r": -1.032,
    "p95_loss_r": -1.019,
    "trades_per_week": 1.41,
    "longest_losing_streak": 5,
    "anti_cheat_ok": true,
    "anti_cheat_reasons": []
  },
  "gates_met": false,
  "monte_carlo": {
    "n_sims": 10000,
    "status": "OK",
    "median_terminal_r": -9.01,
    "p05_terminal_r": -18.273,
    "p95_terminal_r": 0.996,
    "median_max_dd_r": -11.228,
    "p90_max_dd_r": -17.266,
    "p95_max_dd_r": -19.016,
    "prob_dd_ge_5r": 0.953,
    "prob_dd_ge_10r": 0.5982,
    "prob_dd_ge_15r": 0.2072,
    "prob_dd_ge_20r": 0.0306,
    "median_longest_losing_streak": 6,
    "p90_longest_losing_streak": 9,
    "p95_longest_losing_streak": 11
  },
  "by_symbol": {
    "NQ": {
      "n": 5,
      "wins": 3,
      "losses": 2,
      "wr": 0.6,
      "wr_ci95": [
        0.2,
        1.0
      ],
      "pf": 0.81,
      "expectancy_r": -0.0763,
      "max_dd_r": -1.628,
      "avg_win_r": 0.542,
      "avg_loss_r": -1.003,
      "med_win_r": 0.378,
      "med_loss_r": -1.003,
      "worst_r": -1.003,
      "p95_loss_r": -1.003,
      "trades_per_week": 0.28,
      "longest_losing_streak": 1,
      "anti_cheat_ok": true,
      "anti_cheat_reasons": []
    },
    "MNQ": {
      "n": 4,
      "wins": 2,
      "losses": 2,
      "wr": 0.5,
      "wr_ci95": [
        0.0,
        1.0
      ],
      "pf": 0.338,
      "expectancy_r": -0.332,
      "max_dd_r": -1.003,
      "avg_win_r": 0.339,
      "avg_loss_r": -1.003,
      "med_win_r": 0.339,
      "med_loss_r": -1.003,
      "worst_r": -1.003,
      "p95_loss_r": -1.003,
      "trades_per_week": 0.28,
      "longest_losing_streak": 1,
      "anti_cheat_ok": false,
      "anti_cheat_reasons": [
        "tiny_target_or_huge_stop"
      ]
    },
    "ES": {
      "n": 8,
      "wins": 3,
      "losses": 5,
      "wr": 0.375,
      "wr_ci95": [
        0.0,
        0.75
      ],
      "pf": 0.665,
      "expectancy_r": -0.2122,
      "max_dd_r": -3.043,
      "avg_win_r": 1.123,
      "avg_loss_r": -1.013,
      "med_win_r": 1.021,
      "med_loss_r": -1.013,
      "worst_r": -1.019,
      "p95_loss_r": -1.018,
      "trades_per_week": 0.32,
      "longest_losing_streak": 3,
      "anti_cheat_ok": true,
      "anti_cheat_reasons": []
    },
    "MES": {
      "n": 8,
      "wins": 2,
      "losses": 6,
      "wr": 0.25,
      "wr_ci95": [
        0.0,
        0.625
      ],
      "pf": 0.471,
      "expectancy_r": -0.3512,
      "max_dd_r": -4.294,
      "avg_win_r": 1.249,
      "avg_loss_r": -0.885,
      "med_win_r": 1.249,
      "med_loss_r": -1.013,
      "worst_r": -1.032,
      "p95_loss_r": -1.029,
      "trades_per_week": 0.38,
      "longest_losing_streak": 5,
      "anti_cheat_ok": true,
      "anti_cheat_reasons": []
    },
    "GC": {
      "n": 2,
      "wins": 1,
      "losses": 1,
      "wr": 0.5,
      "wr_ci95": [
        0.0,
        1.0
      ],
      "pf": 1.487,
      "expectancy_r": 0.245,
      "max_dd_r": -1.006,
      "avg_win_r": 1.496,
      "avg_loss_r": -1.006,
      "med_win_r": 1.496,
      "med_loss_r": -1.006,
      "worst_r": -1.006,
      "p95_loss_r": -1.006,
      "trades_per_week": 0.08,
      "longest_losing_streak": 1,
      "anti_cheat_ok": true,
      "anti_cheat_reasons": []
    },
    "MGC": {
      "n": 1,
      "wins": 0,
      "losses": 1,
      "wr": 0.0,
      "wr_ci95": [
        0.0,
        0.0
      ],
      "pf": 0.0,
      "expectancy_r": -1.0063,
      "max_dd_r": 0.0,
      "avg_win_r": 0.0,
      "avg_loss_r": -1.006,
      "med_win_r": 0.0,
      "med_loss_r": -1.006,
      "worst_r": -1.006,
      "p95_loss_r": -1.006,
      "trades_per_week": 1.0,
      "longest_losing_streak": 1,
      "anti_cheat_ok": true,
      "anti_cheat_reasons": []
    },
    "CL": {
      "n": 4,
      "wins": 1,
      "losses": 3,
      "wr": 0.25,
      "wr_ci95": [
        0.0,
        0.75
      ],
      "pf": 0.49,
      "expectancy_r": -0.3871,
      "max_dd_r": -1.014,
      "avg_win_r": 1.487,
      "avg_loss_r": -1.012,
      "med_win_r": 1.487,
      "med_loss_r": -1.013,
      "worst_r": -1.014,
      "p95_loss_r": -1.014,
      "trades_per_week": 1.56,
      "longest_losing_streak": 2,
      "anti_cheat_ok": true,
      "anti_cheat_reasons": []
    },
    "MCL": {
      "n": 3,
      "wins": 1,
      "losses": 2,
      "wr": 0.3333,
      "wr_ci95": [
        0.0,
        1.0
      ],
      "pf": 0.736,
      "expectancy_r": -0.1781,
      "max_dd_r": -1.008,
      "avg_win_r": 1.487,
      "avg_loss_r": -1.011,
      "med_win_r": 1.487,
      "med_loss_r": -1.011,
      "worst_r": -1.013,
      "p95_loss_r": -1.013,
      "trades_per_week": 1.17,
      "longest_losing_streak": 1,
      "anti_cheat_ok": true,
      "anti_cheat_reasons": []
    }
  },
  "by_session": {
    "NY_MID": {
      "n": 35,
      "wins": 13,
      "losses": 22,
      "wr": 0.3714,
      "wr_ci95": [
        0.2,
        0.5429
      ],
      "pf": 0.589,
      "expectancy_r": -0.2519,
      "max_dd_r": -10.242,
      "avg_win_r": 0.972,
      "avg_loss_r": -0.975,
      "med_win_r": 1.017,
      "med_loss_r": -1.011,
      "worst_r": -1.032,
      "p95_loss_r": -1.019,
      "trades_per_week": 1.41,
      "longest_losing_streak": 5,
      "anti_cheat_ok": true,
      "anti_cheat_reasons": []
    }
  },
  "final_trades_n": 35
}
```

## D–G. BY MARKET (FINAL holdout for top candidates)
```json
{
  "high_wr": {
    "NQ": {
      "n": 5,
      "wins": 3,
      "losses": 2,
      "wr": 0.6,
      "wr_ci95": [
        0.2,
        1.0
      ],
      "pf": 0.81,
      "expectancy_r": -0.0763,
      "max_dd_r": -1.628,
      "avg_win_r": 0.542,
      "avg_loss_r": -1.003,
      "med_win_r": 0.378,
      "med_loss_r": -1.003,
      "worst_r": -1.003,
      "p95_loss_r": -1.003,
      "trades_per_week": 0.28,
      "longest_losing_streak": 1,
      "anti_cheat_ok": true,
      "anti_cheat_reasons": []
    },
    "MNQ": {
      "n": 4,
      "wins": 2,
      "losses": 2,
      "wr": 0.5,
      "wr_ci95": [
        0.0,
        1.0
      ],
      "pf": 0.338,
      "expectancy_r": -0.332,
      "max_dd_r": -1.003,
      "avg_win_r": 0.339,
      "avg_loss_r": -1.003,
      "med_win_r": 0.339,
      "med_loss_r": -1.003,
      "worst_r": -1.003,
      "p95_loss_r": -1.003,
      "trades_per_week": 0.28,
      "longest_losing_streak": 1,
      "anti_cheat_ok": false,
      "anti_cheat_reasons": [
        "tiny_target_or_huge_stop"
      ]
    },
    "ES": {
      "n": 8,
      "wins": 3,
      "losses": 5,
      "wr": 0.375,
      "wr_ci95": [
        0.0,
        0.75
      ],
      "pf": 0.665,
      "expectancy_r": -0.2122,
      "max_dd_r": -3.043,
      "avg_win_r": 1.123,
      "avg_loss_r": -1.013,
      "med_win_r": 1.021,
      "med_loss_r": -1.013,
      "worst_r": -1.019,
      "p95_loss_r": -1.018,
      "trades_per_week": 0.32,
      "longest_losing_streak": 3,
      "anti_cheat_ok": true,
      "anti_cheat_reasons": []
    },
    "MES": {
      "n": 8,
      "wins": 2,
      "losses": 6,
      "wr": 0.25,
      "wr_ci95": [
        0.0,
        0.625
      ],
      "pf": 0.471,
      "expectancy_r": -0.3512,
      "max_dd_r": -4.294,
      "avg_win_r": 1.249,
      "avg_loss_r": -0.885,
      "med_win_r": 1.249,
      "med_loss_r": -1.013,
      "worst_r": -1.032,
      "p95_loss_r": -1.029,
      "trades_per_week": 0.38,
      "longest_losing_streak": 5,
      "anti_cheat_ok": true,
      "anti_cheat_reasons": []
    },
    "GC": {
      "n": 2,
      "wins": 1,
      "losses": 1,
      "wr": 0.5,
      "wr_ci95": [
        0.0,
        1.0
      ],
      "pf": 1.487,
      "expectancy_r": 0.245,
      "max_dd_r": -1.006,
      "avg_win_r": 1.496,
      "avg_loss_r": -1.006,
      "med_win_r": 1.496,
      "med_loss_r": -1.006,
      "worst_r": -1.006,
      "p95_loss_r": -1.006,
      "trades_per_week": 0.08,
      "longest_losing_streak": 1,
      "anti_cheat_ok": true,
      "anti_cheat_reasons": []
    },
    "MGC": {
      "n": 1,
      "wins": 0,
      "losses": 1,
      "wr": 0.0,
      "wr_ci95": [
        0.0,
        0.0
      ],
      "pf": 0.0,
      "expectancy_r": -1.0063,
      "max_dd_r": 0.0,
      "avg_win_r": 0.0,
      "avg_loss_r": -1.006,
      "med_win_r": 0.0,
      "med_loss_r": -1.006,
      "worst_r": -1.006,
      "p95_loss_r": -1.006,
      "trades_per_week": 1.0,
      "longest_losing_streak": 1,
      "anti_cheat_ok": true,
      "anti_cheat_reasons": []
    },
    "CL": {
      "n": 4,
      "wins": 1,
      "losses": 3,
      "wr": 0.25,
      "wr_ci95": [
        0.0,
        0.75
      ],
      "pf": 0.49,
      "expectancy_r": -0.3871,
      "max_dd_r": -1.014,
      "avg_win_r": 1.487,
      "avg_loss_r": -1.012,
      "med_win_r": 1.487,
      "med_loss_r": -1.013,
      "worst_r": -1.014,
      "p95_loss_r": -1.014,
      "trades_per_week": 1.56,
      "longest_losing_streak": 2,
      "anti_cheat_ok": true,
      "anti_cheat_reasons": []
    },
    "MCL": {
      "n": 3,
      "wins": 1,
      "losses": 2,
      "wr": 0.3333,
      "wr_ci95": [
        0.0,
        1.0
      ],
      "pf": 0.736,
      "expectancy_r": -0.1781,
      "max_dd_r": -1.008,
      "avg_win_r": 1.487,
      "avg_loss_r": -1.011,
      "med_win_r": 1.487,
      "med_loss_r": -1.011,
      "worst_r": -1.013,
      "p95_loss_r": -1.013,
      "trades_per_week": 1.17,
      "longest_losing_streak": 1,
      "anti_cheat_ok": true,
      "anti_cheat_reasons": []
    }
  },
  "balanced": {
    "NQ": {
      "n": 5,
      "wins": 3,
      "losses": 2,
      "wr": 0.6,
      "wr_ci95": [
        0.2,
        1.0
      ],
      "pf": 0.81,
      "expectancy_r": -0.0763,
      "max_dd_r": -1.628,
      "avg_win_r": 0.542,
      "avg_loss_r": -1.003,
      "med_win_r": 0.378,
      "med_loss_r": -1.003,
      "worst_r": -1.003,
      "p95_loss_r": -1.003,
      "trades_per_week": 0.28,
      "longest_losing_streak": 1,
      "anti_cheat_ok": true,
      "anti_cheat_reasons": []
    },
    "MNQ": {
      "n": 4,
      "wins": 2,
      "losses": 2,
      "wr": 0.5,
      "wr_ci95": [
        0.0,
        1.0
      ],
      "pf": 0.338,
      "expectancy_r": -0.332,
      "max_dd_r": -1.003,
      "avg_win_r": 0.339,
      "avg_loss_r": -1.003,
      "med_win_r": 0.339,
      "med_loss_r": -1.003,
      "worst_r": -1.003,
      "p95_loss_r": -1.003,
      "trades_per_week": 0.28,
      "longest_losing_streak": 1,
      "anti_cheat_ok": false,
      "anti_cheat_reasons": [
        "tiny_target_or_huge_stop"
      ]
    },
    "ES": {
      "n": 8,
      "wins": 3,
      "losses": 5,
      "wr": 0.375,
      "wr_ci95": [
        0.0,
        0.75
      ],
      "pf": 0.665,
      "expectancy_r": -0.2122,
      "max_dd_r": -3.043,
      "avg_win_r": 1.123,
      "avg_loss_r": -1.013,
      "med_win_r": 1.021,
      "med_loss_r": -1.013,
      "worst_r": -1.019,
      "p95_loss_r": -1.018,
      "trades_per_week": 0.32,
      "longest_losing_streak": 3,
      "anti_cheat_ok": true,
      "anti_cheat_reasons": []
    },
    "MES": {
      "n": 8,
      "wins": 2,
      "losses": 6,
      "wr": 0.25,
      "wr_ci95": [
        0.0,
        0.625
      ],
      "pf": 0.471,
      "expectancy_r": -0.3512,
      "max_dd_r": -4.294,
      "avg_win_r": 1.249,
      "avg_loss_r": -0.885,
      "med_win_r": 1.249,
      "med_loss_r": -1.013,
      "worst_r": -1.032,
      "p95_loss_r": -1.029,
      "trades_per_week": 0.38,
      "longest_losing_streak": 5,
      "anti_cheat_ok": true,
      "anti_cheat_reasons": []
    },
    "GC": {
      "n": 2,
      "wins": 1,
      "losses": 1,
      "wr": 0.5,
      "wr_ci95": [
        0.0,
        1.0
      ],
      "pf": 1.487,
      "expectancy_r": 0.245,
      "max_dd_r": -1.006,
      "avg_win_r": 1.496,
      "avg_loss_r": -1.006,
      "med_win_r": 1.496,
      "med_loss_r": -1.006,
      "worst_r": -1.006,
      "p95_loss_r": -1.006,
      "trades_per_week": 0.08,
      "longest_losing_streak": 1,
      "anti_cheat_ok": true,
      "anti_cheat_reasons": []
    },
    "MGC": {
      "n": 1,
      "wins": 0,
      "losses": 1,
      "wr": 0.0,
      "wr_ci95": [
        0.0,
        0.0
      ],
      "pf": 0.0,
      "expectancy_r": -1.0063,
      "max_dd_r": 0.0,
      "avg_win_r": 0.0,
      "avg_loss_r": -1.006,
      "med_win_r": 0.0,
      "med_loss_r": -1.006,
      "worst_r": -1.006,
      "p95_loss_r": -1.006,
      "trades_per_week": 1.0,
      "longest_losing_streak": 1,
      "anti_cheat_ok": true,
      "anti_cheat_reasons": []
    },
    "CL": {
      "n": 4,
      "wins": 1,
      "losses": 3,
      "wr": 0.25,
      "wr_ci95": [
        0.0,
        0.75
      ],
      "pf": 0.49,
      "expectancy_r": -0.3871,
      "max_dd_r": -1.014,
      "avg_win_r": 1.487,
      "avg_loss_r": -1.012,
      "med_win_r": 1.487,
      "med_loss_r": -1.013,
      "worst_r": -1.014,
      "p95_loss_r": -1.014,
      "trades_per_week": 1.56,
      "longest_losing_streak": 2,
      "anti_cheat_ok": true,
      "anti_cheat_reasons": []
    },
    "MCL": {
      "n": 3,
      "wins": 1,
      "losses": 2,
      "wr": 0.3333,
      "wr_ci95": [
        0.0,
        1.0
      ],
      "pf": 0.736,
      "expectancy_r": -0.1781,
      "max_dd_r": -1.008,
      "avg_win_r": 1.487,
      "avg_loss_r": -1.011,
      "med_win_r": 1.487,
      "med_loss_r": -1.011,
      "worst_r": -1.013,
      "p95_loss_r": -1.013,
      "trades_per_week": 1.17,
      "longest_losing_streak": 1,
      "anti_cheat_ok": true,
      "anti_cheat_reasons": []
    }
  },
  "high_exp": {
    "NQ": {
      "n": 5,
      "wins": 3,
      "losses": 2,
      "wr": 0.6,
      "wr_ci95": [
        0.2,
        1.0
      ],
      "pf": 0.81,
      "expectancy_r": -0.0763,
      "max_dd_r": -1.628,
      "avg_win_r": 0.542,
      "avg_loss_r": -1.003,
      "med_win_r": 0.378,
      "med_loss_r": -1.003,
      "worst_r": -1.003,
      "p95_loss_r": -1.003,
      "trades_per_week": 0.28,
      "longest_losing_streak": 1,
      "anti_cheat_ok": true,
      "anti_cheat_reasons": []
    },
    "MNQ": {
      "n": 4,
      "wins": 2,
      "losses": 2,
      "wr": 0.5,
      "wr_ci95": [
        0.0,
        1.0
      ],
      "pf": 0.338,
      "expectancy_r": -0.332,
      "max_dd_r": -1.003,
      "avg_win_r": 0.339,
      "avg_loss_r": -1.003,
      "med_win_r": 0.339,
      "med_loss_r": -1.003,
      "worst_r": -1.003,
      "p95_loss_r": -1.003,
      "trades_per_week": 0.28,
      "longest_losing_streak": 1,
      "anti_cheat_ok": false,
      "anti_cheat_reasons": [
        "tiny_target_or_huge_stop"
      ]
    },
    "ES": {
      "n": 8,
      "wins": 3,
      "losses": 5,
      "wr": 0.375,
      "wr_ci95": [
        0.0,
        0.75
      ],
      "pf": 0.665,
      "expectancy_r": -0.2122,
      "max_dd_r": -3.043,
      "avg_win_r": 1.123,
      "avg_loss_r": -1.013,
      "med_win_r": 1.021,
      "med_loss_r": -1.013,
      "worst_r": -1.019,
      "p95_loss_r": -1.018,
      "trades_per_week": 0.32,
      "longest_losing_streak": 3,
      "anti_cheat_ok": true,
      "anti_cheat_reasons": []
    },
    "MES": {
      "n": 8,
      "wins": 2,
      "losses": 6,
      "wr": 0.25,
      "wr_ci95": [
        0.0,
        0.625
      ],
      "pf": 0.471,
      "expectancy_r": -0.3512,
      "max_dd_r": -4.294,
      "avg_win_r": 1.249,
      "avg_loss_r": -0.885,
      "med_win_r": 1.249,
      "med_loss_r": -1.013,
      "worst_r": -1.032,
      "p95_loss_r": -1.029,
      "trades_per_week": 0.38,
      "longest_losing_streak": 5,
      "anti_cheat_ok": true,
      "anti_cheat_reasons": []
    },
    "GC": {
      "n": 2,
      "wins": 1,
      "losses": 1,
      "wr": 0.5,
      "wr_ci95": [
        0.0,
        1.0
      ],
      "pf": 1.487,
      "expectancy_r": 0.245,
      "max_dd_r": -1.006,
      "avg_win_r": 1.496,
      "avg_loss_r": -1.006,
      "med_win_r": 1.496,
      "med_loss_r": -1.006,
      "worst_r": -1.006,
      "p95_loss_r": -1.006,
      "trades_per_week": 0.08,
      "longest_losing_streak": 1,
      "anti_cheat_ok": true,
      "anti_cheat_reasons": []
    },
    "MGC": {
      "n": 1,
      "wins": 0,
      "losses": 1,
      "wr": 0.0,
      "wr_ci95": [
        0.0,
        0.0
      ],
      "pf": 0.0,
      "expectancy_r": -1.0063,
      "max_dd_r": 0.0,
      "avg_win_r": 0.0,
      "avg_loss_r": -1.006,
      "med_win_r": 0.0,
      "med_loss_r": -1.006,
      "worst_r": -1.006,
      "p95_loss_r": -1.006,
      "trades_per_week": 1.0,
      "longest_losing_streak": 1,
      "anti_cheat_ok": true,
      "anti_cheat_reasons": []
    },
    "CL": {
      "n": 4,
      "wins": 1,
      "losses": 3,
      "wr": 0.25,
      "wr_ci95": [
        0.0,
        0.75
      ],
      "pf": 0.49,
      "expectancy_r": -0.3871,
      "max_dd_r": -1.014,
      "avg_win_r": 1.487,
      "avg_loss_r": -1.012,
      "med_win_r": 1.487,
      "med_loss_r": -1.013,
      "worst_r": -1.014,
      "p95_loss_r": -1.014,
      "trades_per_week": 1.56,
      "longest_losing_streak": 2,
      "anti_cheat_ok": true,
      "anti_cheat_reasons": []
    },
    "MCL": {
      "n": 3,
      "wins": 1,
      "losses": 2,
      "wr": 0.3333,
      "wr_ci95": [
        0.0,
        1.0
      ],
      "pf": 0.736,
      "expectancy_r": -0.1781,
      "max_dd_r": -1.008,
      "avg_win_r": 1.487,
      "avg_loss_r": -1.011,
      "med_win_r": 1.487,
      "med_loss_r": -1.011,
      "worst_r": -1.013,
      "p95_loss_r": -1.013,
      "trades_per_week": 1.17,
      "longest_losing_streak": 1,
      "anti_cheat_ok": true,
      "anti_cheat_reasons": []
    }
  }
}
```

## H. SESSION
```json
{
  "high_wr": {
    "NY_MID": {
      "n": 35,
      "wins": 13,
      "losses": 22,
      "wr": 0.3714,
      "wr_ci95": [
        0.2,
        0.5429
      ],
      "pf": 0.589,
      "expectancy_r": -0.2519,
      "max_dd_r": -10.242,
      "avg_win_r": 0.972,
      "avg_loss_r": -0.975,
      "med_win_r": 1.017,
      "med_loss_r": -1.011,
      "worst_r": -1.032,
      "p95_loss_r": -1.019,
      "trades_per_week": 1.41,
      "longest_losing_streak": 5,
      "anti_cheat_ok": true,
      "anti_cheat_reasons": []
    }
  },
  "balanced": {
    "NY_MID": {
      "n": 35,
      "wins": 13,
      "losses": 22,
      "wr": 0.3714,
      "wr_ci95": [
        0.2,
        0.5429
      ],
      "pf": 0.589,
      "expectancy_r": -0.2519,
      "max_dd_r": -10.242,
      "avg_win_r": 0.972,
      "avg_loss_r": -0.975,
      "med_win_r": 1.017,
      "med_loss_r": -1.011,
      "worst_r": -1.032,
      "p95_loss_r": -1.019,
      "trades_per_week": 1.41,
      "longest_losing_streak": 5,
      "anti_cheat_ok": true,
      "anti_cheat_reasons": []
    }
  }
}
```

## I. NY OPEN DEEP DIVE
```json
{
  "selected_window_on_val": "1100_1200",
  "windows": {
    "1100_1200": {
      "selected_on_val": "ny_1100_1200_mC_retest_R1.5",
      "val": {
        "n": 39,
        "wins": 24,
        "losses": 15,
        "wr": 0.6154,
        "wr_ci95": [
          0.4615,
          0.7436
        ],
        "pf": 2.122,
        "expectancy_r": 0.3468,
        "max_dd_r": -3.015,
        "avg_win_r": 1.066,
        "avg_loss_r": -0.804,
        "med_win_r": 1.156,
        "med_loss_r": -1.004,
        "worst_r": -1.03,
        "p95_loss_r": -1.029,
        "trades_per_week": 1.57,
        "longest_losing_streak": 3,
        "anti_cheat_ok": true,
        "anti_cheat_reasons": []
      },
      "final": {
        "n": 35,
        "wins": 13,
        "losses": 22,
        "wr": 0.3714,
        "wr_ci95": [
          0.2,
          0.5429
        ],
        "pf": 0.589,
        "expectancy_r": -0.2519,
        "max_dd_r": -10.242,
        "avg_win_r": 0.972,
        "avg_loss_r": -0.975,
        "med_win_r": 1.017,
        "med_loss_r": -1.011,
        "worst_r": -1.032,
        "p95_loss_r": -1.019,
        "trades_per_week": 1.41,
        "longest_losing_streak": 5,
        "anti_cheat_ok": true,
        "anti_cheat_reasons": []
      },
      "by_symbol_final": {
        "NQ": {
          "n": 5,
          "wins": 3,
          "losses": 2,
          "wr": 0.6,
          "wr_ci95": [
            0.2,
            1.0
          ],
          "pf": 0.81,
          "expectancy_r": -0.0763,
          "max_dd_r": -1.628,
          "avg_win_r": 0.542,
          "avg_loss_r": -1.003,
          "med_win_r": 0.378,
          "med_loss_r": -1.003,
          "worst_r": -1.003,
          "p95_loss_r": -1.003,
          "trades_per_week": 0.28,
          "longest_losing_streak": 1,
          "anti_cheat_ok": true,
          "anti_cheat_reasons": []
        },
        "MNQ": {
          "n": 4,
          "wins": 2,
          "losses": 2,
          "wr": 0.5,
          "wr_ci95": [
            0.0,
            1.0
          ],
          "pf": 0.338,
          "expectancy_r": -0.332,
          "max_dd_r": -1.003,
          "avg_win_r": 0.339,
          "avg_loss_r": -1.003,
          "med_win_r": 0.339,
          "med_loss_r": -1.003,
          "worst_r": -1.003,
          "p95_loss_r": -1.003,
          "trades_per_week": 0.28,
          "longest_losing_streak": 1,
          "anti_cheat_ok": false,
          "anti_cheat_reasons": [
            "tiny_target_or_huge_stop"
          ]
        },
        "ES": {
          "n": 8,
          "wins": 3,
          "losses": 5,
          "wr": 0.375,
          "wr_ci95": [
            0.0,
            0.75
          ],
          "pf": 0.665,
          "expectancy_r": -0.2122,
          "max_dd_r": -3.043,
          "avg_win_r": 1.123,
          "avg_loss_r": -1.013,
          "med_win_r": 1.021,
          "med_loss_r": -1.013,
          "worst_r": -1.019,
          "p95_loss_r": -1.018,
          "trades_per_week": 0.32,
          "longest_losing_streak": 3,
          "anti_cheat_ok": true,
          "anti_cheat_reasons": []
        },
        "MES": {
          "n": 8,
          "wins": 2,
          "losses": 6,
          "wr": 0.25,
          "wr_ci95": [
            0.0,
            0.625
          ],
          "pf": 0.471,
          "expectancy_r": -0.3512,
          "max_dd_r": -4.294,
          "avg_win_r": 1.249,
          "avg_loss_r": -0.885,
          "med_win_r": 1.249,
          "med_loss_r": -1.013,
          "worst_r": -1.032,
          "p95_loss_r": -1.029,
          "trades_per_week": 0.38,
          "longest_losing_streak": 5,
          "anti_cheat_ok": true,
          "anti_cheat_reasons": []
        },
        "GC": {
          "n": 2,
          "wins": 1,
          "losses": 1,
          "wr": 0.5,
          "wr_ci95": [
            0.0,
            1.0
          ],
          "pf": 1.487,
          "expectancy_r": 0.245,
          "max_dd_r": -1.006,
          "avg_win_r": 1.496,
          "avg_loss_r": -1.006,
          "med_win_r": 1.496,
          "med_loss_r": -1.006,
          "worst_r": -1.006,
          "p95_loss_r": -1.006,
          "trades_per_week": 0.08,
          "longest_losing_streak": 1,
          "anti_cheat_ok": true,
          "anti_cheat_reasons": []
        },
        "MGC": {
          "n": 1,
          "wins": 0,
          "losses": 1,
          "wr": 0.0,
          "wr_ci95": [
            0.0,
            0.0
          ],
          "pf": 0.0,
          "expectancy_r": -1.0063,
          "max_dd_r": 0.0,
          "avg_win_r": 0.0,
          "avg_loss_r": -1.006,
          "med_win_r": 0.0,
          "med_loss_r": -1.006,
          "worst_r": -1.006,
          "p95_loss_r": -1.006,
          "trades_per_week": 1.0,
          "longest_losing_streak": 1,
          "anti_cheat_ok": true,
          "anti_cheat_reasons": []
        },
        "CL": {
          "n": 4,
          "wins": 1,
          "losses": 3,
          "wr": 0.25,
          "wr_ci95": [
            0.0,
            0.75
          ],
          "pf": 0.49,
          "expectancy_r": -0.3871,
          "max_dd_r": -1.014,
          "avg_win_r": 1.487,
          "avg_loss_r": -1.012,
          "med_win_r": 1.487,
          "med_loss_r": -1.013,
          "worst_r": -1.014,
          "p95_loss_r": -1.014,
          "trades_per_week": 1.56,
          "longest_losing_streak": 2,
          "anti_cheat_ok": true,
          "anti_cheat_reasons": []
        },
        "MCL": {
          "n": 3,
          "wins": 1,
          "losses": 2,
          "wr": 0.3333,
          "wr_ci95": [
            0.0,
            1.0
          ],
          "pf": 0.736,
          "expectancy_r": -0.1781,
          "max_dd_r": -1.008,
          "avg_win_r": 1.487,
          "avg_loss_r": -1.011,
          "med_win_r": 1.487,
          "med_loss_r": -1.011,
          "worst_r": -1.013,
          "p95_loss_r": -1.013,
          "trades_per_week": 1.17,
          "longest_losing_streak": 1,
          "anti_cheat_ok": true,
          "anti_cheat_reasons": []
        }
      }
    },
    "0930_1030": {
      "selected_on_val": "ny_0930_1030_mC_retest_R1.0",
      "val": {
        "n": 96,
        "wins": 54,
        "losses": 42,
        "wr": 0.5625,
        "wr_ci95": [
          0.4688,
          0.6461
        ],
        "pf": 1.226,
        "expectancy_r": 0.0927,
        "max_dd_r": -5.63,
        "avg_win_r": 0.895,
        "avg_loss_r": -0.939,
        "med_win_r": 0.98,
        "med_loss_r": -1.012,
        "worst_r": -1.063,
        "p95_loss_r": -1.047,
        "trades_per_week": 3.2,
        "longest_losing_streak": 5,
        "anti_cheat_ok": true,
        "anti_cheat_reasons": []
      },
      "final": {
        "n": 91,
        "wins": 46,
        "losses": 45,
        "wr": 0.5055,
        "wr_ci95": [
          0.3956,
          0.5934
        ],
        "pf": 0.961,
        "expectancy_r": -0.0184,
        "max_dd_r": -10.018,
        "avg_win_r": 0.896,
        "avg_loss_r": -0.953,
        "med_win_r": 0.987,
        "med_loss_r": -1.005,
        "worst_r": -1.023,
        "p95_loss_r": -1.02,
        "trades_per_week": 3.73,
        "longest_losing_streak": 5,
        "anti_cheat_ok": true,
        "anti_cheat_reasons": []
      },
      "by_symbol_final": {
        "NQ": {
          "n": 21,
          "wins": 10,
          "losses": 11,
          "wr": 0.4762,
          "wr_ci95": [
            0.2857,
            0.6667
          ],
          "pf": 0.956,
          "expectancy_r": -0.0221,
          "max_dd_r": -4.813,
          "avg_win_r": 0.997,
          "avg_loss_r": -0.948,
          "med_win_r": 0.997,
          "med_loss_r": -1.003,
          "worst_r": -1.005,
          "p95_loss_r": -1.004,
          "trades_per_week": 0.86,
          "longest_losing_streak": 5,
          "anti_cheat_ok": true,
          "anti_cheat_reasons": []
        },
        "MNQ": {
          "n": 17,
          "wins": 7,
          "losses": 10,
          "wr": 0.4118,
          "wr_ci95": [
            0.1765,
            0.6471
          ],
          "pf": 0.741,
          "expectancy_r": -0.1438,
          "max_dd_r": -4.804,
          "avg_win_r": 0.997,
          "avg_loss_r": -0.943,
          "med_win_r": 0.998,
          "med_loss_r": -1.003,
          "worst_r": -1.005,
          "p95_loss_r": -1.004,
          "trades_per_week": 0.7,
          "longest_losing_streak": 5,
          "anti_cheat_ok": true,
          "anti_cheat_reasons": []
        },
        "ES": {
          "n": 18,
          "wins": 9,
          "losses": 9,
          "wr": 0.5,
          "wr_ci95": [
            0.2778,
            0.7222
          ],
          "pf": 0.872,
          "expectancy_r": -0.0652,
          "max_dd_r": -3.072,
          "avg_win_r": 0.886,
          "avg_loss_r": -1.016,
          "med_win_r": 0.976,
          "med_loss_r": -1.016,
          "worst_r": -1.023,
          "p95_loss_r": -1.022,
          "trades_per_week": 0.82,
          "longest_losing_streak": 2,
          "anti_cheat_ok": true,
          "anti_cheat_reasons": []
        },
        "MES": {
          "n": 18,
          "wins": 8,
          "losses": 10,
          "wr": 0.4444,
          "wr_ci95": [
            0.2222,
            0.7222
          ],
          "pf": 0.634,
          "expectancy_r": -0.1997,
          "max_dd_r": -4.875,
          "avg_win_r": 0.777,
          "avg_loss_r": -0.981,
          "med_win_r": 0.974,
          "med_loss_r": -1.017,
          "worst_r": -1.023,
          "p95_loss_r": -1.022,
          "trades_per_week": 0.92,
          "longest_losing_streak": 2,
          "anti_cheat_ok": true,
          "anti_cheat_reasons": []
        },
        "GC": {
          "n": 3,
          "wins": 3,
          "losses": 0,
          "wr": 1.0,
          "wr_ci95": [
            1.0,
            1.0
          ],
          "pf": 999.0,
          "expectancy_r": 0.8189,
          "max_dd_r": 0.0,
          "avg_win_r": 0.819,
          "avg_loss_r": 0.0,
          "med_win_r": 0.995,
          "med_loss_r": 0.0,
          "worst_r": 0.466,
          "p95_loss_r": 0.0,
          "trades_per_week": 0.28,
          "longest_losing_streak": 0,
          "anti_cheat_ok": true,
          "anti_cheat_reasons": []
        },
        "MGC": {
          "n": 4,
          "wins": 3,
          "losses": 1,
          "wr": 0.75,
          "wr_ci95": [
            0.25,
            1.0
          ],
          "pf": 83.844,
          "expectancy_r": 0.6068,
          "max_dd_r": -0.029,
          "avg_win_r": 0.819,
          "avg_loss_r": -0.029,
          "med_win_r": 0.995,
          "med_loss_r": -0.029,
          "worst_r": -0.029,
          "p95_loss_r": -0.029,
          "trades_per_week": 0.31,
          "longest_losing_streak": 1,
          "anti_cheat_ok": true,
          "anti_cheat_reasons": []
        },
        "CL": {
          "n": 6,
          "wins": 4,
          "losses": 2,
          "wr": 0.6667,
          "wr_ci95": [
            0.3333,
            1.0
          ],
          "pf": 1.58,
          "expectancy_r": 0.1962,
          "max_dd_r": -1.016,
          "avg_win_r": 0.801,
          "avg_loss_r": -1.014,
          "med_win_r": 0.987,
          "med_loss_r": -1.014,
          "worst_r": -1.016,
          "p95_loss_r": -1.015,
          "trades_per_week": 0.3,
          "longest_losing_streak": 1,
          "anti_cheat_ok": true,
          "anti_cheat_reasons": []
        },
        "MCL": {
          "n": 4,
          "wins": 2,
          "losses": 2,
          "wr": 0.5,
          "wr_ci95": [
            0.0,
            1.0
          ],
          "pf": 0.973,
          "expectancy_r": -0.0137,
          "max_dd_r": -2.028,
          "avg_win_r": 0.987,
          "avg_loss_r": -1.014,
          "med_win_r": 0.987,
          "med_loss_r": -1.014,
          "worst_r": -1.016,
          "p95_loss_r": -1.015,
          "trades_per_week": 0.33,
          "longest_losing_streak": 2,
          "anti_cheat_ok": true,
          "anti_cheat_reasons": []
        }
      }
    },
    "0930_1100": {
      "selected_on_val": "ny_0930_1100_mC_retest_R1.0",
      "val": {
        "n": 98,
        "wins": 54,
        "losses": 44,
        "wr": 0.551,
        "wr_ci95": [
          0.449,
          0.6533
        ],
        "pf": 1.165,
        "expectancy_r": 0.07,
        "max_dd_r": -5.718,
        "avg_win_r": 0.895,
        "avg_loss_r": -0.943,
        "med_win_r": 0.98,
        "med_loss_r": -1.013,
        "worst_r": -1.063,
        "p95_loss_r": -1.047,
        "trades_per_week": 3.27,
        "longest_losing_streak": 5,
        "anti_cheat_ok": true,
        "anti_cheat_reasons": []
      },
      "final": {
        "n": 91,
        "wins": 46,
        "losses": 45,
        "wr": 0.5055,
        "wr_ci95": [
          0.3956,
          0.5934
        ],
        "pf": 0.961,
        "expectancy_r": -0.0184,
        "max_dd_r": -10.018,
        "avg_win_r": 0.896,
        "avg_loss_r": -0.953,
        "med_win_r": 0.987,
        "med_loss_r": -1.005,
        "worst_r": -1.023,
        "p95_loss_r": -1.02,
        "trades_per_week": 3.73,
        "longest_losing_streak": 5,
        "anti_cheat_ok": true,
        "anti_cheat_reasons": []
      },
      "by_symbol_final": {
        "NQ": {
          "n": 21,
          "wins": 10,
          "losses": 11,
          "wr": 0.4762,
          "wr_ci95": [
            0.2857,
            0.6667
          ],
          "pf": 0.956,
          "expectancy_r": -0.0221,
          "max_dd_r": -4.813,
          "avg_win_r": 0.997,
          "avg_loss_r": -0.948,
          "med_win_r": 0.997,
          "med_loss_r": -1.003,
          "worst_r": -1.005,
          "p95_loss_r": -1.004,
          "trades_per_week": 0.86,
          "longest_losing_streak": 5,
          "anti_cheat_ok": true,
          "anti_cheat_reasons": []
        },
        "MNQ": {
          "n": 17,
          "wins": 7,
          "losses": 10,
          "wr": 0.4118,
          "wr_ci95": [
            0.1765,
            0.6471
          ],
          "pf": 0.741,
          "expectancy_r": -0.1438,
          "max_dd_r": -4.804,
          "avg_win_r": 0.997,
          "avg_loss_r": -0.943,
          "med_win_r": 0.998,
          "med_loss_r": -1.003,
          "worst_r": -1.005,
          "p95_loss_r": -1.004,
          "trades_per_week": 0.7,
          "longest_losing_streak": 5,
          "anti_cheat_ok": true,
          "anti_cheat_reasons": []
        },
        "ES": {
          "n": 18,
          "wins": 9,
          "losses": 9,
          "wr": 0.5,
          "wr_ci95": [
            0.2778,
            0.7222
          ],
          "pf": 0.872,
          "expectancy_r": -0.0652,
          "max_dd_r": -3.072,
          "avg_win_r": 0.886,
          "avg_loss_r": -1.016,
          "med_win_r": 0.976,
          "med_loss_r": -1.016,
          "worst_r": -1.023,
          "p95_loss_r": -1.022,
          "trades_per_week": 0.82,
          "longest_losing_streak": 2,
          "anti_cheat_ok": true,
          "anti_cheat_reasons": []
        },
        "MES": {
          "n": 18,
          "wins": 8,
          "losses": 10,
          "wr": 0.4444,
          "wr_ci95": [
            0.2222,
            0.7222
          ],
          "pf": 0.634,
          "expectancy_r": -0.1997,
          "max_dd_r": -4.875,
          "avg_win_r": 0.777,
          "avg_loss_r": -0.981,
          "med_win_r": 0.974,
          "med_loss_r": -1.017,
          "worst_r": -1.023,
          "p95_loss_r": -1.022,
          "trades_per_week": 0.92,
          "longest_losing_streak": 2,
          "anti_cheat_ok": true,
          "anti_cheat_reasons": []
        },
        "GC": {
          "n": 3,
          "wins": 3,
          "losses": 0,
          "wr": 1.0,
          "wr_ci95": [
            1.0,
            1.0
          ],
          "pf": 999.0,
          "expectancy_r": 0.8189,
          "max_dd_r": 0.0,
          "avg_win_r": 0.819,
          "avg_loss_r": 0.0,
          "med_win_r": 0.995,
          "med_loss_r": 0.0,
          "worst_r": 0.466,
          "p95_loss_r": 0.0,
          "trades_per_week": 0.28,
          "longest_losing_streak": 0,
          "anti_cheat_ok": true,
          "anti_cheat_reasons": []
        },
        "MGC": {
          "n": 4,
          "wins": 3,
          "losses": 1,
          "wr": 0.75,
          "wr_ci95": [
            0.25,
            1.0
          ],
          "pf": 83.844,
          "expectancy_r": 0.6068,
          "max_dd_r": -0.029,
          "avg_win_r": 0.819,
          "avg_loss_r": -0.029,
          "med_win_r": 0.995,
          "med_loss_r": -0.029,
          "worst_r": -0.029,
          "p95_loss_r": -0.029,
          "trades_per_week": 0.31,
          "longest_losing_streak": 1,
          "anti_cheat_ok": true,
          "anti_cheat_reasons": []
        },
        "CL": {
          "n": 6,
          "wins": 4,
          "losses": 2,
          "wr": 0.6667,
          "wr_ci95": [
            0.3333,
            1.0
          ],
          "pf": 1.58,
          "expectancy_r": 0.1962,
          "max_dd_r": -1.016,
          "avg_win_r": 0.801,
          "avg_loss_r": -1.014,
          "med_win_r": 0.987,
          "med_loss_r": -1.014,
          "worst_r": -1.016,
          "p95_loss_r": -1.015,
          "trades_per_week": 0.3,
          "longest_losing_streak": 1,
          "anti_cheat_ok": true,
          "anti_cheat_reasons": []
        },
        "MCL": {
          "n": 4,
          "wins": 2,
          "losses": 2,
          "wr": 0.5,
          "wr_ci95": [
            0.0,
            1.0
          ],
          "pf": 0.973,
          "expectancy_r": -0.0137,
          "max_dd_r": -2.028,
          "avg_win_r": 0.987,
          "avg_loss_r": -1.014,
          "med_win_r": 0.987,
          "med_loss_r": -1.014,
          "worst_r": -1.016,
          "p95_loss_r": -1.015,
          "trades_per_week": 0.33,
          "longest_losing_streak": 2,
          "anti_cheat_ok": true,
          "anti_cheat_reasons": []
        }
      }
    },
    "1000_1100": {
      "selected_on_val": "ny_1000_1100_mC_retest_R1.0",
      "val": {
        "n": 98,
        "wins": 54,
        "losses": 44,
        "wr": 0.551,
        "wr_ci95": [
          0.449,
          0.6533
        ],
        "pf": 1.165,
        "expectancy_r": 0.07,
        "max_dd_r": -5.718,
        "avg_win_r": 0.895,
        "avg_loss_r": -0.943,
        "med_win_r": 0.98,
        "med_loss_r": -1.013,
        "worst_r": -1.063,
        "p95_loss_r": -1.047,
        "trades_per_week": 3.27,
        "longest_losing_streak": 5,
        "anti_cheat_ok": true,
        "anti_cheat_reasons": []
      },
      "final": {
        "n": 91,
        "wins": 46,
        "losses": 45,
        "wr": 0.5055,
        "wr_ci95": [
          0.3956,
          0.5934
        ],
        "pf": 0.961,
        "expectancy_r": -0.0184,
        "max_dd_r": -10.018,
        "avg_win_r": 0.896,
        "avg_loss_r": -0.953,
        "med_win_r": 0.987,
        "med_loss_r": -1.005,
        "worst_r": -1.023,
        "p95_loss_r": -1.02,
        "trades_per_week": 3.73,
        "longest_losing_streak": 5,
        "anti_cheat_ok": true,
        "anti_cheat_reasons": []
      },
      "by_symbol_final": {
        "NQ": {
          "n": 21,
          "wins": 10,
          "losses": 11,
          "wr": 0.4762,
          "wr_ci95": [
            0.2857,
            0.6667
          ],
          "pf": 0.956,
          "expectancy_r": -0.0221,
          "max_dd_r": -4.813,
          "avg_win_r": 0.997,
          "avg_loss_r": -0.948,
          "med_win_r": 0.997,
          "med_loss_r": -1.003,
          "worst_r": -1.005,
          "p95_loss_r": -1.004,
          "trades_per_week": 0.86,
          "longest_losing_streak": 5,
          "anti_cheat_ok": true,
          "anti_cheat_reasons": []
        },
        "MNQ": {
          "n": 17,
          "wins": 7,
          "losses": 10,
          "wr": 0.4118,
          "wr_ci95": [
            0.1765,
            0.6471
          ],
          "pf": 0.741,
          "expectancy_r": -0.1438,
          "max_dd_r": -4.804,
          "avg_win_r": 0.997,
          "avg_loss_r": -0.943,
          "med_win_r": 0.998,
          "med_loss_r": -1.003,
          "worst_r": -1.005,
          "p95_loss_r": -1.004,
          "trades_per_week": 0.7,
          "longest_losing_streak": 5,
          "anti_cheat_ok": true,
          "anti_cheat_reasons": []
        },
        "ES": {
          "n": 18,
          "wins": 9,
          "losses": 9,
          "wr": 0.5,
          "wr_ci95": [
            0.2778,
            0.7222
          ],
          "pf": 0.872,
          "expectancy_r": -0.0652,
          "max_dd_r": -3.072,
          "avg_win_r": 0.886,
          "avg_loss_r": -1.016,
          "med_win_r": 0.976,
          "med_loss_r": -1.016,
          "worst_r": -1.023,
          "p95_loss_r": -1.022,
          "trades_per_week": 0.82,
          "longest_losing_streak": 2,
          "anti_cheat_ok": true,
          "anti_cheat_reasons": []
        },
        "MES": {
          "n": 18,
          "wins": 8,
          "losses": 10,
          "wr": 0.4444,
          "wr_ci95": [
            0.2222,
            0.7222
          ],
          "pf": 0.634,
          "expectancy_r": -0.1997,
          "max_dd_r": -4.875,
          "avg_win_r": 0.777,
          "avg_loss_r": -0.981,
          "med_win_r": 0.974,
          "med_loss_r": -1.017,
          "worst_r": -1.023,
          "p95_loss_r": -1.022,
          "trades_per_week": 0.92,
          "longest_losing_streak": 2,
          "anti_cheat_ok": true,
          "anti_cheat_reasons": []
        },
        "GC": {
          "n": 3,
          "wins": 3,
          "losses": 0,
          "wr": 1.0,
          "wr_ci95": [
            1.0,
            1.0
          ],
          "pf": 999.0,
          "expectancy_r": 0.8189,
          "max_dd_r": 0.0,
          "avg_win_r": 0.819,
          "avg_loss_r": 0.0,
          "med_win_r": 0.995,
          "med_loss_r": 0.0,
          "worst_r": 0.466,
          "p95_loss_r": 0.0,
          "trades_per_week": 0.28,
          "longest_losing_streak": 0,
          "anti_cheat_ok": true,
          "anti_cheat_reasons": []
        },
        "MGC": {
          "n": 4,
          "wins": 3,
          "losses": 1,
          "wr": 0.75,
          "wr_ci95": [
            0.25,
            1.0
          ],
          "pf": 83.844,
          "expectancy_r": 0.6068,
          "max_dd_r": -0.029,
          "avg_win_r": 0.819,
          "avg_loss_r": -0.029,
          "med_win_r": 0.995,
          "med_loss_r": -0.029,
          "worst_r": -0.029,
          "p95_loss_r": -0.029,
          "trades_per_week": 0.31,
          "longest_losing_streak": 1,
          "anti_cheat_ok": true,
          "anti_cheat_reasons": []
        },
        "CL": {
          "n": 6,
          "wins": 4,
          "losses": 2,
          "wr": 0.6667,
          "wr_ci95": [
            0.3333,
            1.0
          ],
          "pf": 1.58,
          "expectancy_r": 0.1962,
          "max_dd_r": -1.016,
          "avg_win_r": 0.801,
          "avg_loss_r": -1.014,
          "med_win_r": 0.987,
          "med_loss_r": -1.014,
          "worst_r": -1.016,
          "p95_loss_r": -1.015,
          "trades_per_week": 0.3,
          "longest_losing_streak": 1,
          "anti_cheat_ok": true,
          "anti_cheat_reasons": []
        },
        "MCL": {
          "n": 4,
          "wins": 2,
          "losses": 2,
          "wr": 0.5,
          "wr_ci95": [
            0.0,
            1.0
          ],
          "pf": 0.973,
          "expectancy_r": -0.0137,
          "max_dd_r": -2.028,
          "avg_win_r": 0.987,
          "avg_loss_r": -1.014,
          "med_win_r": 0.987,
          "med_loss_r": -1.014,
          "worst_r": -1.016,
          "p95_loss_r": -1.015,
          "trades_per_week": 0.33,
          "longest_losing_streak": 2,
          "anti_cheat_ok": true,
          "anti_cheat_reasons": []
        }
      }
    },
    "0930_1000": {
      "selected_on_val": "ny_0930_1000_mC_retest_R1.0",
      "val": {
        "n": 0,
        "wins": 0,
        "losses": 0,
        "wr": 0.0,
        "wr_ci95": [
          0.0,
          0.0
        ],
        "pf": 0.0,
        "expectancy_r": 0.0,
        "max_dd_r": 0.0,
        "avg_win_r": 0.0,
        "avg_loss_r": 0.0,
        "med_win_r": 0.0,
        "med_loss_r": 0.0,
        "worst_r": 0.0,
        "p95_loss_r": 0.0,
        "trades_per_week": 0.0,
        "longest_losing_streak": 0,
        "anti_cheat_ok": true,
        "anti_cheat_reasons": []
      },
      "final": {
        "n": 0,
        "wins": 0,
        "losses": 0,
        "wr": 0.0,
        "wr_ci95": [
          0.0,
          0.0
        ],
        "pf": 0.0,
        "expectancy_r": 0.0,
        "max_dd_r": 0.0,
        "avg_win_r": 0.0,
        "avg_loss_r": 0.0,
        "med_win_r": 0.0,
        "med_loss_r": 0.0,
        "worst_r": 0.0,
        "p95_loss_r": 0.0,
        "trades_per_week": 0.0,
        "longest_losing_streak": 0,
        "anti_cheat_ok": true,
        "anti_cheat_reasons": []
      },
      "by_symbol_final": {}
    }
  }
}
```

## London
```json
{
  "lon_LONDON_MID_mC_reclaim_R1.0": {
    "val": {
      "n": 78,
      "wins": 43,
      "losses": 35,
      "wr": 0.5513,
      "wr_ci95": [
        0.4484,
        0.6667
      ],
      "pf": 1.089,
      "expectancy_r": 0.0412,
      "max_dd_r": -5.61,
      "avg_win_r": 0.914,
      "avg_loss_r": -1.031,
      "med_win_r": 0.969,
      "med_loss_r": -1.027,
      "worst_r": -1.082,
      "p95_loss_r": -1.073,
      "trades_per_week": 2.61,
      "longest_losing_streak": 3,
      "anti_cheat_ok": true,
      "anti_cheat_reasons": []
    }
  },
  "lon_LONDON_LATE_mC_reclaim_R1.5": {
    "val": {
      "n": 331,
      "wins": 159,
      "losses": 172,
      "wr": 0.4804,
      "wr_ci95": [
        0.423,
        0.5347
      ],
      "pf": 1.129,
      "expectancy_r": 0.0649,
      "max_dd_r": -10.692,
      "avg_win_r": 1.182,
      "avg_loss_r": -0.967,
      "med_win_r": 1.479,
      "med_loss_r": -1.012,
      "worst_r": -1.109,
      "p95_loss_r": -1.052,
      "trades_per_week": 10.88,
      "longest_losing_streak": 5,
      "anti_cheat_ok": true,
      "anti_cheat_reasons": []
    }
  },
  "lon_LONDON_LATE_mC_reclaim_R1.0": {
    "val": {
      "n": 331,
      "wins": 170,
      "losses": 161,
      "wr": 0.5136,
      "wr_ci95": [
        0.4622,
        0.565
      ],
      "pf": 0.967,
      "expectancy_r": -0.0153,
      "max_dd_r": -15.731,
      "avg_win_r": 0.889,
      "avg_loss_r": -0.97,
      "med_win_r": 0.983,
      "med_loss_r": -1.013,
      "worst_r": -1.109,
      "p95_loss_r": -1.054,
      "trades_per_week": 10.88,
      "longest_losing_streak": 5,
      "anti_cheat_ok": true,
      "anti_cheat_reasons": []
    }
  },
  "lon_LONDON_LATE_mC_reclaim_R1.25": {
    "val": {
      "n": 331,
      "wins": 162,
      "losses": 169,
      "wr": 0.4894,
      "wr_ci95": [
        0.4381,
        0.5408
      ],
      "pf": 1.016,
      "expectancy_r": 0.0079,
      "max_dd_r": -14.49,
      "avg_win_r": 1.024,
      "avg_loss_r": -0.966,
      "med_win_r": 1.232,
      "med_loss_r": -1.013,
      "worst_r": -1.109,
      "p95_loss_r": -1.053,
      "trades_per_week": 10.88,
      "longest_losing_streak": 5,
      "anti_cheat_ok": true,
      "anti_cheat_reasons": []
    }
  },
  "lon_LONDON_MID_mC_reclaim_R1.25": {
    "val": {
      "n": 78,
      "wins": 39,
      "losses": 39,
      "wr": 0.5,
      "wr_ci95": [
        0.3974,
        0.6154
      ],
      "pf": 1.091,
      "expectancy_r": 0.047,
      "max_dd_r": -8.101,
      "avg_win_r": 1.125,
      "avg_loss_r": -1.031,
      "med_win_r": 1.214,
      "med_loss_r": -1.027,
      "worst_r": -1.082,
      "p95_loss_r": -1.073,
      "trades_per_week": 2.61,
      "longest_losing_streak": 5,
      "anti_cheat_ok": true,
      "anti_cheat_reasons": []
    }
  },
  "lon_LONDON_MID_mC_reclaim_R1.5": {
    "val": {
      "n": 78,
      "wins": 37,
      "losses": 41,
      "wr": 0.4744,
      "wr_ci95": [
        0.3718,
        0.5897
      ],
      "pf": 1.162,
      "expectancy_r": 0.0847,
      "max_dd_r": -6.855,
      "avg_win_r": 1.282,
      "avg_loss_r": -0.996,
      "med_win_r": 1.455,
      "med_loss_r": -1.025,
      "worst_r": -1.082,
      "p95_loss_r": -1.073,
      "trades_per_week": 2.61,
      "longest_losing_streak": 5,
      "anti_cheat_ok": true,
      "anti_cheat_reasons": []
    }
  },
  "lon_LONDON_OPEN_mC_reclaim_R1.0": {
    "val": {
      "n": 208,
      "wins": 105,
      "losses": 103,
      "wr": 0.5048,
      "wr_ci95": [
        0.4375,
        0.5769
      ],
      "pf": 0.921,
      "expectancy_r": -0.0396,
      "max_dd_r": -16.877,
      "avg_win_r": 0.917,
      "avg_loss_r": -1.015,
      "med_win_r": 0.97,
      "med_loss_r": -1.037,
      "worst_r": -1.125,
      "p95_loss_r": -1.091,
      "trades_per_week": 6.83,
      "longest_losing_streak": 7,
      "anti_cheat_ok": true,
      "anti_cheat_reasons": []
    }
  },
  "SELECTED_FINAL": {
    "config": "lon_LONDON_MID_mC_reclaim_R1.0",
    "val": {
      "n": 78,
      "wins": 43,
      "losses": 35,
      "wr": 0.5513,
      "wr_ci95": [
        0.4484,
        0.6667
      ],
      "pf": 1.089,
      "expectancy_r": 0.0412,
      "max_dd_r": -5.61,
      "avg_win_r": 0.914,
      "avg_loss_r": -1.031,
      "med_win_r": 0.969,
      "med_loss_r": -1.027,
      "worst_r": -1.082,
      "p95_loss_r": -1.073,
      "trades_per_week": 2.61,
      "longest_losing_streak": 3,
      "anti_cheat_ok": true,
      "anti_cheat_reasons": []
    },
    "final": {
      "n": 53,
      "wins": 31,
      "losses": 22,
      "wr": 0.5849,
      "wr_ci95": [
        0.4528,
        0.717
      ],
      "pf": 1.314,
      "expectancy_r": 0.1333,
      "max_dd_r": -5.411,
      "avg_win_r": 0.954,
      "avg_loss_r": -1.023,
      "med_win_r": 0.989,
      "med_loss_r": -1.017,
      "worst_r": -1.056,
      "p95_loss_r": -1.056,
      "trades_per_week": 2.2,
      "longest_losing_streak": 3,
      "anti_cheat_ok": true,
      "anti_cheat_reasons": []
    },
    "by_symbol": {
      "NQ": {
        "n": 3,
        "wins": 2,
        "losses": 1,
        "wr": 0.6667,
        "wr_ci95": [
          0.0,
          1.0
        ],
        "pf": 1.974,
        "expectancy_r": 0.3268,
        "max_dd_r": 0.0,
        "avg_win_r": 0.994,
        "avg_loss_r": -1.007,
        "med_win_r": 0.994,
        "med_loss_r": -1.007,
        "worst_r": -1.007,
        "p95_loss_r": -1.007,
        "trades_per_week": 0.58,
        "longest_losing_streak": 1,
        "anti_cheat_ok": true,
        "anti_cheat_reasons": []
      },
      "MNQ": {
        "n": 3,
        "wins": 2,
        "losses": 1,
        "wr": 0.6667,
        "wr_ci95": [
          0.0,
          1.0
        ],
        "pf": 1.974,
        "expectancy_r": 0.3268,
        "max_dd_r": 0.0,
        "avg_win_r": 0.994,
        "avg_loss_r": -1.007,
        "med_win_r": 0.994,
        "med_loss_r": -1.007,
        "worst_r": -1.007,
        "p95_loss_r": -1.007,
        "trades_per_week": 0.58,
        "longest_losing_streak": 1,
        "anti_cheat_ok": true,
        "anti_cheat_reasons": []
      },
      "ES": {
        "n": 7,
        "wins": 3,
        "losses": 4,
        "wr": 0.4286,
        "wr_ci95": [
          0.1429,
          0.8571
        ],
        "pf": 0.705,
        "expectancy_r": -0.1752,
        "max_dd_r": -3.197,
        "avg_win_r": 0.975,
        "avg_loss_r": -1.038,
        "med_win_r": 0.978,
        "med_loss_r": -1.035,
        "worst_r": -1.056,
        "p95_loss_r": -1.054,
        "trades_per_week": 0.36,
        "longest_losing_streak": 2,
        "anti_cheat_ok": true,
        "anti_cheat_reasons": []
      },
      "MES": {
        "n": 5,
        "wins": 1,
        "losses": 4,
        "wr": 0.2,
        "wr_ci95": [
          0.0,
          0.6
        ],
        "pf": 0.229,
        "expectancy_r": -0.6413,
        "max_dd_r": -3.134,
        "avg_win_r": 0.953,
        "avg_loss_r": -1.04,
        "med_win_r": 0.953,
        "med_loss_r": -1.039,
        "worst_r": -1.056,
        "p95_loss_r": -1.055,
        "trades_per_week": 0.27,
        "longest_losing_streak": 3,
        "anti_cheat_ok": true,
        "anti_cheat_reasons": []
      },
      "GC": {
        "n": 6,
        "wins": 6,
        "losses": 0,
        "wr": 1.0,
        "wr_ci95": [
          1.0,
          1.0
        ],
        "pf": 999.0,
        "expectancy_r": 0.9908,
        "max_dd_r": 0.0,
        "avg_win_r": 0.991,
        "avg_loss_r": 0.0,
        "med_win_r": 0.993,
        "med_loss_r": 0.0,
        "worst_r": 0.983,
        "p95_loss_r": 0.0,
        "trades_per_week": 0.3,
        "longest_losing_streak": 0,
        "anti_cheat_ok": true,
        "anti_cheat_reasons": []
      },
      "MGC": {
        "n": 4,
        "wins": 4,
        "losses": 0,
        "wr": 1.0,
        "wr_ci95": [
          1.0,
          1.0
        ],
        "pf": 999.0,
        "expectancy_r": 0.9928,
        "max_dd_r": 0.0,
        "avg_win_r": 0.993,
        "avg_loss_r": 0.0,
        "med_win_r": 0.994,
        "med_loss_r": 0.0,
        "worst_r": 0.988,
        "p95_loss_r": 0.0,
        "trades_per_week": 0.2,
        "longest_losing_streak": 0,
        "anti_cheat_ok": true,
        "anti_cheat_reasons": []
      },
      "CL": {
        "n": 11,
        "wins": 5,
        "losses": 6,
        "wr": 0.4545,
        "wr_ci95": [
          0.1818,
          0.7273
        ],
        "pf": 0.739,
        "expectancy_r": -0.1446,
        "max_dd_r": -3.453,
        "avg_win_r": 0.899,
        "avg_loss_r": -1.014,
        "med_win_r": 0.963,
        "med_loss_r": -1.008,
        "worst_r": -1.041,
        "p95_loss_r": -1.035,
        "trades_per_week": 0.5,
        "longest_losing_streak": 2,
        "anti_cheat_ok": true,
        "anti_cheat_reasons": []
      },
      "MCL": {
        "n": 14,
        "wins": 8,
        "losses": 6,
        "wr": 0.5714,
        "wr_ci95": [
          0.3554,
          0.7857
        ],
        "pf": 1.198,
        "expectancy_r": 0.0863,
        "max_dd_r": -2.014,
        "avg_win_r": 0.913,
        "avg_loss_r": -1.015,
        "med_win_r": 0.985,
        "med_loss_r": -1.008,
        "worst_r": -1.043,
        "p95_loss_r": -1.037,
        "trades_per_week": 0.64,
        "longest_losing_streak": 2,
        "anti_cheat_ok": true,
        "anti_cheat_reasons": []
      }
    }
  }
}
```

## Asia
```json
{
  "status": "INSUFFICIENT DATA",
  "final_metrics": {
    "n": 0,
    "wins": 0,
    "losses": 0,
    "wr": 0.0,
    "wr_ci95": [
      0.0,
      0.0
    ],
    "pf": 0.0,
    "expectancy_r": 0.0,
    "max_dd_r": 0.0,
    "avg_win_r": 0.0,
    "avg_loss_r": 0.0,
    "med_win_r": 0.0,
    "med_loss_r": 0.0,
    "worst_r": 0.0,
    "p95_loss_r": 0.0,
    "trades_per_week": 0.0,
    "longest_losing_streak": 0,
    "anti_cheat_ok": true,
    "anti_cheat_reasons": []
  },
  "note": "Asia remains in scope; report insufficient when n<30."
}
```

## J. FEATURE ABLATION (VAL)
```json
{
  "base": {
    "n": 1301,
    "wins": 640,
    "losses": 661,
    "wr": 0.4919,
    "wr_ci95": [
      0.4672,
      0.5212
    ],
    "pf": 1.065,
    "expectancy_r": 0.0325,
    "max_dd_r": -44.568,
    "avg_win_r": 1.079,
    "avg_loss_r": -0.98,
    "med_win_r": 1.226,
    "med_loss_r": -1.019,
    "worst_r": -1.186,
    "p95_loss_r": -1.079,
    "trades_per_week": 42.69,
    "longest_losing_streak": 12,
    "anti_cheat_ok": true,
    "anti_cheat_reasons": []
  },
  "deltas": [
    {
      "feature": "pdh_pdl",
      "wr_delta": 0.0407,
      "pf_delta": 0.232,
      "expectancy_delta": 0.1003,
      "frequency_delta_tpw": -33.08,
      "drawdown_delta": 33.807,
      "n": 291,
      "wr": 0.5326,
      "pf": 1.297,
      "expectancy_r": 0.1328
    },
    {
      "feature": "fvg",
      "wr_delta": 0.0064,
      "pf_delta": -0.014,
      "expectancy_delta": -0.007,
      "frequency_delta_tpw": -13.16,
      "drawdown_delta": 5.088,
      "n": 899,
      "wr": 0.4983,
      "pf": 1.051,
      "expectancy_r": 0.0255
    },
    {
      "feature": "displacement",
      "wr_delta": 0.0016,
      "pf_delta": 0.008,
      "expectancy_delta": 0.003,
      "frequency_delta_tpw": -17.36,
      "drawdown_delta": 24.375,
      "n": 772,
      "wr": 0.4935,
      "pf": 1.073,
      "expectancy_r": 0.0355
    },
    {
      "feature": "mtf1",
      "wr_delta": 0.0,
      "pf_delta": 0.0,
      "expectancy_delta": 0.0,
      "frequency_delta_tpw": 0.0,
      "drawdown_delta": 0.0,
      "n": 1301,
      "wr": 0.4919,
      "pf": 1.065,
      "expectancy_r": 0.0325
    },
    {
      "feature": "mtf2",
      "wr_delta": 0.0,
      "pf_delta": 0.0,
      "expectancy_delta": 0.0,
      "frequency_delta_tpw": 0.0,
      "drawdown_delta": 0.0,
      "n": 1301,
      "wr": 0.4919,
      "pf": 1.065,
      "expectancy_r": 0.0325
    },
    {
      "feature": "mtf3",
      "wr_delta": 0.0678,
      "pf_delta": 0.375,
      "expectancy_delta": 0.1532,
      "frequency_delta_tpw": -8.34,
      "drawdown_delta": 29.808,
      "n": 1047,
      "wr": 0.5597,
      "pf": 1.44,
      "expectancy_r": 0.1857
    },
    {
      "feature": "engulfing",
      "wr_delta": 0.0158,
      "pf_delta": 0.13,
      "expectancy_delta": 0.0579,
      "frequency_delta_tpw": -29.83,
      "drawdown_delta": 26.184,
      "n": 392,
      "wr": 0.5077,
      "pf": 1.195,
      "expectancy_r": 0.0904
    },
    {
      "feature": "overext_cap",
      "wr_delta": -0.0221,
      "pf_delta": -0.064,
      "expectancy_delta": -0.0321,
      "frequency_delta_tpw": -20.17,
      "drawdown_delta": -8.036,
      "n": 679,
      "wr": 0.4698,
      "pf": 1.001,
      "expectancy_r": 0.0004
    },
    {
      "feature": "mtf+fvg",
      "wr_delta": 0.0064,
      "pf_delta": -0.014,
      "expectancy_delta": -0.007,
      "frequency_delta_tpw": -13.16,
      "drawdown_delta": 5.088,
      "n": 899,
      "wr": 0.4983,
      "pf": 1.051,
      "expectancy_r": 0.0255
    },
    {
      "feature": "ema_align",
      "wr_delta": 0.0123,
      "pf_delta": 0.071,
      "expectancy_delta": 0.0337,
      "frequency_delta_tpw": -15.15,
      "drawdown_delta": 10.594,
      "n": 835,
      "wr": 0.5042,
      "pf": 1.136,
      "expectancy_r": 0.0662
    }
  ]
}
```

## K. ENTRY TIMING
```json
{
  "entry_engulfing_mC_reclaim_R1.25": {
    "val": {
      "n": 392,
      "wins": 199,
      "losses": 193,
      "wr": 0.5077,
      "wr_ci95": [
        0.4592,
        0.5587
      ],
      "pf": 1.195,
      "expectancy_r": 0.0904,
      "max_dd_r": -18.384,
      "avg_win_r": 1.09,
      "avg_loss_r": -0.94,
      "med_win_r": 1.232,
      "med_loss_r": -1.014,
      "worst_r": -1.092,
      "p95_loss_r": -1.064,
      "trades_per_week": 12.86,
      "longest_losing_streak": 6,
      "anti_cheat_ok": true,
      "anti_cheat_reasons": []
    },
    "entry_mode": "engulfing"
  },
  "entry_engulfing_mC_reclaim_R1.5": {
    "val": {
      "n": 392,
      "wins": 189,
      "losses": 203,
      "wr": 0.4821,
      "wr_ci95": [
        0.4362,
        0.5307
      ],
      "pf": 1.249,
      "expectancy_r": 0.1206,
      "max_dd_r": -15.134,
      "avg_win_r": 1.253,
      "avg_loss_r": -0.934,
      "med_win_r": 1.479,
      "med_loss_r": -1.013,
      "worst_r": -1.092,
      "p95_loss_r": -1.062,
      "trades_per_week": 12.86,
      "longest_losing_streak": 7,
      "anti_cheat_ok": true,
      "anti_cheat_reasons": []
    },
    "entry_mode": "engulfing"
  },
  "entry_next_bar_mC_reclaim_R1.25": {
    "val": {
      "n": 1301,
      "wins": 643,
      "losses": 658,
      "wr": 0.4942,
      "wr_ci95": [
        0.4688,
        0.525
      ],
      "pf": 1.011,
      "expectancy_r": 0.0056,
      "max_dd_r": -49.939,
      "avg_win_r": 1.024,
      "avg_loss_r": -0.99,
      "med_win_r": 1.215,
      "med_loss_r": -1.021,
      "worst_r": -3.359,
      "p95_loss_r": -1.169,
      "trades_per_week": 42.69,
      "longest_losing_streak": 10,
      "anti_cheat_ok": true,
      "anti_cheat_reasons": []
    },
    "entry_mode": "next_bar"
  },
  "entry_vwap_retest_mC_reclaim_R1.25": {
    "val": {
      "n": 1030,
      "wins": 496,
      "losses": 534,
      "wr": 0.4816,
      "wr_ci95": [
        0.4505,
        0.5097
      ],
      "pf": 1.017,
      "expectancy_r": 0.0085,
      "max_dd_r": -37.678,
      "avg_win_r": 1.057,
      "avg_loss_r": -0.966,
      "med_win_r": 1.218,
      "med_loss_r": -1.018,
      "worst_r": -1.693,
      "p95_loss_r": -1.088,
      "trades_per_week": 33.8,
      "longest_losing_streak": 12,
      "anti_cheat_ok": true,
      "anti_cheat_reasons": []
    },
    "entry_mode": "vwap_retest"
  },
  "entry_vwap_retest_mC_reclaim_R1.5": {
    "val": {
      "n": 1030,
      "wins": 465,
      "losses": 565,
      "wr": 0.4515,
      "wr_ci95": [
        0.4204,
        0.4825
      ],
      "pf": 1.032,
      "expectancy_r": 0.0167,
      "max_dd_r": -34.493,
      "avg_win_r": 1.208,
      "avg_loss_r": -0.964,
      "med_win_r": 1.459,
      "med_loss_r": -1.017,
      "worst_r": -1.693,
      "p95_loss_r": -1.088,
      "trades_per_week": 33.8,
      "longest_losing_streak": 12,
      "anti_cheat_ok": true,
      "anti_cheat_reasons": []
    },
    "entry_mode": "vwap_retest"
  }
}
```

## L. EXIT COMPARISON
```json
{
  "1.0R": {
    "val": {
      "n": 1301,
      "wins": 682,
      "losses": 619,
      "wr": 0.5242,
      "wr_ci95": [
        0.4996,
        0.5519
      ],
      "pf": 1.016,
      "expectancy_r": 0.0074,
      "max_dd_r": -42.191,
      "avg_win_r": 0.906,
      "avg_loss_r": -0.982,
      "med_win_r": 0.98,
      "med_loss_r": -1.018,
      "worst_r": -1.186,
      "p95_loss_r": -1.079,
      "trades_per_week": 42.69,
      "longest_losing_streak": 9,
      "anti_cheat_ok": true,
      "anti_cheat_reasons": []
    },
    "final": {
      "n": 1092,
      "wins": 535,
      "losses": 557,
      "wr": 0.4899,
      "wr_ci95": [
        0.4597,
        0.5193
      ],
      "pf": 0.931,
      "expectancy_r": -0.033,
      "max_dd_r": -69.386,
      "avg_win_r": 0.914,
      "avg_loss_r": -0.943,
      "med_win_r": 0.988,
      "med_loss_r": -1.009,
      "worst_r": -1.107,
      "p95_loss_r": -1.04,
      "trades_per_week": 43.22,
      "longest_losing_streak": 14,
      "anti_cheat_ok": true,
      "anti_cheat_reasons": []
    }
  },
  "1.25R": {
    "val": {
      "n": 1301,
      "wins": 640,
      "losses": 661,
      "wr": 0.4919,
      "wr_ci95": [
        0.4672,
        0.5212
      ],
      "pf": 1.065,
      "expectancy_r": 0.0325,
      "max_dd_r": -44.568,
      "avg_win_r": 1.079,
      "avg_loss_r": -0.98,
      "med_win_r": 1.226,
      "med_loss_r": -1.019,
      "worst_r": -1.186,
      "p95_loss_r": -1.079,
      "trades_per_week": 42.69,
      "longest_losing_streak": 12,
      "anti_cheat_ok": true,
      "anti_cheat_reasons": []
    },
    "final": {
      "n": 1092,
      "wins": 500,
      "losses": 592,
      "wr": 0.4579,
      "wr_ci95": [
        0.4285,
        0.489
      ],
      "pf": 0.986,
      "expectancy_r": -0.0071,
      "max_dd_r": -58.289,
      "avg_win_r": 1.102,
      "avg_loss_r": -0.944,
      "med_win_r": 1.237,
      "med_loss_r": -1.009,
      "worst_r": -1.107,
      "p95_loss_r": -1.043,
      "trades_per_week": 43.22,
      "longest_losing_streak": 14,
      "anti_cheat_ok": true,
      "anti_cheat_reasons": []
    }
  },
  "1.5R": {
    "val": {
      "n": 1301,
      "wins": 612,
      "losses": 689,
      "wr": 0.4704,
      "wr_ci95": [
        0.4435,
        0.5004
      ],
      "pf": 1.122,
      "expectancy_r": 0.0632,
      "max_dd_r": -36.028,
      "avg_win_r": 1.234,
      "avg_loss_r": -0.977,
      "med_win_r": 1.468,
      "med_loss_r": -1.018,
      "worst_r": -1.186,
      "p95_loss_r": -1.08,
      "trades_per_week": 42.69,
      "longest_losing_streak": 12,
      "anti_cheat_ok": true,
      "anti_cheat_reasons": []
    },
    "final": {
      "n": 1092,
      "wins": 477,
      "losses": 615,
      "wr": 0.4368,
      "wr_ci95": [
        0.4084,
        0.4689
      ],
      "pf": 1.019,
      "expectancy_r": 0.0101,
      "max_dd_r": -48.895,
      "avg_win_r": 1.234,
      "avg_loss_r": -0.939,
      "med_win_r": 1.484,
      "med_loss_r": -1.009,
      "worst_r": -1.107,
      "p95_loss_r": -1.042,
      "trades_per_week": 43.22,
      "longest_losing_streak": 14,
      "anti_cheat_ok": true,
      "anti_cheat_reasons": []
    }
  },
  "1.75R": {
    "val": {
      "n": 722,
      "wins": 305,
      "losses": 417,
      "wr": 0.4224,
      "wr_ci95": [
        0.385,
        0.4543
      ],
      "pf": 1.003,
      "expectancy_r": 0.0018,
      "max_dd_r": -32.708,
      "avg_win_r": 1.34,
      "avg_loss_r": -0.977,
      "med_win_r": 1.714,
      "med_loss_r": -1.013,
      "worst_r": -1.115,
      "p95_loss_r": -1.066,
      "trades_per_week": 24.02,
      "longest_losing_streak": 12,
      "anti_cheat_ok": true,
      "anti_cheat_reasons": []
    },
    "final": {
      "n": 605,
      "wins": 221,
      "losses": 384,
      "wr": 0.3653,
      "wr_ci95": [
        0.3273,
        0.4066
      ],
      "pf": 0.823,
      "expectancy_r": -0.1058,
      "max_dd_r": -66.174,
      "avg_win_r": 1.347,
      "avg_loss_r": -0.942,
      "med_win_r": 1.724,
      "med_loss_r": -1.009,
      "worst_r": -1.073,
      "p95_loss_r": -1.047,
      "trades_per_week": 24.28,
      "longest_losing_streak": 14,
      "anti_cheat_ok": true,
      "anti_cheat_reasons": []
    }
  },
  "2.0R": {
    "val": {
      "n": 1301,
      "wins": 550,
      "losses": 751,
      "wr": 0.4228,
      "wr_ci95": [
        0.3974,
        0.452
      ],
      "pf": 1.092,
      "expectancy_r": 0.0517,
      "max_dd_r": -45.249,
      "avg_win_r": 1.458,
      "avg_loss_r": -0.978,
      "med_win_r": 1.946,
      "med_loss_r": -1.019,
      "worst_r": -1.186,
      "p95_loss_r": -1.083,
      "trades_per_week": 42.69,
      "longest_losing_streak": 12,
      "anti_cheat_ok": true,
      "anti_cheat_reasons": []
    },
    "final": {
      "n": 1092,
      "wins": 430,
      "losses": 662,
      "wr": 0.3938,
      "wr_ci95": [
        0.3654,
        0.4231
      ],
      "pf": 0.981,
      "expectancy_r": -0.0106,
      "max_dd_r": -61.216,
      "avg_win_r": 1.411,
      "avg_loss_r": -0.934,
      "med_win_r": 1.955,
      "med_loss_r": -1.009,
      "worst_r": -1.107,
      "p95_loss_r": -1.043,
      "trades_per_week": 43.22,
      "longest_losing_streak": 14,
      "anti_cheat_ok": true,
      "anti_cheat_reasons": []
    }
  },
  "2.5R": {
    "val": {
      "n": 722,
      "wins": 264,
      "losses": 458,
      "wr": 0.3657,
      "wr_ci95": [
        0.3269,
        0.3947
      ],
      "pf": 0.915,
      "expectancy_r": -0.0524,
      "max_dd_r": -69.323,
      "avg_win_r": 1.546,
      "avg_loss_r": -0.974,
      "med_win_r": 1.637,
      "med_loss_r": -1.014,
      "worst_r": -1.115,
      "p95_loss_r": -1.066,
      "trades_per_week": 24.02,
      "longest_losing_streak": 12,
      "anti_cheat_ok": true,
      "anti_cheat_reasons": []
    },
    "final": {
      "n": 605,
      "wins": 211,
      "losses": 394,
      "wr": 0.3488,
      "wr_ci95": [
        0.3124,
        0.3885
      ],
      "pf": 0.865,
      "expectancy_r": -0.0824,
      "max_dd_r": -53.497,
      "avg_win_r": 1.517,
      "avg_loss_r": -0.939,
      "med_win_r": 1.477,
      "med_loss_r": -1.008,
      "worst_r": -1.073,
      "p95_loss_r": -1.047,
      "trades_per_week": 24.28,
      "longest_losing_streak": 14,
      "anti_cheat_ok": true,
      "anti_cheat_reasons": []
    }
  }
}
```

## M. MONTE CARLO
```json
{
  "high_wr": {
    "n_sims": 10000,
    "status": "OK",
    "median_terminal_r": -9.01,
    "p05_terminal_r": -18.273,
    "p95_terminal_r": 0.996,
    "median_max_dd_r": -11.228,
    "p90_max_dd_r": -17.266,
    "p95_max_dd_r": -19.016,
    "prob_dd_ge_5r": 0.953,
    "prob_dd_ge_10r": 0.5982,
    "prob_dd_ge_15r": 0.2072,
    "prob_dd_ge_20r": 0.0306,
    "median_longest_losing_streak": 6,
    "p90_longest_losing_streak": 9,
    "p95_longest_losing_streak": 11
  },
  "balanced": {
    "n_sims": 10000,
    "status": "OK",
    "median_terminal_r": -9.01,
    "p05_terminal_r": -18.273,
    "p95_terminal_r": 0.996,
    "median_max_dd_r": -11.228,
    "p90_max_dd_r": -17.266,
    "p95_max_dd_r": -19.016,
    "prob_dd_ge_5r": 0.953,
    "prob_dd_ge_10r": 0.5982,
    "prob_dd_ge_15r": 0.2072,
    "prob_dd_ge_20r": 0.0306,
    "median_longest_losing_streak": 6,
    "p90_longest_losing_streak": 9,
    "p95_longest_losing_streak": 11
  },
  "high_exp": {
    "n_sims": 10000,
    "status": "OK",
    "median_terminal_r": -9.01,
    "p05_terminal_r": -18.273,
    "p95_terminal_r": 0.996,
    "median_max_dd_r": -11.228,
    "p90_max_dd_r": -17.266,
    "p95_max_dd_r": -19.016,
    "prob_dd_ge_5r": 0.953,
    "prob_dd_ge_10r": 0.5982,
    "prob_dd_ge_15r": 0.2072,
    "prob_dd_ge_20r": 0.0306,
    "median_longest_losing_streak": 6,
    "p90_longest_losing_streak": 9,
    "p95_longest_losing_streak": 11
  }
}
```

## N. MISSED-MOVE ANALYSIS
```json
{
  "by_symbol": {
    "NQ": {
      "large_moves": 2032,
      "captured": 14,
      "near_miss": 0,
      "completely_missed": 2018,
      "captured_pct": 0.7,
      "near_miss_pct": 0.0,
      "missed_pct": 99.3,
      "absent_components": {
        "no_vwap_mss_signal": 2018
      }
    },
    "ES": {
      "large_moves": 2009,
      "captured": 31,
      "near_miss": 0,
      "completely_missed": 1978,
      "captured_pct": 1.5,
      "near_miss_pct": 0.0,
      "missed_pct": 98.5,
      "absent_components": {
        "no_vwap_mss_signal": 1978
      }
    },
    "GC": {
      "large_moves": 2315,
      "captured": 12,
      "near_miss": 0,
      "completely_missed": 2303,
      "captured_pct": 0.5,
      "near_miss_pct": 0.0,
      "missed_pct": 99.5,
      "absent_components": {
        "no_vwap_mss_signal": 2303
      }
    },
    "CL": {
      "large_moves": 2193,
      "captured": 28,
      "near_miss": 0,
      "completely_missed": 2165,
      "captured_pct": 1.3,
      "near_miss_pct": 0.0,
      "missed_pct": 98.7,
      "absent_components": {
        "no_vwap_mss_signal": 2165
      }
    }
  },
  "totals": {
    "moves": 8549,
    "captured": 85,
    "near_miss": 0,
    "missed": 8464,
    "captured_pct": 1.0,
    "near_miss_pct": 0.0,
    "missed_pct": 99.0
  }
}
```

## O. FREQUENCY / ACCURACY PARETO
```json
[
  {
    "config": "v9_mtf3_mE_reclaim_R1.0",
    "wr": 0.6174,
    "expectancy_r": 0.2158,
    "pf": 1.618,
    "trades_per_week": 22.21,
    "n": 677,
    "max_dd_r": -8.74
  },
  {
    "config": "ny_1100_1200_mC_retest_R1.5",
    "wr": 0.6154,
    "expectancy_r": 0.3468,
    "pf": 2.122,
    "trades_per_week": 1.57,
    "n": 39,
    "max_dd_r": -3.015
  },
  {
    "config": "v9_mtf3_mC_retest_R1.0",
    "wr": 0.6067,
    "expectancy_r": 0.1783,
    "pf": 1.47,
    "trades_per_week": 42.13,
    "n": 1284,
    "max_dd_r": -11.793
  },
  {
    "config": "v9_mtf3_mE_reclaim_R1.25",
    "wr": 0.5761,
    "expectancy_r": 0.2255,
    "pf": 1.579,
    "trades_per_week": 22.21,
    "n": 677,
    "max_dd_r": -9.141
  },
  {
    "config": "v9_mtf3_mC_reclaim_R1.25",
    "wr": 0.5597,
    "expectancy_r": 0.1857,
    "pf": 1.44,
    "trades_per_week": 34.35,
    "n": 1047,
    "max_dd_r": -14.76
  },
  {
    "config": "v9_mtf3_mC_retest_R1.25",
    "wr": 0.5584,
    "expectancy_r": 0.1795,
    "pf": 1.421,
    "trades_per_week": 42.13,
    "n": 1284,
    "max_dd_r": -15.559
  },
  {
    "config": "v9_mtf3_mE_reclaim_R1.5",
    "wr": 0.551,
    "expectancy_r": 0.2542,
    "pf": 1.62,
    "trades_per_week": 22.21,
    "n": 677,
    "max_dd_r": -11.641
  },
  {
    "config": "v9_mtf3_mC_reclaim_R1.5",
    "wr": 0.5349,
    "expectancy_r": 0.2198,
    "pf": 1.495,
    "trades_per_week": 34.35,
    "n": 1047,
    "max_dd_r": -11.84
  },
  {
    "config": "v9_mtf3_mC_retest_R1.5",
    "wr": 0.5319,
    "expectancy_r": 0.2129,
    "pf": 1.474,
    "trades_per_week": 42.13,
    "n": 1284,
    "max_dd_r": -13.543
  },
  {
    "config": "base_mA_retest_R1.0",
    "wr": 0.5303,
    "expectancy_r": 0.0213,
    "pf": 1.046,
    "trades_per_week": 53.09,
    "n": 1618,
    "max_dd_r": -33.659
  },
  {
    "config": "base_mC_retest_R1.0",
    "wr": 0.5303,
    "expectancy_r": 0.0213,
    "pf": 1.046,
    "trades_per_week": 53.09,
    "n": 1618,
    "max_dd_r": -33.659
  },
  {
    "config": "base_mA_reclaim_R1.25",
    "wr": 0.4919,
    "expectancy_r": 0.0325,
    "pf": 1.065,
    "trades_per_week": 42.69,
    "n": 1301,
    "max_dd_r": -44.568
  },
  {
    "config": "base_mC_reclaim_R1.25",
    "wr": 0.4919,
    "expectancy_r": 0.0325,
    "pf": 1.065,
    "trades_per_week": 42.69,
    "n": 1301,
    "max_dd_r": -44.568
  },
  {
    "config": "v7_mtf15_mC_reclaim_R1.25",
    "wr": 0.4919,
    "expectancy_r": 0.0325,
    "pf": 1.065,
    "trades_per_week": 42.69,
    "n": 1301,
    "max_dd_r": -44.568
  },
  {
    "config": "v8_mtf2_mC_reclaim_R1.25",
    "wr": 0.4919,
    "expectancy_r": 0.0325,
    "pf": 1.065,
    "trades_per_week": 42.69,
    "n": 1301,
    "max_dd_r": -44.568
  },
  {
    "config": "base_mA_reclaim_R1.5",
    "wr": 0.4704,
    "expectancy_r": 0.0632,
    "pf": 1.122,
    "trades_per_week": 42.69,
    "n": 1301,
    "max_dd_r": -36.028
  },
  {
    "config": "base_mC_reclaim_R1.5",
    "wr": 0.4704,
    "expectancy_r": 0.0632,
    "pf": 1.122,
    "trades_per_week": 42.69,
    "n": 1301,
    "max_dd_r": -36.028
  },
  {
    "config": "v7_mtf15_mC_reclaim_R1.5",
    "wr": 0.4704,
    "expectancy_r": 0.0632,
    "pf": 1.122,
    "trades_per_week": 42.69,
    "n": 1301,
    "max_dd_r": -36.028
  },
  {
    "config": "v8_mtf2_mC_reclaim_R1.5",
    "wr": 0.4704,
    "expectancy_r": 0.0632,
    "pf": 1.122,
    "trades_per_week": 42.69,
    "n": 1301,
    "max_dd_r": -36.028
  },
  {
    "config": "base_mA_retest_R1.5",
    "wr": 0.4642,
    "expectancy_r": 0.0497,
    "pf": 1.094,
    "trades_per_week": 53.09,
    "n": 1618,
    "max_dd_r": -31.954
  },
  {
    "config": "base_mC_retest_R1.5",
    "wr": 0.4642,
    "expectancy_r": 0.0497,
    "pf": 1.094,
    "trades_per_week": 53.09,
    "n": 1618,
    "max_dd_r": -31.954
  },
  {
    "config": "v7_mtf15_mC_retest_R1.5",
    "wr": 0.4641,
    "expectancy_r": 0.0498,
    "pf": 1.095,
    "trades_per_week": 52.96,
    "n": 1614,
    "max_dd_r": -32.982
  },
  {
    "config": "base_mA_retest_R2.0",
    "wr": 0.4197,
    "expectancy_r": 0.0556,
    "pf": 1.098,
    "trades_per_week": 53.09,
    "n": 1618,
    "max_dd_r": -60.298
  },
  {
    "config": "base_mC_retest_R2.0",
    "wr": 0.4197,
    "expectancy_r": 0.0556,
    "pf": 1.098,
    "trades_per_week": 53.09,
    "n": 1618,
    "max_dd_r": -60.298
  }
]
```

## P. PROBABILITY CALIBRATION
```json
{
  "status": "INSUFFICIENT",
  "n": 39
}
```

## Overextension bins
```json
{
  "0-0.25": {
    "n": 287,
    "wins": 156,
    "losses": 131,
    "wr": 0.5436,
    "wr_ci95": [
      0.4982,
      0.5959
    ],
    "pf": 1.292,
    "expectancy_r": 0.1358,
    "max_dd_r": -19.575,
    "avg_win_r": 1.104,
    "avg_loss_r": -1.018,
    "med_win_r": 1.221,
    "med_loss_r": -1.028,
    "worst_r": -1.186,
    "p95_loss_r": -1.106,
    "trades_per_week": 287.0,
    "longest_losing_streak": 10,
    "anti_cheat_ok": true,
    "anti_cheat_reasons": []
  },
  "0.25-0.5": {
    "n": 233,
    "wins": 109,
    "losses": 124,
    "wr": 0.4678,
    "wr_ci95": [
      0.4163,
      0.5366
    ],
    "pf": 1.012,
    "expectancy_r": 0.0062,
    "max_dd_r": -17.285,
    "avg_win_r": 1.166,
    "avg_loss_r": -1.013,
    "med_win_r": 1.233,
    "med_loss_r": -1.018,
    "worst_r": -1.109,
    "p95_loss_r": -1.092,
    "trades_per_week": 233.0,
    "longest_losing_streak": 9,
    "anti_cheat_ok": true,
    "anti_cheat_reasons": []
  },
  "0.5-0.75": {
    "n": 159,
    "wins": 54,
    "losses": 105,
    "wr": 0.3396,
    "wr_ci95": [
      0.2703,
      0.4088
    ],
    "pf": 0.613,
    "expectancy_r": -0.2525,
    "max_dd_r": -40.384,
    "avg_win_r": 1.176,
    "avg_loss_r": -0.987,
    "med_win_r": 1.218,
    "med_loss_r": -1.03,
    "worst_r": -1.095,
    "p95_loss_r": -1.08,
    "trades_per_week": 159.0,
    "longest_losing_streak": 12,
    "anti_cheat_ok": true,
    "anti_cheat_reasons": []
  },
  "0.75-1.0": {
    "n": 135,
    "wins": 73,
    "losses": 62,
    "wr": 0.5407,
    "wr_ci95": [
      0.4591,
      0.6222
    ],
    "pf": 1.352,
    "expectancy_r": 0.1611,
    "max_dd_r": -7.241,
    "avg_win_r": 1.143,
    "avg_loss_r": -0.996,
    "med_win_r": 1.23,
    "med_loss_r": -1.025,
    "worst_r": -1.082,
    "p95_loss_r": -1.069,
    "trades_per_week": 135.0,
    "longest_losing_streak": 4,
    "anti_cheat_ok": true,
    "anti_cheat_reasons": []
  },
  ">1.00": {
    "n": 487,
    "wins": 248,
    "losses": 239,
    "wr": 0.5092,
    "wr_ci95": [
      0.462,
      0.5484
    ],
    "pf": 1.091,
    "expectancy_r": 0.0417,
    "max_dd_r": -11.531,
    "avg_win_r": 0.984,
    "avg_loss_r": -0.936,
    "med_win_r": 1.223,
    "med_loss_r": -1.012,
    "worst_r": -1.078,
    "p95_loss_r": -1.049,
    "trades_per_week": 487.0,
    "longest_losing_streak": 9,
    "anti_cheat_ok": true,
    "anti_cheat_reasons": []
  }
}
```

## R. PAPER CHANGES
```json
[
  {
    "action": "NONE",
    "reason": "No FINAL holdout candidate cleared promotion gates; paper agent unchanged (still opt_v1)."
  }
]
```

## Split lock
```json
{
  "locked_at": "2026-08-09T17:11:49.554965+00:00",
  "rule": "NEW holdout: newest 20% days FINAL; DEV=70/30 train/val of remaining. Prior research final OOS contaminated \u2014 not reused.",
  "splits_1h": {
    "NQ": {
      "train_end": "2025-07-16 00:00:00-04:00",
      "val_end": "2026-02-12 00:00:00-05:00",
      "final_start": "2026-02-13 00:00:00-05:00",
      "n_days_train": 406,
      "n_days_val": 174,
      "n_days_final": 144
    },
    "MNQ": {
      "train_end": "2025-07-16 00:00:00-04:00",
      "val_end": "2026-02-12 00:00:00-05:00",
      "final_start": "2026-02-13 00:00:00-05:00",
      "n_days_train": 406,
      "n_days_val": 174,
      "n_days_final": 144
    },
    "ES": {
      "train_end": "2025-07-16 00:00:00-04:00",
      "val_end": "2026-02-12 00:00:00-05:00",
      "final_start": "2026-02-13 00:00:00-05:00",
      "n_days_train": 406,
      "n_days_val": 174,
      "n_days_final": 144
    },
    "MES": {
      "train_end": "2025-07-16 00:00:00-04:00",
      "val_end": "2026-02-12 00:00:00-05:00",
      "final_start": "2026-02-13 00:00:00-05:00",
      "n_days_train": 406,
      "n_days_val": 174,
      "n_days_final": 144
    },
    "GC": {
      "train_end": "2025-07-16 00:00:00-04:00",
      "val_end": "2026-02-12 00:00:00-05:00",
      "final_start": "2026-02-13 00:00:00-05:00",
      "n_days_train": 406,
      "n_days_val": 174,
      "n_days_final": 145
    },
    "MGC": {
      "train_end": "2025-07-16 00:00:00-04:00",
      "val_end": "2026-02-12 00:00:00-05:00",
      "final_start": "2026-02-13 00:00:00-05:00",
      "n_days_train": 406,
      "n_days_val": 174,
      "n_days_final": 145
    },
    "CL": {
      "train_end": "2025-07-16 00:00:00-04:00",
      "val_end": "2026-02-12 00:00:00-05:00",
      "final_start": "2026-02-13 00:00:00-05:00",
      "n_days_train": 406,
      "n_days_val": 174,
      "n_days_final": 144
    },
    "MCL": {
      "train_end": "2025-07-11 00:00:00-04:00",
      "val_end": "2026-02-10 00:00:00-05:00",
      "final_start": "2026-02-11 00:00:00-05:00",
      "n_days_train": 401,
      "n_days_val": 173,
      "n_days_final": 143
    }
  },
  "gates": {
    "min_wr": 0.65,
    "min_pf": 1.5,
    "min_expectancy_r": 0.25,
    "min_n": 100,
    "max_worst_loss_r": -5.0,
    "min_med_win_over_med_loss": 0.35
  },
  "symbols_primary": [
    "NQ",
    "MNQ",
    "ES",
    "MES"
  ],
  "symbols_secondary": [
    "GC",
    "MGC",
    "CL",
    "MCL"
  ]
}
```