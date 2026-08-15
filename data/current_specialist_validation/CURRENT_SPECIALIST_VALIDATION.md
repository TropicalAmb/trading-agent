# Current Specialist Validation

## Executive decision

No strategy currently passes every frozen threshold on both the corrected paid Databento lane and the independent Yahoo lane using the bot's configured management. Paper entry is therefore fail-closed; this is not a profitability claim.

## True forward paper cohort

Config: `router_v1_specialists_autonomy5`
Active: `none`

- Overall: n=0 — no measured win rate


## Databento corrected .v.0 frozen replay

Databento GLBX.MDP3 audited volume-continuous `.v.0`; frozen current rules; no optimization

### `nq_context_entry`

- All: n=141 · WR=58.9% · PF=1.30 · E=+0.105R · maxDD=-4.52R
- Latest chronological 20%: n=29 · WR=55.2% · PF=1.26 · E=+0.087R · maxDD=-3.57R
- Holdout start: 2026-07-09 11:00:00-04:00

### `cl_vwap_prox_momentum`

- All: n=133 · WR=53.4% · PF=1.79 · E=+0.259R · maxDD=-4.02R
- Latest chronological 20%: n=27 · WR=63.0% · PF=1.97 · E=+0.276R · maxDD=-2.78R
- Holdout start: 2026-07-02 04:50:00-04:00

### NQ exit architecture

two contracts; half at TP1; runner stop moves to breakeven on the next bar; same-bar stop wins; signal bar must close before 1m execution; identical NQ friction

- Configured manager: n=141 · WR=58.9% · PF=1.30 · E=+0.105R · maxDD=-4.52R
- No scale-out: n=141 · WR=58.9% · PF=1.48 · E=+0.194R · maxDD=-8.97R
- TP1 `0.30R` without pre-TP1 protection: n=141 · WR=80.9% · PF=1.23 · E=+0.042R · maxDD=-3.25R
- TP1 `0.50R` without pre-TP1 protection: n=141 · WR=72.3% · PF=1.30 · E=+0.081R · maxDD=-4.54R
- TP1 `0.75R` without pre-TP1 protection: n=141 · WR=63.8% · PF=1.34 · E=+0.123R · maxDD=-4.84R
- TP1 `1.00R` without pre-TP1 protection: n=141 · WR=58.9% · PF=1.35 · E=+0.140R · maxDD=-9.49R


## Yahoo independent frozen replay

Yahoo independent screening; frozen current rules; no optimization

### `nq_context_entry`

- All: n=49 · WR=57.1% · PF=1.26 · E=+0.090R · maxDD=-4.51R
- Latest chronological 20%: n=10 · WR=40.0% · PF=0.75 · E=-0.111R · maxDD=-4.51R
- Holdout start: 2026-08-07 10:15:00-04:00

### `cl_vwap_prox_momentum`

- All: n=41 · WR=56.1% · PF=1.80 · E=+0.248R · maxDD=-2.35R
- Latest chronological 20%: n=9 · WR=77.8% · PF=2.47 · E=+0.349R · maxDD=-2.14R
- Holdout start: 2026-07-22 14:00:00-04:00

### `vwap_rejection`

- All: n=576 · WR=37.5% · PF=0.83 · E=-0.114R · maxDD=-73.68R
- Latest chronological 20%: n=116 · WR=31.0% · PF=0.63 · E=-0.262R · maxDD=-31.62R
- Holdout start: 2026-05-20 09:00:00-04:00

### NQ exit architecture

two contracts; half at TP1; runner stop moves to breakeven on the next bar; same-bar stop wins; identical NQ point-friction haircut

- Configured manager: n=49 · WR=57.1% · PF=1.26 · E=+0.090R · maxDD=-4.51R
- No scale-out: n=49 · WR=61.2% · PF=1.77 · E=+0.275R · maxDD=-4.15R
- TP1 `0.30R` without pre-TP1 protection: n=49 · WR=75.5% · PF=1.14 · E=+0.032R · maxDD=-4.15R
- TP1 `0.50R` without pre-TP1 protection: n=49 · WR=69.4% · PF=1.29 · E=+0.084R · maxDD=-4.15R
- TP1 `0.75R` without pre-TP1 protection: n=49 · WR=63.3% · PF=1.42 · E=+0.146R · maxDD=-4.15R
- TP1 `1.00R` without pre-TP1 protection: n=49 · WR=61.2% · PF=1.61 · E=+0.215R · maxDD=-4.15R

## Methodology and reproducibility

- Rules and thresholds were frozen before this replay; this run performed no parameter search.
- Primary metrics simulate configured quantity-two management: 1R half exit, next-bar breakeven/profit-stop tightening, stop-first same-bar ordering, 120-minute losing-only time stop, and friction.
- A five-minute signal cannot execute until its signal bar has closed; one-minute Databento paths begin at the next tradable minute.
- Every higher-timeframe feature is point-in-time. Automated prefix-invariance tests verify that appending future bars cannot change an earlier feature or signal.
- CL and MCL are one underlying and are not counted as independent observations.
- The current-stamp cohort excludes partial TP1 rows, prune/demo exits, different config stamps, and research-only strategies.
- Reproduce with `python scripts/run_current_specialist_validation.py`.

## Limitations

Neither replay is a fill-perfect simulator or proof of future returns. Databento marks six source dates degraded; CL also has an elevated 2–30 minute gap rate. Those warnings are retained in `CORRECTED_CACHE_QUALITY.md`. Latest Yahoo NQ has only 10 trades.

## Decision rule

Historical promotion requires both lanes to meet n≥40, WR≥55%, PF≥1.3, E≥0.15R, plus non-negative latest-slice expectancy and PF≥1.0. Forward profitability still requires at least 40 resolved current-stamp paper trades with PF≥1.3 and positive expectancy after friction.

## Sources

- [Databento symbology conventions](https://databento.com/docs/standards-and-conventions/symbology)
- [Databento parent symbology](https://databento.com/docs/examples/symbology/parent-symbology)
- [Databento continuous symbology](https://databento.com/docs/examples/symbology/continuous)
- [r/algotrading: paper-to-live mistakes](https://www.reddit.com/r/algotrading/comments/1vmdce4/paper_2_live_what_mistakes_did_your_trading_bot/)
- [r/algotrading: walk-forward, holdout, and paper validation](https://www.reddit.com/r/algotrading/comments/1u4dcdp/progress_on_my_custom_algo_trading_bot_from_the/)
- [r/algotrading: implementation bugs can manufacture edge](https://www.reddit.com/r/algotrading/comments/1v06g8t/a_bug_in_my_code_accidentally_made_my_strategy/)
