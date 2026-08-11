# Indicator Parity Report

Generated: 2026-08-10T12:46:07.160847+00:00

**Parity status:** LOGIC_PORTED_1_1 from Pine BUY NOW/SELL NOW; strict all-3 HTF (15m/1h/4h) live-asof on every base bar; chart TF runs: 1m_7d and 5m_60d; stops/targets are execution overlay (not in Pine overlay).

**HTF note:** 15m/1h/4h were never ignored — they gate longBias/shortBias on every signal. Prior pass only lacked a long chart-TF history window (Yahoo 1m≈7d). This pass adds native 5m×60d while keeping the same HTF logic.

## Base: `1m_7d` (chart=1m, period=7d)

- Source: `Yahoo Finance native 1m (period=7d)`
- HTF: `15m + 1h + 4h derived live-asof from base (Pine useLiveHTF)`
- Range: `{'NQ': ['2026-08-03 00:00:00-04:00', '2026-08-10 08:35:00-04:00'], 'MNQ': ['2026-08-03 00:00:00-04:00', '2026-08-10 08:35:00-04:00'], 'ES': ['2026-08-03 00:00:00-04:00', '2026-08-10 08:35:00-04:00'], 'MES': ['2026-08-03 00:00:00-04:00', '2026-08-10 08:35:00-04:00']}`
- Exact trades: **5**

| system | n | label | WR | PF | E[R] | maxDD R | trades/day | trades/week | avg win R | avg loss R |
|---|---|---|---|---|---|---|---|---|---|---|
| exact_tv_indicator | 5 | VERY PRELIMINARY | 20.0% | 0.50 | -0.400 | -2.00 | 2.50 | 12.50 | 2.000 | -1.000 |
| pullback_entry | 9 | VERY PRELIMINARY | 55.6% | 2.50 | +0.667 | -1.00 | 3.00 | 15.00 | 2.000 | -1.000 |
| momentum_entry | 228 | STRONGER SAMPLE | 61.8% | 3.19 | +0.605 | -4.00 | 32.57 | 162.86 | 1.423 | -0.722 |
| indicator_plus_keylevel | 5 | VERY PRELIMINARY | 20.0% | 0.50 | -0.400 | -2.00 | 2.50 | 12.50 | 2.000 | -1.000 |
| vwap_ema_volume | 127 | STRONGER SAMPLE | 59.1% | 2.42 | +0.344 | -4.21 | 18.14 | 90.71 | 0.993 | -0.592 |

### Exact indicator — by symbol (1m_7d)

- **NQ**: n=1 (VERY PRELIMINARY) WR=0.0 PF=0.0 E=-1.0 DD=0.0
- **MNQ**: n=1 (VERY PRELIMINARY) WR=0.0 PF=0.0 E=-1.0 DD=0.0
- **ES**: n=1 (VERY PRELIMINARY) WR=0.0 PF=0.0 E=-1.0 DD=0.0
- **MES**: n=2 (VERY PRELIMINARY) WR=0.5 PF=2.0 E=0.5 DD=-1.0

### Exact indicator — by session (1m_7d)

- **ny**: n=3 WR=0.3333333333333333 PF=1.0 E=0.0
- **london**: n=2 WR=0.0 PF=0.0 E=-1.0

### Pullback vs momentum (1m_7d)

- **pullback_entry**: n=9 (VERY PRELIMINARY) WR=0.5555555555555556 PF=2.5 E=0.6666666666666666 DD=-1.0
- **momentum_entry**: n=228 (STRONGER SAMPLE) WR=0.618421052631579 PF=3.1946989351999924 E=0.6047493436759439 DD=-4.0

### Daily P&L (1m_7d, calendar days)

