# How your trading bot works (plain English)

## The two Desktop icons

| Icon | What it does |
|---|---|
| **Start Trading Agent** | Turns the bot **ON**. Window open = running. Close it = bot stops. |
| **Open Agent Paper View** | Only **looks** at results. Does **not** start trading. |

## Red text in the window?

PowerShell often shows log lines in red even when things are fine.  
If you see lines like `INFO ... LIVE DATA` or `cycle session=...` → **working**.  
Only worry if you see `ERROR` / `Traceback` and it stops.

(We also fixed logging so new starts should look less “all red.”)

## When is it running?

Only while the **Start** window is open on your PC.

It checks about **every 1 minute** while running (whenever CME micros are open).

## What it trades

- **MES** — Micro S&P 500  
- **MNQ** — Micro Nasdaq-100  

Same products trade in Asia, London, and New York hours (one CME futures market, different sessions).

## When it can enter trades

**Default: whenever CME micros are open** (almost 24 hours).

It only pauses when the exchange is closed:

- Daily break ~**5:00–6:00 PM ET**
- Weekend gap **Friday ~5 PM → Sunday ~6 PM**

Trades are still labeled Asia / London / NY in the journal for learning.

## Trade details / getting smarter

Every trade logs:

- opened time, closed time  
- hold minutes  
- session name (asia / london / ny_…)  
- entry, exit, stop, target  
- P&L, win/loss, exit reason (stop / target / time)

See:

- Desktop → **Open Agent Paper View**  
- `data\trade_journal.csv` (spreadsheet for learning later)  
- `data\paper_trades.json`

Open trades auto-close when price hits stop or target (checked each cycle), or after **240 minutes** max hold.
