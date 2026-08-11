# Trade Quality Learning Report

Generated: 2026-08-10T12:29:07.665909+00:00

**Usable rows:** 109
**Date range:** 2026-08-06 20:30:04.889042+00:00 → 2026-08-07 13:21:55.882791+00:00
**Sources:** {'paper': 26, 'shadow': 83}
**Duplicates removed:** 0
**Legacy excluded:** 8

## Class balance
{'win_rate': 0.1926605504587156, 'loss_rate': 0.8073394495412844, 'n': 109.0}

## Baseline / nonlinear (val)

- logistic: val brier=0.2552885162526659 auc=0.5729166666666667
- logistic_l2: val brier=0.2453920067226317 auc=0.5416666666666666
- shallow_tree: val brier=0.2425 auc=0.640625
- random_forest: val brier=0.19354314381908802 auc=0.6458333333333333
- gradient_boosting: val brier=0.21177981567848694 auc=0.703125

## FINAL holdout calibration: calibrated=False brier=0.09204129790050081

### Reliability bins
- {'bin': '50-55', 'n': 0, 'pred_avg': None, 'actual_wr': None}
- {'bin': '55-60', 'n': 0, 'pred_avg': None, 'actual_wr': None}
- {'bin': '60-65', 'n': 0, 'pred_avg': None, 'actual_wr': None}
- {'bin': '65-70', 'n': 0, 'pred_avg': None, 'actual_wr': None}
- {'bin': '70-75', 'n': 0, 'pred_avg': None, 'actual_wr': None}
- {'bin': '75-80', 'n': 0, 'pred_avg': None, 'actual_wr': None}
- {'bin': '80+', 'n': 0, 'pred_avg': None, 'actual_wr': None}

## Top winner features
- momentum_aligned=1: +18.2pp (n=24, WR=37.5%)
- body_atr in (0.612, 4.755]: +15.5pp (n=23, WR=34.8%)
- stop_dist_atr in (0.242, 0.743]: +15.5pp (n=23, WR=34.8%)
- atr_pctile in (0.775, 0.985]: +15.5pp (n=23, WR=34.8%)
- price_vs_ema20_atr in (-0.306, 0.517]: +12.6pp (n=22, WR=31.8%)
- price_vs_ema20_atr in (0.517, 0.974]: +12.6pp (n=22, WR=31.8%)
- above_vwap=1: +12.3pp (n=57, WR=31.6%)
- below_vwap=0: +12.3pp (n=57, WR=31.6%)
- near_pdh=1: +11.5pp (n=13, WR=30.8%)
- target_r in (1.5, 1.778]: +11.5pp (n=13, WR=30.8%)

## Top loser features
- ema_bear=1: -10.9pp (n=24, WR=8.3%)
- vwap_dist_atr in (-5.882000000000001, -1.286]: -10.9pp (n=24, WR=8.3%)
- price_vs_ema20_atr in (-2.1759999999999997, -0.306]: -10.6pp (n=23, WR=8.7%)
- price_vs_ema50_atr in (-2.959, -0.569]: -10.6pp (n=23, WR=8.7%)
- atr_pctile in (0.139, 0.346]: -10.6pp (n=23, WR=8.7%)
- above_vwap=0: -10.2pp (n=33, WR=9.1%)
- below_vwap=1: -10.2pp (n=33, WR=9.1%)
- target_r in (1.778, 3.865]: -10.2pp (n=22, WR=9.1%)
- ema20_above_ema50=0: -9.6pp (n=31, WR=9.7%)
- stop_dist_atr in (1.127, 1.582]: -5.6pp (n=22, WR=13.6%)

## Tier calibration
{'tiers': {'A': {'n': 15, 'wr': 0.06666666666666667, 'pf': 0.22749235113612276, 'expectancy_r': -0.2630064154718003}, 'A+': {'n': 3, 'wr': 0.3333333333333333, 'pf': 10.378430983647014, 'expectancy_r': 0.3489763622035505}, 'B': {'n': 81, 'wr': 0.20987654320987653, 'pf': 0.48323397913561855, 'expectancy_r': -0.3595925925925925}}, 'flag': None}

## Router v1 vs v2 (FINAL selection proxy)
- v1: {'n': 8, 'wr': 0.0, 'expectancy_r': -0.36946704299211175, 'pf': 0.0, 'trades_per_week': None}
- v2 balanced: {'n': 8, 'wr': 0.125, 'expectancy_r': -0.5248748309846767, 'pf': 0.2629454722721629, 'trades_per_week': None}
- v2 high_confidence: {'n': 8, 'wr': 0.125, 'expectancy_r': -0.5248748309846767, 'pf': 0.2629454722721629, 'trades_per_week': None}
- **Deploy router_v2?** False — no material OOS improvement and/or calibration insufficient — keep v1

