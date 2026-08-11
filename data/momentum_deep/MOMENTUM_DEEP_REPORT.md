# Momentum Deep Diagnostic Report

Generated: 2026-08-10T12:56:23.158118+00:00

**Paper agent: NOT modified.**

## Executive findings

1. Open momentum candles alone are not an edge (5m trigger WR≈32%, E≈0).
2. Parity-bias momentum on 5m×60d×8 symbols: n=4579, WR=51.7%, PF=2.14, E=+0.55R — edge is payoff asymmetry, not high WR.
3. Strongest stable filter: `|VWAP|≤0.25 ATR` → n=487, WR=61.2%, E=+0.84R (~11% retained). OOS TRAIN/VAL/FINAL = 61.5% / 62.1% / 58.7%.
4. No pooled rule with n≥30 and WR≥65%. CL + VWAP-proximal: n=121, WR=69.4%, E=+1.08R. NQ ny_open: n=71, WR=64.8%, E=+0.94R.
5. Exact Pine BUY/SELL requires HTF+VWAP+sweep/retest+confirm — that collapses 1m/7d signals to single digits.
6. Do not change active paper from this pass.

Primary book: **5m parity_bias** (15m+1h+4h+VWAP + mom confirm). Within it, 15/60/240 already agree — VWAP distance / session / OE discriminate winners.

Open **trigger** book is contrast only (too loose).

## A. Historical data inventory

See `data/momentum_deep/DATA_INVENTORY.md`.
No local OHLC warehouse. Yahoo max: 1m≈7d, 5m/15m≈60d, 1h/4h≈2y. 1m not fabricated.

## B. 1m momentum baselines

- **parity_bias**: n=895 (STRONGER SAMPLE) WR=55.0% PF=2.45 E=+0.650 DD=-7.00 t/wk=639.3
- **trigger**: n=1877 (STRONGER SAMPLE) WR=31.4% PF=0.92 E=-0.057 DD=-120.00 t/wk=1340.7

## C. 5m momentum baselines

- **parity_bias (PRIMARY)**: n=4579 (STRONGER SAMPLE) WR=51.7% PF=2.14 E=+0.549 DD=-20.00 t/wk=388.1
- **trigger (open)**: n=8231 (STRONGER SAMPLE) WR=32.2% PF=0.95 E=-0.033 DD=-338.77 t/wk=697.5

### Multi-R (5m parity_bias, target before -1R stop)

- 1.0R: WR=66.9% n=4579
- 1.25R: WR=62.2% n=4579
- 1.5R: WR=58.1% n=4579
- 2.0R: WR=51.6% n=4579

- MFE mean winners/losers: 9.61 / 2.55
- MAE mean winners/losers: 1.37 / 4.80

## D. Winner vs loser (5m parity_bias)

Wins=2366 Losses=2213
- **agree_4h**: {'winner_rate': 1.0, 'loser_rate': 1.0}
- **agree_1h**: {'winner_rate': 1.0, 'loser_rate': 1.0}
- **agree_15m**: {'winner_rate': 1.0, 'loser_rate': 1.0}
- **agree_5m**: {'winner_rate': 1.0, 'loser_rate': 1.0}
- **agree_1h_15m**: {'winner_rate': 1.0, 'loser_rate': 1.0}
- **agree_1h_15m_5m**: {'winner_rate': 1.0, 'loser_rate': 1.0}
- **agree_4h_1h**: {'winner_rate': 1.0, 'loser_rate': 1.0}
- **agree_all4**: {'winner_rate': 1.0, 'loser_rate': 1.0}
- **vwap_side_ok**: {'winner_rate': 1.0, 'loser_rate': 1.0}
- **pullback_recent**: {'winner_rate': 1.0, 'loser_rate': 1.0}
- **ema_aligned**: {'winner_rate': 0.7041420118343196, 'loser_rate': 0.7591504744690465}
- **overextended**: {'winner_rate': 0.194843617920541, 'loser_rate': 0.3000451875282422}
- **breakout**: {'winner_rate': 0.2265426880811496, 'loser_rate': 0.3271577044735653}
- **retest**: {'winner_rate': 0.037193575655114115, 'loser_rate': 0.05241753276095797}
- **rel_volume**: {'winner_mean': 1.3259034090307305, 'loser_mean': 1.4518837402390607, 'winner_median': 1.033847569575026, 'loser_median': 1.100649230198479}
- **abs_dist_vwap_atr**: {'winner_mean': 2.6364280044691597, 'loser_mean': 2.9008961230784513, 'winner_median': 1.504485160977629, 'loser_median': 1.950358211716484}
- **body_range**: {'winner_mean': 0.6478316699023424, 'loser_mean': 0.6663028624793612, 'winner_median': 0.6785776570830635, 'loser_median': 0.6932153392330384}
- **atr_pctile**: {'winner_mean': 0.5167353707739167, 'loser_mean': 0.5430339789436506, 'winner_median': 0.52, 'loser_median': 0.57}
- **htf_agree_count**: {'winner_rate': 4.0, 'loser_rate': 4.0}

