# Full Research Program — Final Report

## Verdict

**NO CANDIDATE MEETS STANDARD**

Gates: `{"min_wr": 0.65, "min_pf": 1.5, "min_expectancy_r": 0.25, "min_n": 100, "max_worst_loss_r": -5.0, "min_med_win_over_med_loss": 0.35}`

Friction: Friction: 2 ticks slip + 1 tick buffer per side (research_wit convention); fixed-R stops/targets; no lookahead on entry bar; train/val/final chronological freeze.

## A. Research scale

- Strategy families: **18**
- Total configurations: **93**
- Historical bars: **81486**
- Train trades: **14253**
- Validation trades: **4788**
- Final untouched OOS trades (selected path): **607**
- Selected for final: **20**
- Families: breakout_retest, ema_pullback, failed_breakout, fvg_mtf, fvg_retest, liquidity_sweep_mss, liquidity_sweep_reclaim, momentum, mss_retest, mtf_ema, opening_range, orb_failed, supply_demand, sweep_mss_fvg, trend_continuation, vwap_mss, vwap_reclaim, vwap_rejection

## B. Top 10 finalists (FINAL OOS only)

| Strategy | Fam | TF | n | WR | CI95 | PF | E[R] | MaxDD | /wk | AvgW | AvgL | Worst | Gates |
|----------|-----|----|---|----|------|----|------|-------|-----|------|------|-------|-------|
| orb5_first_break_vwap1_R1.0 | opening_range | 5m | 10 | 80.0% | [0.5, 1.0] | 5.387 | 0.5657 | -1.043 | 6.95 | 0.868 | -0.645 | -1.043 | False |
| orb5_first_break_vwap1_R1.5 | opening_range | 5m | 10 | 70.0% | [0.4, 1.0] | 3.862 | 0.6657 | -1.283 | 6.95 | 1.283 | -0.775 | -1.043 | False |
| vwap_mss_R1.0 | vwap_mss | 1h | 68 | 64.7% | [0.5294, 0.7647] | 1.731 | 0.2664 | -5.165 | 5.53 | 0.974 | -1.032 | -1.079 | False |
| orb5_first_break_vwap0_R1.0 | opening_range | 5m | 11 | 63.6% | [0.3636, 0.8182] | 1.955 | 0.2988 | -2.263 | 7.65 | 0.961 | -0.86 | -1.1 | False |
| orb15_first_break_vwap1_R1.0 | opening_range | 5m | 11 | 63.6% | [0.3636, 0.9091] | 1.739 | 0.2195 | -2.266 | 7.66 | 0.812 | -0.817 | -1.019 | False |
| orb5_first_break_vwap1_R2.0 | opening_range | 5m | 10 | 60.0% | [0.3, 0.9] | 2.98 | 0.6657 | -3.362 | 6.95 | 1.67 | -0.841 | -1.043 | False |
| orb15_retest_vwap0_R1.0 | opening_range | 5m | 30 | 60.0% | [0.4, 0.7667] | 1.385 | 0.1369 | -4.444 | 20.8 | 0.82 | -0.888 | -1.048 | False |
| orb15_first_break_vwap0_R1.0 | opening_range | 5m | 12 | 58.3% | [0.3333, 0.8333] | 1.318 | 0.1141 | -2.266 | 8.35 | 0.812 | -0.863 | -1.045 | False |
| vwap_mss_R2.0 | vwap_mss | 1h | 68 | 57.4% | [0.4702, 0.6912] | 2.521 | 0.6683 | -5.165 | 5.53 | 1.931 | -1.03 | -1.079 | False |
| vwap_mss_R1.5 | vwap_mss | 1h | 68 | 57.4% | [0.4702, 0.6912] | 1.924 | 0.4061 | -5.165 | 5.53 | 1.474 | -1.03 | -1.079 | False |

## C. High-confidence gate

**NO CANDIDATE MEETS STANDARD**

### Closest misses

