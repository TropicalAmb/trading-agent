# Bridge + Tradovate DEMO setup (your plan)

**Goal:** See real automated orders on **Tradovate demo money** (not your cash).  
**Later:** Put ~$300 into live Tradovate when you’re comfortable (no $1k API needed with the bridge).  
**Skip:** Topstep Combine.

```
Our strategy / TradingView alert
        ↓
PickMyTrade (5-day free trial bridge)
        ↓
YOUR Tradovate DEMO account  ← fake money, real plumbing
```

---

## About putting $300 in later (yes, that makes sense)

With the **bridge**, you usually **do not** need Tradovate’s **$1,000 + $25 API**.  
~$300 live later can work for **1 micro** (MES/MNQ), but it’s tight:

- One bad day can wipe a big chunk of $300  
- Start with **1 contract**, hard daily loss stop  
- Demo first until you’re comfortable  

---

## What you need

1. **Tradovate** login (use **Simulation / Demo**)  
2. **PickMyTrade** free trial — https://pickmytrade.trade/ (no credit card for trial)  
3. **TradingView** plan that supports **webhooks** (Essential/Pro or higher — free TV cannot send webhooks)

If your TradingView is free, tell me — we’ll use a workaround (agent posts to the bridge from your PC).

---

## Step-by-step (do this in order)

### A) Tradovate demo

1. Go to https://trader.tradovate.com/  
2. Log in  
3. Choose **Access Simulation Environment** (demo) — not live  
4. Leave it logged in / confirm you can see MES or MNQ charts  

### B) PickMyTrade trial

1. Open https://pickmytrade.trade/  
2. Start **5-day free trial** (no credit card)  
3. In the dashboard: **Connect broker** → **Tradovate**  
4. Log in with the **same** Tradovate credentials  
5. Select the **DEMO / simulation** account (double-check — not live)  
6. Set defaults:  
   - Quantity: **1**  
   - Symbol: **MES** (or MNQ)  
   - Stop / take-profit as you like (e.g. risk ~$75–100, target ~$150)  

### C) Generate webhook

1. In PickMyTrade click **Generate Alert**  
2. Copy:  
   - **Webhook URL**  
   - **JSON message** (Buy and Sell if they give both)  
3. Paste those into:

   `C:\Users\patri\trading-agent\CREDENTIALS.txt`

   under the PickMyTrade section (see below).

### D) TradingView alert (if you have webhook-capable TV)

1. Open a **MES** chart (or MNQ)  
2. Create **Alert**  
3. Message = paste PickMyTrade **JSON**  
4. Notifications → check **Webhook URL** → paste PickMyTrade URL  
5. For a quick test: condition that will fire soon (or “Any alert() function call” on a test script)  
6. Create alert  

### E) Confirm it worked

1. When alert fires → check **PickMyTrade** log  
2. Check **Tradovate demo** → order / position appeared  
3. Tell me: **“demo order showed up”** or **“stuck at step ___”**

---

## After demo looks good

1. End of trial: decide if $50/mo bridge is worth it  
2. Fund **live** Tradovate with what you can (~$300 if that’s your max)  
3. In PickMyTrade, switch connection from **demo → live** (careful)  
4. Keep size at **1 micro**

---

## Paste here in CREDENTIALS.txt (after you get them)

```
PICKMYTRADE_WEBHOOK_URL=
PICKMYTRADE_BUY_JSON=
PICKMYTRADE_SELL_JSON=
TRADOVATE_MODE=demo
```
