# Supply/Demand + Price Action Research Report

**Verdict:** `FAIL`

Dual-source pass (yahoo_5m_60d). Hard gates WR>=65 n>=100.

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
Total trades generated: 1423
Configs tried: 12

## Best config per family (selected on TRAIN expectancy)
### supply_demand — `sd_v2_R1.5_imp1.5`
Params: `{'target_r': 1.5, 'impulse_atr': 1.5, 'allow_all_sessions': True}`
- **train**: n=485 WR=0.4289 PF=0.892 E=-0.0673 DD=-50.16 gates_ok=False
- **val**: n=160 WR=0.3563 PF=0.675 E=-0.225 DD=-44.9 gates_ok=False
- **final**: n=174 WR=0.408 PF=0.758 E=-0.1576 DD=-29.988 gates_ok=False
- **all**: n=819 WR=0.4103 PF=0.817 E=-0.1173 DD=-108.291 gates_ok=False
- **stress**: n=None WR=None PF=None E=None DD=None gates_ok=False

### price_action — `pa_sweep_R2.0_lb12`
Params: `{'target_r': 2.0, 'lookback': 12, 'allow_all_sessions': True}`
- **train**: n=347 WR=0.3746 PF=0.993 E=-0.0045 DD=-25.806 gates_ok=False
- **val**: n=145 WR=0.3172 PF=0.782 E=-0.1632 DD=-31.137 gates_ok=False
- **final**: n=112 WR=0.3125 PF=0.73 E=-0.1988 DD=-22.925 gates_ok=False
- **all**: n=604 WR=0.3493 PF=0.889 E=-0.0786 DD=-63.941 gates_ok=False
- **stress**: n=None WR=None PF=None E=None DD=None gates_ok=False

## Top cells by WR (n≥15)
| family | strategy | cell | n | WR | PF | E | gates |
|---|---|---|---:|---:|---:|---:|---|

## Promotion rule
- **READY** → may wire one locked paper engine (manual). - **WATCH/FAIL** → keep `router_v1_specialists_only`; do not re-enable location spray.
