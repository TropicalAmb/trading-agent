# Start here (no coding experience needed)

**Confused? Read [`SIMPLE_GUIDE.md`](SIMPLE_GUIDE.md) first.**

Then:
- [`TRADOVATE_CONNECT.md`](TRADOVATE_CONNECT.md) — how *you* connect Tradovate once  
- [`STRATEGY_RESEARCH.md`](STRATEGY_RESEARCH.md) — multi-strategy confluence (high selectivity)

**Everyday autonomy (after connect):** double-click / run:

```powershell
.\scripts\Start-Agent.ps1
```

Leave that window open. The agent trades for you. You are not meant to type PowerShell all day.

---

## Step 1 — Open a terminal in the project

1. Press the Windows key, type **PowerShell**, open it.
2. Paste this and press Enter:

```powershell
cd C:\Users\patri\trading-agent
```

You should now be “inside” the trading-agent folder.

---

## Step 2 — One-time setup (only the first time)

Paste this whole block and press Enter:

```powershell
cd C:\Users\patri\trading-agent
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -e .
copy .env.example .env
```

If Windows blocks scripts, run this once, then retry Activate:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

---

## Step 3 — Run the demo (fake market, zero risk)

Every time you want to run commands, activate the environment first:

```powershell
cd C:\Users\patri\trading-agent
.\.venv\Scripts\Activate.ps1
```

**Easiest:** double-click or run:

```powershell
.\scripts\run-demo.ps1
```

Or manually:

```powershell
python -m agent.main --mock --once --skip-session-check
python -m agent.tools.report
```

What you should see:
- It “scans” symbols and maybe dry-runs a trade
- A summary prints from the journal

Your results file lives here:
- `C:\Users\patri\trading-agent\data\decisions.csv`
- `C:\Users\patri\trading-agent\data\journal.db`

---

## Step 4 — Run the backtest (is the strategy any good?)

```powershell
.\scripts\run-backtest.ps1
```

Or:

```powershell
python -m agent.tools.backtest
```

This downloads free historical prices and simulates the credit-spread rules.
Read the report: **expectancy**, **win rate**, **max drawdown**, **profit factor**.

If expectancy is negative, we change rules — we do **not** go live.

---

## Step 5 — Paper trade with Interactive Brokers (still fake money)

1. Create an account at [interactivebrokers.com](https://www.interactivebrokers.com/)
2. Enable **Paper Trading** (practice account)
3. Download **IB Gateway**, log in with the **paper** username
4. In Gateway: enable API (socket clients). Paper port is usually **4002**
5. Edit `C:\Users\patri\trading-agent\.env` in Notepad:

```env
TRADING_MODE=paper
ALLOW_LIVE_TRADING=false
IBKR_HOST=127.0.0.1
IBKR_PORT=4002
ANTHROPIC_API_KEY=   # optional for now
```

6. Keep Gateway open, then:

```powershell
.\scripts\run-paper.ps1
```

Still starts in **dry_run** mode (logs what it would do, does not send orders) until you change `config\settings.yaml`:

```yaml
execution:
  dry_run: false
```

---

## Step 6 — Where do you watch results?

| Place | Purpose |
|---|---|
| PowerShell output | What just happened |
| `data\decisions.csv` | Spreadsheet of every decision |
| `python -m agent.tools.report` | Quick journal summary |
| IBKR app / website | Real paper account P&L once orders are live-to-paper |
| This Cursor chat | Only when you want to change the bot |

You do **not** need TradingView for the bot to run.

---

## What “serious” means from here

1. Backtest → only keep rule sets with positive expectancy  
2. Paper trade ≥ 20 sessions with dry_run off (paper money)  
3. Review journal: did it obey risk rules?  
4. Live money only after that — and still 1 contract max  

If you want help with Step 5 (IBKR), say **“help me connect IBKR”** and we’ll do it together screen-by-screen.
