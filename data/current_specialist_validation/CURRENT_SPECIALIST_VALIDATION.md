# Current Specialist Validation

## Executive decision

Only strategies that pass the frozen promotion thresholds can enter paper. `nq_context_entry` is active; `cl_vwap_prox_momentum` and `vwap_rejection` are research-only. No strategy is called forward-profitable until the exact-stamp forward cohort passes its separate proof rule.

## True forward paper cohort

Config: `router_v1_specialists_autonomy4`
Active: `nq_context_entry`

- Overall: n=0 — no measured win rate
- `nq_context_entry`: n=0 — no measured win rate

## Frozen-rule independent Yahoo replay

This is chronological historical replay, not future data. The latest 20% was not used to retune parameters in this run. NQ includes a 3-tick point haircut, CL includes a 0.07R fee/slippage haircut, and VWAP uses a 3-tick haircut.

### `nq_context_entry`

### `cl_vwap_prox_momentum`

### `vwap_rejection`

## NQ two-contract exit sensitivity

two contracts; half at TP1; runner stop moves to breakeven on the next bar; same-bar stop wins; identical NQ point-friction haircut

- No scale-out: n=49 · WR=59.2% · PF=1.64 · E=+0.265R · maxDD=-5.05R
- TP1 `0.30R`: n=49 · WR=75.5% · PF=1.05 · E=+0.013R · maxDD=-5.05R
- TP1 `0.50R`: n=49 · WR=69.4% · PF=1.19 · E=+0.059R · maxDD=-5.05R
- TP1 `0.75R`: n=49 · WR=61.2% · PF=1.30 · E=+0.116R · maxDD=-5.05R
- TP1 `1.00R`: n=49 · WR=59.2% · PF=1.48 · E=+0.197R · maxDD=-5.05R

- All: n=576 · WR=37.5% · PF=0.83 · E=-0.114R · maxDD=-73.68R
- Latest chronological 20%: n=116 · WR=31.0% · PF=0.63 · E=-0.262R · maxDD=-31.62R
- Holdout start: 2026-05-20 09:00:00-04:00

## Methodology and reproducibility

- Rules and thresholds were frozen before this replay; this run performed no parameter search.
- Every higher-timeframe feature is point-in-time. Automated prefix-invariance tests verify that appending future bars cannot change an earlier feature or signal.
- CL and MCL are one underlying and are not counted as independent observations.
- The current-stamp cohort excludes partial TP1 rows, prune/demo exits, different config stamps, and research-only strategies.
- Reproduce with `python scripts/run_current_specialist_validation.py`.

## Limitations

Yahoo replay is an independent screen, not a fill-perfect simulator or proof of future returns. Confidence intervals are wide for the latest NQ and CL slices. Corrected Databento `.v.0` validation remains pending explicit download approval.

## Decision rule

Do not claim forward profitability until a strategy has at least 40 resolved current-stamp trades with PF≥1.3 and positive expectancy after friction. A backtest or Yahoo screen cannot substitute for that cohort.

## Sources

- [Databento symbology conventions](https://databento.com/docs/standards-and-conventions/symbology)
- [Databento parent symbology](https://databento.com/docs/examples/symbology/parent-symbology)
- [Databento continuous symbology](https://databento.com/docs/examples/symbology/continuous)
- [r/algotrading: paper-to-live mistakes](https://www.reddit.com/r/algotrading/comments/1vmdce4/paper_2_live_what_mistakes_did_your_trading_bot/)
- [r/algotrading: walk-forward, holdout, and paper validation](https://www.reddit.com/r/algotrading/comments/1u4dcdp/progress_on_my_custom_algo_trading_bot_from_the/)
- [r/algotrading: implementation bugs can manufacture edge](https://www.reddit.com/r/algotrading/comments/1v06g8t/a_bug_in_my_code_accidentally_made_my_strategy/)
