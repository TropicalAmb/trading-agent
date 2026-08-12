# NQ Databento Finetune Report

**Verdict:** `NQ STRATEGY NOT YET GOOD ENOUGH`
**Progress:** `VAL_POSITIVE_HOLD_WEAK`

Source: Databento cache only (`NQ_1m_cache.parquet`), bars=167582
Range: `2025-06-15 18:00:00-04:00` → `2025-12-11 15:57:00-05:00`
Window (train/val): `1000_1130`

## Per-trigger holdout
```
{
  "PULLBACK": {
    "n": 15,
    "wr": 0.4667,
    "pf": 1.806,
    "expectancy_r": 0.316,
    "max_dd_r": -2.53,
    "avg_win_r": 1.517,
    "avg_loss_r": -0.735,
    "worst_r": -1.027,
    "trades_per_week": 2.56,
    "long_n": 8,
    "short_n": 7,
    "anti_cheat_ok": true,
    "config": {
      "window": "1000_1130",
      "confirmation": "next_bar",
      "exit": "2.0R"
    },
    "train": {
      "n": 29,
      "wr": 0.6207,
      "pf": 3.199,
      "expectancy_r": 0.6396,
      "max_dd_r": -2.01,
      "avg_win_r": 1.499,
      "avg_loss_r": -0.767,
      "worst_r": -1.007,
      "trades_per_week": 2.33,
      "long_n": 21,
      "short_n": 8,
      "anti_cheat_ok": true
    },
    "val": {
      "n": 39,
      "wr": 0.5897,
      "pf": 3.082,
      "expectancy_r": 0.6192,
      "max_dd_r": -2.134,
      "avg_win_r": 1.554,
      "avg_loss_r": -0.725,
      "worst_r": -1.007,
      "trades_per_week": 2.24,
      "long_n": 28,
      "short_n": 11,
      "anti_cheat_ok": true
    }
  },
  "LIQUIDITY": {
    "n": 6,
    "wr": 0.8333,
    "pf": 46.851,
    "expectancy_r": 0.3633,
    "max_dd_r": 0.0,
    "avg_win_r": 0.445,
    "avg_loss_r": -0.048,
    "worst_r": -0.048,
    "trades_per_week": 1.5,
    "long_n": 1,
    "short_n": 5,
    "anti_cheat_ok": true,
    "config": {
      "window": "1000_1130",
      "confirmation": "rejection_wick",
      "exit": "1.0R"
    },
    "train": {
      "n": 19,
      "wr": 0.4211,
      "pf": 1.334,
      "expectancy_r": 0.0726,
      "max_dd_r": -2.129,
      "avg_win_r": 0.689,
      "avg_loss_r": -0.375,
      "worst_r": -1.002,
      "trades_per_week": 1.45,
      "long_n": 9,
      "short_n": 10,
      "anti_cheat_ok": true
    },
    "val": {
      "n": 28,
      "wr": 0.5357,
      "pf": 1.947,
      "expectancy_r": 0.1653,
      "max_dd_r": -2.129,
      "avg_win_r": 0.634,
      "avg_loss_r": -0.376,
      "worst_r": -1.002,
      "trades_per_week": 1.54,
      "long_n": 12,
      "short_n": 16,
      "anti_cheat_ok": true
    }
  },
  "BREAKOUT_RETEST": {
    "n": 11,
    "wr": 0.1818,
    "pf": 0.142,
    "expectancy_r": -0.7046,
    "max_dd_r": -7.185,
    "avg_win_r": 0.642,
    "avg_loss_r": -1.004,
    "worst_r": -1.006,
    "trades_per_week": 2.08,
    "long_n": 0,
    "short_n": 11,
    "anti_cheat_ok": true,
    "config": {
      "window": "1000_1130",
      "confirmation": "next_bar",
      "exit": "2.0R"
    },
    "train": {
      "n": 21,
      "wr": 0.0952,
      "pf": 0.161,
      "expectancy_r": -0.7415,
      "max_dd_r": -14.568,
      "avg_win_r": 1.49,
      "avg_loss_r": -0.976,
      "worst_r": -1.008,
      "trades_per_week": 1.63,
      "long_n": 6,
      "short_n": 15,
      "anti_cheat_ok": true
    },
    "val": {
      "n": 29,
      "wr": 0.1034,
      "pf": 0.155,
      "expectancy_r": -0.7456,
      "max_dd_r": -20.619,
      "avg_win_r": 1.324,
      "avg_loss_r": -0.984,
      "worst_r": -1.012,
      "trades_per_week": 1.61,
      "long_n": 7,
      "short_n": 22,
      "anti_cheat_ok": true
    }
  }
}
```