#### exact_tv_indicator
- calendar days=7 active=2
- **1c**: avg=-104.42346938775128; win med/p75=None/None; lose med/worst=-365.4821428571295/-685.964285714259; ≥500/≥1000/neg/zero=0%/0%/29%/71%
- **2c**: avg=-208.84693877550257; win med/p75=None/None; lose med/worst=-730.964285714259/-1371.928571428518; ≥500/≥1000/neg/zero=0%/0%/29%/71%
- **3c**: avg=-313.2704081632538; win med/p75=None/None; lose med/worst=-1096.4464285713884/-2057.892857142777; ≥500/≥1000/neg/zero=0%/0%/29%/71%
#### indicator_plus_keylevel
- calendar days=7 active=2
- **1c**: avg=-104.42346938775128; win med/p75=None/None; lose med/worst=-365.4821428571295/-685.964285714259; ≥500/≥1000/neg/zero=0%/0%/29%/71%
- **2c**: avg=-208.84693877550257; win med/p75=None/None; lose med/worst=-730.964285714259/-1371.928571428518; ≥500/≥1000/neg/zero=0%/0%/29%/71%
- **3c**: avg=-313.2704081632538; win med/p75=None/None; lose med/worst=-1096.4464285713884/-2057.892857142777; ≥500/≥1000/neg/zero=0%/0%/29%/71%
#### vwap_ema_volume
- calendar days=7 active=7
- **1c**: avg=3382.433673469378; win med/p75=6308.866071428523/12534.125000000044; lose med/worst=-1557.5/-10421.5; ≥500/≥1000/neg/zero=57%/43%/43%/0%
- **2c**: avg=6764.867346938756; win med/p75=12617.732142857047/25068.250000000087; lose med/worst=-3115.0/-20843.0; ≥500/≥1000/neg/zero=57%/57%/43%/0%
- **3c**: avg=10147.301020408135; win med/p75=18926.598214285572/37602.37500000013; lose med/worst=-4672.5/-31264.5; ≥500/≥1000/neg/zero=57%/57%/43%/0%
#### pullback_entry
- calendar days=7 active=3
- **1c**: avg=250.98469387754474; win med/p75=1221.428571428536/1595.2857142856956; lose med/worst=-685.964285714259/-685.964285714259; ≥500/≥1000/neg/zero=14%/14%/14%/57%
- **2c**: avg=501.9693877550895; win med/p75=2442.857142857072/3190.571428571391; lose med/worst=-1371.928571428518/-1371.928571428518; ≥500/≥1000/neg/zero=29%/14%/14%/57%
- **3c**: avg=752.9540816326343; win med/p75=3664.2857142856083/4785.857142857087; lose med/worst=-2057.892857142777/-2057.892857142777; ≥500/≥1000/neg/zero=29%/29%/14%/57%
#### momentum_entry
- calendar days=7 active=7
- **1c**: avg=7661.698979591806; win med/p75=4628.178571428578/7801.6071428570385; lose med/worst=None/522.982142857185; ≥500/≥1000/neg/zero=100%/86%/0%/0%
- **2c**: avg=15323.397959183612; win med/p75=9256.357142857156/15603.214285714077; lose med/worst=None/1045.96428571437; ≥500/≥1000/neg/zero=100%/100%/0%/0%
- **3c**: avg=22985.09693877542; win med/p75=13884.535714285734/23404.821428571115; lose med/worst=None/1568.9464285715549; ≥500/≥1000/neg/zero=100%/100%/0%/0%

## Base: `5m_60d` (chart=5m, period=60d)

- Source: `Yahoo Finance native 5m (period=60d)`
- HTF: `15m + 1h + 4h derived live-asof from base (Pine useLiveHTF)`
- Range: `{'NQ': ['2026-05-31 18:10:00-04:00', '2026-08-10 08:35:00-04:00'], 'MNQ': ['2026-05-31 18:10:00-04:00', '2026-08-10 08:35:00-04:00'], 'ES': ['2026-05-31 18:10:00-04:00', '2026-08-10 08:35:00-04:00'], 'MES': ['2026-05-31 18:10:00-04:00', '2026-08-10 08:35:00-04:00']}`
- Exact trades: **47**

| system | n | label | WR | PF | E[R] | maxDD R | trades/day | trades/week | avg win R | avg loss R |
|---|---|---|---|---|---|---|---|---|---|---|
| exact_tv_indicator | 47 | PROMISING / NOT CONFIRMED | 70.2% | 4.71 | +1.106 | -2.00 | 2.61 | 13.06 | 2.000 | -1.000 |
| pullback_entry | 55 | PROMISING / NOT CONFIRMED | 76.4% | 6.46 | +1.291 | -2.00 | 2.50 | 12.50 | 2.000 | -1.000 |
| momentum_entry | 377 | STRONGER SAMPLE | 50.9% | 1.71 | +0.278 | -6.63 | 6.73 | 33.66 | 1.309 | -0.793 |
| indicator_plus_keylevel | 47 | PROMISING / NOT CONFIRMED | 70.2% | 4.71 | +1.106 | -2.00 | 2.61 | 13.06 | 2.000 | -1.000 |
| vwap_ema_volume | 275 | STRONGER SAMPLE | 45.1% | 1.23 | +0.100 | -12.82 | 5.19 | 25.94 | 1.181 | -0.787 |

### Exact indicator — by symbol (5m_60d)

- **NQ**: n=10 (VERY PRELIMINARY) WR=0.7 PF=4.666666666666667 E=1.1 DD=-2.0
- **MNQ**: n=9 (VERY PRELIMINARY) WR=0.6666666666666666 PF=4.0 E=1.0 DD=-2.0
- **ES**: n=15 (VERY PRELIMINARY) WR=0.7333333333333333 PF=5.5 E=1.2 DD=-2.0
- **MES**: n=13 (VERY PRELIMINARY) WR=0.6923076923076923 PF=4.5 E=1.0769230769230769 DD=-2.0

