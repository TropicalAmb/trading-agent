# High-Precision NQ State Model

**Status: FAIL**

- Frozen validation threshold: 0.55
- Model: `HistGradientBoostingClassifier` with predeclared shallow depth and regularization
- Feature timing: completed 15m signal bar; next 15m open entry; no future/unfinished features

| Segment | n | WR | PF | Expectancy |
|---|---:|---:|---:|---:|
| Development | 301 | 55.5% | 1.24 | +0.085R |
| Validation | 139 | 49.6% | 1.22 | +0.086R |
| Untouched long holdout | 188 | 45.2% | 1.08 | +0.032R |
| Paid Databento current | 39 | 46.2% | 1.30 | +0.113R |
| Independent Yahoo current | 13 | 53.8% | 1.65 | +0.213R |

## Promotion decision

No paper change. Gate failures: validation_WR<70%, validation_PF<1.30, validation_E<0.15R, holdout_WR<70%, holdout_PF<1.30, holdout_E<0.15R, paid_WR<70%, yahoo_WR<70%

The label is used only for development training. Every displayed performance row comes from the configured two-contract replay with stop-first ambiguity and friction.
