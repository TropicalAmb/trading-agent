# Connect Tradovate (what YOU do — once)

## Do you need the $25 API + $1,000?

**For our Python bot talking to Tradovate’s API directly: yes (today’s rules).**

| Item | Included in normal account? | Notes |
|---|---|---|
| **API Access add-on** | **No — separate ~$25/month** | Not bundled with a basic Tradovate login |
| **~$1,000 in a live account** | **Yes, required to unlock API** | Subscribe button stays greyed out without it |
| Prop / Topstep accounts | Usually **cannot** buy Tradovate API keys | Different path (TopstepX / bridges) |

So: the $25 is **not** “included for free.” It’s an add-on. And Tradovate wants a **live funded** account (~$1k) before you can buy that add-on.

**If you can’t put $1,000 in yet — that’s fine.** We keep improving the agent in **mock / dry-run** (no money needed). You’re not blocked from building.

## Ways to automate WITHOUT Tradovate’s $25 + $1k API

| Path | Need $1k Tradovate API? | Rough cost | Notes |
|---|---|---|---|
| **Keep building on mock** (now) | No | $0 | Strategy work continues; no real orders |
| **Webhook bridge** (PickMyTrade / TradersPost) | Often **no** (they’re a vendor) | ~$50/mo + TradingView webhook plan | TradingView alert → bridge → your Tradovate/prop account |
| **TopstepX API** (later for funded) | No Tradovate API | ~$14.50–$29/mo | Separate from Tradovate personal |
| **Direct Tradovate API** (our Python client) | **Yes** | $25/mo + $1k balance | Full control; what we coded for |

You do **not** have to choose the $1k path right now.

## Steps

1. Log into [Tradovate](https://trader.tradovate.com/) in your browser.  
2. Top right → **Application Settings**.  
3. **Add-Ons** → activate **API Access** (paid).  
4. **API Access** tab → **Generate API Key**.  
5. Copy **CID** and **Secret** (shown once). Also note the **dedicated API password** if they give one.  
6. On your PC, open this file in Notepad:

   `C:\Users\patri\trading-agent\.env`

   (If missing, copy from `.env.example`.)

7. Fill in:

```env
BROKER_BACKEND=tradovate
TRADOVATE_DEMO=false
TRADOVATE_USERNAME=your_username
TRADOVATE_PASSWORD=your_api_or_account_password
TRADOVATE_CID=123
TRADOVATE_SEC=your-secret-here
TRADOVATE_APP_ID=trading-agent
TRADOVATE_APP_VERSION=1.0
```

8. Tell me in chat: **“credentials are in .env”** (do **not** paste the password here).  
9. I will run the connection test and keep `dry_run: true` until you say to go live.

## After connect — autonomy

I start the agent (or you double-click a start script).  
It runs on your PC and sends orders to Tradovate when confluence says so.  
You watch P&L in the Tradovate app — you don’t place the trades.