## Combined holdout
```
{
  "n": 32,
  "wr": 0.4375,
  "pf": 0.944,
  "expectancy_r": -0.026,
  "max_dd_r": -7.751,
  "avg_win_r": 1.009,
  "avg_loss_r": -0.831,
  "worst_r": -1.027,
  "trades_per_week": 5.46,
  "long_n": null,
  "short_n": null,
  "anti_cheat_ok": true
}
```

## Best balanced
```
{
  "trigger": "PULLBACK",
  "window": "1000_1130",
  "confirmation": "next_bar",
  "exit": "2.0R",
  "target_r": 2.0,
  "train": {
    "n": 29,
    "wr": 0.6207,
    "pf": 3.199,
    "expectancy_r": 0.6396,
    "max_dd_r": -2.01,
    "avg_win_r": 1.499,
    "avg_loss_r": -0.767,
    "worst_r": -1.007,
    "trades_per_week": 2.33,
    "long_n": 21,
    "short_n": 8,
    "anti_cheat_ok": true
  },
  "val": {
    "n": 39,
    "wr": 0.5897,
    "pf": 3.082,
    "expectancy_r": 0.6192,
    "max_dd_r": -2.134,
    "avg_win_r": 1.554,
    "avg_loss_r": -0.725,
    "worst_r": -1.007,
    "trades_per_week": 2.24,
    "long_n": 28,
    "short_n": 11,
    "anti_cheat_ok": true
  },
  "holdout": {
    "n": 15,
    "wr": 0.4667,
    "pf": 1.806,
    "expectancy_r": 0.316,
    "max_dd_r": -2.53,
    "avg_win_r": 1.517,
    "avg_loss_r": -0.735,
    "worst_r": -1.027,
    "trades_per_week": 2.56,
    "long_n": 8,
    "short_n": 7,
    "anti_cheat_ok": true
  },
  "select_score": 109.5488,
  "select_n": 39
}
```

## Best high-accuracy
```
{
  "trigger": "PULLBACK",
  "window": "1000_1130",
  "confirmation": "next_bar",
  "exit": "1.75R",
  "target_r": 1.75,
  "train": {
    "n": 29,
    "wr": 0.6552,
    "pf": 3.429,
    "expectancy_r": 0.6224,
    "max_dd_r": -2.01,
    "avg_win_r": 1.341,
    "avg_loss_r": -0.743,
    "worst_r": -1.007,
    "trades_per_week": 2.33,
    "long_n": 21,
    "short_n": 8,
    "anti_cheat_ok": true
  },
  "val": {
    "n": 39,
    "wr": 0.6154,
    "pf": 3.138,
    "expectancy_r": 0.5807,
    "max_dd_r": -2.357,
    "avg_win_r": 1.385,
    "avg_loss_r": -0.706,
    "worst_r": -1.007,
    "trades_per_week": 2.24,
    "long_n": 28,
    "short_n": 11,
    "anti_cheat_ok": true
  },
  "holdout": {
    "n": 15,
    "wr": 0.5333,
    "pf": 2.28,
    "expectancy_r": 0.416,
    "max_dd_r": -1.702,
    "avg_win_r": 1.389,
    "avg_loss_r": -0.697,
    "worst_r": -1.027,
    "trades_per_week": 2.56,
    "long_n": 8,
    "short_n": 7,
    "anti_cheat_ok": true
  },
  "select_score": 109.5014,
  "select_n": 39
}
```

## Best expectancy
```
{
  "trigger": "PULLBACK",
  "window": "1000_1130",
  "confirmation": "next_bar",
  "exit": "2.0R",
  "target_r": 2.0,
  "train": {
    "n": 29,
    "wr": 0.6207,
    "pf": 3.199,
    "expectancy_r": 0.6396,
    "max_dd_r": -2.01,
    "avg_win_r": 1.499,
    "avg_loss_r": -0.767,
    "worst_r": -1.007,
    "trades_per_week": 2.33,
    "long_n": 21,
    "short_n": 8,
    "anti_cheat_ok": true
  },
  "val": {
    "n": 39,
    "wr": 0.5897,
    "pf": 3.082,
    "expectancy_r": 0.6192,
    "max_dd_r": -2.134,
    "avg_win_r": 1.554,
    "avg_loss_r": -0.725,
    "worst_r": -1.007,
    "trades_per_week": 2.24,
    "long_n": 28,
    "short_n": 11,
    "anti_cheat_ok": true
  },
  "holdout": {
    "n": 15,
    "wr": 0.4667,
    "pf": 1.806,
    "expectancy_r": 0.316,
    "max_dd_r": -2.53,
    "avg_win_r": 1.517,
    "avg_loss_r": -0.735,
    "worst_r": -1.027,
    "trades_per_week": 2.56,
    "long_n": 8,
    "short_n": 7,
    "anti_cheat_ok": true
  },
  "select_score": 109.5488,
  "select_n": 39
}
```

