# Specialist Validation Report

Generated: 2026-08-10T13:04:59.594246+00:00

**Paper agent not replaced. Candidates added as research engines only.**

## 1. CL — cl_vwap_prox_momentum_v1

Definition: 5m parity-bias momentum + `|VWAP|<=0.25 ATR` on CL/MCL.
Baseline: n=121 (STRONGER SAMPLE) WR=69.4% PF=4.54 E=+1.083 DD=-5.00 t/wk=13.8

### Holdout
- train: n=96 (PROMISING / NOT CONFIRMED) WR=66.7% PF=4.00 E=+1.000 DD=-7.00 t/wk=14.5
- holdout: n=25 (VERY PRELIMINARY) WR=80.0% PF=8.00 E=+1.400 DD=-3.00 t/wk=10.4

### Walk-forward folds
- fold 1: n=24 (VERY PRELIMINARY) WR=62.5% PF=3.33 E=+0.875 DD=-4.00 t/wk=13.3 range=['2026-06-01 07:20:00-04:00', '2026-06-11 13:20:00-04:00']
- fold 2: n=24 (VERY PRELIMINARY) WR=58.3% PF=2.80 E=+0.750 DD=-7.00 t/wk=15.0 range=['2026-06-12 03:20:00-04:00', '2026-06-25 02:05:00-04:00']
- fold 3: n=24 (VERY PRELIMINARY) WR=70.8% PF=4.86 E=+1.125 DD=-2.00 t/wk=13.3 range=['2026-06-25 02:05:00-04:00', '2026-07-07 05:25:00-04:00']
- fold 4: n=24 (VERY PRELIMINARY) WR=75.0% PF=6.00 E=+1.250 DD=-2.00 t/wk=13.3 range=['2026-07-07 07:05:00-04:00', '2026-07-21 00:50:00-04:00']
- fold 5: n=25 (VERY PRELIMINARY) WR=80.0% PF=8.00 E=+1.400 DD=-3.00 t/wk=10.4 range=['2026-07-21 03:40:00-04:00', '2026-08-07 09:45:00-04:00']

### Monthly
- 2026-06: n=62 (PROMISING / NOT CONFIRMED) WR=61.3% PF=3.17 E=+0.839 DD=-5.00 t/wk=15.5
- 2026-07: n=49 (PROMISING / NOT CONFIRMED) WR=73.5% PF=5.54 E=+1.204 DD=-3.00 t/wk=12.2
- 2026-08: n=10 (VERY PRELIMINARY) WR=100.0% PF=999.00 E=+2.000 DD=0.00 t/wk=12.5

### Session / side / symbol / vol regime
**session**
- asia: n=52 (PROMISING / NOT CONFIRMED) WR=71.2% PF=4.93 E=+1.135 DD=-3.00 t/wk=9.3
- london: n=35 (PROMISING / NOT CONFIRMED) WR=62.9% PF=3.38 E=+0.886 DD=-5.00 t/wk=8.8
- ny_afternoon: n=7 (VERY PRELIMINARY) WR=71.4% PF=5.00 E=+1.143 DD=-1.00 t/wk=5.8
- ny_lunch: n=8 (VERY PRELIMINARY) WR=75.0% PF=6.00 E=+1.250 DD=-1.00 t/wk=5.7
- ny_mid_morning: n=8 (VERY PRELIMINARY) WR=62.5% PF=3.33 E=+0.875 DD=-2.00 t/wk=8.0
- ny_open: n=5 (VERY PRELIMINARY) WR=100.0% PF=999.00 E=+2.000 DD=0.00 t/wk=5.0
- ny_premarket: n=6 (VERY PRELIMINARY) WR=66.7% PF=4.00 E=+1.000 DD=-1.00 t/wk=5.0
**side**
- BUY: n=44 (PROMISING / NOT CONFIRMED) WR=79.5% PF=7.78 E=+1.386 DD=-3.00 t/wk=7.3
- SELL: n=77 (PROMISING / NOT CONFIRMED) WR=63.6% PF=3.50 E=+0.909 DD=-5.00 t/wk=11.7
**symbol**
- CL: n=63 (PROMISING / NOT CONFIRMED) WR=74.6% PF=5.88 E=+1.238 DD=-3.00 t/wk=7.9
- MCL: n=58 (PROMISING / NOT CONFIRMED) WR=63.8% PF=3.52 E=+0.914 DD=-5.00 t/wk=8.3
**vol**
- EXTREME: n=33 (PROMISING / NOT CONFIRMED) WR=81.8% PF=9.00 E=+1.455 DD=-1.00 t/wk=7.5
- HIGH: n=23 (VERY PRELIMINARY) WR=52.2% PF=2.18 E=+0.565 DD=-4.00 t/wk=7.7
- LOW: n=29 (VERY PRELIMINARY) WR=65.5% PF=3.80 E=+0.966 DD=-2.00 t/wk=7.6
- NORMAL: n=36 (PROMISING / NOT CONFIRMED) WR=72.2% PF=5.20 E=+1.167 DD=-2.00 t/wk=8.6