## E. Strongest individual predictors (n≥30)

| conditions | n | label | WR | PF | E | t/wk | retained |
|---|---:|---|---:|---:|---:|---:|---:|
| |VWAP|<=0.25ATR | 487 | STRONGER SAMPLE | 61.2% | 3.15 | +0.836 | 43.5 | 11% |
| session=ny_open | 241 | STRONGER SAMPLE | 55.6% | 2.50 | +0.668 | 26.2 | 5% |
| not overextended | 3454 | STRONGER SAMPLE | 55.2% | 2.46 | +0.654 | 292.7 | 75% |
| |VWAP| 0.25-0.75ATR | 811 | STRONGER SAMPLE | 55.1% | 2.46 | +0.654 | 69.9 | 18% |
| session=ny_lunch | 337 | STRONGER SAMPLE | 53.7% | 2.32 | +0.611 | 37.4 | 7% |
| session=asia | 1790 | STRONGER SAMPLE | 53.6% | 2.31 | +0.609 | 151.7 | 39% |
| rel_vol<=1.15 | 2550 | STRONGER SAMPLE | 53.6% | 2.31 | +0.606 | 216.1 | 56% |
| session=ny_mid_morning | 312 | STRONGER SAMPLE | 52.2% | 2.18 | +0.563 | 32.5 | 7% |
| session=ny_afternoon | 487 | STRONGER SAMPLE | 52.2% | 2.18 | +0.565 | 50.7 | 11% |
| 4H agrees | 4579 | STRONGER SAMPLE | 51.7% | 2.14 | +0.549 | 388.1 | 100% |
| 1H agrees | 4579 | STRONGER SAMPLE | 51.7% | 2.14 | +0.549 | 388.1 | 100% |
| 15m agrees | 4579 | STRONGER SAMPLE | 51.7% | 2.14 | +0.549 | 388.1 | 100% |
| 5m agrees | 4579 | STRONGER SAMPLE | 51.7% | 2.14 | +0.549 | 388.1 | 100% |
| 1H+15m agree | 4579 | STRONGER SAMPLE | 51.7% | 2.14 | +0.549 | 388.1 | 100% |
| 1H+15m+5m agree | 4579 | STRONGER SAMPLE | 51.7% | 2.14 | +0.549 | 388.1 | 100% |
| 4H+1H agree | 4579 | STRONGER SAMPLE | 51.7% | 2.14 | +0.549 | 388.1 | 100% |
| 4H+1H+15m agree | 4579 | STRONGER SAMPLE | 51.7% | 2.14 | +0.549 | 388.1 | 100% |
| all 4 TF agree | 4579 | STRONGER SAMPLE | 51.7% | 2.14 | +0.549 | 388.1 | 100% |
| VWAP side OK | 4579 | STRONGER SAMPLE | 51.7% | 2.14 | +0.549 | 388.1 | 100% |
| pullback before | 4579 | STRONGER SAMPLE | 51.7% | 2.14 | +0.549 | 388.1 | 100% |

