# Breakout Retest Forward Report

**Generated:** 2026-08-12T22:46:16.592203+00:00
**Active stamp (expected):** `router_v1_paperfix2`
**Heartbeat stamp:** `router_v1_paperfix2`

> RESEARCH + OBSERVATION ONLY. No paper config / risk / qty / engine changes in this pass.

## A. Paper agent health

```json
{
  "scan_state": "PASS_NO_CANDIDATE",
  "decision": "PASS \u2014 ONLY RESEARCH/SHADOW A",
  "ts": "2026-08-12T22:45:48.571786+00:00",
  "session": "asia | mode=active"
}
```

## B. Post-paperfix2 total performance (all strategies)

- n=12 wins=6 losses=6 WR=0.5 PF=7.3388 E[R]=0.2256 PnL=$1785.96 maxDD_R=-1.284 (evidence=ANECDOTAL)

## C. Breakout_retest total performance (post-paperfix2 paper fills)

- n=10 wins=5 losses=5 WR=0.5 PF=2.964 E[R]=0.2837 PnL=$1794.71 maxDD_R=-0.978 (evidence=ANECDOTAL)

Pre-paperfix2 breakout (contaminated / prior stamps): - n=7 wins=0 losses=7 WR=0.0 PF=0.0 E[R]=-0.275 PnL=$-765.49 maxDD_R=-1.296 (evidence=ANECDOTAL)

## D. Breakout_retest by symbol (post-paperfix2)

| Cell | Evidence | n | WR | shrunk WR | PF | E[R] | PnL |
|---|---|---:|---:|---:|---:|---:|---:|
| `MNQ` | ANECDOTAL | 4 | 0.25 | 0.4583 | 1.513 | 0.0599 | -21.5 |
| `CL` | ANECDOTAL | 1 | 1.0 | 0.5238 | 999.0 | 1.3762 | 389.99 |
| `ES` | ANECDOTAL | 1 | 1.0 | 0.5238 | 999.0 | 0.7956 | 475.0 |
| `GC` | ANECDOTAL | 1 | 1.0 | 0.5238 | 999.0 | 0.753 | 989.97 |
| `M2K` | ANECDOTAL | 1 | 0.0 | 0.4762 | 0.0 | -0.4934 | -19.5 |
| `MES` | ANECDOTAL | 1 | 0.0 | 0.4762 | 0.0 | -0.4851 | -56.25 |
| `MYM` | ANECDOTAL | 1 | 1.0 | 0.5238 | 999.0 | 0.6514 | 37.0 |

## E. Breakout_retest by session (post-paperfix2)

| Cell | Evidence | n | WR | shrunk WR | PF | E[R] | PnL |
|---|---|---:|---:|---:|---:|---:|---:|
| `ny` | ANECDOTAL | 10 | 0.5 | 0.5 | 2.964 | 0.2837 | 1794.71 |

## F–H. Forensic snapshots (ES +475 / CL +390 / GC +990)

Label: **ANECDOTAL TODAY** unless historical support noted in shrink hierarchy.

### PAPER-00213 — GC SELL PnL=989.97 (target)

- session=ny regime=TREND_DOWN tier=A+ qty=3 contract=full
- R≈0.7530341340359837 stamp=router_v1_paperfix2
- features: `{"above_vwap": 0, "agreeing_n": 1, "below_vwap": 1, "cascade_location": "POOR_LOCATION", "cascade_thesis": "SHORT_SUPPORT", "dir_15m": -1, "dir_1h": 1, "dir_4h": -1, "direction": "SHORT", "ema_bear": 1, "ema_bull": 0, "global_score": 89.0, "local_score": 82, "momentum_aligned": 0, "mtf_aligned": 2, "near_pdh": 0, "near_pdl": 0, "overextended": 0, "regime": "TREND_DOWN", "session": "ny", "strategy": "breakout_retest", "symbol": "GC", "target_r": 1.7000000000001245, "tier_rank": 1}`
- shrink hierarchy: `[{"key": ["GC", "ny", "TREND_DOWN", "SELL"], "level": "strat+sym+sess+regime+dir", "n": 1, "prior": 0.565, "raw_wr": 1.0, "shrunk_wr": 0.5857}, {"key": ["GC", "ny", "TREND_DOWN"], "level": "strat+sym+sess+regime", "n": 2, "prior": 0.5215, "raw_wr": 1.0, "shrunk_wr": 0.565}, {"key": ["GC", "ny"], "level": "strat+sym+sess", "n": 2, "prior": 0.4737, "raw_wr": 1.0, "shrunk_wr": 0.5215}, {"key": ["GC"], "level": "strat+sym", "n": 2, "prior": 0.4211, "raw_wr": 1.0, "shrunk_wr": 0.4737}, {"key": [], "level": "strat", "n": 37, "prior": 0.5, "raw_wr": 0.3784, "shrunk_wr": 0.4211}]`

