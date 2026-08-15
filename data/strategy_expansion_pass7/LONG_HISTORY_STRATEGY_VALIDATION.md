# Long-History Strategy Validation

**Status: NO_STRATEGY_CLEARED_ALL_GATES**

No paper strategy is enabled unless the external holdout, corrected paid Databento recent window, and independent current Yahoo window all pass. The external file is research-only.

**Translation warning:** Reddit descriptions contain discretionary language. Each family is a frozen mechanical translation evaluated with the configured two-contract lifecycle; reported post win rates are hypotheses, not evidence for these implementations.

| Family | Variant | Long n | Long WR | Holdout n | Holdout WR | Paid n | Paid WR | Yahoo n | Yahoo WR | Eligible |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| nq_macd_ema_vwap_momentum | rising_rvol15_body70 | 2786 | 43.9% | 674 | 41.8% | 91 | 51.6% | 38 | 52.6% | NO |
| nq_flag_ema_vwap_pullback | impulse3_touch15_vol90 | 260 | 45.4% | 74 | 58.1% | 14 | 64.3% | 8 | 75.0% | NO |
| nq_vwap_ema9_rejection | twobar_wick20_near40 | 133 | 41.3% | 32 | 43.8% | 3 | 33.3% | 2 | 50.0% | NO |
| balanced_keltner_stochastic_reentry | kc20_adx25_stoch15 | 26 | 53.8% | 2 | 50.0% | 0 | 0.0% | 0 | 0.0% | NO |
| bollinger_keltner_mfi_squeeze | sq5_kc20_rvol15_mfi65 | 1582 | 44.9% | 353 | 46.2% | 39 | 25.6% | 10 | 20.0% | NO |

## Profitability evidence

| Family | Holdout PF | Holdout E | Paid PF | Paid E | Yahoo PF | Yahoo E |
|---|---:|---:|---:|---:|---:|---:|
| nq_macd_ema_vwap_momentum | 0.976 | -0.010R | 1.548 | +0.180R | 1.768 | +0.246R |
| nq_flag_ema_vwap_pullback | 1.839 | +0.270R | 4.008 | +0.451R | 6.011 | +0.643R |
| nq_vwap_ema9_rejection | 0.960 | -0.016R | 0.462 | -0.364R | 0.486 | -0.259R |
| balanced_keltner_stochastic_reentry | 0.802 | -0.102R | 0.000 | +0.000R | 0.000 | +0.000R |
| bollinger_keltner_mfi_squeeze | 0.961 | -0.018R | 0.317 | -0.489R | 0.212 | -0.645R |

## Method

Public hypotheses were encoded as completed-bar rules with a small pre-declared parameter set. Selection used only the external validation segment. The final external holdout was opened after selection, and the chosen variant was then frozen for corrected Databento and Yahoo checks. All results include the configured two-contract scale-out, stop-first bar ambiguity, gap-through-stop handling, and friction.

## Promotion decision

Paper remains fail-closed unless `paper_eligible` contains a strategy. A high win rate with too few trades is explicitly rejected.