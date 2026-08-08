# Your real accounts — how they fit

## What you have

| Account | What it is | Role for the agent |
|---|---|---|
| **TradingView** | Charts + alerts | Optional confluence (your alerts must agree) |
| **Tradovate (personal)** | Your futures broker | **Practice / prove strategy here first** |
| **Topstep on TopstepX** | Prop firm on ProjectX | **Funded later** — different API than Tradovate |
| Combines | Evaluation | You want to skip for now — OK. Prove on Tradovate first |

**TopstepX ≠ Tradovate.**  
Same “futures world,” different login/API. We wire **Tradovate personal** now; **TopstepX API** when you’re ready for funded.

## Plan that matches what you said

1. Hash a **high-performing** strategy on data + dry-run (`vwap_acceptance`).  
2. Connect **Tradovate personal** (demo/live small).  
3. Only after stats look good → Topstep **funded** path (TopstepX API). No rush into combines.

## Strategy (short)

See `STRATEGY_RESEARCH.md`.

- Default: **VWAP/POC acceptance** (high hit-rate style)  
- Your alerts: optional **confluence gate**, not the whole brain  
- Not “average my script with research into mush”

## Credentials you’ll need (when ready)

**Tradovate personal `.env`:** username, password, app cid/sec, account id  
**TopstepX later:** API key from TopstepX/ProjectX settings (~$14.50–29/mo API access)

Never paste passwords into chat — only into local `.env`.
