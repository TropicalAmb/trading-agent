# Cheapest path (no $1,000)

## Opening credentials (if `.env` won’t open)

Use this file instead (normal Notepad file):

`C:\Users\patri\trading-agent\CREDENTIALS.txt`

Or in PowerShell:

```powershell
notepad C:\Users\patri\trading-agent\CREDENTIALS.txt
```

(We can copy those values into `.env` later.)

---

## Cost ranking for YOUR situation

You: no $1k for Tradovate API, no Topstep **funded** account yet, have TradingView + Tradovate + Topstep (not funded).

| Rank | Path | Money needed now | Can auto-trade MES/MNQ for real? |
|---|---|---|---|
| **1 (now)** | Keep agent in **mock / dry-run** | **$0** | No real money — builds/tests strategy |
| **2** | **Topstep Combine** + later TopstepX API | Combine fee (varies, often ~$50–150+) then API ~$15–29/mo when automating | Yes, on prop capital after you pass |
| **3** | **Webhook bridge** (PickMyTrade etc.) | Bridge ~$0 trial then ~$50/mo + TradingView plan with webhooks | Often works with demo / some prop links **without** Tradovate’s $1k API |
| **4** | Tradovate direct API | **~$1,000 balance + $25/mo** | Skip for now |
| — | **TradingView alone** | TV subscription | **No** — charts/alerts only, cannot place futures orders by itself |

### Important clarifications

- **TradingView is not a broker API for MES/MNQ.** It can *signal*; something else must *execute*.
- **Topstep without funded** = you still need a **Combine** (evaluation) before funded. There’s no free funded account.
- **Cheapest real path** if you want live automation soon without $1k:  
  **TradingView alerts → bridge (trial) → Tradovate demo/sim or Topstep when you buy a combine**  
  OR stay at **$0 mock** until you can afford a combine.

---

## Recommended for you this week

1. **$0** — keep using the agent in mock (strategy work).  
2. When ready to spend a little: try a **bridge free trial** (no $1k).  
3. When ready for prop capital: buy a **Topstep Combine**, pass it, then automate via **TopstepX** or a bridge — still no Tradovate $1k required.