## F–H. Interactions (rationale-limited, depth≤4)

| conditions | n | WR | PF | E | t/wk | retained |
|---|---:|---:|---:|---:|---:|---:|
| vwap_side_ok & abs_vwap<=0.25 | 487 | 61.2% | 3.15 | +0.836 | 43.5 | 11% |
| agree_all4==1 & abs_vwap<=0.75 | 1298 | 57.4% | 2.69 | +0.722 | 110.0 | 28% |
| agree_4h_1h==1 & abs_vwap<=0.6 | 1087 | 57.1% | 2.67 | +0.714 | 92.1 | 24% |
| not overextended & agree_1h_15m & vwap_ok | 3454 | 55.2% | 2.46 | +0.654 | 292.7 | 75% |
| vwap_side_ok & abs_vwap 0.25-0.75 | 811 | 55.1% | 2.46 | +0.654 | 69.9 | 18% |
| agree_1h_15m==1 | 4579 | 51.7% | 2.14 | +0.549 | 388.1 | 100% |
| agree_1h_15m==1 & vwap_side_ok | 4579 | 51.7% | 2.14 | +0.549 | 388.1 | 100% |
| agree_1h_15m==1 & pullback_recent | 4579 | 51.7% | 2.14 | +0.549 | 388.1 | 100% |
| agree_1h_15m_5m==1 & vwap_side_ok | 4579 | 51.7% | 2.14 | +0.549 | 388.1 | 100% |
| agree_4h_1h_15m==1 & vwap_side_ok & pullback | 4579 | 51.7% | 2.14 | +0.549 | 388.1 | 100% |
| pullback_recent & body_range>0.5 | 3519 | 50.9% | 2.07 | +0.525 | 298.2 | 77% |
| agree_15m_5m==1 & rel_vol>1.15 | 2029 | 49.2% | 1.94 | +0.477 | 171.9 | 44% |
| agree_1h==1 & ema_aligned & rel_vol>1.15 | 1362 | 47.0% | 1.77 | +0.410 | 115.4 | 30% |
| retest==1 & agree_1h_15m | 204 | 43.1% | 1.52 | +0.294 | 23.2 | 4% |
| breakout==1 & agree_1h_15m | 1260 | 42.5% | 1.48 | +0.276 | 106.8 | 28% |

## I. Conditional WR ≥ 65% (n≥30)

_None on 5m parity_bias with n≥30._

## I0. Conditional WR ≥ 60% (n≥30) — ranked

- |VWAP|<=0.25ATR: n=487 (STRONGER SAMPLE) WR=61.2% PF=3.15 E=+0.836 DD=-6.00 t/wk=43.5 retained=11%
- vwap_side_ok & abs_vwap<=0.25: n=487 (STRONGER SAMPLE) WR=61.2% PF=3.15 E=+0.836 DD=-6.00 t/wk=43.5 retained=11%

## J. Conditional WR ≥ 70% (n≥30)

_None on 5m parity_bias with n≥30._

## K. WR / frequency Pareto frontier

