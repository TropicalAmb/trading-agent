# Router specialist comparison (OOS)

Generated: 2026-08-10T12:09:51.391028+00:00

## Strategy OOS (FINAL holdout)

| name | kind | symbol | n | WR | PF | E[R] | max_dd_r |
|---|---|---|---|---|---|---|---|
| complex_ema_pullback | existing | NQ | 35 | 31.4% | 0.68 | -0.220 | -9.16 |
| complex_breakout_retest | existing | NQ | 50 | 40.0% | 1.02 | +0.011 | -13.78 |
| complex_vwap_reclaim_hc | existing | NQ | 113 | 38.9% | 0.96 | -0.026 | -14.36 |
| simple_trend_pullback | simple | NQ | 134 | 38.1% | 0.92 | -0.049 | -14.00 |
| simple_liquidity_reversal | simple | NQ | 129 | 34.1% | 0.78 | -0.147 | -26.50 |
| simple_vwap_reclaim | simple | NQ | 113 | 38.9% | 0.96 | -0.026 | -14.36 |
| complex_ema_pullback | existing | ES | 29 | 41.4% | 1.00 | +0.001 | -6.17 |
| complex_breakout_retest | existing | ES | 51 | 39.2% | 0.87 | -0.080 | -9.50 |
| complex_vwap_reclaim_hc | existing | ES | 113 | 35.4% | 0.76 | -0.158 | -26.83 |
| simple_trend_pullback | simple | ES | 140 | 42.9% | 1.12 | +0.071 | -11.50 |
| simple_liquidity_reversal | simple | ES | 119 | 37.0% | 0.88 | -0.076 | -20.00 |
| simple_vwap_reclaim | simple | ES | 113 | 35.4% | 0.76 | -0.158 | -26.83 |
| complex_ema_pullback | existing | GC | 41 | 29.3% | 0.63 | -0.258 | -12.54 |
| complex_breakout_retest | existing | GC | 39 | 38.5% | 0.87 | -0.083 | -10.15 |
| complex_vwap_reclaim_hc | existing | GC | 83 | 44.6% | 1.15 | +0.083 | -7.57 |
| simple_trend_pullback | simple | GC | 144 | 32.6% | 0.73 | -0.184 | -39.00 |
| simple_liquidity_reversal | simple | GC | 111 | 36.9% | 0.88 | -0.077 | -12.00 |
| simple_vwap_reclaim | simple | GC | 83 | 44.6% | 1.15 | +0.083 | -7.57 |
| complex_ema_pullback | existing | CL | 42 | 45.2% | 1.20 | +0.108 | -5.25 |
| complex_breakout_retest | existing | CL | 47 | 46.8% | 1.34 | +0.174 | -5.35 |
| complex_vwap_reclaim_hc | existing | CL | 91 | 44.0% | 1.11 | +0.065 | -8.84 |
| simple_trend_pullback | simple | CL | 144 | 39.6% | 0.98 | -0.010 | -11.50 |
| simple_liquidity_reversal | simple | CL | 108 | 49.1% | 1.45 | +0.227 | -5.50 |
| simple_vwap_reclaim | simple | CL | 91 | 44.0% | 1.11 | +0.065 | -8.84 |
| complex_ema_pullback | existing | MNQ | 35 | 31.4% | 0.68 | -0.220 | -9.16 |
| complex_breakout_retest | existing | MNQ | 51 | 39.2% | 1.00 | -0.001 | -12.29 |
| complex_vwap_reclaim_hc | existing | MNQ | 106 | 35.9% | 0.84 | -0.103 | -18.16 |
| simple_trend_pullback | simple | MNQ | 137 | 38.7% | 0.95 | -0.033 | -15.00 |
| simple_liquidity_reversal | simple | MNQ | 129 | 34.9% | 0.80 | -0.128 | -24.00 |
| simple_vwap_reclaim | simple | MNQ | 106 | 35.9% | 0.84 | -0.103 | -18.16 |
| complex_ema_pullback | existing | MES | 28 | 39.3% | 0.92 | -0.051 | -6.16 |
| complex_breakout_retest | existing | MES | 51 | 39.2% | 0.87 | -0.080 | -9.52 |
| complex_vwap_reclaim_hc | existing | MES | 109 | 33.9% | 0.72 | -0.194 | -28.73 |
| simple_trend_pullback | simple | MES | 139 | 44.6% | 1.21 | +0.115 | -10.00 |
| simple_liquidity_reversal | simple | MES | 122 | 36.9% | 0.88 | -0.078 | -21.00 |
| simple_vwap_reclaim | simple | MES | 109 | 33.9% | 0.72 | -0.194 | -28.73 |

## Missed-move coverage

| symbol | missed existing | missed simple | missed either | lift |
|---|---|---|---|---|
| NQ | 1799 | 1799 | 1799 | 0 |
| ES | 1718 | 1718 | 1718 | 0 |
| GC | 2008 | 2008 | 2008 | 0 |
| CL | 1928 | 1928 | 1928 | 0 |
| MNQ | 1800 | 1800 | 1800 | 0 |
| MES | 1756 | 1756 | 1756 | 0 |

Aggregate: `{'missed_existing': 11009, 'missed_simple': 11009, 'missed_either': 11009, 'symbols': 6}`

Note: `missed_*` counts large moves with no matching candidate in that set. Positive lift means specialists reduced misses vs existing-only.
