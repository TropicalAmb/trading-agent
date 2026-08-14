# Dual-Source Research Hardening (Databento + Yahoo)

**Generated:** 2026-08-13T19:54:37.523069+00:00

## Data
- Databento: local 1m caches NQ/ES/CL/GC (~180d), resampled to 5m/1h. **No new API spend.**
- Yahoo: 5m/60d + 1h/365d free download.
- Databento spend this session (cache pull): ~$25.59
- Spend lock: **no further Databento downloads without user OK**

## S&D / Price Action verdicts
- `yahoo_5m_60d`: **FAIL**
- `databento_5m_180d`: **WATCH**
- `databento_5m_yahoo_overlap`: **WATCH**

## Full registry (all strategy families)
- `yahoo`: selected=17 / 93 hard-gate finalists=0
  - vwap_mss `vwap_mss_R2.0` final n=66 WR=0.5758 E=0.6731 gates=False
  - vwap_mss `vwap_mss_R1.5` final n=66 WR=0.5758 E=0.4105 gates=False
  - vwap_mss `vwap_mss_R1.0` final n=66 WR=0.6364 E=0.2438 gates=False
  - trend_continuation `trend_cont_R1.0` final n=58 WR=0.6207 E=0.2129 gates=False
  - opening_range `orb5_first_break_vwap1_R1.0` final n=6 WR=0.5 E=0.0839 gates=False
  - liquidity_sweep_mss `liq_sweep_MSS_R1.5` final n=24 WR=0.5833 E=0.0821 gates=False
  - liquidity_sweep_mss `liq_sweep_MSS_R2.0` final n=24 WR=0.5833 E=0.0783 gates=False
  - opening_range `orb15_first_break_vwap1_R1.5` final n=8 WR=0.375 E=0.0354 gates=False
  - orb_failed `orb5_failed_R1.5` final n=26 WR=0.4231 E=-0.0567 gates=False
  - opening_range `orb5_first_break_vwap1_R1.5` final n=6 WR=0.3333 E=-0.0828 gates=False
  - momentum `momentum_R1.0` final n=134 WR=0.4552 E=-0.116 gates=False
  - breakout_retest `breakout_retest_R1.0` final n=85 WR=0.4235 E=-0.1576 gates=False
- `databento_180d`: selected=6 / 93 hard-gate finalists=0
  - vwap_rejection `vwap_reject_R1.5` final n=86 WR=0.7674 E=0.8385 gates=False
  - vwap_rejection `vwap_reject_R2.0` final n=86 WR=0.6512 E=0.8103 gates=False
  - vwap_rejection `vwap_reject_R1.0` final n=86 WR=0.814 E=0.605 gates=False
  - supply_demand `supply_demand_R2.0` final n=15 WR=0.4667 E=0.3526 gates=False
  - supply_demand `supply_demand_R1.0` final n=15 WR=0.6 E=0.2938 gates=False
  - supply_demand `supply_demand_R1.5` final n=15 WR=0.4667 E=0.1859 gates=False
- `databento_yahoo_overlap`: selected=3 / 93 hard-gate finalists=0
  - vwap_rejection `vwap_reject_R2.0` final n=36 WR=0.6389 E=0.7483 gates=False
  - vwap_rejection `vwap_reject_R1.5` final n=36 WR=0.7222 E=0.6949 gates=False
  - vwap_rejection `vwap_reject_R1.0` final n=36 WR=0.7778 E=0.5154 gates=False

## Reading the dual test
- **Agree FAIL on Yahoo + Databento** → do not paper that family.
- **Ready on both** → candidate for paper specialist wiring.
- **Ready on one only** → WATCH; do not promote from single-source luck.
- Paper remains `router_v1_specialists_only` until dual-ready exists.