| conditions | n | WR | E | t/wk | retained |
|---|---:|---:|---:|---:|---:|
| |VWAP|<=0.25ATR | 487 | 61.2% | +0.836 | 43.5 | 11% |
| vwap_side_ok & abs_vwap<=0.25 | 487 | 61.2% | +0.836 | 43.5 | 11% |
| agree_all4==1 & abs_vwap<=0.75 | 1298 | 57.4% | +0.722 | 110.0 | 28% |
| not overextended | 3454 | 55.2% | +0.654 | 292.7 | 75% |
| not overextended & agree_1h_15m & vwap_ok | 3454 | 55.2% | +0.654 | 292.7 | 75% |
| BASE | 4579 | 51.7% | +0.549 | 388.1 | 100% |
| BASE | 4579 | 51.7% | +0.549 | 388.1 | 100% |
| 4H agrees | 4579 | 51.7% | +0.549 | 388.1 | 100% |
| 1H agrees | 4579 | 51.7% | +0.549 | 388.1 | 100% |
| 15m agrees | 4579 | 51.7% | +0.549 | 388.1 | 100% |
| 5m agrees | 4579 | 51.7% | +0.549 | 388.1 | 100% |
| 1H+15m agree | 4579 | 51.7% | +0.549 | 388.1 | 100% |
| 1H+15m+5m agree | 4579 | 51.7% | +0.549 | 388.1 | 100% |
| 4H+1H agree | 4579 | 51.7% | +0.549 | 388.1 | 100% |
| 4H+1H+15m agree | 4579 | 51.7% | +0.549 | 388.1 | 100% |
| all 4 TF agree | 4579 | 51.7% | +0.549 | 388.1 | 100% |
| VWAP side OK | 4579 | 51.7% | +0.549 | 388.1 | 100% |
| pullback before | 4579 | 51.7% | +0.549 | 388.1 | 100% |
| agree_1h_15m==1 | 4579 | 51.7% | +0.549 | 388.1 | 100% |
| agree_1h_15m==1 & vwap_side_ok | 4579 | 51.7% | +0.549 | 388.1 | 100% |

## L. NQ specialization

Baseline: n=1205 (STRONGER SAMPLE) WR=52.0% PF=2.17 E=+0.561 DD=-20.00 t/wk=102.1
- session=ny_open: n=71 (PROMISING / NOT CONFIRMED) WR=64.8% PF=3.68 E=+0.944 DD=-2.00 t/wk=9.9 retained=6%
- session=asia: n=473 (STRONGER SAMPLE) WR=55.8% PF=2.53 E=+0.674 DD=-11.00 t/wk=40.1 retained=39%
- |VWAP| 0.25-0.75ATR: n=185 (STRONGER SAMPLE) WR=55.7% PF=2.51 E=+0.670 DD=-5.00 t/wk=18.1 retained=15%
- vwap_side_ok & abs_vwap 0.25-0.75: n=185 (STRONGER SAMPLE) WR=55.7% PF=2.51 E=+0.670 DD=-5.00 t/wk=18.1 retained=15%
- agree_all4==1 & abs_vwap<=0.75: n=317 (STRONGER SAMPLE) WR=55.5% PF=2.50 E=+0.666 DD=-6.00 t/wk=27.3 retained=26%
- |VWAP|<=0.25ATR: n=132 (STRONGER SAMPLE) WR=55.3% PF=2.47 E=+0.659 DD=-5.00 t/wk=13.8 retained=11%
- vwap_side_ok & abs_vwap<=0.25: n=132 (STRONGER SAMPLE) WR=55.3% PF=2.47 E=+0.659 DD=-5.00 t/wk=13.8 retained=11%
- not overextended: n=923 (STRONGER SAMPLE) WR=55.3% PF=2.47 E=+0.658 DD=-16.00 t/wk=78.2 retained=77%
- not overextended & agree_1h_15m & vwap_ok: n=923 (STRONGER SAMPLE) WR=55.3% PF=2.47 E=+0.658 DD=-16.00 t/wk=78.2 retained=77%
- agree_4h_1h==1 & abs_vwap<=0.6: n=269 (STRONGER SAMPLE) WR=55.0% PF=2.45 E=+0.651 DD=-6.00 t/wk=24.0 retained=22%

## M. ES specialization