### PAPER-00210 — CL SELL PnL=389.99 (target)

- session=ny regime=TREND_DOWN tier=A+ qty=2 contract=full
- R≈1.3762304243956776 stamp=router_v1_paperfix2
- features: `{"above_vwap": 0, "agreeing_n": 2, "below_vwap": 1, "cascade_location": "POOR_LOCATION", "cascade_thesis": "SHORT_SUPPORT", "dir_15m": -1, "dir_1h": -1, "dir_4h": -1, "direction": "SHORT", "ema_bear": 1, "ema_bull": 0, "global_score": 100.0, "local_score": 82, "momentum_aligned": 0, "mtf_aligned": 3, "near_pdh": 0, "near_pdl": 0, "overextended": 0, "regime": "TREND_DOWN", "session": "ny", "strategy": "breakout_retest", "symbol": "CL", "target_r": 1.6999999999999098, "tier_rank": 1}`
- shrink hierarchy: `[{"key": ["CL", "ny", "TREND_DOWN", "SELL"], "level": "strat+sym+sess+regime+dir", "n": 2, "prior": 0.4762, "raw_wr": 0.5, "shrunk_wr": 0.4783}, {"key": ["CL", "ny", "TREND_DOWN"], "level": "strat+sym+sess+regime", "n": 4, "prior": 0.4714, "raw_wr": 0.5, "shrunk_wr": 0.4762}, {"key": ["CL", "ny"], "level": "strat+sym+sess", "n": 5, "prior": 0.4393, "raw_wr": 0.6, "shrunk_wr": 0.4714}, {"key": ["CL"], "level": "strat+sym", "n": 6, "prior": 0.4211, "raw_wr": 0.5, "shrunk_wr": 0.4393}, {"key": [], "level": "strat", "n": 37, "prior": 0.5, "raw_wr": 0.3784, "shrunk_wr": 0.4211}]`

### PAPER-00209 — MNQ SELL PnL=127.0 (stop)

- session=ny regime=TREND_DOWN tier=A+ qty=2 contract=micro
- R≈0.705879083468771 stamp=router_v1_paperfix2
- features: `{"above_vwap": 0, "agreeing_n": 3, "below_vwap": 1, "cascade_location": "ACCEPTABLE_LOCATION", "cascade_thesis": "SHORT_SUPPORT", "dir_15m": -1, "dir_1h": -1, "dir_4h": 1, "direction": "SHORT", "ema_bear": 1, "ema_bull": 0, "global_score": 100.0, "local_score": 82, "momentum_aligned": 0, "mtf_aligned": 2, "near_pdh": 0, "near_pdl": 0, "overextended": 0, "regime": "TREND_DOWN", "session": "ny", "strategy": "breakout_retest", "symbol": "MNQ", "target_r": 2.667889449330788, "tier_rank": 1}`
- shrink hierarchy: `[{"key": ["MNQ", "ny", "TREND_DOWN", "SELL"], "level": "strat+sym+sess+regime+dir", "n": 3, "prior": 0.3519, "raw_wr": 0.3333, "shrunk_wr": 0.3495}, {"key": ["MNQ", "ny", "TREND_DOWN"], "level": "strat+sym+sess+regime", "n": 6, "prior": 0.3575, "raw_wr": 0.3333, "shrunk_wr": 0.3519}, {"key": ["MNQ", "ny"], "level": "strat+sym+sess", "n": 9, "prior": 0.3684, "raw_wr": 0.3333, "shrunk_wr": 0.3575}, {"key": ["MNQ"], "level": "strat+sym", "n": 11, "prior": 0.4211, "raw_wr": 0.2727, "shrunk_wr": 0.3684}, {"key": [], "level": "strat", "n": 37, "prior": 0.5, "raw_wr": 0.3784, "shrunk_wr": 0.4211}]`

