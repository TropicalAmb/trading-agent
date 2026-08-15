# Long-History Regime Selector

**Status: FAIL**

This research-only router can permit a frozen base family only when old-regime entry features predict a win. It does not alter paper configuration.

- Threshold selected on validation only: 0.45
- Development: n=236, WR=50.4%, PF=0.89, E=-0.053R
- Validation: n=94, WR=50.0%, PF=1.39, E=+0.130R
- Holdout: n=107, WR=31.8%, PF=0.55, E=-0.245R
- Paid recent: n=4, WR=75.0%, PF=95.04, E=+0.526R
- Yahoo current: n=1, WR=100.0%, PF=999.00, E=+0.939R
- Gate failures: validation_WR<70%, validation_E<0.15R, holdout_WR<70%, holdout_PF<1.30, holdout_E<0.15R, paid_n<10, yahoo_n<10