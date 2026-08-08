# Trading Agent (paper futures)

Autonomous **paper** futures trading agent: Yahoo delayed data → strategy engines → global A+/A/B/C tiering → portfolio/risk → paper blotter.

**No profitability is guaranteed.** Paper only until you explicitly enable live.

## Where this project lives

| | |
|---|---|
| **Local path** | `C:\Users\patri\trading-agent` |
| **GitHub** | https://github.com/TropicalAmb/trading-agent *(private)* |
| **Paper dashboard** | `data\paper_trading_view.html` |
| **Start / stop** | Desktop **Start Trading Agent** / **Stop Trading Agent**, or `scripts\Start-Agent.ps1` / `scripts\Stop-Agent.bat` |

Open in Cursor/VS Code:

```powershell
code C:\Users\patri\trading-agent
```

Clone (after you have access):

```powershell
gh repo clone TropicalAmb/trading-agent
cd trading-agent
```

## New here?

- [`START_HERE.md`](START_HERE.md) — how to run
- [`PROJECT_MEMORY.md`](PROJECT_MEMORY.md) — binding preferences (risk, quantity, tier floor)
- [`CONNECT_REAL.md`](CONNECT_REAL.md) — broker / real-hookup notes

## What it does now

- Multi-symbol futures book (MES/MNQ/MGC/MYM/M2K/MCL/ES/NQ/CL/GC)
- Engines: EMA pullback, liquidity sweep, VWAP acceptance, sweep retest, momentum, breakout retest, trend continuation, opening range
- Global scoring + tiering; **minimum execute tier = A** (B = shadow research only)
- 1-minute scheduler, 5-minute bars, Globex sessions with weekend gap auto-resume
- Paper blotter + execution decision ledger (every A/A+ ends EXECUTED or REJECTED)

Legacy options / credit-spread / IBKR paths may still exist in the tree; the live paper loop is `python -m agent.live_main` via the supervisor.

## Quick start (local)

```powershell
cd C:\Users\patri\trading-agent
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -e .
copy .env.example .env

# One scan cycle (mock broker):
python -m agent.live_main --mock --once --skip-session-check

# Or start the background supervised agent:
.\scripts\Start-Agent.ps1
```

Open `data\paper_trading_view.html` for the live paper view.

## Tests

```powershell
pytest -q
```

## Layout (high level)

```
src/agent/
  live_main.py           # supervised paper cycle
  decision/              # pipeline, global score, tiering, ranker
  strategy/              # engines
  paper/blotter.py       # paper view + fills
  schedule/sessions.py   # Globex / weekend gap
config/settings.yaml
scripts/                 # Start/Stop, autostart, watchdog
tests/
```

## Safety

- Paper mode by default; live requires explicit flags
- Risk limits and quantity defaults are locked in config / `PROJECT_MEMORY.md` — do not silently change
- Never commit `.env` or `data/*` runtime journals