## High-accuracy cells (≥100)
[]

## Promising (≥40)
[]

## Missed-move archetypes
[{'symbol': 'CL', 'missed_sample': 80, 'clusters': {'mtf_trend_compression': 77, 'vwap_hold_pullback': 0, 'sweep_like_wick': 0, 'other': 3}}, {'symbol': 'ES', 'missed_sample': 80, 'clusters': {'mtf_trend_compression': 78, 'vwap_hold_pullback': 0, 'sweep_like_wick': 0, 'other': 2}}, {'symbol': 'GC', 'missed_sample': 80, 'clusters': {'mtf_trend_compression': 79, 'vwap_hold_pullback': 1, 'sweep_like_wick': 0, 'other': 0}}]

## Discovery hypotheses
[{'name': 'discovery_momentum_aligned=1', 'mode': 'SHADOW_ONLY', 'rule': 'momentum_aligned=1', 'evidence_lift_pp': 18.23394495412844, 'n': 24, 'status': 'HYPOTHESIS'}, {'name': 'discovery_body_atr_in_(0.612,_4.755]', 'mode': 'SHADOW_ONLY', 'rule': 'body_atr in (0.612, 4.755]', 'evidence_lift_pp': 15.516553649780612, 'n': 23, 'status': 'HYPOTHESIS'}, {'name': 'discovery_stop_dist_atr_in_(0.242,_0.743]', 'mode': 'SHADOW_ONLY', 'rule': 'stop_dist_atr in (0.242, 0.743]', 'evidence_lift_pp': 15.516553649780612, 'n': 23, 'status': 'HYPOTHESIS'}, {'name': 'discovery_atr_pctile_in_(0.775,_0.985]', 'mode': 'SHADOW_ONLY', 'rule': 'atr_pctile in (0.775, 0.985]', 'evidence_lift_pp': 15.516553649780612, 'n': 23, 'status': 'HYPOTHESIS'}, {'name': 'discovery_price_vs_ema20_atr_in_(-0.306,_0.517]', 'mode': 'SHADOW_ONLY', 'rule': 'price_vs_ema20_atr in (-0.306, 0.517]', 'evidence_lift_pp': 12.552126772310256, 'n': 22, 'status': 'HYPOTHESIS'}, {'name': "discovery_strategy×symbol_('ema_pullback', 'MNQ')", 'mode': 'SHADOW_ONLY', 'rule': "{'interaction': 'strategy×symbol', 'values': ('ema_pullback', 'MNQ'), 'n': 19, 'wr': 0.42105263157894735, 'lift_pp': 22.839208112023172, 'expectancy_r': -0.058125162106650585}", 'evidence_lift_pp': 22.839208112023172, 'n': 19, 'status': 'HYPOTHESIS'}, {'name': 'discovery_mtf_aligned×above_vwap_(2.0, 1.0)', 'mode': 'SHADOW_ONLY', 'rule': "{'interaction': 'mtf_aligned×above_vwap', 'values': (2.0, 1.0), 'n': 22, 'wr': 0.36363636363636365, 'lift_pp': 17.097581317764803, 'expectancy_r': 0.3377355349506812}", 'evidence_lift_pp': 17.097581317764803, 'n': 22, 'status': 'HYPOTHESIS'}, {'name': 'discovery_mtf_aligned×above_vwap_(1.0, 1.0)', 'mode': 'SHADOW_ONLY', 'rule': "{'interaction': 'mtf_aligned×above_vwap', 'values': (1.0, 1.0), 'n': 17, 'wr': 0.35294117647058826, 'lift_pp': 16.028062601187266, 'expectancy_r': -0.10713094756953316}", 'evidence_lift_pp': 16.028062601187266, 'n': 17, 'status': 'HYPOTHESIS'}, {'name': "discovery_near_pdl×session_(0.0, 'ny')", 'mode': 'SHADOW_ONLY', 'rule': "{'interaction': 'near_pdl×session', 'values': (0.0, 'ny'), 'n': 64, 'wr': 0.265625, 'lift_pp': 7.2964449541284395, 'expectancy_r': -0.19303080555434812}", 'evidence_lift_pp': 7.2964449541284395, 'n': 64, 'status': 'HYPOTHESIS'}, {'name': "discovery_momentum_aligned×regime_(0.0, 'TREND_UP')", 'mode': 'SHADOW_ONLY', 'rule': "{'interaction': 'momentum_aligned×regime', 'values': (0.0, 'TREND_UP'), 'n': 27, 'wr': 0.25925925925925924, 'lift_pp': 6.659870880054363, 'expectancy_r': -0.32659254251397835}", 'evidence_lift_pp': 6.659870880054363, 'n': 27, 'status': 'HYPOTHESIS'}]