### Exact indicator — by session (5m_60d)

- **ny**: n=26 WR=0.6153846153846154 PF=3.2 E=0.8461538461538461
- **london**: n=14 WR=1.0 PF=999.0 E=2.0
- **asia**: n=7 WR=0.42857142857142855 PF=1.5 E=0.2857142857142857

### Pullback vs momentum (5m_60d)

- **pullback_entry**: n=55 (PROMISING / NOT CONFIRMED) WR=0.7636363636363637 PF=6.461538461538462 E=1.290909090909091 DD=-2.0
- **momentum_entry**: n=377 (STRONGER SAMPLE) WR=0.5092838196286472 PF=1.7136983541047566 E=0.2776410791275351 DD=-6.625107388316152

### Daily P&L (5m_60d, calendar days)

#### exact_tv_indicator
- calendar days=60 active=18
- **1c**: avg=395.8205357142877; win med/p75=1457.3214285714175/2743.5714285714457; lose med/worst=-751.8749999999786/-1540.0714285714494; ≥500/≥1000/neg/zero=17%/15%/7%/70%
- **2c**: avg=791.6410714285754; win med/p75=2914.642857142835/5487.142857142891; lose med/worst=-1503.7499999999573/-3080.1428571428987; ≥500/≥1000/neg/zero=22%/17%/7%/70%
- **3c**: avg=1187.4616071428632; win med/p75=4371.964285714253/8230.714285714337; lose med/worst=-2255.624999999936/-4620.214285714348; ≥500/≥1000/neg/zero=22%/20%/7%/70%
#### indicator_plus_keylevel
- calendar days=60 active=18
- **1c**: avg=395.8205357142877; win med/p75=1457.3214285714175/2743.5714285714457; lose med/worst=-751.8749999999786/-1540.0714285714494; ≥500/≥1000/neg/zero=17%/15%/7%/70%
- **2c**: avg=791.6410714285754; win med/p75=2914.642857142835/5487.142857142891; lose med/worst=-1503.7499999999573/-3080.1428571428987; ≥500/≥1000/neg/zero=22%/17%/7%/70%
- **3c**: avg=1187.4616071428632; win med/p75=4371.964285714253/8230.714285714337; lose med/worst=-2255.624999999936/-4620.214285714348; ≥500/≥1000/neg/zero=22%/20%/7%/70%
#### vwap_ema_volume
- calendar days=60 active=53
- **1c**: avg=781.7410714285686; win med/p75=7964.125/12859.0625; lose med/worst=-4283.25/-23176.87500000005; ≥500/≥1000/neg/zero=38%/37%/48%/12%
- **2c**: avg=1563.4821428571372; win med/p75=15928.25/25718.125; lose med/worst=-8566.5/-46353.7500000001; ≥500/≥1000/neg/zero=40%/38%/48%/12%
- **3c**: avg=2345.223214285706; win med/p75=23892.375/38577.1875; lose med/worst=-12849.75/-69530.62500000015; ≥500/≥1000/neg/zero=40%/38%/48%/12%
#### pullback_entry
- calendar days=60 active=22
- **1c**: avg=542.3306547619082; win med/p75=1457.3214285714175/2743.5714285714457; lose med/worst=-667.5892857142867/-934.6428571428332; ≥500/≥1000/neg/zero=22%/20%/7%/63%
- **2c**: avg=1084.6613095238165; win med/p75=2914.642857142835/5487.142857142891; lose med/worst=-1335.1785714285734/-1869.2857142856665; ≥500/≥1000/neg/zero=28%/22%/7%/63%
- **3c**: avg=1626.9919642857249; win med/p75=4371.964285714253/8230.714285714337; lose med/worst=-2002.76785714286/-2803.9285714284997; ≥500/≥1000/neg/zero=28%/27%/7%/63%
#### momentum_entry
- calendar days=60 active=56
- **1c**: avg=3441.600892857144; win med/p75=6422.785714285696/11952.75; lose med/worst=-7568.5/-18177.75; ≥500/≥1000/neg/zero=62%/60%/25%/7%
- **2c**: avg=6883.201785714288; win med/p75=12845.571428571391/23905.5; lose med/worst=-15137.0/-36355.5; ≥500/≥1000/neg/zero=63%/62%/25%/7%
- **3c**: avg=10324.80267857143; win med/p75=19268.357142857087/35858.25; lose med/worst=-22705.5/-54533.25; ≥500/≥1000/neg/zero=63%/63%/25%/7%

## Notes
- Chart TF = when BUY/SELL fires (1m vs 5m). HTF bias always uses 15m/1h/4h.
- Pine `sweepValidBars=240` is in **chart bars** (same as TV when you change chart TF).
- Delay is not used as a reason to skip HTF — only Yahoo history depth differs by interval.
- Stops/targets are execution assumptions (Pine is overlay-only).