- `orb5_first_break_vwap1_R1.0` final={'n': 10, 'wins': 8, 'losses': 2, 'wr': 0.8, 'wr_ci95': [0.5, 1.0], 'pf': 5.387, 'expectancy_r': 0.5657, 'max_dd_r': -1.043, 'avg_win_r': 0.868, 'avg_loss_r': -0.645, 'med_win_r': 0.96, 'med_loss_r': -0.645, 'worst_r': -1.043, 'p95_loss_r': -1.003, 'trades_per_week': 6.95, 'longest_losing_streak': 1, 'anti_cheat_ok': True, 'anti_cheat_reasons': []} failed=['n']
- `orb5_first_break_vwap1_R1.5` final={'n': 10, 'wins': 7, 'losses': 3, 'wr': 0.7, 'wr_ci95': [0.4, 1.0], 'pf': 3.862, 'expectancy_r': 0.6657, 'max_dd_r': -1.283, 'avg_win_r': 1.283, 'avg_loss_r': -0.775, 'med_win_r': 1.457, 'med_loss_r': -1.037, 'worst_r': -1.043, 'p95_loss_r': -1.042, 'trades_per_week': 6.95, 'longest_losing_streak': 2, 'anti_cheat_ok': True, 'anti_cheat_reasons': []} failed=['n']
- `vwap_mss_R1.0` final={'n': 68, 'wins': 44, 'losses': 24, 'wr': 0.6471, 'wr_ci95': [0.5294, 0.7647], 'pf': 1.731, 'expectancy_r': 0.2664, 'max_dd_r': -5.165, 'avg_win_r': 0.974, 'avg_loss_r': -1.032, 'med_win_r': 0.984, 'med_loss_r': -1.031, 'worst_r': -1.079, 'p95_loss_r': -1.072, 'trades_per_week': 5.53, 'longest_losing_streak': 5, 'anti_cheat_ok': True, 'anti_cheat_reasons': []} failed=['wr', 'n']
- `orb5_first_break_vwap0_R1.0` final={'n': 11, 'wins': 7, 'losses': 4, 'wr': 0.6364, 'wr_ci95': [0.3636, 0.8182], 'pf': 1.955, 'expectancy_r': 0.2988, 'max_dd_r': -2.263, 'avg_win_r': 0.961, 'avg_loss_r': -0.86, 'med_win_r': 0.963, 'med_loss_r': -1.047, 'worst_r': -1.1, 'p95_loss_r': -1.093, 'trades_per_week': 7.65, 'longest_losing_streak': 2, 'anti_cheat_ok': True, 'anti_cheat_reasons': []} failed=['wr', 'n']
- `orb15_first_break_vwap1_R1.0` final={'n': 11, 'wins': 7, 'losses': 4, 'wr': 0.6364, 'wr_ci95': [0.3636, 0.9091], 'pf': 1.739, 'expectancy_r': 0.2195, 'max_dd_r': -2.266, 'avg_win_r': 0.812, 'avg_loss_r': -0.817, 'med_win_r': 0.958, 'med_loss_r': -1.011, 'worst_r': -1.019, 'p95_loss_r': -1.019, 'trades_per_week': 7.66, 'longest_losing_streak': 3, 'anti_cheat_ok': True, 'anti_cheat_reasons': []} failed=['wr', 'E', 'n']

## D. Best by market (final OOS, n≥15)

