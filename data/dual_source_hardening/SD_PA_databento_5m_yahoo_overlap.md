# Supply/Demand + Price Action Research Report

**Verdict:** `WATCH`

Dual-source pass (databento_5m_yahoo_overlap). Hard gates WR>=65 n>=100.

## Gates
```
{
  "min_wr": 0.65,
  "min_pf": 1.5,
  "min_expectancy_r": 0.25,
  "min_n": 100,
  "max_worst_loss_r": -5.0,
  "min_med_win_over_med_loss": 0.35
}
```

Friction: same as sd_pa_research
Total trades generated: 1779
Configs tried: 12

## Best config per family (selected on TRAIN expectancy)
### supply_demand — `sd_v2_R2.0_imp1.5`
Params: `{'target_r': 2.0, 'impulse_atr': 1.5, 'allow_all_sessions': True}`
- **train**: n=481 WR=0.4865 PF=1.787 E=0.3476 DD=-10.502 gates_ok=False
- **val**: n=146 WR=0.4589 PF=1.446 E=0.2111 DD=-12.987 gates_ok=False
- **final**: n=176 WR=0.5227 PF=2.045 E=0.4463 DD=-6.459 gates_ok=False
- **all**: n=803 WR=0.4894 PF=1.776 E=0.3444 DD=-13.283 gates_ok=False
- **stress**: n=None WR=None PF=None E=None DD=None gates_ok=False

### price_action — `pa_sweep_R2.0_lb20`
Params: `{'target_r': 2.0, 'lookback': 20, 'allow_all_sessions': True}`
- **train**: n=596 WR=0.4312 PF=1.299 E=0.1211 DD=-17.042 gates_ok=False
- **val**: n=203 WR=0.5025 PF=1.854 E=0.2923 DD=-12.424 gates_ok=False
- **final**: n=177 WR=0.2994 PF=0.75 E=-0.1139 DD=-22.24 gates_ok=False
- **all**: n=976 WR=0.4221 PF=1.284 E=0.1141 DD=-23.046 gates_ok=False
- **stress**: n=None WR=None PF=None E=None DD=None gates_ok=False

## Top cells by WR (n≥15)
| family | strategy | cell | n | WR | PF | E | gates |
|---|---|---|---:|---:|---:|---:|---|

## Promotion rule
- **READY** → may wire one locked paper engine (manual). - **WATCH/FAIL** → keep `router_v1_specialists_only`; do not re-enable location spray.
