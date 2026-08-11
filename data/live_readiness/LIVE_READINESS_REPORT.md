# LIVE READINESS REPORT

Generated: 2026-08-11T15:46:53.534275+00:00
**Verdict: READY FOR BROKER-SIM VALIDATION**

## A. SYSTEM HEALTH
- config_version: router_v1_readiness1
- execution_profile: balanced · mode=paper · v2_enabled=False
- supervisor: running / healthy
- heartbeat_age_sec: 4.7
- silence: OK mins=5.0

## B. ADAPTIVE LEARNING
- E2E pipeline_ok: True
- e2e candidates/resolved: 12/12
- schema_version: 2
- retrain: {'retrained': True, 'challenger': 'trade_quality_challenger_20260811_1547', 'brier': 0.2395512444585533, 'calibrated': False, 'promoted': False, 'bins': [{'bin': '50-55', 'n': 16, 'pred_avg': 0.5113775748001292, 'actual_wr': 0.3125}, {'bin': '55-60', 'n': 0, 'pred_avg': None, 'actual_wr': None}, {'bin': '60-65', 'n': 0, 'pred_avg': None, 'actual_wr': None}, {'bin': '65-70', 'n': 0, 'pred_avg': None, 'actual_wr': None}, {'bin': '70-75', 'n': 0, 'pred_avg': None, 'actual_wr': None}, {'bin': '75-80', 'n': 0, 'pred_avg': None, 'actual_wr': None}, {'bin': '80+', 'n': 0, 'pred_avg': None, 'actual_wr': None}], 'family': 'nonlinear', 'model': 'random_forest'}
- persistence_files_ok: True
- production store rows: 758
- champion: trade_quality_v1_20260810

## C. CL ANALYSIS
- warning: This paper winner is cl_vwap_prox_momentum (validated specialist), NOT liquidity_reversal. Do not treat as LR promotion evidence.
- trade_id: PAPER-00151
- snapshot strategy: cl_vwap_prox_momentum
- LR hist overall: {'n': 833, 'wr': 0.3985594237695078, 'raw_wr': 0.3985594237695078, 'shrunk_wr': 0.40093786635404455, 'pf': 0.9940119760479035, 'expectancy_r': -0.0036014405762308703, 'max_dd_r': -36.50000000000051, 'category': 'VALIDATED'}
- relative best cells: 15
- validated/developing/early: 25/2/0

## D. SCORE/TIER CALIBRATION
- tier: {'tiers': {'A': {'n': 234, 'wr': 0.32051282051282054, 'pf': 0.7776881775935656, 'expectancy_r': -0.10498411853965593}, 'A+': {'n': 150, 'wr': 0.3, 'pf': 0.6812379368263294, 'expectancy_r': -0.1714002943836722}, 'B': {'n': 418, 'wr': 0.40669856459330145, 'pf': 1.034503231332243, 'expectancy_r': 0.016961722488038285}}, 'flag': 'TIER_CALIBRATION_FAILURE'}
- global score buckets: [{'bucket': '50-59', 'n': 32, 'wr': 0.53125, 'pf': 1.8475333333333332, 'expectancy_r': 0.39728125}, {'bucket': '60-69', 'n': 177, 'wr': 0.384180790960452, 'pf': 0.885487479095628, 'expectancy_r': -0.059576271186440655}, {'bucket': '70-79', 'n': 162, 'wr': 0.345679012345679, 'pf': 0.9593453428441576, 'expectancy_r': -0.020988778538794318}, {'bucket': '80-89', 'n': 215, 'wr': 0.3581395348837209, 'pf': 0.8172303670106955, 'expectancy_r': -0.08540124654587869}, {'bucket': '90+', 'n': 226, 'wr': 0.3274336283185841, 'pf': 0.7617047122531154, 'expectancy_r': -0.11952446654440825}]
- flags: tier=TIER_CALIBRATION_FAILURE score=GLOBAL_SCORE_CALIBRATION_FAILURE

