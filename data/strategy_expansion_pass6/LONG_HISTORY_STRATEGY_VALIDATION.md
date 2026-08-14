# Long-History Strategy Validation

**Status: NO_STRATEGY_CLEARED_ALL_GATES**

No paper strategy is enabled unless the external holdout, corrected paid Databento recent window, and independent current Yahoo window all pass. The external file is research-only.

**Proxy warning:** BVC/VPIN-style fields are estimated from one-minute OHLCV and are not true bid/ask delta, queue imbalance, cancellations, or depth. No strategy may be promoted on proxy semantics alone.

| Family | Variant | Long n | Long WR | Holdout n | Holdout WR | Paid n | Paid WR | Yahoo n | Yahoo WR | Eligible |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| bvc_cvd_divergence | price075_flow20_vwap075 | 1 | 100.0% | 0 | 0.0% | 0 | 0.0% | 0 | 0.0% | NO |
| bvc_absorption_reversal | pressure25_volume15_eff25 | 0 | 0.0% | 0 | 0.0% | 0 | 0.0% | 0 | 0.0% | NO |
| bvc_pressure_breakout | pressure25_volume15_eff70 | 324 | 45.1% | 90 | 44.4% | 6 | 50.0% | 0 | 0.0% | NO |
| vpin_failed_extension | toxicity_q90x105_edge25 | 691 | 42.3% | 193 | 47.1% | 23 | 47.8% | 10 | 60.0% | NO |
| impact_shock_reversal | impact20_range15_edge30 | 96 | 41.7% | 37 | 40.5% | 5 | 20.0% | 2 | 50.0% | NO |

## Method

Public hypotheses were encoded as completed-bar rules with a small pre-declared parameter set. Selection used only the external validation segment. The final external holdout was opened after selection, and the chosen variant was then frozen for corrected Databento and Yahoo checks. All results include the configured two-contract scale-out, stop-first bar ambiguity, gap-through-stop handling, and friction.

## Promotion decision

Paper remains fail-closed unless `paper_eligible` contains a strategy. A high win rate with too few trades is explicitly rejected.