## WR vs R
```
[
  {
    "R": 1.0,
    "val": {
      "n": 39,
      "wr": 0.6154,
      "pf": 1.883,
      "expectancy_r": 0.2399,
      "max_dd_r": -3.107,
      "avg_win_r": 0.831,
      "avg_loss_r": -0.706,
      "worst_r": -1.007,
      "trades_per_week": 2.24,
      "long_n": 28,
      "short_n": 11,
      "anti_cheat_ok": true
    },
    "holdout": {
      "n": 15,
      "wr": 0.5333,
      "pf": 1.357,
      "expectancy_r": 0.116,
      "max_dd_r": -1.712,
      "avg_win_r": 0.827,
      "avg_loss_r": -0.697,
      "worst_r": -1.027,
      "trades_per_week": 2.56,
      "long_n": 8,
      "short_n": 7,
      "anti_cheat_ok": true
    }
  },
  {
    "R": 1.25,
    "val": {
      "n": 39,
      "wr": 0.6154,
      "pf": 2.288,
      "expectancy_r": 0.35,
      "max_dd_r": -2.857,
      "avg_win_r": 1.01,
      "avg_loss_r": -0.706,
      "worst_r": -1.007,
      "trades_per_week": 2.24,
      "long_n": 28,
      "short_n": 11,
      "anti_cheat_ok": true
    },
    "holdout": {
      "n": 15,
      "wr": 0.5333,
      "pf": 1.664,
      "expectancy_r": 0.216,
      "max_dd_r": -1.702,
      "avg_win_r": 1.014,
      "avg_loss_r": -0.697,
      "worst_r": -1.027,
      "trades_per_week": 2.56,
      "long_n": 8,
      "short_n": 7,
      "anti_cheat_ok": true
    }
  },
  {
    "R": 1.5,
    "val": {
      "n": 39,
      "wr": 0.6154,
      "pf": 2.713,
      "expectancy_r": 0.4654,
      "max_dd_r": -2.607,
      "avg_win_r": 1.198,
      "avg_loss_r": -0.706,
      "worst_r": -1.007,
      "trades_per_week": 2.24,
      "long_n": 28,
      "short_n": 11,
      "anti_cheat_ok": true
    },
    "holdout": {
      "n": 15,
      "wr": 0.5333,
      "pf": 1.972,
      "expectancy_r": 0.316,
      "max_dd_r": -1.702,
      "avg_win_r": 1.202,
      "avg_loss_r": -0.697,
      "worst_r": -1.027,
      "trades_per_week": 2.56,
      "long_n": 8,
      "short_n": 7,
      "anti_cheat_ok": true
    }
  },
  {
    "R": 1.75,
    "val": {
      "n": 39,
      "wr": 0.6154,
      "pf": 3.138,
      "expectancy_r": 0.5807,
      "max_dd_r": -2.357,
      "avg_win_r": 1.385,
      "avg_loss_r": -0.706,
      "worst_r": -1.007,
      "trades_per_week": 2.24,
      "long_n": 28,
      "short_n": 11,
      "anti_cheat_ok": true
    },
    "holdout": {
      "n": 15,
      "wr": 0.5333,
      "pf": 2.28,
      "expectancy_r": 0.416,
      "max_dd_r": -1.702,
      "avg_win_r": 1.389,
      "avg_loss_r": -0.697,
      "worst_r": -1.027,
      "trades_per_week": 2.56,
      "long_n": 8,
      "short_n": 7,
      "anti_cheat_ok": true
    }
  },
  {
    "R": 2.0,
    "val": {
      "n": 39,
      "wr": 0.5897,
      "pf": 3.082,
      "expectancy_r": 0.6192,
      "max_dd_r": -2.134,
      "avg_win_r": 1.554,
      "avg_loss_r": -0.725,
      "worst_r": -1.007,
      "trades_per_week": 2.24,
      "long_n": 28,
      "short_n": 11,
      "anti_cheat_ok": true
    },
    "holdout": {
      "n": 15,
      "wr": 0.4667,
      "pf": 1.806,
      "expectancy_r": 0.316,
      "max_dd_r": -2.53,
      "avg_win_r": 1.517,
      "avg_loss_r": -0.735,
      "worst_r": -1.027,
      "trades_per_week": 2.56,
      "long_n": 8,
      "short_n": 7,
      "anti_cheat_ok": true
    }
  }
]
```

## Interpretation
- First honest Databento-positive cell: **PULLBACK / 10:00-11:30 / next_bar**.
- Val: ~59% WR, PF~3.0, E~+0.62R (n≈39). Holdout: n=15 still thin — not demo-ready.
- For higher WR preference, holdout WR-vs-R favors **1.25R–1.75R** over 2.0R.
- Liquidity holdout n=6 is anecdotal. Breakout still weak on this sample.
- Cache only (~180d). No multi-year Databento dump.
