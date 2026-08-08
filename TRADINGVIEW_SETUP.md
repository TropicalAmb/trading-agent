# TradingView + daily paper view

## What you asked for

> When the AI bot makes orders, will I see it in my TradingView paper view?

**No.** TradingView does **not** give retail bots an API to push orders into **TradingView → Paper Trading**. That panel only shows trades TradingView itself places (you click, or a Pine `strategy` on their platform).

What we set up instead:

```
TradingView chart alert  →  webhook  →  our agent  →  LOCAL Paper Trading View
                                                      (data/paper_trading_view.html)
```

Check **`data\paper_trading_view.html`** every day (or `scripts\Open-Paper-View.ps1`).  
When you later fund Tradovate (~$1k API path), the same agent can send **real** broker orders — those show in **Tradovate**, still not in TV Paper Trading.

---

## Daily routine

1. Run `scripts\Setup-TradingView.ps1` (or `Start-Agent.ps1`) — leave window open  
2. Open paper view: `scripts\Open-Paper-View.ps1`  
3. Optional: keep ngrok running so TradingView alerts can reach your PC  

---

## TradingView alert (one-time in TV)

1. Chart MES or MNQ  
2. Create alert → enable **Webhook URL** (needs a paid TV plan that includes webhooks)  
3. URL (after ngrok):

```
https://YOUR-NGROK-HOST/tv?secret=YOUR_SECRET_FROM_CREDENTIALS
```

4. Message:

```json
{"action":"BUY","symbol":"MES","price":{{close}},"time":"{{timenow}}"}
```

Use `SELL` for shorts. Secret is in `CREDENTIALS.txt` → `WEBHOOK_SECRET`.

5. Local test without TradingView: with agent running, run `scripts\Test-TradingView-Webhook.ps1`

---

## Prove it works right now (no TV account steps)

```
scripts\Open-Paper-View.ps1
```

You should already see a demo `PAPER-00001` BUY MES fill from setup.  
That is your “paper trading section” for this bot.