Baseline: n=1173 (STRONGER SAMPLE) WR=50.9% PF=2.07 E=+0.526 DD=-10.00 t/wk=99.4
- |VWAP| 0.25-0.75ATR: n=207 (STRONGER SAMPLE) WR=58.5% PF=2.81 E=+0.754 DD=-4.00 t/wk=19.5 retained=18%
- vwap_side_ok & abs_vwap 0.25-0.75: n=207 (STRONGER SAMPLE) WR=58.5% PF=2.81 E=+0.754 DD=-4.00 t/wk=19.5 retained=18%
- agree_all4==1 & abs_vwap<=0.75: n=320 (STRONGER SAMPLE) WR=58.4% PF=2.81 E=+0.753 DD=-6.00 t/wk=28.1 retained=27%
- |VWAP|<=0.25ATR: n=113 (STRONGER SAMPLE) WR=58.4% PF=2.81 E=+0.752 DD=-5.00 t/wk=13.5 retained=10%
- vwap_side_ok & abs_vwap<=0.25: n=113 (STRONGER SAMPLE) WR=58.4% PF=2.81 E=+0.752 DD=-5.00 t/wk=13.5 retained=10%
- session=ny_lunch: n=91 (PROMISING / NOT CONFIRMED) WR=58.2% PF=2.79 E=+0.747 DD=-3.00 t/wk=13.8 retained=8%
- agree_4h_1h==1 & abs_vwap<=0.6: n=267 (STRONGER SAMPLE) WR=57.7% PF=2.73 E=+0.730 DD=-6.00 t/wk=24.3 retained=23%
- session=ny_mid_morning: n=92 (PROMISING / NOT CONFIRMED) WR=57.6% PF=2.68 E=+0.714 DD=-6.00 t/wk=11.2 retained=8%
- not overextended: n=889 (STRONGER SAMPLE) WR=54.9% PF=2.43 E=+0.647 DD=-7.00 t/wk=75.3 retained=76%
- not overextended & agree_1h_15m & vwap_ok: n=889 (STRONGER SAMPLE) WR=54.9% PF=2.43 E=+0.647 DD=-7.00 t/wk=75.3 retained=76%

## N. GC specialization

Baseline: n=1098 (STRONGER SAMPLE) WR=50.9% PF=2.07 E=+0.524 DD=-12.00 t/wk=93.1
- |VWAP|<=0.25ATR: n=121 (STRONGER SAMPLE) WR=62.0% PF=3.26 E=+0.860 DD=-6.00 t/wk=13.8 retained=11%
- vwap_side_ok & abs_vwap<=0.25: n=121 (STRONGER SAMPLE) WR=62.0% PF=3.26 E=+0.860 DD=-6.00 t/wk=13.8 retained=11%
- agree_all4==1 & abs_vwap<=0.75: n=330 (STRONGER SAMPLE) WR=58.5% PF=2.82 E=+0.755 DD=-8.00 t/wk=28.9 retained=30%
- session=ny_afternoon: n=120 (STRONGER SAMPLE) WR=57.5% PF=2.71 E=+0.725 DD=-6.00 t/wk=15.8 retained=11%
- |VWAP| 0.25-0.75ATR: n=209 (STRONGER SAMPLE) WR=56.5% PF=2.59 E=+0.694 DD=-7.00 t/wk=19.4 retained=19%
- vwap_side_ok & abs_vwap 0.25-0.75: n=209 (STRONGER SAMPLE) WR=56.5% PF=2.59 E=+0.694 DD=-7.00 t/wk=19.4 retained=19%
- agree_4h_1h==1 & abs_vwap<=0.6: n=275 (STRONGER SAMPLE) WR=56.4% PF=2.58 E=+0.691 DD=-8.00 t/wk=24.1 retained=25%
- session=ny_mid_morning: n=63 (PROMISING / NOT CONFIRMED) WR=55.6% PF=2.50 E=+0.667 DD=-5.00 t/wk=9.5 retained=6%
- not overextended: n=807 (STRONGER SAMPLE) WR=54.6% PF=2.40 E=+0.635 DD=-8.00 t/wk=68.4 retained=73%
- not overextended & agree_1h_15m & vwap_ok: n=807 (STRONGER SAMPLE) WR=54.6% PF=2.40 E=+0.635 DD=-8.00 t/wk=68.4 retained=73%

## O. CL specialization