{
  "NQ": {
    "config": "vwap_mss_R1.0",
    "family": "vwap_mss",
    "final": {
      "n": 24,
      "wins": 16,
      "losses": 8,
      "wr": 0.6667,
      "wr_ci95": [
        0.4583,
        0.8333
      ],
      "pf": 1.971,
      "expectancy_r": 0.3262,
      "max_dd_r": -3.065,
      "avg_win_r": 0.993,
      "avg_loss_r": -1.008,
      "med_win_r": 0.993,
      "med_loss_r": -1.008,
      "worst_r": -1.01,
      "p95_loss_r": -1.01,
      "trades_per_week": 1.98,
      "longest_losing_streak": 2,
      "anti_cheat_ok": true,
      "anti_cheat_reasons": []
    }
  },
  "ES": {
    "config": "vwap_mss_R1.0",
    "family": "vwap_mss",
    "final": {
      "n": 16,
      "wins": 9,
      "losses": 7,
      "wr": 0.5625,
      "wr_ci95": [
        0.3125,
        0.8125
      ],
      "pf": 1.146,
      "expectancy_r": 0.0679,
      "max_dd_r": -2.368,
      "avg_win_r": 0.944,
      "avg_loss_r": -1.059,
      "med_win_r": 0.944,
      "med_loss_r": -1.057,
      "worst_r": -1.079,
      "p95_loss_r": -1.077,
      "trades_per_week": 1.42,
      "longest_losing_streak": 2,
      "anti_cheat_ok": true,
      "anti_cheat_reasons": []
    }
  },
  "GC": {
    "config": "breakout_retest_R1.0",
    "family": "breakout_retest",
    "final": {
      "n": 16,
      "wins": 7,
      "losses": 9,
      "wr": 0.4375,
      "wr_ci95": [
        0.1875,
        0.6875
      ],
      "pf": 0.76,
      "expectancy_r": -0.1366,
      "max_dd_r": -4.141,
      "avg_win_r": 0.988,
      "avg_loss_r": -1.011,
      "med_win_r": 0.99,
      "med_loss_r": -1.011,
      "worst_r": -1.015,
      "p95_loss_r": -1.014,
      "trades_per_week": 1.35,
      "longest_losing_streak": 4,
      "anti_cheat_ok": true,
      "anti_cheat_reasons": []
    }
  },
  "CL": {
    "config": "vwap_mss_R2.0",
    "family": "vwap_mss",
    "final": {
      "n": 17,
      "wins": 9,
      "losses": 8,
      "wr": 0.5294,
      "wr_ci95": [
        0.2941,
        0.7647
      ],
      "pf": 1.93,
      "expectancy_r": 0.4527,
      "max_dd_r": -5.165,
      "avg_win_r": 1.775,
      "avg_loss_r": -1.035,
      "med_win_r": 1.952,
      "med_loss_r": -1.034,
      "worst_r": -1.042,
      "p95_loss_r": -1.041,
      "trades_per_week": 1.47,
      "longest_losing_streak": 5,
      "anti_cheat_ok": true,
      "anti_cheat_reasons": []
    }
  }
}

## E. Best by session

{
  "ASIA": null,
  "LONDON": {
    "config": "vwap_mss_R1.0",
    "session": "LONDON",
    "final": {
      "n": 37,
      "wins": 21,
      "losses": 16,
      "wr": 0.5676,
      "wr_ci95": [
        0.4054,
        0.7297
      ],
      "pf": 1.238,
      "expectancy_r": 0.1066,
      "max_dd_r": -5.417,
      "avg_win_r": 0.976,
      "avg_loss_r": -1.035,
      "med_win_r": 0.985,
      "med_loss_r": -1.034,
      "worst_r": -1.079,
      "p95_loss_r": -1.074,
      "trades_per_week": 3.01,
      "longest_losing_streak": 4,
      "anti_cheat_ok": true,
      "anti_cheat_reasons": []
    }
  },
  "NY": {
    "config": "vwap_mss_R1.0",
    "session": "NY_OPEN",
    "final": {
      "n": 21,
      "wins": 17,
      "losses": 4,
      "wr": 0.8095,
      "wr_ci95": [
        0.619,
        0.9524
      ],
      "pf": 4.009,
      "expectancy_r": 0.5898,
      "max_dd_r": -1.126,
      "avg_win_r": 0.971,
      "avg_loss_r": -1.029,
      "med_win_r": 0.979,
      "med_loss_r": -1.035,
      "worst_r": -1.042,
      "p95_loss_r": -1.042,
      "trades_per_week": 1.79,
      "longest_losing_streak": 1,
      "anti_cheat_ok": true,
      "anti_cheat_reasons": []
    }
  }
}

## F. WR / frequency Pareto

