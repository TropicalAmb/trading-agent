# NQ WR≥65% Consistency Search

**Verdict:** `NQ_WR65_HIT_SAMPLE_THIN`
Ready configs: `3` / cells scored `3336`
Cache: `2025-06-15 18:00:00-04:00` → `2025-12-11 15:57:00-05:00` (167582 bars)

## Best / closest
```
{
  "window": "1000_1130",
  "confirmation": "rejection_wick",
  "exit": "1.75R",
  "target_r": 1.75,
  "zone_atr": 0.35,
  "stop_atr": 0.3,
  "vwap_buffer_atr": 0.15,
  "sides": [
    "BUY"
  ],
  "n_cands": 45,
  "train": {
    "n": 30,
    "wr": 0.9333,
    "pf": 31.3,
    "expectancy_r": 1.5288,
    "max_dd_r": -0.511,
    "avg_win_r": 1.692,
    "avg_loss_r": -0.757,
    "worst_r": -1.002,
    "trades_per_week": 2.0,
    "anti_cheat_ok": true
  },
  "val": {
    "n": 38,
    "wr": 0.9211,
    "pf": 27.529,
    "expectancy_r": 1.5103,
    "max_dd_r": -0.65,
    "avg_win_r": 1.702,
    "avg_loss_r": -0.721,
    "worst_r": -1.002,
    "trades_per_week": 2.01,
    "anti_cheat_ok": true
  },
  "holdout": {
    "n": 7,
    "wr": 1.0,
    "pf": 999.0,
    "expectancy_r": 1.503,
    "max_dd_r": 0.0,
    "avg_win_r": 1.503,
    "avg_loss_r": 0.0,
    "worst_r": 0.064,
    "trades_per_week": 1.69,
    "anti_cheat_ok": true
  },
  "folds": [
    {
      "fold": 1,
      "n": 8,
      "wr": 0.875,
      "pf": 12.135,
      "expectancy_r": 1.3952,
      "max_dd_r": 0.0,
      "avg_win_r": 1.738,
      "avg_loss_r": -1.002,
      "worst_r": -1.002,
      "trades_per_week": 2.44,
      "anti_cheat_ok": true
    },
    {
      "fold": 2,
      "n": 11,
      "wr": 0.9091,
      "pf": 33.983,
      "expectancy_r": 1.5329,
      "max_dd_r": -0.511,
      "avg_win_r": 1.737,
      "avg_loss_r": -0.511,
      "worst_r": -0.511,
      "trades_per_week": 3.07,
      "anti_cheat_ok": true
    },
    {
      "fold": 3,
      "n": 8,
      "wr": 1.0,
      "pf": 999.0,
      "expectancy_r": 1.7382,
      "max_dd_r": 0.0,
      "avg_win_r": 1.738,
      "avg_loss_r": 0.0,
      "worst_r": 1.723,
      "trades_per_week": 2.43,
      "anti_cheat_ok": true
    },
    {
      "fold": 4,
      "n": 3,
      "wr": 1.0,
      "pf": 999.0,
      "expectancy_r": 1.3113,
      "max_dd_r": 0.0,
      "avg_win_r": 1.311,
      "avg_loss_r": 0.0,
      "worst_r": 0.453,
      "trades_per_week": 1.05,
      "anti_cheat_ok": true
    },
    {
      "fold": 5,
      "n": 8,
      "wr": 0.875,
      "pf": 18.745,
      "expectancy_r": 1.4413,
      "max_dd_r": -0.65,
      "avg_win_r": 1.74,
      "avg_loss_r": -0.65,
      "worst_r": -0.65,
      "trades_per_week": 2.79,
      "anti_cheat_ok": true
    }
  ],
  "consistency_ok": false,
  "fail_reasons": [
    "holdout_n=7<20"
  ],
  "comfort_score": 199.325,
  "mean_fold_wr": 0.914775,
  "min_fold_wr": 0.875
}
```

