# Long-History Strategy Validation

**Status: NO_STRATEGY_CLEARED_ALL_GATES**

No paper strategy is enabled unless the external holdout, corrected paid Databento recent window, and independent current Yahoo window all pass. The external file is research-only.

| Family | Variant | Long n | Long WR | Holdout n | Holdout WR | Paid n | Paid WR | Yahoo n | Yahoo WR | Eligible |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| prior_day_level_failure | pierce010_close35 | 892 | 41.9% | 226 | 42.0% | 28 | 32.1% | 11 | 18.2% | NO |
| opening_range_retest_continuation | or30_break05_depth35 | 1340 | 41.0% | 349 | 39.0% | 50 | 50.0% | 19 | 52.6% | NO |
| opening_range_midpoint_continuation | or60_impulse50_depth25 | 1095 | 42.0% | 291 | 44.0% | 22 | 63.6% | 7 | 85.7% | NO |
| conditional_overnight_reversal | same_sign_gap050_prior025_exmon | 100 | 44.0% | 28 | 42.9% | 4 | 50.0% | 0 | 0.0% | NO |
| value_area_breakout_continuation | break05_depth25 | 512 | 43.4% | 144 | 35.4% | 18 | 61.1% | 9 | 55.6% | NO |
| overnight_range_break_retest | break05_depth35 | 987 | 43.7% | 261 | 44.1% | 26 | 53.8% | 9 | 44.4% | NO |
| session_extreme_two_bar_reversal | vwap10_confirm35 | 2957 | 42.2% | 756 | 41.8% | 99 | 41.4% | 41 | 36.6% | NO |
| weekly_value_area_failed_auction | outside10_retest05 | 203 | 33.0% | 50 | 30.0% | 8 | 12.5% | 5 | 0.0% | NO |

## Method

Public hypotheses were encoded as completed-bar rules with a small pre-declared parameter set. Selection used only the external validation segment. The final external holdout was opened after selection, and the chosen variant was then frozen for corrected Databento and Yahoo checks. All results include the configured two-contract scale-out, stop-first bar ambiguity, gap-through-stop handling, and friction.

## Promotion decision

Paper remains fail-closed unless `paper_eligible` contains a strategy. A high win rate with too few trades is explicitly rejected.