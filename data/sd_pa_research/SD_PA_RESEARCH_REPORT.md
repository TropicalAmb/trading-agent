# Supply/Demand + Price Action Research Report

**Verdict:** `FAIL`

No supply_demand or price_action config cleared promotion gates.

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

Friction: Friction: 2 ticks slip + 1 tick buffer per side; fixed-R targets; no lookahead on entry bar; 60/20/20 chronological freeze before selection.
Total trades generated: 9633
Configs tried: 12

## Best config per family (selected on TRAIN expectancy)
### supply_demand — `sd_v2_R1.5_imp1.5`
Params: `{'target_r': 1.5, 'impulse_atr': 1.5, 'allow_all_sessions': True}`
- **train**: n=485 WR=0.4289 PF=0.892 E=-0.0673 DD=-40.267 gates_ok=False
- **val**: n=160 WR=0.3563 PF=0.675 E=-0.225 DD=-41.156 gates_ok=False
- **final**: n=174 WR=0.408 PF=0.758 E=-0.1576 DD=-35.303 gates_ok=False
- **all**: n=819 WR=0.4103 PF=0.817 E=-0.1173 DD=-113.309 gates_ok=False
- **stress**: n=819 WR=0.4066 PF=0.714 E=-0.1973 DD=-172.162 gates_ok=False
- folds: f1:n=204 wr=0.4314 E=-0.0329, f2:n=204 wr=0.4118 E=-0.1125, f3:n=204 wr=0.3971 E=-0.1546, f4:n=207 wr=0.401 E=-0.1685

### price_action — `pa_sweep_R2.0_lb12`
Params: `{'target_r': 2.0, 'lookback': 12, 'allow_all_sessions': True}`
- **train**: n=347 WR=0.3746 PF=0.993 E=-0.0045 DD=-19.287 gates_ok=False
- **val**: n=145 WR=0.3172 PF=0.782 E=-0.1632 DD=-33.097 gates_ok=False
- **final**: n=112 WR=0.3125 PF=0.73 E=-0.1988 DD=-24.182 gates_ok=False
- **all**: n=604 WR=0.3493 PF=0.889 E=-0.0786 DD=-65.197 gates_ok=False
- **stress**: n=604 WR=0.3477 PF=0.791 E=-0.1586 DD=-105.49 gates_ok=False
- folds: f1:n=151 wr=0.3775 E=0.0019, f2:n=151 wr=0.404 E=0.0781, f3:n=151 wr=0.298 E=-0.2223, f4:n=151 wr=0.3179 E=-0.1722

