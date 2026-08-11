# Session Open Momentum + Strategy Cull

Generated: 2026-08-11T18:05:52.451328+00:00

**Data caveat:** Yahoo 5m ~60d only — NOT Databento. Results are directional research, not live-proof. Prefer Databento for multi-month CME bars when ready.

## NQ NY-open specialist (existing)
- verdict: **KEEP_RESEARCH** (DEVELOPING)
- n=74 WR=0.6486486486486487 PF=3.6923076923076925 E=0.9459459459459459 DD=-2.0 t/wk=9.736842105263158

## Session-open cells (Asia / London / NY open)

| Cell | n | WR | PF | E[R] | DD | Verdict |
|---|---:|---:|---:|---:|---:|---|
| NQ_FAMILY|asia|parity_mom | 485 | 0.5628865979381443 | 2.5754716981132075 | 0.688659793814433 | -11.0 | **KEEP_RESEARCH** |
| ES_FAMILY|asia|parity_mom | 454 | 0.5418502202643172 | 2.3653846153846154 | 0.6255506607929515 | -8.0 | **WATCH** |
| CL_FAMILY|asia|parity_mom | 428 | 0.5467289719626168 | 2.4123711340206184 | 0.6401869158878505 | -6.0 | **WATCH** |
| NQ_FAMILY|london|parity_mom | 280 | 0.4785714285714286 | 1.8356164383561644 | 0.4357142857142857 | -18.0 | **X_OUT** |
| ES_FAMILY|london|parity_mom | 289 | 0.4290657439446367 | 1.503030303030303 | 0.28719723183391005 | -14.0 | **X_OUT** |
| CL_FAMILY|london|parity_mom | 281 | 0.5231316725978647 | 2.1940298507462686 | 0.5693950177935944 | -7.0 | **WATCH** |
| NQ_FAMILY|ny_open|parity_mom | 74 | 0.6486486486486487 | 3.6923076923076925 | 0.9459459459459459 | -2.0 | **KEEP_RESEARCH** |
| ES_FAMILY|ny_open|parity_mom | 76 | 0.5526315789473685 | 2.4705882352941178 | 0.6578947368421053 | -6.0 | **KEEP_RESEARCH** |
| CL_FAMILY|ny_open|parity_mom | 51 | 0.5490196078431373 | 2.4347826086956523 | 0.6470588235294118 | -4.0 | **WATCH** |

## Learning-store strategy cull (paper/shadow outcomes)

- **ANECDOTAL_WATCH** `vwap_mss`: n=11 WR=54.5% shrunk=51.6% PF=2.04 E=+0.215R
- **WATCH** `trend_continuation`: n=89 WR=47.2% shrunk=47.7% PF=1.44 E=+0.125R
- **WATCH** `opening_range`: n=27 WR=40.7% shrunk=44.7% PF=1.22 E=+0.105R
- **WATCH** `vwap_acceptance`: n=56 WR=39.3% shrunk=42.1% PF=1.15 E=+0.073R
- **WATCH** `vwap_reclaim`: n=41 WR=31.7% shrunk=37.7% PF=1.04 E=+0.027R
- **WATCH** `ema_pullback`: n=376 WR=37.8% shrunk=38.4% PF=0.92 E=-0.034R
- **ANECDOTAL_WATCH** `liquidity_sweep`: n=15 WR=26.7% shrunk=40.0% PF=0.49 E=-0.089R
- **X_OUT** `trend_pullback`: n=122 WR=30.3% shrunk=33.1% PF=0.71 E=-0.188R
- **X_OUT** `unknown`: n=58 WR=5.2% shrunk=16.7% PF=0.31 E=-0.209R
- **ANECDOTAL_WATCH** `liquidity_reversal`: n=19 WR=21.1% shrunk=35.9% PF=0.71 E=-0.227R
- **X_OUT** `breakout_retest`: n=62 WR=29.0% shrunk=34.1% PF=0.62 E=-0.254R

## X_OUT (stop spending research time)

- NQ_FAMILY|london|parity_mom
- ES_FAMILY|london|parity_mom
- trend_pullback
- unknown
- breakout_retest

## KEEP_RESEARCH

- NQ_FAMILY|asia|parity_mom
- NQ_FAMILY|ny_open|parity_mom
- ES_FAMILY|ny_open|parity_mom