### PAPER-00198 — ES BUY PnL=475.0 (target)

- session=ny regime=TREND_UP tier=A+ qty=2 contract=full
- R≈0.7956448911223654 stamp=router_v1_paperfix2
- features: `{"above_vwap": 1, "agreeing_n": 3, "below_vwap": 0, "cascade_location": "ACCEPTABLE_LOCATION", "cascade_thesis": "MIXED", "dir_15m": 1, "dir_1h": 1, "dir_4h": -1, "direction": "LONG", "ema_bear": 0, "ema_bull": 1, "global_score": 97.0, "local_score": 82, "momentum_aligned": 0, "mtf_aligned": 2, "near_pdh": 0, "near_pdl": 0, "overextended": 0, "regime": "TREND_UP", "session": "ny", "strategy": "breakout_retest", "symbol": "ES", "target_r": 1.7000000000000914, "tier_rank": 1}`
- shrink hierarchy: `[{"key": ["ES", "ny", "TREND_UP", "BUY"], "level": "strat+sym+sess+regime+dir", "n": 1, "prior": 0.602, "raw_wr": 1.0, "shrunk_wr": 0.621}, {"key": ["ES", "ny", "TREND_UP"], "level": "strat+sym+sess+regime", "n": 2, "prior": 0.5622, "raw_wr": 1.0, "shrunk_wr": 0.602}, {"key": ["ES", "ny"], "level": "strat+sym+sess", "n": 3, "prior": 0.4966, "raw_wr": 1.0, "shrunk_wr": 0.5622}, {"key": ["ES"], "level": "strat+sym", "n": 3, "prior": 0.4211, "raw_wr": 1.0, "shrunk_wr": 0.4966}, {"key": [], "level": "strat", "n": 37, "prior": 0.5, "raw_wr": 0.3784, "shrunk_wr": 0.4211}]`

## I. Winner vs loser feature comparison (post-paperfix2 paper)

_n is small — treat as ANECDOTAL unless evidence column says otherwise._

| Feature | Evidence | winner_n | loser_n | stats |
|---|---|---:|---:|---|
| `dir_15m` | ANECDOTAL | 5 | 5 | w_med=-1.0 l_med=-1.0 diff=0.0 |
| `dir_1h` | ANECDOTAL | 5 | 5 | w_med=-1.0 l_med=1.0 diff=-2.0 |
| `dir_4h` | ANECDOTAL | 5 | 5 | w_med=-1.0 l_med=1.0 diff=-2.0 |
| `mtf_aligned` | ANECDOTAL | 5 | 5 | w_med=2.0 l_med=2.0 diff=0.0 |
| `above_vwap` | ANECDOTAL | 5 | 5 | w_med=0.0 l_med=1.0 diff=-1.0 |
| `below_vwap` | ANECDOTAL | 5 | 5 | w_med=1.0 l_med=0.0 diff=1.0 |
| `ema_bull` | ANECDOTAL | 5 | 5 | w_med=0.0 l_med=1.0 diff=-1.0 |
| `ema_bear` | ANECDOTAL | 5 | 5 | w_med=1.0 l_med=0.0 diff=1.0 |
| `overextended` | ANECDOTAL | 5 | 5 | w_med=0.0 l_med=0.0 diff=0.0 |
| `near_pdh` | ANECDOTAL | 5 | 5 | w_med=0.0 l_med=0.0 diff=0.0 |
| `near_pdl` | ANECDOTAL | 5 | 5 | w_med=0.0 l_med=0.0 diff=0.0 |
| `momentum_aligned` | ANECDOTAL | 5 | 5 | w_med=0.0 l_med=0.0 diff=0.0 |
| `agreeing_n` | ANECDOTAL | 5 | 5 | w_med=3.0 l_med=2.0 diff=1.0 |
| `target_r` | ANECDOTAL | 5 | 5 | w_med=1.7 l_med=3.0047 diff=-1.3047 |
| `global_score` | ANECDOTAL | 5 | 5 | w_med=97.0 l_med=100.0 diff=-3.0 |
| `local_score` | ANECDOTAL | 5 | 5 | w_med=82.0 l_med=82.0 diff=0.0 |
| `cascade_location=ACCEPTABLE_LOCATION` | ANECDOTAL | 5 | 5 | w_freq=0.6 l_freq=0.4 diff=0.2 |
| `cascade_location=POOR_LOCATION` | ANECDOTAL | 5 | 5 | w_freq=0.4 l_freq=0.6 diff=-0.2 |
| `cascade_thesis=LONG_SUPPORT` | ANECDOTAL | 5 | 5 | w_freq=0.0 l_freq=0.2 diff=-0.2 |
| `cascade_thesis=MIXED` | ANECDOTAL | 5 | 5 | w_freq=0.4 l_freq=0.4 diff=0.0 |
| `cascade_thesis=SHORT_SUPPORT` | ANECDOTAL | 5 | 5 | w_freq=0.6 l_freq=0.4 diff=0.2 |