### Monte Carlo
{
  "n_sims": 5000,
  "status": "OK",
  "median_terminal_r": 131.0,
  "p05_terminal_r": 107.0,
  "p95_terminal_r": 155.0,
  "median_max_dd_r": -4.0,
  "p90_max_dd_r": -5.0,
  "p95_max_dd_r": -6.0,
  "prob_dd_ge_5r": 0.2242,
  "prob_dd_ge_10r": 0.0006,
  "prob_dd_ge_15r": 0.0,
  "prob_dd_ge_20r": 0.0,
  "median_longest_losing_streak": 4,
  "p90_longest_losing_streak": 5,
  "p95_longest_losing_streak": 6
}

### Stress (slip+fee): n=121 (STRONGER SAMPLE) WR=69.4% PF=4.09 E=+1.013 DD=-5.35 t/wk=13.8

### Kill thresholds (pre-deploy)
{
  "hist_max_dd_r": -5.0,
  "hist_p95_dd_r": -6.0,
  "trailing_stop_r": -7.5,
  "hard_kill_r": -9.0,
  "n": 121.0,
  "method": "historical_bootstrap"
}

## 2. NQ — nq_ny_open_momentum_v1

Definition: 5m parity-bias momentum + session=ny_open on NQ/MNQ.
Baseline: n=71 (PROMISING / NOT CONFIRMED) WR=64.8% PF=3.68 E=+0.944 DD=-2.00 t/wk=9.9

### Holdout
- train: n=56 (PROMISING / NOT CONFIRMED) WR=60.7% PF=3.09 E=+0.821 DD=-4.00 t/wk=9.7
- holdout: n=15 (VERY PRELIMINARY) WR=80.0% PF=8.00 E=+1.400 DD=-2.00 t/wk=9.4

### Walk-forward
- fold 1: n=14 (VERY PRELIMINARY) WR=57.1% PF=2.67 E=+0.714 DD=-4.00 t/wk=10.0
- fold 2: n=14 (VERY PRELIMINARY) WR=57.1% PF=2.67 E=+0.714 DD=-3.00 t/wk=10.0
- fold 3: n=14 (VERY PRELIMINARY) WR=71.4% PF=5.00 E=+1.143 DD=-4.00 t/wk=8.8
- fold 4: n=14 (VERY PRELIMINARY) WR=57.1% PF=2.67 E=+0.714 DD=-4.00 t/wk=8.8
- fold 5: n=15 (VERY PRELIMINARY) WR=80.0% PF=8.00 E=+1.400 DD=-2.00 t/wk=9.4

### Monthly
- 2026-06: n=30 (PROMISING / NOT CONFIRMED) WR=60.0% PF=3.00 E=+0.800 DD=-2.00 t/wk=10.0
- 2026-07: n=31 (PROMISING / NOT CONFIRMED) WR=67.7% PF=4.20 E=+1.032 DD=-2.00 t/wk=9.7
- 2026-08: n=10 (VERY PRELIMINARY) WR=70.0% PF=4.67 E=+1.100 DD=-1.00 t/wk=10.0

### Session / side / vol
**side**
- BUY: n=35 (PROMISING / NOT CONFIRMED) WR=71.4% PF=5.00 E=+1.143 DD=-1.00 t/wk=9.7
- SELL: n=36 (PROMISING / NOT CONFIRMED) WR=58.3% PF=2.80 E=+0.750 DD=-2.00 t/wk=10.0
**symbol**
- MNQ: n=35 (PROMISING / NOT CONFIRMED) WR=65.7% PF=3.83 E=+0.971 DD=-2.00 t/wk=5.0
- NQ: n=36 (PROMISING / NOT CONFIRMED) WR=63.9% PF=3.54 E=+0.917 DD=-2.00 t/wk=5.0
**vol**
- EXTREME: n=66 (PROMISING / NOT CONFIRMED) WR=62.1% PF=3.28 E=+0.864 DD=-2.00 t/wk=10.0
- HIGH: n=5 (VERY PRELIMINARY) WR=100.0% PF=999.00 E=+2.000 DD=0.00 t/wk=8.3

### Monte Carlo
{
  "n_sims": 5000,
  "status": "OK",
  "median_terminal_r": 67.0,
  "p05_terminal_r": 46.0,
  "p95_terminal_r": 88.0,
  "median_max_dd_r": -4.0,
  "p90_max_dd_r": -6.0,
  "p95_max_dd_r": -6.0,
  "prob_dd_ge_5r": 0.2424,
  "prob_dd_ge_10r": 0.0026,
  "prob_dd_ge_15r": 0.0,
  "prob_dd_ge_20r": 0.0,
  "median_longest_losing_streak": 4,
  "p90_longest_losing_streak": 5,
  "p95_longest_losing_streak": 6
}

### Stress: n=71 (PROMISING / NOT CONFIRMED) WR=64.8% PF=3.32 E=+0.874 DD=-2.35 t/wk=9.9

### Kill thresholds
{
  "hist_max_dd_r": -2.0,
  "hist_p95_dd_r": -6.0,
  "trailing_stop_r": -7.5,
  "hard_kill_r": -9.0,
  "n": 71.0,
  "method": "historical_bootstrap"
}

## Paper changes
{
  "cl_vwap_prox_momentum": {
    "activate_paper_executable": false,
    "reason": "Holdout remains interesting \u2014 add research engine + lifecycle tracking; do NOT make sole paper champion (n still limited).",
    "add_as_research_engine": true,
    "recommend_paper_shadow_track": true
  },
  "nq_ny_open_momentum": {
    "activate_paper_executable": false,
    "reason": "PROMISING / NOT CONFIRMED \u2014 remain research_only",
    "add_as_research_engine": true
  }
}
