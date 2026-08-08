# Brokers for MES/MNQ + our Python agent

**Correction (important):** IBKR is **not** the best option if they ask you for **$100k liquid net worth proof** for futures. That is a suitability gate, not “deposit $100k.” If you can’t honestly provide that statement, **stop the IBKR futures path** and use one of the options below.

| Rank | Broker | Why it might fit you | Catch |
|---|---|---|---|
| **1 (realistic now)** | **Tradovate practice / personal** (you already have) | Real futures platform, micros, no IBKR-style $100k statement for most people | Native **API** still wants ~**$1k funded + ~$25/mo** for full automation |
| **2** | **Our agent in MOCK / paper sim** | $0, already works, tests the confluence strategy | Not real fills / not real money |
| **3** | **AMP / similar FCM** | Often easier to open for micros with smaller capital | Cheap to fund, but **API** (Rithmic etc.) is often expensive monthly |
| **4** | **NinjaTrader Brokerage** | Low day margins on micros | Automation is mostly **inside NinjaTrader**, not our Python agent |
| **5** | **IBKR** | Free Gateway API **if** they approve futures | Can demand **proof of ~$100k liquid net worth** (what hit you). Bad fit until that changes. |
| — | **TradeStation API** | — | Often ~**$10k** assets for API — worse |
| — | **PickMyTrade** | Bridge only | You said no — we won’t push it |

## Honest ranking for *your* situation

You want: autonomous agent + MES/MNQ + small capital later (~$300) + no $1k API gate + no fake net-worth docs.

**Right now the honest path is:**

1. Keep running the agent on **mock / sim** (strategy + risk logic).
2. Use **Tradovate practice** (or watch-only) so you learn the product.
3. When you can put ~**$1k** into Tradovate (or find an FCM with a cheap API), we wire **real** orders there.
4. Revisit IBKR only if your finances actually support their futures approval — do **not** fake statements.

IBKR was recommended as “cheapest API on paper.” That ignored their **futures suitability** screen. That was bad advice for your case.
