# Long-History Strategy Validation

**Status: NO_STRATEGY_CLEARED_ALL_GATES**

No paper strategy is enabled unless the external holdout, corrected paid Databento recent window, and independent current Yahoo window all pass. The external file is research-only.

| Family | Variant | Long n | Long WR | Holdout n | Holdout WR | Paid n | Paid WR | Yahoo n | Yahoo WR | Eligible |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| nq_opening_shock_reversal | shock60_confirm3 | 12 | 50.0% | 1 | 100.0% | 0 | 0.0% | 0 | 0.0% | NO |
| gap_reject_then_go | gap25_fill20 | 87 | 35.6% | 18 | 44.4% | 2 | 100.0% | 1 | 100.0% | NO |
| initial_balance_vwap_retest | ib80_rvol10_depth25 | 1750 | 43.2% | 478 | 40.0% | 57 | 56.1% | 19 | 52.6% | NO |
| volume_climax_rejection | vol20_range15_edge25 | 1483 | 40.9% | 357 | 40.9% | 57 | 42.1% | 18 | 50.0% | NO |
| lunch_vwap_reclaim | stretch20_reclaim075 | 1502 | 40.8% | 405 | 43.5% | 41 | 34.2% | 18 | 27.8% | NO |
| two_test_range_breakout | look24_range40_rvol12 | 953 | 41.7% | 244 | 43.9% | 31 | 38.7% | 11 | 45.5% | NO |
| nq_post_settlement_alignment | drift10_gap20 | 299 | 43.8% | 66 | 42.4% | 9 | 55.6% | 1 | 100.0% | NO |

## Method

Public hypotheses were encoded as completed-bar rules with a small pre-declared parameter set. Selection used only the external validation segment. The final external holdout was opened after selection, and the chosen variant was then frozen for corrected Databento and Yahoo checks. All results include the configured two-contract scale-out, stop-first bar ambiguity, gap-through-stop handling, and friction.

## Promotion decision

Paper remains fail-closed unless `paper_eligible` contains a strategy. A high win rate with too few trades is explicitly rejected.