## E. ROUTER COMPARISON (FINAL holdout, costs_r=0.05)
- v1: {'raw_n': 18, 'raw_wr': 0.3333333333333333, 'raw_expectancy_r': -0.22683333333333333, 'raw_pf': 0.6597500000000001, 'n': 18, 'wr': 0.3333333333333333, 'wr_ci95': [0.16278554363662856, 0.5625093065574964], 'pf': 0.6045238095238096, 'expectancy_r': -0.2768333333333333, 'max_dd_r': -4.811, 'trades_per_week': 18.0, 'avg_win': 1.2695, 'avg_loss': -1.0500000000000003, 'worst': -1.05, 'longest_losing_streak': 3, 'costs_r_applied': 0.05}
- v2 HC: {'raw_n': 18, 'raw_wr': 0.3888888888888889, 'raw_expectancy_r': 0.23787839877428224, 'raw_pf': 1.5285410909416062, 'n': 18, 'wr': 0.3888888888888889, 'wr_ci95': [0.2030499192693116, 0.6138133141934383], 'pf': 1.3909071050804636, 'expectancy_r': 0.18787839877428222, 'max_dd_r': -3.172188822062921, 'trades_per_week': 18.0, 'avg_win': 1.7189999999999999, 'avg_loss': -0.7864717110966292, 'worst': -1.05, 'longest_losing_streak': 3, 'costs_r_applied': 0.05}
- material_oos_improvement: False
- deploy_v2_paper: False — keep router_v1 paper — v2 shows directional lift on small FINAL holdout (n=18, WR=0.3888888888888889) but sample <30 and WR << 65% HC target; HC65/67/70 thresholds currently select 0 trades (model probs clustered ~0.5)
- chosen_model: random_forest brier=0.22691895574169574

## F. ACCURACY/FREQUENCY FRONTIER
[
  {
    "profile": "HC70",
    "threshold": 0.7,
    "n": 0,
    "wr": null,
    "wr_ci95": null,
    "pf": null,
    "expectancy_r": null,
    "max_dd_r": null,
    "trades_per_week": 0.0,
    "avg_win": null,
    "avg_loss": null,
    "worst": null,
    "longest_losing_streak": 0
  },
  {
    "profile": "HC67",
    "threshold": 0.67,
    "n": 0,
    "wr": null,
    "wr_ci95": null,
    "pf": null,
    "expectancy_r": null,
    "max_dd_r": null,
    "trades_per_week": 0.0,
    "avg_win": null,
    "avg_loss": null,
    "worst": null,
    "longest_losing_streak": 0
  },
  {
    "profile": "HC65",
    "threshold": 0.65,
    "n": 0,
    "wr": null,
    "wr_ci95": null,
    "pf": null,
    "expectancy_r": null,
    "max_dd_r": null,
    "trades_per_week": 0.0,
    "avg_win": null,
    "avg_loss": null,
    "worst": null,
    "longest_losing_streak": 0
  },
  {
    "profile": "BALANCED",
    "threshold": 0.5,
    "n": 18,
    "wr": 0.3333333333333333,
    "wr_ci95": [
      0.16278554363662856,
      0.5625093065574964
    ],
    "pf": 0.6045238095238096,
    "expectancy_r": -0.2768333333333333,
    "max_dd_r": -4.811,
    "trades_per_week": 18.0,
    "avg_win": 1.2695,
    "avg_loss": -1.0500000000000003,
    "worst": -1.05,
    "longest_losing_streak": 3
  }
]

## G. CALIBRATION
{
  "calibrated": false,
  "bins": [
    {
      "bin": "50-55",
      "n": 0,
      "pred_avg": null,
      "actual_wr": null
    },
    {
      "bin": "55-60",
      "n": 0,
      "pred_avg": null,
      "actual_wr": null
    },
    {
      "bin": "60-65",
      "n": 0,
      "pred_avg": null,
      "actual_wr": null
    },
    {
      "bin": "65-70",
      "n": 0,
      "pred_avg": null,
      "actual_wr": null
    },
    {
      "bin": "70-75",
      "n": 0,
      "pred_avg": null,
      "actual_wr": null
    },
    {
      "bin": "75-80",
      "n": 0,
      "pred_avg": null,
      "actual_wr": null
    },
    {
      "bin": "80+",
      "n": 0,
      "pred_avg": null,
      "actual_wr": null
    }
  ],
  "brier": 0.21914627398083356
}

## H. EXECUTION TESTS
- passed/failed: 17/0

