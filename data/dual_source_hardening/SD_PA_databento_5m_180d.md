# Supply/Demand + Price Action Research Report

**Verdict:** `WATCH`

Dual-source pass (databento_5m_180d). Hard gates WR>=65 n>=100.

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
Total trades generated: 4401
Configs tried: 12

## Best config per family (selected on TRAIN expectancy)
### supply_demand — `sd_v2_R2.0_imp1.5`
Params: `{'target_r': 2.0, 'impulse_atr': 1.5, 'allow_all_sessions': True}`
- **train**: n=1197 WR=0.457 PF=1.668 E=0.3192 DD=-11.65 gates_ok=False
- **val**: n=398 WR=0.4724 PF=1.663 E=0.2954 DD=-10.502 gates_ok=False
- **final**: n=411 WR=0.5109 PF=1.91 E=0.3995 DD=-13.283 gates_ok=False
- **all**: n=2006 WR=0.4711 PF=1.714 E=0.3309 DD=-13.283 gates_ok=False
- **stress**: n=None WR=None PF=None E=None DD=None gates_ok=False

### price_action — `pa_sweep_R2.0_lb20`
Params: `{'target_r': 2.0, 'lookback': 20, 'allow_all_sessions': True}`
- **train**: n=1414 WR=0.4173 PF=1.285 E=0.1149 DD=-32.252 gates_ok=False
- **val**: n=509 WR=0.4047 PF=1.236 E=0.099 DD=-17.042 gates_ok=False
- **final**: n=472 WR=0.4386 PF=1.338 E=0.1288 DD=-16.485 gates_ok=False
- **all**: n=2395 WR=0.4188 PF=1.284 E=0.1142 DD=-32.252 gates_ok=False
- **stress**: n=None WR=None PF=None E=None DD=None gates_ok=False

## Top cells by WR (n≥15)
| family | strategy | cell | n | WR | PF | E | gates |
|---|---|---|---:|---:|---:|---:|---|

## Promotion rule
- **READY** → may wire one locked paper engine (manual). - **WATCH/FAIL** → keep `router_v1_specialists_only`; do not re-enable location spray.
