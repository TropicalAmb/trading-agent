# NQ WR≥65% Dense Iteration

**Verdict:** `NQ_WR65_HIT_SAMPLE_THIN`
Ready: 272 | Comfortable (holdout n≥40 + gates): 0
Range: `2025-04-16 18:00:00-04:00` → `2025-12-11 15:57:00-05:00` (223922 bars)

## Champion
```
{
  "window": "1000_1130",
  "confirmation": "signal_close",
  "exit": "1.0R",
  "target_r": 1.0,
  "zone_atr": 0.35,
  "stop_atr": 0.4,
  "vwap_buffer_atr": 0.15,
  "cooldown": 4,
  "sides": [
    "BUY"
  ],
  "n_cands": 148,
  "train": {
    "n": 102,
    "wr": 0.7549,
    "pf": 4.69,
    "expectancy_r": 0.5672,
    "max_dd_r": -1.942,
    "avg_win_r": 0.955,
    "avg_loss_r": -0.627,
    "worst_r": -1.003,
    "trades_per_week": 5.03,
    "anti_cheat_ok": true
  },
  "val": {
    "n": 121,
    "wr": 0.7521,
    "pf": 4.95,
    "expectancy_r": 0.5767,
    "max_dd_r": -1.942,
    "avg_win_r": 0.961,
    "avg_loss_r": -0.589,
    "worst_r": -1.003,
    "trades_per_week": 4.6,
    "anti_cheat_ok": true
  },
  "holdout": {
    "n": 27,
    "wr": 0.7037,
    "pf": 3.357,
    "expectancy_r": 0.4445,
    "max_dd_r": -1.323,
    "avg_win_r": 0.9,
    "avg_loss_r": -0.636,
    "worst_r": -1.002,
    "trades_per_week": 4.39,
    "anti_cheat_ok": true
  },
  "folds": [
    {
      "fold": 1,
      "n": 27,
      "wr": 0.7778,
      "pf": 6.338,
      "expectancy_r": 0.6334,
      "max_dd_r": -1.003,
      "avg_win_r": 0.967,
      "avg_loss_r": -0.534,
      "worst_r": -1.003,
      "trades_per_week": 6.3,
      "anti_cheat_ok": true
    },
    {
      "fold": 2,
      "n": 29,
      "wr": 0.8276,
      "pf": 6.166,
      "expectancy_r": 0.6437,
      "max_dd_r": -1.72,
      "avg_win_r": 0.928,
      "avg_loss_r": -0.723,
      "worst_r": -1.002,
      "trades_per_week": 6.54,
      "anti_cheat_ok": true
    },
    {
      "fold": 3,
      "n": 26,
      "wr": 0.7308,
      "pf": 4.523,
      "expectancy_r": 0.5638,
      "max_dd_r": -1.382,
      "avg_win_r": 0.991,
      "avg_loss_r": -0.594,
      "worst_r": -1.002,
      "trades_per_week": 4.91,
      "anti_cheat_ok": true
    },
    {
      "fold": 4,
      "n": 20,
      "wr": 0.65,
      "pf": 2.579,
      "expectancy_r": 0.3713,
      "max_dd_r": -1.942,
      "avg_win_r": 0.933,
      "avg_loss_r": -0.672,
      "worst_r": -1.002,
      "trades_per_week": 4.52,
      "anti_cheat_ok": true
    },
    {
      "fold": 5,
      "n": 19,
      "wr": 0.7368,
      "pf": 7.012,
      "expectancy_r": 0.6277,
      "max_dd_r": -1.076,
      "avg_win_r": 0.994,
      "avg_loss_r": -0.397,
      "worst_r": -0.61,
      "trades_per_week": 3.8,
      "anti_cheat_ok": true
    }
  ],
  "consistency_ok": true,
  "comfortable": false,
  "fail_reasons": [],
  "comfort_score": 176.1125,
  "mean_fold_wr": 0.7445999999999999,
  "min_fold_wr": 0.65
}
```

## Comfortable
```
[]
```