Baseline: n=1103 (STRONGER SAMPLE) WR=52.9% PF=2.24 E=+0.586 DD=-10.00 t/wk=93.5
- |VWAP|<=0.25ATR: n=121 (STRONGER SAMPLE) WR=69.4% PF=4.54 E=+1.083 DD=-5.00 t/wk=13.8 retained=11%
- vwap_side_ok & abs_vwap<=0.25: n=121 (STRONGER SAMPLE) WR=69.4% PF=4.54 E=+1.083 DD=-5.00 t/wk=13.8 retained=11%
- agree_4h_1h==1 & abs_vwap<=0.6: n=276 (STRONGER SAMPLE) WR=59.4% PF=2.93 E=+0.783 DD=-6.00 t/wk=24.6 retained=25%
- agree_all4==1 & abs_vwap<=0.75: n=331 (STRONGER SAMPLE) WR=57.1% PF=2.66 E=+0.713 DD=-7.00 t/wk=29.6 retained=30%
- not overextended: n=835 (STRONGER SAMPLE) WR=55.8% PF=2.53 E=+0.674 DD=-8.00 t/wk=70.8 retained=76%
- not overextended & agree_1h_15m & vwap_ok: n=835 (STRONGER SAMPLE) WR=55.8% PF=2.53 E=+0.674 DD=-8.00 t/wk=70.8 retained=76%
- rel_vol<=1.15: n=570 (STRONGER SAMPLE) WR=55.8% PF=2.52 E=+0.674 DD=-10.00 t/wk=48.3 retained=52%
- session=asia: n=426 (STRONGER SAMPLE) WR=54.9% PF=2.44 E=+0.648 DD=-6.00 t/wk=36.1 retained=39%
- session=ny_mid_morning: n=71 (PROMISING / NOT CONFIRMED) WR=53.5% PF=2.30 E=+0.606 DD=-3.00 t/wk=11.1 retained=6%
- session=ny_open: n=49 (PROMISING / NOT CONFIRMED) WR=53.1% PF=2.26 E=+0.592 DD=-4.00 t/wk=9.4 retained=4%

## P. Session specialization

- **asia**: n=1790 (STRONGER SAMPLE) WR=53.6% PF=2.31 E=+0.609 DD=-11.00 t/wk=151.7
- **london**: n=1111 (STRONGER SAMPLE) WR=46.7% PF=1.75 E=+0.401 DD=-18.00 t/wk=113.4
- **ny_afternoon**: n=487 (STRONGER SAMPLE) WR=52.2% PF=2.18 E=+0.565 DD=-7.00 t/wk=50.7
- **ny_lunch**: n=337 (STRONGER SAMPLE) WR=53.7% PF=2.32 E=+0.611 DD=-9.00 t/wk=37.4
- **ny_mid_morning**: n=312 (STRONGER SAMPLE) WR=52.2% PF=2.18 E=+0.563 DD=-6.00 t/wk=32.5
- **ny_open**: n=241 (STRONGER SAMPLE) WR=55.6% PF=2.50 E=+0.668 DD=-6.00 t/wk=26.2
- **ny_premarket**: n=301 (STRONGER SAMPLE) WR=51.5% PF=2.10 E=+0.534 DD=-6.00 t/wk=30.7

## Q. Shallow tree (depth≤3)

Train accuracy: 0.5754531557108539
Importances: {'agree_4h': 0.0, 'agree_1h': 0.0, 'agree_15m': 0.0, 'agree_5m': 0.0, 'agree_1h_15m': 0.0, 'vwap_side_ok': 0.0, 'abs_dist_vwap_atr': 0.38488856024940743, 'pullback_recent': 0.0, 'rel_volume': 0.0, 'ema_aligned': 0.0, 'overextended': 0.45757888790126405, 'body_range': 0.06142806710627769, 'htf_agree_count': 0.0, 'breakout': 0.09610448474305072}
```
|--- overextended <= 0.50
|   |--- abs_dist_vwap_atr <= 0.42
|   |   |--- body_range <= 0.38
|   |   |   |--- class: 1
|   |   |--- body_range >  0.38
|   |   |   |--- class: 1
|   |--- abs_dist_vwap_atr >  0.42
|   |   |--- abs_dist_vwap_atr <= 0.50
|   |   |   |--- class: 0
|   |   |--- abs_dist_vwap_atr >  0.50
|   |   |   |--- class: 1
|--- overextended >  0.50
|   |--- abs_dist_vwap_atr <= 0.91
|   |   |--- breakout <= 0.50
|   |   |   |--- class: 1
|   |   |--- breakout >  0.50
|   |   |   |--- class: 0
|   |--- abs_dist_vwap_atr >  0.91
|   |   |--- abs_dist_vwap_atr <= 10.41
|   |   |   |--- class: 0
|   |   |--- abs_dist_vwap_atr >  10.41
|   |   |   |--- class: 1

```

