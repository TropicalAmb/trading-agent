# Long-History Strategy Validation

**Status: NO_STRATEGY_CLEARED_ALL_GATES**

No paper strategy is enabled unless the external holdout, corrected paid Databento recent window, and independent current Yahoo window all pass. The external file is research-only.

| Family | Variant | Long n | Long WR | Holdout n | Holdout WR | Paid n | Paid WR | Yahoo n | Yahoo WR | Eligible |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| daily_ibs_capitulation_reversion | ibs30_excursion25_stop050 | 311 | 44.7% | 100 | 42.0% | 7 | 42.9% | 0 | 0.0% | NO |

## Method

Public hypotheses were encoded as completed-bar rules with a small pre-declared parameter set. Selection used only the external validation segment. The final external holdout was opened after selection, and the chosen variant was then frozen for corrected Databento and Yahoo checks. All results include the configured two-contract scale-out, stop-first bar ambiguity, gap-through-stop handling, and friction.

## Promotion decision

Paper remains fail-closed unless `paper_eligible` contains a strategy. A high win rate with too few trades is explicitly rejected.