## Ready top
```
[
  {
    "window": "1000_1130",
    "confirmation": "signal_close",
    "exit": "1.0R",
    "target_r": 1.0,
    "zone_atr": 0.35,
    "stop_atr": 0.4,
    "vwap_buffer_atr": 0.15,
    "cooldown": 4,
    "sides": [
      "BUY"
    ],
    "n_cands": 148,
    "train": {
      "n": 102,
      "wr": 0.7549,
      "pf": 4.69,
      "expectancy_r": 0.5672,
      "max_dd_r": -1.942,
      "avg_win_r": 0.955,
      "avg_loss_r": -0.627,
      "worst_r": -1.003,
      "trades_per_week": 5.03,
      "anti_cheat_ok": true
    },
    "val": {
      "n": 121,
      "wr": 0.7521,
      "pf": 4.95,
      "expectancy_r": 0.5767,
      "max_dd_r": -1.942,
      "avg_win_r": 0.961,
      "avg_loss_r": -0.589,
      "worst_r": -1.003,
      "trades_per_week": 4.6,
      "anti_cheat_ok": true
    },
    "holdout": {
      "n": 27,
      "wr": 0.7037,
      "pf": 3.357,
      "expectancy_r": 0.4445,
      "max_dd_r": -1.323,
      "avg_win_r": 0.9,
      "avg_loss_r": -0.636,
      "worst_r": -1.002,
      "trades_per_week": 4.39,
      "anti_cheat_ok": true
    },
    "folds": [
      {
        "fold": 1,
        "n": 27,
        "wr": 0.7778,
        "pf": 6.338,
        "expectancy_r": 0.6334,
        "max_dd_r": -1.003,
        "avg_win_r": 0.967,
        "avg_loss_r": -0.534,
        "worst_r": -1.003,
        "trades_per_week": 6.3,
        "anti_cheat_ok": true
      },
      {
        "fold": 2,
        "n": 29,
        "wr": 0.8276,
        "pf": 6.166,
        "expectancy_r": 0.6437,
        "max_dd_r": -1.72,
        "avg_win_r": 0.928,
        "avg_loss_r": -0.723,
        "worst_r": -1.002,
        "trades_per_week": 6.54,
        "anti_cheat_ok": true
      },
      {
        "fold": 3,
        "n": 26,
        "wr": 0.7308,
        "pf": 4.523,
        "expectancy_r": 0.5638,
        "max_dd_r": -1.382,
        "avg_win_r": 0.991,
        "avg_loss_r": -0.594,
        "worst_r": -1.002,
        "trades_per_week": 4.91,
        "anti_cheat_ok": true
      },
      {
        "fold": 4,
        "n": 20,
        "wr": 0.65,
        "pf": 2.579,
        "expectancy_r": 0.3713,
        "max_dd_r": -1.942,
        "avg_win_r": 0.933,
        "avg_loss_r": -0.672,
        "worst_r": -1.002,
        "trades_per_week": 4.52,
        "anti_cheat_ok": true
      },
      {
        "fold": 5,
        "n": 19,
        "wr": 0.7368,
        "pf": 7.012,
        "expectancy_r": 0.6277,
        "max_dd_r": -1.076,
        "avg_win_r": 0.994,
        "avg_loss_r": -0.397,
        "worst_r": -0.61,
        "trades_per_week": 3.8,
        "anti_cheat_ok": true
      }
    ],
    "consistency_ok": true,
    "comfortable": false,
    "fail_reasons": [],
    "comfort_score": 176.1125,
    "mean_fold_wr": 0.7445999999999999,
    "min_fold_wr": 0.65
  },
  {
    "window": "1000_1130",
    "confirmation": "signal_close",
    "exit": "1.1R",
    "target_r": 1.1,
    "zone_atr": 0.35,
    "stop_atr": 0.4,
    "vwap_buffer_atr": 0.15,
    "cooldown": 4,
    "sides": [
      "BUY"
    ],
    "n_cands": 148,
    "train": {
      "n": 102,
      "wr": 0.7255,
      "pf": 4.495,
      "expectancy_r": 0.5911,
      "max_dd_r": -2.455,
      "avg_win_r": 1.048,
      "avg_loss_r": -0.616,
      "worst_r": -1.003,
      "trades_per_week": 5.03,
      "anti_cheat_ok": true
    },
    "val": {
      "n": 121,
      "wr": 0.7273,
      "pf": 4.827,
      "expectancy_r": 0.6084,
      "max_dd_r": -2.455,
      "avg_win_r": 1.055,
      "avg_loss_r": -0.583,
      "worst_r": -1.003,
      "trades_per_week": 4.6,
      "anti_cheat_ok": true
    },
    "holdout": {
      "n": 27,
      "wr": 0.7037,
      "pf": 3.691,
      "expectancy_r": 0.5075,
      "max_dd_r": -1.223,
      "avg_win_r": 0.989,
      "avg_loss_r": -0.636,
      "worst_r": -1.002,
      "trades_per_week": 4.39,
      "anti_cheat_ok": true
    },
    "folds": [
      {
        "fold": 1,
        "n": 27,
        "wr": 0.7407,
        "pf": 6.055,
        "expectancy_r": 0.6558,
        "max_dd_r": -1.003,
        "avg_win_r": 1.06,
        "avg_loss_r": -0.5,
        "worst_r": -1.003,
        "trades_per_week": 6.3,
        "anti_cheat_ok": true
      },
      {
        "fold": 2,
        "n": 29,
        "wr": 0.7586,
        "pf": 4.562,
        "expectancy_r": 0.6,
        "max_dd_r": -2.455,
        "avg_win_r": 1.013,
        "avg_loss_r": -0.698,
        "worst_r": -1.002,
        "trades_per_week": 6.54,
        "anti_cheat_ok": true
      },
      {
        "fold": 3,
        "n": 26,
        "wr": 0.7308,
        "pf": 4.98,
        "expectancy_r": 0.6369,
        "max_dd_r": -1.382,
        "avg_win_r": 1.091,
        "avg_loss_r": -0.594,
        "worst_r": -1.002,
        "trades_per_week": 4.91,
        "anti_cheat_ok": true
      },
      {
        "fold": 4,
        "n": 20,
        "wr": 0.65,
        "pf": 2.835,
        "expectancy_r": 0.4313,
        "max_dd_r": -1.942,
        "avg_win_r": 1.025,
        "avg_loss_r": -0.672,
        "worst_r": -1.002,
        "trades_per_week": 4.52,
        "anti_cheat_ok": true
      },
      {
        "fold": 5,
        "n": 19,
        "wr": 0.7368,
        "pf": 7.718,
        "expectancy_r": 0.7014,
        "max_dd_r": -1.076,
        "avg_win_r": 1.094,
        "avg_loss_r": -0.397,
        "worst_r": -0.61,
        "trades_per_week": 3.8,
        "anti_cheat_ok": true
      }
    ],
    "consistency_ok": true,
    "comfortable": false,
    "fail_reasons": [],
    "comfort_score": 177.6875,
    "mean_fold_wr": 0.72338,
    "min_fold_wr": 0.65
  },
  {
    "window": "1000_1130",
    "confirmation": "signal_close",
    "exit": "1.15R",
    "target_r": 1.15,
    "zone_atr": 0.35,
    "stop_atr": 0.4,
    "vwap_buffer_atr": 0.15,
    "cooldown": 4,
    "sides": [
      "BUY"
    ],
    "n_cands": 148,
    "train": {
      "n": 102,
      "wr": 0.7255,
      "pf": 4.698,
      "expectancy_r": 0.6254,
      "max_dd_r": -2.455,
      "avg_win_r": 1.095,
      "avg_loss_r": -0.616,
      "worst_r": -1.003,
      "trades_per_week": 5.03,
      "anti_cheat_ok": true
    },
    "val": {
      "n": 121,
      "wr": 0.7273,
      "pf": 5.046,
      "expectancy_r": 0.6431,
      "max_dd_r": -2.455,
      "avg_win_r": 1.103,
      "avg_loss_r": -0.583,
      "worst_r": -1.003,
      "trades_per_week": 4.6,
      "anti_cheat_ok": true
    },
    "holdout": {
      "n": 27,
      "wr": 0.7037,
      "pf": 3.858,
      "expectancy_r": 0.5389,
      "max_dd_r": -1.223,
      "avg_win_r": 1.034,
      "avg_loss_r": -0.636,
      "worst_r": -1.002,
      "trades_per_week": 4.39,
      "anti_cheat_ok": true
    },
    "folds": [
      {
        "fold": 1,
        "n": 27,
        "wr": 0.7407,
        "pf": 6.327,
        "expectancy_r": 0.6909,
        "max_dd_r": -1.003,
        "avg_win_r": 1.108,
        "avg_loss_r": -0.5,
        "worst_r": -1.003,
        "trades_per_week": 6.3,
        "anti_cheat_ok": true
      },
      {
        "fold": 2,
        "n": 29,
        "wr": 0.7586,
        "pf": 4.766,
        "expectancy_r": 0.6345,
        "max_dd_r": -2.455,
        "avg_win_r": 1.058,
        "avg_loss_r": -0.698,
        "worst_r": -1.002,
        "trades_per_week": 6.54,
        "anti_cheat_ok": true
      },
      {
        "fold": 3,
        "n": 26,
        "wr": 0.7308,
        "pf": 5.208,
        "expectancy_r": 0.6735,
        "max_dd_r": -1.382,
        "avg_win_r": 1.141,
        "avg_loss_r": -0.594,
        "worst_r": -1.002,
        "trades_per_week": 4.91,
        "anti_cheat_ok": true
      },
      {
        "fold": 4,
        "n": 20,
        "wr": 0.65,
        "pf": 2.962,
        "expectancy_r": 0.4613,
        "max_dd_r": -1.942,
        "avg_win_r": 1.071,
        "avg_loss_r": -0.672,
        "worst_r": -1.002,
        "trades_per_week": 4.52,
        "anti_cheat_ok": true
      },
      {
        "fold": 5,
        "n": 19,
        "wr": 0.7368,
        "pf": 8.071,
        "expectancy_r": 0.7383,
        "max_dd_r": -1.076,
        "avg_win_r": 1.144,
        "avg_loss_r": -0.397,
        "worst_r": -0.61,
        "trades_per_week": 3.8,
        "anti_cheat_ok": true
      }
    ],
    "consistency_ok": true,
    "comfortable": false,
    "fail_reasons": [],
    "comfort_score": 178.4725,
    "mean_fold_wr": 0.72338,
    "min_fold_wr": 0.65
  },
  {
    "window": "1000_1130",
    "confirmation": "signal_close",
    "exit": "1.25R",
    "target_r": 1.25,
    "zone_atr": 0.35,
    "stop_atr": 0.4,
    "vwap_buffer_atr": 0.15,
    "cooldown": 4,
    "sides": [
      "BUY"
    ],
    "n_cands": 148,
    "train": {
      "n": 102,
      "wr": 0.7255,
      "pf": 5.104,
      "expectancy_r": 0.694,
      "max_dd_r": -2.455,
      "avg_win_r": 1.19,
      "avg_loss_r": -0.616,
      "worst_r": -1.003,
      "trades_per_week": 5.03,
      "anti_cheat_ok": true
    },
    "val": {
      "n": 121,
      "wr": 0.719,
      "pf": 5.303,
      "expectancy_r": 0.6988,
      "max_dd_r": -2.455,
      "avg_win_r": 1.198,
      "avg_loss_r": -0.578,
      "worst_r": -1.003,
      "trades_per_week": 4.6,
      "anti_cheat_ok": true
    },
    "holdout": {
      "n": 27,
      "wr": 0.7037,
      "pf": 4.192,
      "expectancy_r": 0.6019,
      "max_dd_r": -1.223,
      "avg_win_r": 1.123,
      "avg_loss_r": -0.636,
      "worst_r": -1.002,
      "trades_per_week": 4.39,
      "anti_cheat_ok": true
    },
    "folds": [
      {
        "fold": 1,
        "n": 27,
        "wr": 0.7407,
        "pf": 6.869,
        "expectancy_r": 0.7613,
        "max_dd_r": -1.003,
        "avg_win_r": 1.203,
        "avg_loss_r": -0.5,
        "worst_r": -1.003,
        "trades_per_week": 6.3,
        "anti_cheat_ok": true
      },
      {
        "fold": 2,
        "n": 29,
        "wr": 0.7586,
        "pf": 5.176,
        "expectancy_r": 0.7034,
        "max_dd_r": -2.455,
        "avg_win_r": 1.149,
        "avg_loss_r": -0.698,
        "worst_r": -1.002,
        "trades_per_week": 6.54,
        "anti_cheat_ok": true
      },
      {
        "fold": 3,
        "n": 26,
        "wr": 0.7308,
        "pf": 5.664,
        "expectancy_r": 0.7465,
        "max_dd_r": -1.382,
        "avg_win_r": 1.241,
        "avg_loss_r": -0.594,
        "worst_r": -1.002,
        "trades_per_week": 4.91,
        "anti_cheat_ok": true
      },
      {
        "fold": 4,
        "n": 20,
        "wr": 0.65,
        "pf": 3.218,
        "expectancy_r": 0.5213,
        "max_dd_r": -1.942,
        "avg_win_r": 1.164,
        "avg_loss_r": -0.672,
        "worst_r": -1.002,
        "trades_per_week": 4.52,
        "anti_cheat_ok": true
      },
      {
        "fold": 5,
        "n": 19,
        "wr": 0.6842,
        "pf": 6.736,
        "expectancy_r": 0.7244,
        "max_dd_r": -1.076,
        "avg_win_r": 1.243,
        "avg_loss_r": -0.4,
        "worst_r": -0.61,
        "trades_per_week": 3.8,
        "anti_cheat_ok": true
      }
    ],
    "consistency_ok": true,
    "comfortable": false,
    "fail_reasons": [],
    "comfort_score": 180.0475,
    "mean_fold_wr": 0.71286,
    "min_fold_wr": 0.65
  },
  {
    "window": "1000_1130",
    "confirmation": "signal_close",
    "exit": "1.0R",
    "target_r": 1.0,
    "zone_atr": 0.35,
    "stop_atr": 0.45,
    "vwap_buffer_atr": 0.15,
    "cooldown": 4,
    "sides": [
      "BUY"
    ],
    "n_cands": 148,
    "train": {
      "n": 102,
      "wr": 0.7549,
      "pf": 4.912,
      "expectancy_r": 0.5742,
      "max_dd_r": -1.693,
      "avg_win_r": 0.955,
      "avg_loss_r": -0.599,
      "worst_r": -1.002,
      "trades_per_week": 5.03,
      "anti_cheat_ok": true
    },
    "val": {
      "n": 121,
      "wr": 0.7521,
      "pf": 5.175,
      "expectancy_r": 0.5831,
      "max_dd_r": -1.693,
      "avg_win_r": 0.961,
      "avg_loss_r": -0.563,
      "worst_r": -1.002,
      "trades_per_week": 4.6,
      "anti_cheat_ok": true
    },
    "holdout": {
      "n": 27,
      "wr": 0.7037,
      "pf": 3.425,
      "expectancy_r": 0.4483,
      "max_dd_r": -1.242,
      "avg_win_r": 0.9,
      "avg_loss_r": -0.624,
      "worst_r": -1.002,
      "trades_per_week": 4.39,
      "anti_cheat_ok": true
    },
    "folds": [
      {
        "fold": 1,
        "n": 27,
        "wr": 0.7778,
        "pf": 6.393,
        "expectancy_r": 0.6343,
        "max_dd_r": -1.002,
        "avg_win_r": 0.967,
        "avg_loss_r": -0.529,
        "worst_r": -1.002,
        "trades_per_week": 6.3,
        "anti_cheat_ok": true
      },
      {
        "fold": 2,
        "n": 29,
        "wr": 0.8276,
        "pf": 6.25,
        "expectancy_r": 0.6453,
        "max_dd_r": -1.693,
        "avg_win_r": 0.928,
        "avg_loss_r": -0.713,
        "worst_r": -1.002,
        "trades_per_week": 6.54,
        "anti_cheat_ok": true
      },
      {
        "fold": 3,
        "n": 26,
        "wr": 0.7308,
        "pf": 4.628,
        "expectancy_r": 0.5679,
        "max_dd_r": -1.342,
        "avg_win_r": 0.991,
        "avg_loss_r": -0.581,
        "worst_r": -1.002,
        "trades_per_week": 4.91,
        "anti_cheat_ok": true
      },
      {
        "fold": 4,
        "n": 20,
        "wr": 0.65,
        "pf": 2.914,
        "expectancy_r": 0.3983,
        "max_dd_r": -1.473,
        "avg_win_r": 0.933,
        "avg_loss_r": -0.595,
        "worst_r": -0.866,
        "trades_per_week": 4.52,
        "anti_cheat_ok": true
      },
      {
        "fold": 5,
        "n": 19,
        "wr": 0.7368,
        "pf": 7.219,
        "expectancy_r": 0.631,
        "max_dd_r": -1.046,
        "avg_win_r": 0.994,
        "avg_loss_r": -0.386,
        "worst_r": -0.596,
        "trades_per_week": 3.8,
        "anti_cheat_ok": true
      }
    ],
    "consistency_ok": true,
    "comfortable": false,
    "fail_reasons": [],
    "comfort_score": 176.2075,
    "mean_fold_wr": 0.7445999999999999,
    "min_fold_wr": 0.65
  }
]
```