### Historical learning-store feature compare (resolved WIN/LOSS)

| Feature | Evidence | winner_n | loser_n | stats |
|---|---|---:|---:|---|
| `dir_15m` | ANECDOTAL | 9 | 11 | w_med=-1.0 l_med=-1.0 diff=0.0 |
| `dir_1h` | ANECDOTAL | 9 | 11 | w_med=-1.0 l_med=1.0 diff=-2.0 |
| `dir_4h` | ANECDOTAL | 9 | 11 | w_med=-1.0 l_med=1.0 diff=-2.0 |
| `mtf_aligned` | ANECDOTAL | 9 | 11 | w_med=2.0 l_med=2.0 diff=0.0 |
| `above_vwap` | ANECDOTAL | 9 | 11 | w_med=0.0 l_med=1.0 diff=-1.0 |
| `below_vwap` | ANECDOTAL | 9 | 11 | w_med=1.0 l_med=0.0 diff=1.0 |
| `ema_bull` | ANECDOTAL | 9 | 11 | w_med=0.0 l_med=1.0 diff=-1.0 |
| `ema_bear` | ANECDOTAL | 9 | 11 | w_med=1.0 l_med=0.0 diff=1.0 |
| `overextended` | ANECDOTAL | 9 | 11 | w_med=0.0 l_med=0.0 diff=0.0 |
| `near_pdh` | ANECDOTAL | 9 | 11 | w_med=0.0 l_med=0.0 diff=0.0 |
| `near_pdl` | ANECDOTAL | 9 | 11 | w_med=0.0 l_med=0.0 diff=0.0 |
| `momentum_aligned` | ANECDOTAL | 9 | 11 | w_med=0.0 l_med=0.0 diff=0.0 |
| `agreeing_n` | ANECDOTAL | 9 | 11 | w_med=3.0 l_med=2.0 diff=1.0 |
| `target_r` | ANECDOTAL | 9 | 11 | w_med=1.7 l_med=2.8864 diff=-1.1864 |
| `global_score` | ANECDOTAL | 9 | 11 | w_med=97.0 l_med=90.0 diff=7.0 |
| `local_score` | ANECDOTAL | 9 | 11 | w_med=82.0 l_med=82.0 diff=0.0 |
| `cascade_location=ACCEPTABLE_LOCATION` | ANECDOTAL | 9 | 11 | w_freq=0.6667 l_freq=0.3636 diff=0.303 |
| `cascade_location=POOR_LOCATION` | ANECDOTAL | 9 | 11 | w_freq=0.3333 l_freq=0.6364 diff=-0.303 |
| `cascade_thesis=LONG_SUPPORT` | ANECDOTAL | 9 | 11 | w_freq=0.0 l_freq=0.3636 diff=-0.3636 |
| `cascade_thesis=MIXED` | ANECDOTAL | 9 | 11 | w_freq=0.4444 l_freq=0.1818 diff=0.2626 |
| `cascade_thesis=SHORT_SUPPORT` | ANECDOTAL | 9 | 11 | w_freq=0.5556 l_freq=0.4545 diff=0.101 |