## Ready (passed consistency gates)
```
[
  {
    "window": "1000_1130",
    "confirmation": "signal_close",
    "exit": "1.0R",
    "target_r": 1.0,
    "zone_atr": 0.15,
    "stop_atr": 0.45,
    "vwap_buffer_atr": 0.15,
    "sides": [
      "BUY",
      "SELL"
    ],
    "n_cands": 81,
    "train": {
      "n": 51,
      "wr": 0.6667,
      "pf": 3.145,
      "expectancy_r": 0.4508,
      "max_dd_r": -3.517,
      "avg_win_r": 0.991,
      "avg_loss_r": -0.63,
      "worst_r": -1.013,
      "trades_per_week": 3.57,
      "anti_cheat_ok": true
    },
    "val": {
      "n": 61,
      "wr": 0.6557,
      "pf": 2.772,
      "expectancy_r": 0.4156,
      "max_dd_r": -3.517,
      "avg_win_r": 0.992,
      "avg_loss_r": -0.681,
      "worst_r": -1.013,
      "trades_per_week": 3.31,
      "anti_cheat_ok": true
    },
    "holdout": {
      "n": 20,
      "wr": 0.7,
      "pf": 2.33,
      "expectancy_r": 0.3492,
      "max_dd_r": -1.731,
      "avg_win_r": 0.874,
      "avg_loss_r": -0.875,
      "worst_r": -1.02,
      "trades_per_week": 3.89,
      "anti_cheat_ok": true
    },
    "folds": [
      {
        "fold": 1,
        "n": 14,
        "wr": 0.5714,
        "pf": 1.995,
        "expectancy_r": 0.2825,
        "max_dd_r": -1.492,
        "avg_win_r": 0.991,
        "avg_loss_r": -0.662,
        "worst_r": -1.007,
        "trades_per_week": 5.44,
        "anti_cheat_ok": true
      },
      {
        "fold": 2,
        "n": 19,
        "wr": 0.6316,
        "pf": 2.812,
        "expectancy_r": 0.4031,
        "max_dd_r": -3.517,
        "avg_win_r": 0.99,
        "avg_loss_r": -0.604,
        "worst_r": -1.013,
        "trades_per_week": 5.31,
        "anti_cheat_ok": true
      },
      {
        "fold": 3,
        "n": 13,
        "wr": 0.7692,
        "pf": 3.97,
        "expectancy_r": 0.5708,
        "max_dd_r": -1.491,
        "avg_win_r": 0.992,
        "avg_loss_r": -0.833,
        "worst_r": -1.007,
        "trades_per_week": 3.79,
        "anti_cheat_ok": true
      },
      {
        "fold": 4,
        "n": 5,
        "wr": 0.8,
        "pf": 215.067,
        "expectancy_r": 0.7914,
        "max_dd_r": -0.018,
        "avg_win_r": 0.994,
        "avg_loss_r": -0.018,
        "worst_r": -0.018,
        "trades_per_week": 2.5,
        "anti_cheat_ok": true
      },
      {
        "fold": 5,
        "n": 10,
        "wr": 0.6,
        "pf": 1.658,
        "expectancy_r": 0.2364,
        "max_dd_r": -2.007,
        "avg_win_r": 0.993,
        "avg_loss_r": -0.899,
        "worst_r": -1.005,
        "trades_per_week": 3.18,
        "anti_cheat_ok": true
      }
    ],
    "consistency_ok": true,
    "fail_reasons": [],
    "comfort_score": 164.522,
    "mean_fold_wr": 0.67444,
    "min_fold_wr": 0.5714
  },
  {
    "window": "1000_1130",
    "confirmation": "signal_close",
    "exit": "1.15R",
    "target_r": 1.15,
    "zone_atr": 0.15,
    "stop_atr": 0.45,
    "vwap_buffer_atr": 0.15,
    "sides": [
      "BUY",
      "SELL"
    ],
    "n_cands": 81,
    "train": {
      "n": 51,
      "wr": 0.6667,
      "pf": 3.621,
      "expectancy_r": 0.5508,
      "max_dd_r": -3.517,
      "avg_win_r": 1.141,
      "avg_loss_r": -0.63,
      "worst_r": -1.013,
      "trades_per_week": 3.57,
      "anti_cheat_ok": true
    },
    "val": {
      "n": 61,
      "wr": 0.6557,
      "pf": 3.191,
      "expectancy_r": 0.514,
      "max_dd_r": -3.517,
      "avg_win_r": 1.142,
      "avg_loss_r": -0.681,
      "worst_r": -1.013,
      "trades_per_week": 3.31,
      "anti_cheat_ok": true
    },
    "holdout": {
      "n": 20,
      "wr": 0.7,
      "pf": 2.672,
      "expectancy_r": 0.4392,
      "max_dd_r": -1.731,
      "avg_win_r": 1.003,
      "avg_loss_r": -0.875,
      "worst_r": -1.02,
      "trades_per_week": 3.89,
      "anti_cheat_ok": true
    },
    "folds": [
      {
        "fold": 1,
        "n": 14,
        "wr": 0.5714,
        "pf": 2.297,
        "expectancy_r": 0.3682,
        "max_dd_r": -1.327,
        "avg_win_r": 1.141,
        "avg_loss_r": -0.662,
        "worst_r": -1.007,
        "trades_per_week": 5.44,
        "anti_cheat_ok": true
      },
      {
        "fold": 2,
        "n": 19,
        "wr": 0.6316,
        "pf": 3.238,
        "expectancy_r": 0.4978,
        "max_dd_r": -3.517,
        "avg_win_r": 1.14,
        "avg_loss_r": -0.604,
        "worst_r": -1.013,
        "trades_per_week": 5.31,
        "anti_cheat_ok": true
      },
      {
        "fold": 3,
        "n": 13,
        "wr": 0.7692,
        "pf": 4.57,
        "expectancy_r": 0.6861,
        "max_dd_r": -1.491,
        "avg_win_r": 1.142,
        "avg_loss_r": -0.833,
        "worst_r": -1.007,
        "trades_per_week": 3.79,
        "anti_cheat_ok": true
      },
      {
        "fold": 4,
        "n": 5,
        "wr": 0.8,
        "pf": 247.528,
        "expectancy_r": 0.9114,
        "max_dd_r": -0.018,
        "avg_win_r": 1.144,
        "avg_loss_r": -0.018,
        "worst_r": -0.018,
        "trades_per_week": 2.5,
        "anti_cheat_ok": true
      },
      {
        "fold": 5,
        "n": 10,
        "wr": 0.6,
        "pf": 1.908,
        "expectancy_r": 0.3264,
        "max_dd_r": -2.007,
        "avg_win_r": 1.143,
        "avg_loss_r": -0.899,
        "worst_r": -1.005,
        "trades_per_week": 3.18,
        "anti_cheat_ok": true
      }
    ],
    "consistency_ok": true,
    "fail_reasons": [],
    "comfort_score": 168.482,
    "mean_fold_wr": 0.67444,
    "min_fold_wr": 0.5714
  },
  {
    "window": "1000_1130",
    "confirmation": "signal_close",
    "exit": "1.0R",
    "target_r": 1.0,
    "zone_atr": 0.15,
    "stop_atr": 0.6,
    "vwap_buffer_atr": 0.15,
    "sides": [
      "BUY",
      "SELL"
    ],
    "n_cands": 81,
    "train": {
      "n": 51,
      "wr": 0.6667,
      "pf": 3.524,
      "expectancy_r": 0.4742,
      "max_dd_r": -2.657,
      "avg_win_r": 0.993,
      "avg_loss_r": -0.564,
      "worst_r": -1.01,
      "trades_per_week": 3.57,
      "anti_cheat_ok": true
    },
    "val": {
      "n": 61,
      "wr": 0.6557,
      "pf": 3.027,
      "expectancy_r": 0.4361,
      "max_dd_r": -2.657,
      "avg_win_r": 0.993,
      "avg_loss_r": -0.625,
      "worst_r": -1.01,
      "trades_per_week": 3.31,
      "anti_cheat_ok": true
    },
    "holdout": {
      "n": 20,
      "wr": 0.7,
      "pf": 2.379,
      "expectancy_r": 0.3542,
      "max_dd_r": -1.666,
      "avg_win_r": 0.873,
      "avg_loss_r": -0.856,
      "worst_r": -1.017,
      "trades_per_week": 3.89,
      "anti_cheat_ok": true
    },
    "folds": [
      {
        "fold": 1,
        "n": 14,
        "wr": 0.5714,
        "pf": 2.088,
        "expectancy_r": 0.2956,
        "max_dd_r": -1.355,
        "avg_win_r": 0.993,
        "avg_loss_r": -0.634,
        "worst_r": -1.006,
        "trades_per_week": 5.44,
        "anti_cheat_ok": true
      },
      {
        "fold": 2,
        "n": 19,
        "wr": 0.6316,
        "pf": 3.595,
        "expectancy_r": 0.4524,
        "max_dd_r": -2.657,
        "avg_win_r": 0.992,
        "avg_loss_r": -0.473,
        "worst_r": -1.01,
        "trades_per_week": 5.31,
        "anti_cheat_ok": true
      },
      {
        "fold": 3,
        "n": 13,
        "wr": 0.7692,
        "pf": 4.055,
        "expectancy_r": 0.5758,
        "max_dd_r": -1.444,
        "avg_win_r": 0.994,
        "avg_loss_r": -0.817,
        "worst_r": -1.006,
        "trades_per_week": 3.79,
        "anti_cheat_ok": true
      },
      {
        "fold": 4,
        "n": 5,
        "wr": 0.8,
        "pf": 231.378,
        "expectancy_r": 0.7927,
        "max_dd_r": -0.017,
        "avg_win_r": 0.995,
        "avg_loss_r": -0.017,
        "worst_r": -0.017,
        "trades_per_week": 2.5,
        "anti_cheat_ok": true
      },
      {
        "fold": 5,
        "n": 10,
        "wr": 0.6,
        "pf": 1.683,
        "expectancy_r": 0.2421,
        "max_dd_r": -2.006,
        "avg_win_r": 0.994,
        "avg_loss_r": -0.886,
        "worst_r": -1.004,
        "trades_per_week": 3.18,
        "anti_cheat_ok": true
      }
    ],
    "consistency_ok": true,
    "fail_reasons": [],
    "comfort_score": 164.892,
    "mean_fold_wr": 0.67444,
    "min_fold_wr": 0.5714
  }
]
```

