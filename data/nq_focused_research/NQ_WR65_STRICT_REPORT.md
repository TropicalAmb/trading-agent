# NQ WR>=65% Strict Consistency

**Verdict:** `NQ STRATEGY READY FOR DEMO`
Strict (all folds>=65%, holdout n>=40)=96
Soft comfortable=182

## Champion
```
{
  "window": "0930_1200",
  "confirmation": "signal_close",
  "trigger": "PULLBACK",
  "exit": "1.15R",
  "target_r": 1.15,
  "zone_atr": 0.3,
  "stop_atr": 0.55,
  "vwap_buffer_atr": 0.2,
  "cooldown": 2,
  "sides": [
    "BUY"
  ],
  "val": {
    "n": 288,
    "wr": 0.7604,
    "pf": 5.89,
    "expectancy_r": 0.7024,
    "max_dd_r": -2.75,
    "avg_win_r": 1.113,
    "avg_loss_r": -0.599,
    "worst_r": -1.003,
    "trades_per_week": 10.95,
    "anti_cheat_ok": true
  },
  "holdout": {
    "n": 57,
    "wr": 0.7368,
    "pf": 4.915,
    "expectancy_r": 0.6411,
    "max_dd_r": -2.934,
    "avg_win_r": 1.092,
    "avg_loss_r": -0.622,
    "worst_r": -1.002,
    "trades_per_week": 9.25,
    "anti_cheat_ok": true
  },
  "folds": [
    {
      "fold": 1,
      "n": 76,
      "wr": 0.7632,
      "pf": 6.296,
      "expectancy_r": 0.7141,
      "max_dd_r": -2.75,
      "avg_win_r": 1.112,
      "avg_loss_r": -0.569,
      "worst_r": -1.003,
      "trades_per_week": 17.11,
      "anti_cheat_ok": true
    },
    {
      "fold": 2,
      "n": 66,
      "wr": 0.803,
      "pf": 7.31,
      "expectancy_r": 0.7416,
      "max_dd_r": -1.475,
      "avg_win_r": 1.07,
      "avg_loss_r": -0.597,
      "worst_r": -1.003,
      "trades_per_week": 14.4,
      "anti_cheat_ok": true
    },
    {
      "fold": 3,
      "n": 61,
      "wr": 0.7869,
      "pf": 7.128,
      "expectancy_r": 0.7583,
      "max_dd_r": -1.211,
      "avg_win_r": 1.121,
      "avg_loss_r": -0.581,
      "worst_r": -1.003,
      "trades_per_week": 11.53,
      "anti_cheat_ok": true
    },
    {
      "fold": 4,
      "n": 38,
      "wr": 0.6842,
      "pf": 3.333,
      "expectancy_r": 0.5476,
      "max_dd_r": -1.71,
      "avg_win_r": 1.143,
      "avg_loss_r": -0.743,
      "worst_r": -1.002,
      "trades_per_week": 8.58,
      "anti_cheat_ok": true
    },
    {
      "fold": 5,
      "n": 47,
      "wr": 0.7234,
      "pf": 5.645,
      "expectancy_r": 0.6809,
      "max_dd_r": -1.533,
      "avg_win_r": 1.144,
      "avg_loss_r": -0.53,
      "worst_r": -1.003,
      "trades_per_week": 9.12,
      "anti_cheat_ok": true
    }
  ],
  "strict_ok": true,
  "fail_reasons": [],
  "comfort_score": 283.5535,
  "mean_fold_wr": 0.75214,
  "min_fold_wr": 0.6842
}
```