[
  {
    "config": "vwap_mss_R1.0",
    "wr": 0.6471,
    "pf": 1.731,
    "expectancy_r": 0.2664,
    "trades_per_week": 5.53,
    "n": 68
  },
  {
    "config": "orb15_retest_vwap0_R1.0",
    "wr": 0.6,
    "pf": 1.385,
    "expectancy_r": 0.1369,
    "trades_per_week": 20.8,
    "n": 30
  },
  {
    "config": "vwap_mss_R2.0",
    "wr": 0.5735,
    "pf": 2.521,
    "expectancy_r": 0.6683,
    "trades_per_week": 5.53,
    "n": 68
  },
  {
    "config": "vwap_mss_R1.5",
    "wr": 0.5735,
    "pf": 1.924,
    "expectancy_r": 0.4061,
    "trades_per_week": 5.53,
    "n": 68
  },
  {
    "config": "orb15_retest_vwap1_R1.0",
    "wr": 0.5714,
    "pf": 1.376,
    "expectancy_r": 0.1336,
    "trades_per_week": 19.38,
    "n": 28
  },
  {
    "config": "orb15_retest_vwap0_R2.0",
    "wr": 0.5667,
    "pf": 1.53,
    "expectancy_r": 0.2068,
    "trades_per_week": 20.8,
    "n": 30
  },
  {
    "config": "orb15_retest_vwap0_R1.5",
    "wr": 0.5667,
    "pf": 1.395,
    "expectancy_r": 0.154,
    "trades_per_week": 20.8,
    "n": 30
  },
  {
    "config": "orb15_retest_vwap1_R2.0",
    "wr": 0.5357,
    "pf": 1.44,
    "expectancy_r": 0.1728,
    "trades_per_week": 19.38,
    "n": 28
  },
  {
    "config": "orb15_retest_vwap1_R1.5",
    "wr": 0.5357,
    "pf": 1.341,
    "expectancy_r": 0.1341,
    "trades_per_week": 19.38,
    "n": 28
  },
  {
    "config": "liq_sweep_MSS_R1.5",
    "wr": 0.5357,
    "pf": 1.084,
    "expectancy_r": 0.0354,
    "trades_per_week": 2.28,
    "n": 28
  },
  {
    "config": "liq_sweep_MSS_R2.0",
    "wr": 0.5357,
    "pf": 1.073,
    "expectancy_r": 0.0309,
    "trades_per_week": 2.28,
    "n": 28
  }
]

## G. Monte Carlo (top finalist)

{}

## H. Probability calibration (train→val)

{
  "buckets": {
    "50-55": {
      "n": 631,
      "predicted_mean": 0.5132,
      "observed_wr": 0.4739,
      "abs_error": 0.0394,
      "status": "OK"
    },
    "55-60": {
      "n": 178,
      "predicted_mean": 0.5774,
      "observed_wr": 0.5281,
      "abs_error": 0.0493,
      "status": "OK"
    },
    "60-65": {
      "n": 0,
      "status": "INSUFFICIENT"
    },
    "65-70": {
      "n": 0,
      "status": "INSUFFICIENT"
    },
    "70-75": {
      "n": 0,
      "status": "INSUFFICIENT"
    },
    "75-80": {
      "n": 0,
      "status": "INSUFFICIENT"
    },
    "80+": {
      "n": 0,
      "status": "INSUFFICIENT"
    }
  },
  "mae": 0.0443,
  "min_n_per_bucket": 30
}

## I. Missed-move analysis

{
  "large_directional_moves": 154,
  "undetected": 154,
  "detected_a_plus_a": 0,
  "detected_b_only": 0,
  "note": "Offline harness used empty candidates_by_bar \u2014 establishes move frequency baseline on NQ 1h tail."
}

## J. Failure-mode clusters (top finalist)

{
  "n_losses": 2,
  "by_session": {
    "NY_MID": 1,
    "NY_OPEN": 1
  },
  "by_regime": {
    "TREND_DOWN": 1,
    "HIGH_VOLATILITY": 1
  }
}

## K. Paper bot freeze confirmation

- paper_bot_frozen: **True**
- paper_bot_modified: **False**

## L. Current exact risk config (read-only snapshot)

{
  "risk_per_trade_pct": 0.01,
  "max_account_risk_per_trade": 500,
  "max_risk_dollars_per_trade": 500,
  "max_total_open_risk_dollars": 3500,
  "max_daily_loss_dollars": 4000,
  "max_correlated_risk_dollars": 1500,
  "daily_loss_kill_pct": 0.08,
  "default_quantity": 2,
  "quantity_by_tier": {
    "A+": 3,
    "A": 2
  },
  "minimum_trade_tier": "A",
  "note": "READ-ONLY snapshot. Research program does not modify these values."
}

## M. Recommended champion candidate

null

_Not activated. Awaiting explicit approval._
