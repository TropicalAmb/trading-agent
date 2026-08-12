# High-confidence research pass

**Verdict: NO CANDIDATE YET MEETS HIGH-CONFIDENCE STANDARD**

- Configs tested: 84
- Families: 10 (EMA_pullback, FVG_retest, MTF_EMA_pullback, PDH_PDL_sweep, PDH_PDL_sweep_MSS, Sweep_MSS_FVG, VWAP_reclaim, VWAP_rejection, opening_range, trend_continuation)
- Total OOS trades evaluated: 8652
- Champion candidates (all gates): 0

## Gates
`{'min_wr': 0.65, 'min_pf': 1.5, 'min_expectancy_r': 0.25, 'min_n': 100}`

## Top 10 (R-space only)

| Strategy | TF | n | WR | PF | E[R] | MaxDD[R] | /wk | WorstR | Gates |
|----------|----|---|----|----|------|----------|-----|--------|-------|
| ORB5_first_break_vwap1_1.5 | 5m | 10 | 70.0% | 3.862 | 0.6657 | -1.283 | 6.95 | -1.043 | False |
| ORB5_first_break_vwap1_1.0 | 5m | 10 | 80.0% | 5.387 | 0.5657 | -1.043 | 6.95 | -1.043 | False |
| ORB5_first_break_vwap1_1.25 | 5m | 10 | 70.0% | 3.217 | 0.5157 | -1.283 | 6.95 | -1.043 | False |
| TrendCont_1.0 | 1h | 120 | 57.5% | 1.288 | 0.1252 | -6.29 | 4.83 | -1.079 | False |
| TrendCont_1.25 | 1h | 120 | 50.0% | 1.195 | 0.1002 | -7.764 | 4.83 | -1.079 | False |
| TrendCont_2.0 | 1h | 120 | 37.5% | 1.157 | 0.1002 | -11.384 | 4.83 | -1.079 | False |
| TrendCont_1.5 | 1h | 120 | 44.2% | 1.139 | 0.0794 | -9.29 | 4.83 | -1.079 | False |
| VWAP_reclaim_2.0 | 1h | 404 | 35.6% | 1.052 | 0.0341 | -25.081 | 16.16 | -1.089 | False |
| FVG_2.0 | 1h | 292 | 35.6% | 0.999 | -0.0008 | -17.29 | 34.04 | -1.242 | False |
| VWAP_reclaim_1.25 | 1h | 404 | 45.3% | 0.985 | -0.0084 | -25.762 | 16.16 | -1.089 | False |

## Hard risk (restored)
{
  "risk_per_trade_pct": 0.01,
  "max_account_risk_per_trade": 500,
  "max_risk_dollars_per_trade": 500,
  "max_total_open_risk_dollars": 3500,
  "max_daily_loss_dollars": 4000,
  "max_correlated_risk_dollars": 1500
}

## Active bot changes
- Restored finite risk: max_risk_dollars_per_trade=500, risk_per_trade_pct=0.01, max_account_risk_per_trade=500
- Oversized full-size setups → SHADOW + suggest micro (not unlimited risk)
- No champion swap — gates not used to promote a new live strategy
- Paper mode unchanged; quantity not increased from this pass