## Top cells by WR (n≥15)
| family | strategy | cell | n | WR | PF | E | gates |
|---|---|---|---:|---:|---:|---:|---|
| supply_demand | `sd_v2_R1.5_imp1.5` | CL|NY_MID|BUY | 17 | 0.7059 | 2.027 | 0.3504 | False |
| price_action | `pa_sweep_R2.0_lb12` | GC|ASIA|SELL | 22 | 0.6818 | 4.321 | 1.0195 | False |
| supply_demand | `sd_v2_R1.5_imp1.5` | CL|LONDON|SELL | 31 | 0.5806 | 1.659 | 0.3171 | False |
| supply_demand | `sd_v2_R1.5_imp1.5` | ALL|NY_MID|BUY | 37 | 0.5135 | 1.083 | 0.0423 | False |
| supply_demand | `sd_v2_R1.5_imp1.5` | ALL|NY_AFT|SELL | 32 | 0.5 | 1.295 | 0.1438 | False |
| price_action | `pa_sweep_R2.0_lb12` | CL|ASIA|SELL | 20 | 0.5 | 1.336 | 0.2057 | False |
| supply_demand | `sd_v2_R1.5_imp1.5` | GC|ASIA|BUY | 46 | 0.4783 | 1.249 | 0.133 | False |
| supply_demand | `sd_v2_R1.5_imp1.5` | CL|ALL|SELL | 108 | 0.4722 | 0.965 | -0.0215 | False |
| price_action | `pa_sweep_R2.0_lb12` | ALL|NY_AFT|BUY | 31 | 0.4516 | 1.281 | 0.169 | False |
| price_action | `pa_sweep_R2.0_lb12` | GC|ALL|SELL | 58 | 0.4483 | 1.427 | 0.2408 | False |
| supply_demand | `sd_v2_R1.5_imp1.5` | GC|ASIA|SELL | 29 | 0.4483 | 1.101 | 0.0597 | False |
| supply_demand | `sd_v2_R1.5_imp1.5` | NQ|LONDON|BUY | 27 | 0.4444 | 1.066 | 0.0361 | False |
| price_action | `pa_sweep_R2.0_lb12` | ES|LONDON|BUY | 18 | 0.4444 | 1.184 | 0.1179 | False |
| supply_demand | `sd_v2_R1.5_imp1.5` | GC|ALL|BUY | 106 | 0.4434 | 1.05 | 0.0283 | False |
| supply_demand | `sd_v2_R1.5_imp1.5` | NQ|ASIA|SELL | 34 | 0.4412 | 1.042 | 0.0245 | False |
| supply_demand | `sd_v2_R1.5_imp1.5` | ES|LONDON|SELL | 39 | 0.4359 | 0.759 | -0.1643 | False |
| supply_demand | `sd_v2_R1.5_imp1.5` | NQ|ALL|SELL | 101 | 0.4356 | 1.098 | 0.0546 | False |
| supply_demand | `sd_v2_R1.5_imp1.5` | ALL|NY_MID|SELL | 30 | 0.4333 | 0.948 | -0.0278 | False |
| supply_demand | `sd_v2_R1.5_imp1.5` | CL|ALL|BUY | 95 | 0.4316 | 0.77 | -0.1502 | False |
| supply_demand | `sd_v2_R1.5_imp1.5` | ALL|LONDON|SELL | 134 | 0.4254 | 0.914 | -0.0541 | False |
| supply_demand | `sd_v2_R1.5_imp1.5` | GC|LONDON|BUY | 33 | 0.4242 | 1.08 | 0.0457 | False |
| price_action | `pa_sweep_R2.0_lb12` | ALL|ASIA|SELL | 98 | 0.4184 | 1.192 | 0.1246 | False |
| supply_demand | `sd_v2_R1.5_imp1.5` | ES|ALL|SELL | 108 | 0.4167 | 0.775 | -0.1483 | False |
| supply_demand | `sd_v2_R1.5_imp1.5` | ALL|ASIA|SELL | 159 | 0.4151 | 0.808 | -0.1275 | False |
| supply_demand | `sd_v2_R1.5_imp1.5` | CL|ASIA|SELL | 53 | 0.4151 | 0.675 | -0.2342 | False |
| price_action | `pa_sweep_R2.0_lb12` | ES|ALL|BUY | 68 | 0.4118 | 1.098 | 0.0658 | False |
| price_action | `pa_sweep_R2.0_lb12` | ALL|NY_OPEN|SELL | 22 | 0.4091 | 1.167 | 0.1013 | False |
| price_action | `pa_sweep_R2.0_lb12` | ES|LONDON|SELL | 22 | 0.4091 | 1.055 | 0.0384 | False |
| supply_demand | `sd_v2_R1.5_imp1.5` | NQ|LONDON|SELL | 37 | 0.4054 | 1.025 | 0.0143 | False |
| price_action | `pa_sweep_R2.0_lb12` | ALL|NY_MID|SELL | 35 | 0.4 | 1.096 | 0.0603 | False |
| supply_demand | `sd_v2_R1.5_imp1.5` | NQ|NY_OPEN|SELL | 15 | 0.4 | 1.077 | 0.0423 | False |
| supply_demand | `sd_v2_R1.5_imp1.5` | ALL|ASIA|BUY | 164 | 0.3963 | 0.785 | -0.1461 | False |
| price_action | `pa_sweep_R2.0_lb12` | ALL|NY_AFT|SELL | 28 | 0.3929 | 1.003 | 0.002 | False |
| supply_demand | `sd_v2_R1.5_imp1.5` | ALL|NY_AFT|BUY | 51 | 0.3922 | 0.641 | -0.2231 | False |
| price_action | `pa_sweep_R2.0_lb12` | ES|ALL|SELL | 69 | 0.3913 | 0.96 | -0.029 | False |
| supply_demand | `sd_v2_R1.5_imp1.5` | CL|LONDON|BUY | 31 | 0.3871 | 0.772 | -0.1584 | False |
| supply_demand | `sd_v2_R1.5_imp1.5` | ES|ASIA|BUY | 44 | 0.3864 | 0.603 | -0.3054 | False |
| supply_demand | `sd_v2_R1.5_imp1.5` | ALL|LONDON|BUY | 120 | 0.3833 | 0.775 | -0.151 | False |
| supply_demand | `sd_v2_R1.5_imp1.5` | NQ|ASIA|BUY | 47 | 0.383 | 0.891 | -0.0693 | False |
| price_action | `pa_sweep_R2.0_lb12` | NQ|LONDON|BUY | 29 | 0.3793 | 1.174 | 0.1114 | False |

## Promotion rule
- **READY** → may wire one locked paper engine (manual). - **WATCH/FAIL** → keep `router_v1_specialists_only`; do not re-enable location spray.
