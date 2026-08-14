# Broad Futures Strategy Discovery

Generated: 2026-08-14T19:20:18.642213+00:00

**Verdict: NO_70_PERCENT_STRATEGY_VALIDATED**

Paid Databento API calls: **0**; additional spend: **$0.00**. The run used the audited local NQ.v.0 and CL.v.0 caches.

## Finalists selected without seeing holdout

| Family | Symbol | Variant | All n | All WR | All PF | All E | Holdout n | Holdout WR | Holdout PF | Holdout E | 70% gate |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| daily_ibs_capitulation_reversion | NQ | ibs30_excursion25_stop050 | 7 | 42.9% | 1.22 | +0.095R | 1 | 100.0% | 999.00 | +1.292R | FAIL |
| volatility_compression_breakout | CL | compress40 | 65 | 52.3% | 1.20 | +0.078R | 12 | 58.3% | 1.21 | +0.095R | FAIL |
| vwap_band_reentry | CL | z2_re1_flat035 | 6 | 83.3% | 7.18 | +0.708R | 2 | 50.0% | 1.72 | +0.246R | FAIL |
| atr_rsi_failure_reversion | CL | stretch20 | 355 | 47.0% | 1.05 | +0.021R | 85 | 47.1% | 1.20 | +0.080R | FAIL |
| atr_rsi_failure_reversion | NQ | stretch20 | 469 | 44.1% | 0.97 | -0.014R | 122 | 45.9% | 1.03 | +0.015R | FAIL |
| initial_balance_failed_break | CL | pierce000 | 86 | 44.2% | 1.03 | +0.012R | 23 | 43.5% | 1.25 | +0.098R | FAIL |
| donchian_trend_breakout | CL | donchian20_stop10 | 263 | 44.5% | 0.96 | -0.019R | 66 | 42.4% | 0.95 | -0.023R | FAIL |
| intraday_open_to_close_momentum | NQ | impulse010 | 81 | 42.0% | 0.64 | -0.070R | 25 | 40.0% | 0.67 | -0.060R | FAIL |
| london_range_sweep_reversal | NQ | pierce010 | 99 | 44.4% | 1.04 | +0.016R | 25 | 40.0% | 0.85 | -0.066R | FAIL |
| initial_balance_failed_break | NQ | pierce010_flat | 81 | 38.3% | 0.63 | -0.188R | 22 | 36.4% | 0.62 | -0.192R | FAIL |
| intraday_open_to_close_momentum | CL | impulse020_highvol | 13 | 30.8% | 0.39 | -0.093R | 9 | 33.3% | 0.56 | -0.051R | FAIL |
| donchian_trend_breakout | NQ | donchian20_stop10 | 279 | 42.6% | 1.07 | +0.026R | 72 | 33.3% | 0.76 | -0.114R | FAIL |
| opening_drive_pullback | CL | impulse050 | 51 | 37.2% | 0.69 | -0.158R | 15 | 33.3% | 0.38 | -0.403R | FAIL |
| london_range_sweep_reversal | CL | pierce010 | 70 | 32.9% | 0.48 | -0.312R | 20 | 30.0% | 0.40 | -0.379R | FAIL |
| opening_drive_pullback | NQ | impulse050 | 45 | 35.6% | 0.77 | -0.107R | 14 | 28.6% | 0.52 | -0.278R | FAIL |
| overnight_gap_reversion | NQ | gap030 | 32 | 37.5% | 1.10 | +0.034R | 11 | 27.3% | 0.81 | -0.072R | FAIL |
| volatility_compression_breakout | NQ | compress40 | 93 | 40.9% | 0.98 | -0.006R | 26 | 26.9% | 0.63 | -0.174R | FAIL |
| overnight_gap_reversion | CL | gap030 | 44 | 29.5% | 0.62 | -0.184R | 12 | 25.0% | 0.53 | -0.262R | FAIL |
| vwap_band_reentry | NQ | z2_re1_flat035 | 8 | 37.5% | 1.61 | +0.162R | 0 | 0.0% | 0.00 | +0.000R | FAIL |
| intraday_capitulation_reversal | NQ | bb20_20_rsi2 | 7 | 71.4% | 2.12 | +0.322R | 0 | 0.0% | 0.00 | +0.000R | FAIL |
| trend_capitulation_reclaim | NQ | bb20_20 | 4 | 75.0% | 346.71 | +0.661R | 0 | 0.0% | 0.00 | +0.000R | FAIL |
| balanced_value_area_reversion | NQ | value3_balance35 | 1 | 0.0% | 0.00 | -1.031R | 0 | 0.0% | 0.00 | +0.000R | FAIL |
| balanced_value_area_reversion | CL | value3_balance35 | 0 | 0.0% | 0.00 | +0.000R | 0 | 0.0% | 0.00 | +0.000R | FAIL |
| daily_ibs_capitulation_reversion | CL | ibs30_excursion25_stop050 | 0 | 0.0% | 0.00 | +0.000R | 0 | 0.0% | 0.00 | +0.000R | FAIL |
| intraday_capitulation_reversal | CL | bb20_20_rsi2 | 0 | 0.0% | 0.00 | +0.000R | 0 | 0.0% | 0.00 | +0.000R | FAIL |
| trend_capitulation_reclaim | CL | bb20_20 | 0 | 0.0% | 0.00 | +0.000R | 0 | 0.0% | 0.00 | +0.000R | FAIL |

## Why the holdout is protected

Each family had only a small, pre-declared parameter set. One variant per family and symbol was chosen using validation metrics. The final 25% was evaluated only after that choice, and the finalist p-values were adjusted for the number of families examined.

## Promotion rule

A strategy is not enabled merely because one cell prints 70%. It must also have enough trades, positive validation and holdout expectancy, acceptable profit factor, realistic configured exits, and no anti-cheat failure.

## Regime-aware meta-selector

One regularized logistic selector per symbol was trained only on development rows. Its probability threshold was chosen only on validation rows, and its entry-time-only performance was then opened on holdout.

| Symbol | Threshold | Development n/WR | Validation n/WR/PF/E | Holdout n/WR/PF/E | Yahoo n/WR/PF/E | Verdict |
|---|---:|---|---|---|---|---|
| NQ | 0.55 | 103/63.1% | 52/46.2%/1.56/+0.158R | 41/31.7%/0.71/-0.129R | 67/35.8%/0.71/-0.149R | FAIL |
| CL | 0.50 | 135/65.2% | 92/43.5%/0.85/-0.074R | 70/48.6%/1.07/+0.029R | 125/45.6%/1.01/+0.006R | FAIL |