## J–K. High-performance cells + shrunk WR

### Learning-store by symbol (includes shadow/non-exec resolved)

| Cell | Evidence | n | WR | shrunk WR | PF | E[R] | PnL |
|---|---|---:|---:|---:|---:|---:|---:|
| `MNQ` | ANECDOTAL | 6 | 0.3333 | 0.4231 | 0.863 | -0.0475 | 0 |
| `MES` | ANECDOTAL | 4 | 0.0 | 0.375 | 0.0 | -0.8979 | 0 |
| `CL` | ANECDOTAL | 3 | 0.6667 | 0.4783 | 1.058 | 0.0322 | 0 |
| `MYM` | ANECDOTAL | 3 | 0.6667 | 0.4783 | 10.792 | 0.4262 | 0 |
| `ES` | ANECDOTAL | 2 | 1.0 | 0.5 | 999.0 | 1.3664 | 0 |
| `GC` | ANECDOTAL | 1 | 1.0 | 0.4762 | 999.0 | 1.2138 | 0 |
| `M2K` | ANECDOTAL | 1 | 0.0 | 0.4286 | 0.0 | -1.2056 | 0 |

Learning overall: - n=20 wins=9 losses=11 WR=0.45 PF=0.795 E[R]=-0.103 PnL=$0 maxDD_R=-5.464 (evidence=EARLY)

Shadow closed breakout: - n=78 wins=22 losses=56 WR=0.2821 PF=0.575 E[R]=-0.2933 PnL=$-3137.29 maxDD_R=-25.053 (evidence=DEVELOPING)

## L–M. Asia / London

Overnight forward sample still collecting. Current post-fix2 session cells:

| Cell | Evidence | n | WR | shrunk WR | PF | E[R] | PnL |
|---|---|---:|---:|---:|---:|---:|---:|
| `ny` | ANECDOTAL | 10 | 0.5 | 0.5 | 2.964 | 0.2837 | 1794.71 |

## N. Open CL trade

```json
{
  "trade_id": "PAPER-00222",
  "side": "SELL",
  "qty": 3,
  "entry": 82.74,
  "stop": 82.83555095672608,
  "target": 82.62156337356566,
  "opened_at": "2026-08-12 18:10:00",
  "session": "asia",
  "risk_dollars": 226.65287017822777,
  "reward_dollars": 385.30987930300853,
  "status": "OPEN"
}
```

## O. Software / runtime issues

No strategy changes applied this pass. Monitor heartbeat / supervisor separately.

## P. Full-size family preference

Policy unchanged (`prefer_full_size_in_family: true`). Contract-class cells (post paper):

| Cell | Evidence | n | WR | shrunk WR | PF | E[R] | PnL |
|---|---|---:|---:|---:|---:|---:|---:|
| `micro` | ANECDOTAL | 7 | 0.2857 | 0.4444 | 0.939 | -0.0125 | -60.25 |
| `full` | ANECDOTAL | 3 | 1.0 | 0.5652 | 999.0 | 0.975 | 1854.96 |

## Q. Time-stop fix verification

Recent time_stop exits (audit; inflated hold_minutes on pre-fix stamps expected):