## Closest top 5
```
[
  {
    "window": "1000_1130",
    "confirmation": "rejection_wick",
    "exit": "1.75R",
    "target_r": 1.75,
    "zone_atr": 0.35,
    "stop_atr": 0.3,
    "vwap_buffer_atr": 0.15,
    "sides": [
      "BUY"
    ],
    "n_cands": 45,
    "train": {
      "n": 30,
      "wr": 0.9333,
      "pf": 31.3,
      "expectancy_r": 1.5288,
      "max_dd_r": -0.511,
      "avg_win_r": 1.692,
      "avg_loss_r": -0.757,
      "worst_r": -1.002,
      "trades_per_week": 2.0,
      "anti_cheat_ok": true
    },
    "val": {
      "n": 38,
      "wr": 0.9211,
      "pf": 27.529,
      "expectancy_r": 1.5103,
      "max_dd_r": -0.65,
      "avg_win_r": 1.702,
      "avg_loss_r": -0.721,
      "worst_r": -1.002,
      "trades_per_week": 2.01,
      "anti_cheat_ok": true
    },
    "holdout": {
      "n": 7,
      "wr": 1.0,
      "pf": 999.0,
      "expectancy_r": 1.503,
      "max_dd_r": 0.0,
      "avg_win_r": 1.503,
      "avg_loss_r": 0.0,
      "worst_r": 0.064,
      "trades_per_week": 1.69,
      "anti_cheat_ok": true
    },
    "folds": [
      {
        "fold": 1,
        "n": 8,
        "wr": 0.875,
        "pf": 12.135,
        "expectancy_r": 1.3952,
        "max_dd_r": 0.0,
        "avg_win_r": 1.738,
        "avg_loss_r": -1.002,
        "worst_r": -1.002,
        "trades_per_week": 2.44,
        "anti_cheat_ok": true
      },
      {
        "fold": 2,
        "n": 11,
        "wr": 0.9091,
        "pf": 33.983,
        "expectancy_r": 1.5329,
        "max_dd_r": -0.511,
        "avg_win_r": 1.737,
        "avg_loss_r": -0.511,
        "worst_r": -0.511,
        "trades_per_week": 3.07,
        "anti_cheat_ok": true
      },
      {
        "fold": 3,
        "n": 8,
        "wr": 1.0,
        "pf": 999.0,
        "expectancy_r": 1.7382,
        "max_dd_r": 0.0,
        "avg_win_r": 1.738,
        "avg_loss_r": 0.0,
        "worst_r": 1.723,
        "trades_per_week": 2.43,
        "anti_cheat_ok": true
      },
      {
        "fold": 4,
        "n": 3,
        "wr": 1.0,
        "pf": 999.0,
        "expectancy_r": 1.3113,
        "max_dd_r": 0.0,
        "avg_win_r": 1.311,
        "avg_loss_r": 0.0,
        "worst_r": 0.453,
        "trades_per_week": 1.05,
        "anti_cheat_ok": true
      },
      {
        "fold": 5,
        "n": 8,
        "wr": 0.875,
        "pf": 18.745,
        "expectancy_r": 1.4413,
        "max_dd_r": -0.65,
        "avg_win_r": 1.74,
        "avg_loss_r": -0.65,
        "worst_r": -0.65,
        "trades_per_week": 2.79,
        "anti_cheat_ok": true
      }
    ],
    "consistency_ok": false,
    "fail_reasons": [
      "holdout_n=7<20"
    ],
    "comfort_score": 199.325,
    "mean_fold_wr": 0.914775,
    "min_fold_wr": 0.875
  },
  {
    "window": "1000_1130",
    "confirmation": "rejection_wick",
    "exit": "1.75R",
    "target_r": 1.75,
    "zone_atr": 0.25,
    "stop_atr": 0.3,
    "vwap_buffer_atr": 0.15,
    "sides": [
      "BUY"
    ],
    "n_cands": 37,
    "train": {
      "n": 27,
      "wr": 0.963,
      "pf": 85.862,
      "expectancy_r": 1.6068,
      "max_dd_r": -0.511,
      "avg_win_r": 1.688,
      "avg_loss_r": -0.511,
      "worst_r": -0.511,
      "trades_per_week": 1.89,
      "anti_cheat_ok": true
    },
    "val": {
      "n": 32,
      "wr": 0.9688,
      "pf": 102.874,
      "expectancy_r": 1.6275,
      "max_dd_r": -0.511,
      "avg_win_r": 1.697,
      "avg_loss_r": -0.511,
      "worst_r": -0.511,
      "trades_per_week": 1.76,
      "anti_cheat_ok": true
    },
    "holdout": {
      "n": 5,
      "wr": 1.0,
      "pf": 999.0,
      "expectancy_r": 1.4068,
      "max_dd_r": 0.0,
      "avg_win_r": 1.407,
      "avg_loss_r": 0.0,
      "worst_r": 0.064,
      "trades_per_week": 1.21,
      "anti_cheat_ok": true
    },
    "folds": [
      {
        "fold": 1,
        "n": 7,
        "wr": 1.0,
        "pf": 999.0,
        "expectancy_r": 1.7377,
        "max_dd_r": 0.0,
        "avg_win_r": 1.738,
        "avg_loss_r": 0.0,
        "worst_r": 1.734,
        "trades_per_week": 2.72,
        "anti_cheat_ok": true
      },
      {
        "fold": 2,
        "n": 11,
        "wr": 0.9091,
        "pf": 33.983,
        "expectancy_r": 1.5329,
        "max_dd_r": -0.511,
        "avg_win_r": 1.737,
        "avg_loss_r": -0.511,
        "worst_r": -0.511,
        "trades_per_week": 3.07,
        "anti_cheat_ok": true
      },
      {
        "fold": 3,
        "n": 7,
        "wr": 1.0,
        "pf": 999.0,
        "expectancy_r": 1.7378,
        "max_dd_r": 0.0,
        "avg_win_r": 1.738,
        "avg_loss_r": 0.0,
        "worst_r": 1.723,
        "trades_per_week": 2.44,
        "anti_cheat_ok": true
      },
      {
        "fold": 4,
        "n": 2,
        "wr": 1.0,
        "pf": 999.0,
        "expectancy_r": 1.0968,
        "max_dd_r": 0.0,
        "avg_win_r": 1.097,
        "avg_loss_r": 0.0,
        "worst_r": 0.453,
        "trades_per_week": 14.0,
        "anti_cheat_ok": true
      },
      {
        "fold": 5,
        "n": 5,
        "wr": 1.0,
        "pf": 999.0,
        "expectancy_r": 1.7394,
        "max_dd_r": 0.0,
        "avg_win_r": 1.739,
        "avg_loss_r": 0.0,
        "worst_r": 1.737,
        "trades_per_week": 1.75,
        "anti_cheat_ok": true
      }
    ],
    "consistency_ok": false,
    "fail_reasons": [
      "holdout_n=5<20"
    ],
    "comfort_score": 196.94299999999998,
    "mean_fold_wr": 0.977275,
    "min_fold_wr": 0.9091
  },
  {
    "window": "1000_1130",
    "confirmation": "rejection_wick",
    "exit": "1.75R",
    "target_r": 1.75,
    "zone_atr": 0.25,
    "stop_atr": 0.3,
    "vwap_buffer_atr": 0.05,
    "sides": [
      "BUY"
    ],
    "n_cands": 33,
    "train": {
      "n": 23,
      "wr": 0.9565,
      "pf": 72.242,
      "expectancy_r": 1.5835,
      "max_dd_r": -0.511,
      "avg_win_r": 1.679,
      "avg_loss_r": -0.511,
      "worst_r": -0.511,
      "trades_per_week": 1.61,
      "anti_cheat_ok": true
    },
    "val": {
      "n": 28,
      "wr": 0.9643,
      "pf": 89.254,
      "expectancy_r": 1.6113,
      "max_dd_r": -0.511,
      "avg_win_r": 1.69,
      "avg_loss_r": -0.511,
      "worst_r": -0.511,
      "trades_per_week": 1.54,
      "anti_cheat_ok": true
    },
    "holdout": {
      "n": 5,
      "wr": 1.0,
      "pf": 999.0,
      "expectancy_r": 1.4068,
      "max_dd_r": 0.0,
      "avg_win_r": 1.407,
      "avg_loss_r": 0.0,
      "worst_r": 0.064,
      "trades_per_week": 1.21,
      "anti_cheat_ok": true
    },
    "folds": [
      {
        "fold": 1,
        "n": 6,
        "wr": 1.0,
        "pf": 999.0,
        "expectancy_r": 1.7363,
        "max_dd_r": 0.0,
        "avg_win_r": 1.736,
        "avg_loss_r": 0.0,
        "worst_r": 1.727,
        "trades_per_week": 2.33,
        "anti_cheat_ok": true
      },
      {
        "fold": 2,
        "n": 10,
        "wr": 0.9,
        "pf": 30.584,
        "expectancy_r": 1.5124,
        "max_dd_r": -0.511,
        "avg_win_r": 1.737,
        "avg_loss_r": -0.511,
        "worst_r": -0.511,
        "trades_per_week": 2.79,
        "anti_cheat_ok": true
      },
      {
        "fold": 3,
        "n": 5,
        "wr": 1.0,
        "pf": 999.0,
        "expectancy_r": 1.737,
        "max_dd_r": 0.0,
        "avg_win_r": 1.737,
        "avg_loss_r": 0.0,
        "worst_r": 1.723,
        "trades_per_week": 1.75,
        "anti_cheat_ok": true
      },
      {
        "fold": 4,
        "n": 2,
        "wr": 1.0,
        "pf": 999.0,
        "expectancy_r": 1.0968,
        "max_dd_r": 0.0,
        "avg_win_r": 1.097,
        "avg_loss_r": 0.0,
        "worst_r": 0.453,
        "trades_per_week": 14.0,
        "anti_cheat_ok": true
      },
      {
        "fold": 5,
        "n": 5,
        "wr": 1.0,
        "pf": 999.0,
        "expectancy_r": 1.7394,
        "max_dd_r": 0.0,
        "avg_win_r": 1.739,
        "avg_loss_r": 0.0,
        "worst_r": 1.737,
        "trades_per_week": 1.75,
        "anti_cheat_ok": true
      }
    ],
    "consistency_ok": false,
    "fail_reasons": [
      "holdout_n=5<20"
    ],
    "comfort_score": 196.67000000000002,
    "mean_fold_wr": 0.975,
    "min_fold_wr": 0.9
  },
  {
    "window": "1000_1130",
    "confirmation": "rejection_wick",
    "exit": "1.75R",
    "target_r": 1.75,
    "zone_atr": 0.35,
    "stop_atr": 0.3,
    "vwap_buffer_atr": 0.05,
    "sides": [
      "BUY"
    ],
    "n_cands": 37,
    "train": {
      "n": 25,
      "wr": 0.92,
      "pf": 25.549,
      "expectancy_r": 1.4863,
      "max_dd_r": -0.511,
      "avg_win_r": 1.681,
      "avg_loss_r": -0.757,
      "worst_r": -1.002,
      "trades_per_week": 1.67,
      "anti_cheat_ok": true
    },
    "val": {
      "n": 31,
      "wr": 0.9032,
      "pf": 21.896,
      "expectancy_r": 1.4582,
      "max_dd_r": -0.65,
      "avg_win_r": 1.692,
      "avg_loss_r": -0.721,
      "worst_r": -1.002,
      "trades_per_week": 1.64,
      "anti_cheat_ok": true
    },
    "holdout": {
      "n": 6,
      "wr": 1.0,
      "pf": 999.0,
      "expectancy_r": 1.4631,
      "max_dd_r": 0.0,
      "avg_win_r": 1.463,
      "avg_loss_r": 0.0,
      "worst_r": 0.064,
      "trades_per_week": 1.45,
      "anti_cheat_ok": true
    },
    "folds": [
      {
        "fold": 1,
        "n": 7,
        "wr": 0.8571,
        "pf": 10.393,
        "expectancy_r": 1.3451,
        "max_dd_r": 0.0,
        "avg_win_r": 1.736,
        "avg_loss_r": -1.002,
        "worst_r": -1.002,
        "trades_per_week": 2.13,
        "anti_cheat_ok": true
      },
      {
        "fold": 2,
        "n": 10,
        "wr": 0.9,
        "pf": 30.584,
        "expectancy_r": 1.5124,
        "max_dd_r": -0.511,
        "avg_win_r": 1.737,
        "avg_loss_r": -0.511,
        "worst_r": -0.511,
        "trades_per_week": 2.79,
        "anti_cheat_ok": true
      },
      {
        "fold": 3,
        "n": 5,
        "wr": 1.0,
        "pf": 999.0,
        "expectancy_r": 1.737,
        "max_dd_r": 0.0,
        "avg_win_r": 1.737,
        "avg_loss_r": 0.0,
        "worst_r": 1.723,
        "trades_per_week": 1.75,
        "anti_cheat_ok": true
      },
      {
        "fold": 4,
        "n": 3,
        "wr": 1.0,
        "pf": 999.0,
        "expectancy_r": 1.3113,
        "max_dd_r": 0.0,
        "avg_win_r": 1.311,
        "avg_loss_r": 0.0,
        "worst_r": 0.453,
        "trades_per_week": 1.05,
        "anti_cheat_ok": true
      },
      {
        "fold": 5,
        "n": 6,
        "wr": 0.8333,
        "pf": 13.384,
        "expectancy_r": 1.3412,
        "max_dd_r": -0.65,
        "avg_win_r": 1.739,
        "avg_loss_r": -0.65,
        "worst_r": -0.65,
        "trades_per_week": 2.1,
        "anti_cheat_ok": true
      }
    ],
    "consistency_ok": false,
    "fail_reasons": [
      "holdout_n=6<20"
    ],
    "comfort_score": 196.5765,
    "mean_fold_wr": 0.8976,
    "min_fold_wr": 0.8333
  },
  {
    "window": "1000_1130",
    "confirmation": "rejection_wick",
    "exit": "1.75R",
    "target_r": 1.75,
    "zone_atr": 0.35,
    "stop_atr": 0.45,
    "vwap_buffer_atr": 0.15,
    "sides": [
      "BUY"
    ],
    "n_cands": 45,
    "train": {
      "n": 30,
      "wr": 0.9,
      "pf": 18.521,
      "expectancy_r": 1.4406,
      "max_dd_r": -1.005,
      "avg_win_r": 1.692,
      "avg_loss_r": -0.822,
      "worst_r": -1.005,
      "trades_per_week": 2.0,
      "anti_cheat_ok": true
    },
    "val": {
      "n": 38,
      "wr": 0.8947,
      "pf": 18.927,
      "expectancy_r": 1.4428,
      "max_dd_r": -1.005,
      "avg_win_r": 1.702,
      "avg_loss_r": -0.765,
      "worst_r": -1.005,
      "trades_per_week": 2.01,
      "anti_cheat_ok": true
    },
    "holdout": {
      "n": 7,
      "wr": 1.0,
      "pf": 999.0,
      "expectancy_r": 1.5035,
      "max_dd_r": 0.0,
      "avg_win_r": 1.503,
      "avg_loss_r": 0.0,
      "worst_r": 0.057,
      "trades_per_week": 1.69,
      "anti_cheat_ok": true
    },
    "folds": [
      {
        "fold": 1,
        "n": 8,
        "wr": 0.75,
        "pf": 5.201,
        "expectancy_r": 1.0543,
        "max_dd_r": -1.005,
        "avg_win_r": 1.74,
        "avg_loss_r": -1.004,
        "worst_r": -1.005,
        "trades_per_week": 2.44,
        "anti_cheat_ok": true
      },
      {
        "fold": 2,
        "n": 11,
        "wr": 0.9091,
        "pf": 37.912,
        "expectancy_r": 1.5406,
        "max_dd_r": -0.459,
        "avg_win_r": 1.741,
        "avg_loss_r": -0.459,
        "worst_r": -0.459,
        "trades_per_week": 3.07,
        "anti_cheat_ok": true
      },
      {
        "fold": 3,
        "n": 8,
        "wr": 1.0,
        "pf": 999.0,
        "expectancy_r": 1.7415,
        "max_dd_r": 0.0,
        "avg_win_r": 1.742,
        "avg_loss_r": 0.0,
        "worst_r": 1.731,
        "trades_per_week": 2.43,
        "anti_cheat_ok": true
      },
      {
        "fold": 4,
        "n": 3,
        "wr": 1.0,
        "pf": 999.0,
        "expectancy_r": 1.3019,
        "max_dd_r": 0.0,
        "avg_win_r": 1.302,
        "avg_loss_r": 0.0,
        "worst_r": 0.419,
        "trades_per_week": 1.05,
        "anti_cheat_ok": true
      },
      {
        "fold": 5,
        "n": 8,
        "wr": 0.875,
        "pf": 20.622,
        "expectancy_r": 1.4509,
        "max_dd_r": -0.592,
        "avg_win_r": 1.743,
        "avg_loss_r": -0.592,
        "worst_r": -0.592,
        "trades_per_week": 2.79,
        "anti_cheat_ok": true
      }
    ],
    "consistency_ok": false,
    "fail_reasons": [
      "holdout_n=7<20"
    ],
    "comfort_score": 195.5875,
    "mean_fold_wr": 0.883525,
    "min_fold_wr": 0.75
  }
]
```
