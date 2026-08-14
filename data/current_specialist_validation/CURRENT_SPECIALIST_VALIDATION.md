# Current Specialist Validation

## Executive decision

The old Databento parent-symbol cache is excluded. Only `nq_context_entry` and `cl_vwap_prox_momentum` remain active for clean paper-forward measurement. `vwap_rejection` is disabled after a large negative-expectancy replay. No strategy is called forward-profitable yet.

## True forward paper cohort

Config: `router_v1_specialists_autonomy3`
Active: `cl_vwap_prox_momentum, nq_context_entry`

- Overall: n=0 — no measured win rate
- `cl_vwap_prox_momentum`: n=0 — no measured win rate
- `nq_context_entry`: n=0 — no measured win rate

## Frozen-rule independent Yahoo replay

This is chronological historical replay, not future data. The latest 20% was not used to retune parameters in this run. NQ includes a 3-tick point haircut, CL includes a 0.07R fee/slippage haircut, and VWAP uses a 3-tick haircut.

### `nq_context_entry`

- All: n=48 · WR=60.4% · PF=1.73 · E=+0.292R · maxDD=-4.04R
- Latest chronological 20%: n=10 · WR=50.0% · PF=1.13 · E=+0.067R · maxDD=-4.04R
- Holdout start: 2026-08-06 10:50:00-04:00

### `cl_vwap_prox_momentum`

- All: n=41 · WR=41.5% · PF=1.28 · E=+0.174R · maxDD=-6.42R
- Latest chronological 20%: n=9 · WR=44.4% · PF=1.44 · E=+0.263R · maxDD=-4.28R
- Holdout start: 2026-07-22 14:00:00-04:00

### `vwap_rejection`

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
