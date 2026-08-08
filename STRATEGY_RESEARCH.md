# Strategy research — what we run, and why

## Plain answer to “what are you doing for strategy?”

**Default now = multi-strategy CONFLUENCE (August 2026 high-probability style).**

We run several engines. A trade only happens when **at least 2 agree on the same direction**:

| Engine | Style |
|---|---|
| `liquidity_sweep` | PDH/PDL liquidity raid → reclaim + VWAP filter (MM-style liquidity) |
| `vwap_acceptance` | VWAP / prior-value mean reversion (high hit-rate style) |
| `sweep_retest` | Your PDH/PDL sweep-retest logic |
| `vwap_orb` | *(off by default)* ORB was too sprayy alone on delayed Yahoo data |

That is a **real combination**, not mush: disagreement = **no trade**.  
Fewer trades, higher selectivity (aiming toward the 65–75% “only A+ setups” idea from 2026 confluence/ICT playbooks).

TradingView alerts are **optional**. Full autonomy does **not** need them — the agent watches the market itself.

---

## What “high performing” means here (not TikTok win rate)

We rank strategies by:

1. **Expectancy** (avg $ / trade after costs) — most important  
2. **Profit factor** / drawdown — survivability (critical for funded)  
3. **Win rate** — useful, but a 55% strategy with 2R can beat an 80% strategy with tiny targets  
4. **Automatable + Topstep rules** — flatten by ~3:10 CT, no overnight, 1 contract while proving  

There is still **no 100% strategy**. “High performing” = best *evidence + fit for MES/MNQ funded rules*, not magic.

---

## Why VWAP / value acceptance as the high-performer pick

Among public writeups and systematic notes for **MES/MNQ**:

- **VWAP / POC (value) acceptance** — often cited around **~60%+ hit rate with ~2R** when filtered (skip strong trend days, require “acceptance” not a spike-through). That matches your “I want high performing / high success rate” preference better than raw ORB.  
- **Raw ORB / many liquidity-grab variants** — several careful MNQ studies show they **fail after friction** when naively automated on 5m bars.  
- **Your Sweep Retest** — can be strong discretionary; not independently #1 in public research, so it’s confluence/optional, not the sole default.

**Caveat:** Blog backtests are not peer-reviewed proof. We still dry-run → Tradovate practice → only then Topstep funded.

---

## Recommended operating mode for you

```
HIGH_PERFORMANCE mode (default):
  Engine: vwap_acceptance
  Optional: require_tv_alert_confluence = true  (your alert must agree)
  Size: 1 MES (or 1 MNQ)
  Target: ~$150 | Max risk: ~$100
  Flatten: 15:05 CT
```

When the day is a **strong trend day**, acceptance fades get skipped (filter).  
Later we can auto-switch to `vwap_orb` on trend days (regime switch) — that’s a next upgrade.

---

## Your accounts (how they fit)

| Account | Use |
|---|---|
| **TradingView** | Alerts / charts (optional confluence) |
| **Tradovate (personal)** | Practice / personal capital while hashing the strategy — **do this first** |
| **TopstepX** | Funded automation later via TopstepX/ProjectX API (not the Tradovate API) |
| **Combines** | You’d rather skip — fair. Strategy must be proven on Tradovate first; funded still usually requires an evaluation path unless you already have active funded |

**Important:** TopstepX ≠ Tradovate. Two different APIs. We practice on Tradovate; we add TopstepX order routing when you’re ready for funded.
