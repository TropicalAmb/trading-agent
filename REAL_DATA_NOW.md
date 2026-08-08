# Real data without $1k Tradovate / without IBKR $100k proof

## Stop the circle — what’s real vs fake

| Piece | Status today | Cost |
|---|---|---|
| **Market bars for strategy** | **REAL** via Yahoo Finance (`MES=F`, `MNQ=F`) | $0 |
| **TradingView alerts into agent** | Ready — needs webhook URL (ngrok) + TV plan that allows webhooks | $0–TV subscription |
| **Broker order API (Tradovate)** | Blocked until ~$1k funded + API add-on | ~$1k |
| **IBKR futures** | Blocked by their net-worth suitability for you | N/A |

`--mock` / dry-run = **fake order routing only**.  
Strategy prices are **not** dummy if Yahoo returns bars (prove with `scripts\Show-Live-Data.ps1`).

Yahoo is usually **~10–15 minutes delayed** vs CME. Good enough to stop “dummy data” and run the logic. Not exchange-grade tick data.

---

## Option A — Prove Yahoo live data (do this in 10 seconds)

Double-click / run:

`C:\Users\patri\trading-agent\scripts\Show-Live-Data.ps1`

You should see last close + bar time for MES and MNQ.

---

## Option B — TradingView → agent (real chart prices / signals)

TradingView **cannot** be a full free bar history API for our Python loop.  
It **can** send **real alerts** (with `{{close}}`) into our agent.

### You need
1. TradingView plan that supports **webhooks** (not the free plan).
2. **ngrok** (free) so TradingView’s cloud can reach your PC.
3. Agent running with webhook on (already default in config).

### Steps
1. Install ngrok: https://ngrok.com/download  
2. Start agent: `scripts\Start-Agent.ps1` (leave window open)  
3. In another terminal: `ngrok http 8787`  
4. Copy the `https://....ngrok.app` URL  
5. In TradingView alert → Webhook URL:

```
https://YOUR-NGROK-ID.ngrok.app/tv?secret=YOUR_SECRET
```

Use the same secret as `WEBHOOK_SECRET` in `CREDENTIALS.txt`.

6. Alert message (JSON):

```json
{"action":"BUY","symbol":"MES","price":{{close}},"time":"{{timenow}}"}
```

(or `"SELL"`). Use a condition on your chart / strategy.

When it fires, the agent logs: `TradingView REAL alert ... price=...`

---

## Option C — What is still impossible at $0

- Tradovate **order** API without their live funded + API subscription  
- Free **official CME real-time** tick stream into our agent  
- IBKR Gateway for you while they demand $100k liquid-net-worth proof  

Those are broker/exchange gates, not something we can code around.

---

## What to do next (pick one)

1. Run **Show-Live-Data** and confirm you see real MES/MNQ numbers.  
2. If you have TradingView webhooks: say **“set up TradingView”** and we’ll wire ngrok + secret with you.  
3. Keep agent on Yahoo bars + mock/dry-run orders until you can fund a broker API.