## I. RISK TESTS
- settings: {'risk_per_trade_pct': 0.01, 'max_account_risk_per_trade': 500, 'max_risk_dollars_per_trade': 500, 'max_daily_loss_dollars': 4000, 'max_total_open_risk_dollars': 3500, 'max_correlated_risk_dollars': 1500, 'daily_loss_kill_dollars': 4000, 'max_open_positions': 50}
- oversized approved? False reasons=['RISK_LIMIT $1000.00 > hard cap $500.00']
- live_pilot risk: {'risk_per_trade_pct': 0.005, 'max_account_risk_per_trade': 150, 'max_risk_dollars_per_trade': 150, 'max_open_positions': 4, 'max_total_open_risk_dollars': 400, 'max_daily_loss_dollars': 300, 'max_correlated_risk_dollars': 200, 'daily_loss_kill_pct': 0.03, 'daily_loss_kill_dollars': 300, 'max_correlated_index_positions': 2, 'no_martingale': True, 'no_averaging_down': True, 'no_size_escalation_after_wins': True}
- finite_controls_ok: True

## J. RESTART/PERSISTENCE
{
  "learning_rows_before": 758,
  "learning_rows_after_reload": 758,
  "champion_before": "trade_quality_v1_20260810",
  "champion_after": "trade_quality_v1_20260810",
  "unchanged": true,
  "paper_trades_exists": true,
  "loop_state_exists": true
}

## K. REAL-TIME DATA STATUS
- paper provider: YahooDelayedFuturesProvider
- realtime healthy: False
- error: NOT_CONNECTED: broker MD session not established

## L. BROKER STATUS
- SimulatedBroker: verified in execution tests
- Tradovate live brackets: market entry only; OCO stop/target TODO
- IBKR adapter present; live fills async not fully wired

## M. LIVE_PILOT CONFIG
- path: config/live_pilot.yaml
- activated: False
- universe: ['MES', 'MNQ', 'MGC', 'MCL']
- max qty: 1

## N. REMAINING EXTERNAL DEPENDENCIES
[
  {
    "item": "Tradovate API credentials",
    "env": "TRADOVATE_USERNAME, TRADOVATE_PASSWORD, TRADOVATE_CID, TRADOVATE_SEC",
    "status": "required"
  },
  {
    "item": "Tradovate account id/spec",
    "env": "TRADOVATE_ACCOUNT_ID / TRADOVATE_ACCOUNT_SPEC",
    "status": "required for orders"
  },
  {
    "item": "CME market data entitlement on demo/live account",
    "env": "account subscription (not a local env var)",
    "status": "required for realtime bars"
  },
  {
    "item": "Market data websocket URL / SDK",
    "env": "market_data.realtime_url + Tradovate MD websocket",
    "status": "not implemented"
  },
  {
    "item": "Front-month contract mapping",
    "env": "instruments.*.tradovate_symbol (e.g. MESH6)",
    "status": "required before live brackets"
  },
  {
    "item": "ALLOW_LIVE_TRADING=1 + mode:live",
    "env": "ALLOW_LIVE_TRADING",
    "status": "explicit approval gate"
  }
]

## O. FILES CHANGED (sprint)
- src/agent/learning/schema.py
- src/agent/learning/store.py
- src/agent/learning/loop.py
- src/agent/decision/performance_router_v2.py
- src/agent/execution/kill_switch.py
- src/agent/execution/sim_broker.py
- src/agent/execution/order_state.py
- src/agent/execution/directional.py
- src/agent/data/historical.py
- src/agent/data/broker_realtime.py
- src/agent/data/yahoo_delayed.py
- src/agent/data/__init__.py
- config/live_pilot.yaml
- scripts/run_live_readiness_sprint.py
- tests/test_live_readiness.py
- data/live_readiness/*
- PROJECT_MEMORY.md
- DEBUG.md

## P. TEST RESULTS
{
  "returncode": 0,
  "stdout_tail": "..................................                                       [100%]\n============================== warnings summary ===============================\ntests/test_cl_priority_learning.py: 485 warnings\ntests/test_performance_router.py: 970 warnings\n  C:\\Users\\patri\\trading-agent\\.venv\\Lib\\site-packages\\joblib\\numpy_pickle.py:207: DeprecationWarning: Setting the shape on a NumPy array has been deprecated in NumPy 2.5.\n  As an alternative, you can create a new view using np.reshape (with copy=False if needed).\n    array.shape = self.shape\n\n-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html\n34 passed, 1455 warnings in 7.45s\n",
  "stderr_tail": ""
}

## FAILURE ANALYSIS (v2 HC losses)
{}

## BLOCKERS
- Realtime futures MD entitlement + BrokerRealtimeProvider.connect implementation
- Tradovate/TopstepX credentials (TRADOVATE_*) + account id/spec
- Front-month contract mapping for MES/MNQ/MGC/MCL
- Complete Tradovate OCO stop/target attachment
- Successful broker demo simulation under human supervision
- Explicit approval before any real-money activation