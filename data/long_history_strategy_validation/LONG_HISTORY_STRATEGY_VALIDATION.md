# Long-History Strategy Validation

**Status: NO_STRATEGY_CLEARED_ALL_GATES**

No paper strategy is enabled unless the external holdout, corrected paid Databento recent window, and independent current Yahoo window all pass. The external file is research-only.

| Family | Variant | Long n | Long WR | Holdout n | Holdout WR | Paid n | Paid WR | Yahoo n | Yahoo WR | Eligible |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| vwap_band_reentry | z2_re1_flat035 | 470 | 45.7% | 138 | 52.2% | 8 | 37.5% | 2 | 100.0% | NO |
| atr_rsi_failure_reversion | stretch15 | 15107 | 40.5% | 3996 | 41.7% | 505 | 44.5% | 200 | 41.0% | NO |
| intraday_capitulation_reversal | bb20_20_rsi2 | 188 | 38.8% | 45 | 26.7% | 7 | 71.4% | 2 | 50.0% | NO |
| trend_capitulation_reclaim | bb20_25 | 15 | 40.0% | 5 | 60.0% | 1 | 100.0% | 0 | 0.0% | NO |
| london_range_sweep_reversal | pierce000 | 2964 | 40.9% | 752 | 40.8% | 103 | 42.7% | 40 | 40.0% | NO |
| initial_balance_failed_break | pierce000 | 2811 | 41.8% | 706 | 44.5% | 96 | 40.6% | 37 | 37.8% | NO |
| overnight_gap_reversion | gap050 | 526 | 41.2% | 128 | 41.4% | 23 | 26.1% | 0 | 0.0% | NO |
| balanced_value_area_reversion | value3_balance35 | 69 | 44.9% | 20 | 45.0% | 1 | 0.0% | 0 | 0.0% | NO |

## Method

Public hypotheses were encoded as completed-bar rules with a small pre-declared parameter set. Selection used only the external validation segment. The final external holdout was opened after selection, and the chosen variant was then frozen for corrected Databento and Yahoo checks. All results include the configured two-contract scale-out, stop-first bar ambiguity, gap-through-stop handling, and friction.

## Promotion decision

Paper remains fail-closed unless `paper_eligible` contains a strategy. A high win rate with too few trades is explicitly rejected.