```json
[
  {
    "id": "PAPER-00173",
    "symbol": "MNQ",
    "opened_at": "2026-08-12 09:05:00",
    "received_at": "2026-08-12 13:15:42.260732+00:00",
    "closed_at": "2026-08-12T13:23:31.525482+00:00",
    "hold_minutes": 258.53,
    "config_version": "router_v1_paperfix1",
    "era": "pre_paperfix2",
    "note": "pre-fix stamps may show inflated hold_minutes; post_paperfix2 should age from received_at"
  },
  {
    "id": "PAPER-00171",
    "symbol": "MYM",
    "opened_at": "2026-08-12 08:55:00",
    "received_at": "2026-08-12 13:08:39.708912+00:00",
    "closed_at": "2026-08-12T13:10:30.984530+00:00",
    "hold_minutes": 255.52,
    "config_version": "router_v1_paperfix1",
    "era": "pre_paperfix2",
    "note": "pre-fix stamps may show inflated hold_minutes; post_paperfix2 should age from received_at"
  },
  {
    "id": "PAPER-00169",
    "symbol": "MES",
    "opened_at": "2026-08-12 08:20:00",
    "received_at": "2026-08-12 12:30:28.102269+00:00",
    "closed_at": "2026-08-12T12:32:19.024046+00:00",
    "hold_minutes": 252.32,
    "config_version": "router_v1_paperfix1",
    "era": "pre_paperfix2",
    "note": "pre-fix stamps may show inflated hold_minutes; post_paperfix2 should age from received_at"
  },
  {
    "id": "PAPER-00167",
    "symbol": "MES",
    "opened_at": "2026-08-11 10:50:00",
    "received_at": "2026-08-11 15:00:56.754340+00:00",
    "closed_at": "2026-08-11T15:02:37.695565+00:00",
    "hold_minutes": 252.63,
    "config_version": "router_v1_quality2h",
    "era": "pre_paperfix2",
    "note": "pre-fix stamps may show inflated hold_minutes; post_paperfix2 should age from received_at"
  },
  {
    "id": "PAPER-00165",
    "symbol": "MNQ",
    "opened_at": "2026-08-11 10:05:00",
    "received_at": "2026-08-11 14:15:57.973447+00:00",
    "closed_at": "2026-08-11T14:24:35.529270+00:00",
    "hold_minutes": 259.59,
    "config_version": "router_v1_quality2h",
    "era": "pre_paperfix2",
    "note": "pre-fix stamps may show inflated hold_minutes; post_paperfix2 should age from received_at"
  },
  {
    "id": "PAPER-00160",
    "symbol": "M2K",
    "opened_at": "2026-08-11 04:00:00",
    "received_at": "2026-08-11 08:11:10.535280+00:00",
    "closed_at": "2026-08-11T08:11:56.679659+00:00",
    "hold_minutes": 251.94,
    "config_version": "router_v1_quality2h",
    "era": "pre_paperfix2",
    "note": "pre-fix stamps may show inflated hold_minutes; post_paperfix2 should age from received_at"
  },
  {
    "id": "PAPER-00158",
    "symbol": "M2K",
    "opened_at": "2026-08-11 03:35:00",
    "received_at": "2026-08-11 07:46:12.280805+00:00",
    "closed_at": "2026-08-11T07:46:56.283371+00:00",
    "hold_minutes": 251.94,
    "config_version": "router_v1_quality2h",
    "era": "pre_paperfix2",
    "note": "pre-fix stamps may show inflated hold_minutes; post_paperfix2 should age from received_at"
  },
  {
    "id": "PAPER-00156",
    "symbol": "M2K",
    "opened_at": "2026-08-11 02:15:00",
    "received_at": "2026-08-11 06:26:15.744259+00:00",
    "closed_at": "2026-08-11T06:26:58.825547+00:00",
    "hold_minutes": 251.98,
    "config_version": "router_v1_quality2h",
    "era": "pre_paperfix2",
    "note": "pre-fix stamps may show inflated hold_minutes; post_paperfix2 should age from received_at"
  },
  {
    "id": "PAPER-00152",
    "symbol": "MYM",
    "opened_at": "2026-08-11 01:50:00",
    "received_at": "2026-08-11 06:01:10.888337+00:00",
    "closed_at": "2026-08-11T06:01:58.538471+00:00",
    "hold_minutes": 251.98,
    "config_version": "router_v1_quality2h",
    "era": "pre_paperfix2",
    "note": "pre-fix stamps may show inflated hold_minutes; post_paperfix2 should age from received_at"
  },
  {
    "id": "PAPER-00147",
    "symbol": "MES",
    "opened_at": "2026-08-11 01:35:00",
    "received_at": "2026-08-11 05:46:08.087812+00:00",
    "closed_at": "2026-08-11T05:47:58.556220+00:00",
    "hold_minutes": 252.98,
    "config_version": "router_v1_quality2h",
    "era": "pre_paperfix2",
    "note": "pre-fix stamps may show inflated hold_minutes; post_paperfix2 should age from received_at"
  },
  {
    "id": "PAPER-00146",
    "symbol": "MNQ",
    "opened_at": "2026-08-11 01:35:00",
    "received_at": "2026-08-11 05:46:10.211682+00:00",
    "closed_at": "2026-08-11T05:47:58.329116+00:00",
    "hold_minutes": 252.97,
    "config_version": "router_v1_quality2h",
    "era": "pre_paperfix2",
    "note": "pre-fix stamps may show inflated hold_minutes; post_paperfix2 should age from received_at"
  },
  {
    "id": "PAPER-00145",
    "symbol": "M2K",
    "opened_at": "2026-08-11 01:35:00",
    "received_at": "2026-08-11 05:46:17.154966+00:00",
    "closed_at": "2026-08-11T05:47:58.056652+00:00",
    "hold_minutes": 252.97,
    "config_version": "router_v1_quality2h",
    "era": "pre_paperfix2",
    "note": "pre-fix stamps may show inflated hold_minutes; post_paperfix2 should age from received_at"
  },
  {
    "id": "PAPER-00143",
    "symbol": "MYM",
    "opened_at": "2026-08-10 22:40:00",
    "received_at": "2026-08-11 02:51:14.582866+00:00",
    "closed_at": "2026-08-11T02:52:55.618084+00:00",
    "hold_minutes": 252.93,
    "config_version": "router_v1_quality2h",
    "era": "pre_paperfix2",
    "note": "pre-fix stamps may show inflated hold_minutes; post_paperfix2 should age from received_at"
  },
  {
    "id": "PAPER-00141",
    "symbol": "MYM",
    "opened_at": "2026-08-10 22:35:00",
    "received_at": "2026-08-11 02:46:11.023965+00:00",
    "closed_at": "2026-08-11T02:46:55.688972+00:00",
    "hold_minutes": 251.93,
    "config_version": "router_v1_quality2h",
    "era": "pre_paperfix2",
    "note": "pre-fix stamps may show inflated hold_minutes; post_paperfix2 should age from received_at"
  },
  {
    "id": "PAPER-00139",
    "symbol": "MNQ",
    "opened_at": "2026-08-10 22:30:00",
    "received_at": "2026-08-11 02:41:07.619933+00:00",
    "closed_at": "2026-08-11T02:41:56.032329+00:00",
    "hold_minutes": 251.93,
    "config_version": "router_v1_quality2h",
    "era": "pre_paperfix2",
    "note": "pre-fix stamps may show inflated hold_minutes; post_paperfix2 should age from received_at"
  },
  {
    "id": "PAPER-00137",
    "symbol": "MYM",
    "opened_at": "2026-08-10 21:15:00",
    "received_at": "2026-08-11 01:26:08.690665+00:00",
    "closed_at": "2026-08-11T01:26:50.856638+00:00",
    "hold_minutes": 251.85,
    "config_version": "router_v1_quality2h",
    "era": "pre_paperfix2",
    "note": "pre-fix stamps may show inflated hold_minutes; post_paperfix2 should age from received_at"
  },
  {
    "id": "PAPER-00132",
    "symbol": "MES",
    "opened_at": "2026-08-10 11:45:00",
    "received_at": "2026-08-10 15:55:34.763474+00:00",
    "closed_at": "2026-08-10T15:56:31.906206+00:00",
    "hold_minutes": 251.53,
    "config_version": "router_v1",
    "era": "pre_paperfix2",
    "note": "pre-fix stamps may show inflated hold_minutes; post_paperfix2 should age from received_at"
  },
  {
    "id": "PAPER-00130",
    "symbol": "MGC",
    "opened_at": "2026-08-10 11:40:00",
    "received_at": "2026-08-10 15:50:36.112306+00:00",
    "closed_at": "2026-08-10T15:51:33.241524+00:00",
    "hold_minutes": 251.55,
    "config_version": "router_v1",
    "era": "pre_paperfix2",
    "note": "pre-fix stamps may show inflated hold_minutes; post_paperfix2 should age from received_at"
  },
  {
    "id": "PAPER-00128",
    "symbol": "MGC",
    "opened_at": "2026-08-10 11:35:00",
    "received_at": "2026-08-10 15:45:37.147387+00:00",
    "closed_at": "2026-08-10T15:49:32.266876+00:00",
    "hold_minutes": 254.54,
    "config_version": "router_v1",
    "era": "pre_paperfix2",
    "note": "pre-fix stamps may show inflated hold_minutes; post_paperfix2 should age from received_at"
  },
  {
    "id": "PAPER-00125",
    "symbol": "MGC",
    "opened_at": "2026-08-10 11:30:00",
    "received_at": "2026-08-10 15:40:39.223596+00:00",
    "closed_at": "2026-08-10T15:41:32.621822+00:00",
    "hold_minutes": 251.54,
    "config_version": "router_v1",
    "era": "pre
```