## R. Untouched OOS (freeze rules from TRAIN)

### |VWAP|<=0.25ATR
- TRAIN: n=317 (STRONGER SAMPLE) WR=61.5% PF=3.20 E=+0.845 DD=-7.00 t/wk=44.0 retained=12%
- VALIDATION: n=95 (PROMISING / NOT CONFIRMED) WR=62.1% PF=3.28 E=+0.863 DD=-6.00 t/wk=43.2 retained=10%
- FINAL: n=75 (PROMISING / NOT CONFIRMED) WR=58.7% PF=2.84 E=+0.760 DD=-6.00 t/wk=37.5 retained=8%
- overfit_flag=False stable=True
### vwap_side_ok & abs_vwap<=0.25
- TRAIN: n=317 (STRONGER SAMPLE) WR=61.5% PF=3.20 E=+0.845 DD=-7.00 t/wk=44.0 retained=12%
- VALIDATION: n=95 (PROMISING / NOT CONFIRMED) WR=62.1% PF=3.28 E=+0.863 DD=-6.00 t/wk=43.2 retained=10%
- FINAL: n=75 (PROMISING / NOT CONFIRMED) WR=58.7% PF=2.84 E=+0.760 DD=-6.00 t/wk=37.5 retained=8%
- overfit_flag=False stable=True

## S. Exact Pine BUY/SELL Boolean map

- BUY NOW = `longBias AND longSetup AND (close > open) AND (close > high[1])`
- SELL NOW = `shortBias AND shortSetup AND (close < open) AND (close < low[1])`
- longBias = `allBullNow AND (useVWAP ? close > vwap : TRUE)  where allBullNow = (s15==1 AND s1h==1 AND s4h==1)`
- longSetup = `longSweepActive AND longRetestZone AND close > pdl`
- mandatory: all three HTF bullish (15/60/240)
- mandatory: VWAP filter when useVWAP=true (default)
- mandatory: PDL sweep then retest zone active
- mandatory: close > pdl
- mandatory: bullish confirmation candle vs prior high

## T. Why exact indicator_parity n≈5 on 1m/7d

{
  "symbol": "NQ",
  "interval": "1m",
  "period": "7d",
  "bars_total": 7365,
  "candidate_bars_after_warmup": 7285,
  "long_all3_htf": 2005,
  "long_htf_and_vwap": 1738,
  "long_parity_momentum_bias_trigger": 590,
  "long_pullback_entry_bars": 1,
  "final_BUY_NOW": 0,
  "final_SELL_NOW": 2,
  "final_signals_either": 2,
  "why_n_collapsed": "BUY NOW requires ALL of: allBullNow(15+1h+4h) AND VWAP AND longSweepActive+retestZone+close>pdl AND bullish break of prior high. On ~7d of 1m data that intersection is rare (often single-digit per symbol)."
}
BUY NOW requires ALL of: allBullNow(15+1h+4h) AND VWAP AND longSweepActive+retestZone+close>pdl AND bullish break of prior high. On ~7d of 1m data that intersection is rare (often single-digit per symbol).

## U. Paper strategy change?

{
  "change_active_paper": false,
  "reason": "Diagnostic pass only; require stable OOS before any paper change.",
  "interesting": true,
  "stable_rules": [
    "|VWAP|<=0.25ATR",
    "vwap_side_ok & abs_vwap<=0.25"
  ]
}
