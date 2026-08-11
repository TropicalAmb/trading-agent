# CL Priority Learning Report

Generated: 2026-08-11T15:13:20.576710+00:00

## Policy
- Do **not** promote from one paper trade
- Keep multi-strategy mix / router_v1 paper path
- CL `liquidity_reversal` = priority **learning/shadow** cell only

## Why the recent CL winner won (non-causal)

**Warning:** This paper winner is cl_vwap_prox_momentum (validated specialist), NOT liquidity_reversal. Do not treat as LR promotion evidence.

- trade_id: `PAPER-00151`
- strategy: `cl_vwap_prox_momentum`
- direction: `BUY` session=`asia`
- global_score/tier: `78.0` / `A`
- MTF: 15m=-1 1h=1 4h=1 aligned=2
- VWAP above=1 dist_atr=None
- agreeing: ['cl_vwap_prox_momentum', 'ema_pullback', 'vwap_reclaim']
- result R=0.8541001480164029 MFE=0.19000457763671363 MAE=None pnl=270.0
- features_source: learning_store+trade

### Anecdotal traits (single trade)
- {'note': 'Paper winner strategy is cl_vwap_prox_momentum (NOT liquidity_reversal). Traits below are anecdotal until confirmed vs a same-strategy loss cohort.', 'winner_strategy': 'cl_vwap_prox_momentum'}
- {'trait': 'session', 'value': 'asia', 'status': 'anecdotal_single_trade'}
- {'trait': 'mtf_aligned', 'value': 2, 'status': 'anecdotal_single_trade'}
- {'trait': 'above_vwap', 'value': 1, 'status': 'anecdotal_single_trade'}
- {'trait': 'dir_15m', 'value': -1, 'status': 'anecdotal_single_trade'}
- {'trait': 'dir_1h', 'value': 1, 'status': 'anecdotal_single_trade'}
- {'trait': 'dir_4h', 'value': 1, 'status': 'anecdotal_single_trade'}
- {'trait': 'near_pdl', 'value': 0, 'status': 'anecdotal_single_trade'}
- {'trait': 'agreeing_engines', 'value': ['cl_vwap_prox_momentum', 'ema_pullback', 'vwap_reclaim'], 'status': 'anecdotal_single_trade'}
- {'trait': 'global_score', 'value': 78.0, 'status': 'anecdotal_single_trade'}
- {'trait': 'tier', 'value': 'A', 'status': 'anecdotal_single_trade'}

### Statistical candidates (CL LR historical win vs loss)

- median_vwap_dist_atr: winners=-11.309531093995778 losers=-11.796724377722544 delta=0.48719328372676607
- median_realized_r: winners=1.5 losers=-1.0 delta=2.5

## CL liquidity_reversal winner vs loser (historical)
- n_wins=332 n_losses=500
- winners: {"pct_london": 0.3463855421686747, "pct_asia": 0.35240963855421686, "pct_ny": 0.30120481927710846, "pct_mtf_aligned_ge2": null, "pct_above_vwap": 0.3433734939759036, "pct_below_vwap": 0.6566265060240963, "pct_ema_bull": null, "pct_overextended": null, "pct_near_pdh": null, "pct_near_pdl": null, "pct_buy": 0.4939759036144578, "median_global_score": null, "median_expected_r": null, "median_vwap_dist_atr": -11.309531093995778, "median_realized_r": 1.5}
- losers: {"pct_london": 0.278, "pct_asia": 0.38, "pct_ny": 0.342, "pct_mtf_aligned_ge2": null, "pct_above_vwap": 0.34, "pct_below_vwap": 0.66, "pct_ema_bull": null, "pct_overextended": null, "pct_near_pdh": null, "pct_near_pdl": null, "pct_buy": 0.526, "median_global_score": null, "median_expected_r": null, "median_vwap_dist_atr": -11.796724377722544, "median_realized_r": -1.0}

## Strongest subcells (vs ~49.1% OOS WR ref / PF≥1.2 / E>0)

_None met WR≥49.1% with PF≥1.2 and E>0 in this hist BT._

## Relative-best subcells (diagnostic; may be below OOS ref)

- [VALIDATED] session+direction=london|BUY: n=111 WR=47.7% shrunk=48.1% PF=1.37 E=+0.194R DD=-10.499999999999964
- [VALIDATED] session+direction=asia|SELL: n=116 WR=45.7% shrunk=46.3% PF=1.26 E=+0.142R DD=-12.500000000000261
- [VALIDATED] session+vwap=london|below_vwap: n=165 WR=45.5% shrunk=45.9% PF=1.25 E=+0.136R DD=-12.999999999999908
- [VALIDATED] session=london: n=254 WR=45.3% shrunk=45.6% PF=1.24 E=+0.132R DD=-12.999999999999908
- [VALIDATED] session+regime=london|UNKNOWN: n=254 WR=45.3% shrunk=45.6% PF=1.24 E=+0.132R DD=-12.999999999999908
- [VALIDATED] session+mtf=london|mtf_unk: n=254 WR=45.3% shrunk=45.6% PF=1.24 E=+0.132R DD=-12.999999999999908
- [DEVELOPING] session+vwap=london|above_vwap: n=89 WR=44.9% shrunk=45.9% PF=1.22 E=+0.124R DD=-7.0
- [VALIDATED] session+direction=london|SELL: n=143 WR=43.4% shrunk=44.2% PF=1.15 E=+0.084R DD=-8.999999999999984
- [VALIDATED] direction=SELL: n=405 WR=41.5% shrunk=41.9% PF=1.06 E=+0.037R DD=-21.00000000000036
- [VALIDATED] vwap=above_vwap: n=284 WR=40.1% shrunk=40.8% PF=1.01 E=+0.004R DD=-33.499999999999986
- [VALIDATED] regime=UNKNOWN: n=832 WR=39.9% shrunk=40.1% PF=1.00 E=-0.002R DD=-36.50000000000051
- [VALIDATED] mtf=mtf_unk: n=832 WR=39.9% shrunk=40.1% PF=1.00 E=-0.002R DD=-36.50000000000051

### VALIDATED (n>=100): 25
### DEVELOPING (n>=40): 2
### EARLY (n>=20): 0 — do not control paper

Overall historical: {'n': 832, 'wr': 0.39903846153846156, 'raw_wr': 0.39903846153846156, 'shrunk_wr': 0.4014084507042254, 'pf': 0.9959999999999993, 'expectancy_r': -0.002403846153846532, 'max_dd_r': -36.50000000000051, 'category': 'VALIDATED'}

Learning store CL rows: 75