## R. Learning-store counts

```json
{
  "paper_breakout_rows": 18,
  "learning_resolved_breakout": 20,
  "shadow_closed_breakout": 78,
  "post_br_closed": 10
}
```

## S. Discovery patterns worth further research (NOT deploy)

1. Post-fix2 target hits clustered on full-size ES/CL/GC — **dollar size ≠ R-edge**; compare R/WR by contract_class.
2. Many MNQ breakout stops same day — check session/regime/MTF vs winners before any filter.
3. Available entry_features are compact (MTF/VWAP/EMA flags). Deeper structure (level type, retest depth) needs richer logging — do not invent fields.
4. Do not promote breakout_retest from today's anecdotal n.

## Direct answers (preview — refresh after overnight)

```json
{
  "1_clean_paperfix2_wr": 0.5,
  "2_clean_paperfix2_pf": 7.3388,
  "3_clean_expectancy_r": 0.2837,
  "4_breakout_post_wr": 0.5,
  "5_breakout_post_pf": 2.964,
  "6_strongest_symbol_cell": {
    "cell": "MNQ",
    "evidence": "ANECDOTAL",
    "n": 4,
    "wins": 1,
    "losses": 3,
    "wr": 0.25,
    "pf": 1.513,
    "expectancy_r": 0.0599,
    "max_dd_r": -0.416,
    "pnl": -21.5,
    "avg_win_usd": 127.0,
    "avg_loss_usd": -49.5,
    "n_with_r": 4,
    "raw_wr": 0.25,
    "shrunk_wr": 0.4583,
    "prior_mean": 0.5
  },
  "7_strongest_session_cell": {
    "cell": "ny",
    "evidence": "ANECDOTAL",
    "n": 10,
    "wins": 5,
    "losses": 5,
    "wr": 0.5,
    "pf": 2.964,
    "expectancy_r": 0.2837,
    "max_dd_r": -0.978,
    "pnl": 1794.71,
    "avg_win_usd": 403.79,
    "avg_loss_usd": -44.85,
    "n_with_r": 10,
    "raw_wr": 0.5,
    "shrunk_wr": 0.5,
    "prior_mean": 0.5
  },
  "8_shared_traits_big_winners_anecdotal": [
    {
      "dir_4h": "-1"
    },
    {
      "overextended": "0"
    },
    {
      "near_pdh": "0"
    },
    {
      "near_pdl": "0"
    },
    {
      "momentum_aligned": "0"
    },
    {
      "local_score": "82"
    }
  ],
  "10_feature_rows_post": 21,
  "13_open_cl": {
    "trade_id": "PAPER-00222",
    "side": "SELL",
    "qty": 3,
    "entry": 82.74,
    "stop": 82.83555095672608,
    "target": 82.62156337356566,
    "opened_at": "2026-08-12 18:10:00",
    "session": "asia",
    "risk_dollars": 226.65287017822777,
    "reward_dollars": 385.30987930300853,
    "status": "OPEN"
  },
  "17_verdict": "ANECDOTAL \u2014 post_paperfix2 breakout n is small; do not promote. Collect overnight Asia/London before judging."
}
```

## Policy lock

- Keep `router_v1_paperfix2` overnight.
- No auto-tune from Asia/London tiny samples.
- Re-run: `python scripts/run_breakout_retest_forward_report.py`
