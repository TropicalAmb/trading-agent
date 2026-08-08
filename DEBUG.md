# DEBUG.md — Trading Agent (known bugs, traps, fixes)

**Last updated:** 2026-08-07  
**Purpose:** Prevent Cursor from reintroducing bugs we already fixed. Read with `PROJECT_MEMORY.md`.

---

## How to operate when debugging

1. Inspect the **actual repo** first — do not invent a new architecture.
2. Prefer fixing existing modules over rewriting.
3. After fixes: run `pytest tests/`, then a real `--once` paper scan, then confirm heartbeat on the blotter.
4. If zero trades: prove it with per-symbol engine reasons — never hand-wave “quiet market.”
5. Do **not** silently change risk/universe/quantity/poll to “make it look better.”

---

## A–L paper-journal corrections (2026-08-07)

| ID | Symptom | Root cause | Fix location |
|----|---------|------------|--------------|
| A | Lone `ema_pullback` @78/82 opened as A/A+ | Strategy-local score treated as global quality; pipeline inflated `reason_count=max(2,…)` | `decision/tiering.py`, `decision/pipeline.py` |
| B | Tiers too soft / fake A+ | Need location + independent confirmations for A/A+ | `assign_tier` / `assign_tier_for_setup` |
| C | Same MYM/MGC pullback every minute | No structural setup identity | `decision/setup_identity.py` + mark on fill |
| D | Trades looked like wall-clock time | Must store market vs received timestamps | `TradeSetup`, blotter `opened_at` = market time |
| E | Duplicate decisions on unchanged Yahoo bar | Need exactly-once bar cursor | `data/bar_cursor.py` + pipeline pending bars |
| F | MGC risk ~$269 vs $250 cap | Hard cap not consistently enforced; display/stop drift possible | `risk/directional.py` `RISK_LIMIT`; pipeline `_hard_risk_ok` |
| G | 2-contract / TP1 scale-outs on paper | qty must default 1; scale-out only if qty≥2 | `quantity.*`, blotter `take_partial` |
| H | MES+ES (etc.) treated independent | Product families | `risk.product_families` + `PortfolioCoordinator` |
| I | No post-trade learning payload | Missing MAE/MFE/R/delay dump | `journal/diagnostics.py` |
| J | B rejects not tracked hypothetically | Missing B journal file | `HypotheticalBTracker` |
| K | “found 2 setups” but votes show `—` | Engine dict overwritten across catch-up bars; count ≠ candidate list | pipeline accumulate votes; blotter `candidates` column |
| L | Session P&L only cumulative | Need day×session segmentation | `blotter.daily_session_pnl()` + HTML section |

---

## Delayed Yahoo data traps

- Wall clock ≠ market bar time. Example: received 10:45, bar 10:32 → trade belongs to **10:32**.
- Yahoo can return the **same** latest bar for several 1-minute scans → must not re-signal.
- Cap catch-up bursts (`pending[-3:]`) so history dumps don’t spray entries.
- First-run cursor: evaluate latest bar only (avoid backfill spray).
- Stale feed → `DATA_STALE` pass, not silent trade.
- Closing trades: normalize naive market timestamps vs aware UTC or `_hold_minutes` TypeErrors (fixed in blotter `_parse_ts`).

---

## Tiering traps (do not reintroduce)

```text
BAD:  assign_tier(..., reason_count=max(2, len(reasons)))  # mints fake A+
BAD:  lone ema_pullback conf=82 → execute as A
GOOD: strategy_local_score stored in metadata; global tier separate
GOOD: lone EMA without location/agreement → max B; journal only
```

Agreement across engines **boosts** confidence; it is **never** a global mandatory filter.

---

## Risk / sizing traps

- `risk.max_risk_dollars_per_trade` is a **hard** ceiling (no undocumented tolerance).
- Engines may use tighter strategy-local max risk; never exceed hard cap.
- Blotter historically treats signal `risk_dollars` as **per-contract** and multiplies by qty — adapters convert TradeSetup position $ → per-contract for that path.
- Instrument point values must stay correct (MES 5, MNQ 2, MGC 10, MYM 0.5, M2K 5, MCL 100, ES 50, NQ 20, CL 1000, GC 100). Unit-tested in `tests/test_invariants.py`.
- Do not use `risk.max_contracts_per_trade: 2` as live sizing — `quantity.default_quantity` owns sizing.

---

## Windows terminal flash / plug-in popups (2026-08-07)

### Symptoms
- Terminals randomly open/close while working
- Terminals open when plugging in laptop / waking

### Causes
1. `watchdog_tick.py` / `run_supervised.py` spawned **visible** `powershell.exe` for process queries every few minutes
2. Scheduled task `WakeToRun=true` + `StartWhenAvailable` fired on power/resume
3. Stuck `start_agent.py` windows waiting on “Press Enter to close…”
4. Task `RestartOnFailure` + races could spawn duplicate supervisors

### Fixes
- `scripts/_win_silent.py` — `CREATE_NO_WINDOW` + hidden startupinfo; PID match via `.Contains()` (not `-like`, because `.` is a wildcard in `-like`)
- Tasks: **Hidden=true**, **WakeToRun=false**, no RestartOnFailure on Autonomous (supervisor self-restarts)
- `start_agent.py` auto-closes in 3s on success
- `stop_agent.py` silent stop (also clears stuck start_agent consoles)
- Supervisor single-instance: mutex `Global\\TradingAgentSupervisorMutex` + file lock

### Note on “two pythonw PIDs”
Windows/venv often shows a small parent pythonw + larger child with the same command line. That is not necessarily two logical supervisors. Trust mutex + `supervisor_status.json` + single heartbeat writer.

---

## Scan-tape / dashboard traps

- `signals_found` = executable A+/A count  
- `candidates` list may include journaled B/C for transparency — do **not** overwrite executable count with `len(candidates)` on PASS  
- Never erase a real engine vote with a later `none` from a newer catch-up bar  
- Day P&L keys off market/open timestamp (ET day) for delayed-feed honesty  

---

## Overnight death (historical)

| Cause | Mitigation |
|-------|------------|
| Yahoo hang | Timeouts, retries, per-symbol isolation |
| Stale heartbeat | Supervisor kills hung agent; watchdog every 5 min |
| PC sleep | Stay-awake requests; ultimately **VPS** (`DEPLOY_VPS.md`) |
| Duplicate supervisors | Mutex + IgnoreNew + no task RestartOnFailure |

---

## Paper mode invariants

- `mode: paper` ⇒ never call live `place_bracket_order` (forced dry_run in executor).
- Mock broker OK for routing; market bars still real Yahoo delayed prints.
- Local blotter HTML is the paper UI — **not** TradingView.com Paper Trading.

---

## Test commands

```powershell
cd C:\Users\patri\trading-agent
.\.venv\Scripts\python.exe -m pytest tests/ -q
.\.venv\Scripts\python.exe -m agent.live_main --mock --once
```

Expect ~64+ tests passing after mega-spec work.  
Live once-scan should show DELAYED feed, per-symbol engine reasons, and lone EMA as B/PASS.

---

## Files most often involved in regressions

| Area | Paths |
|------|-------|
| Pipeline / tiers | `src/agent/decision/pipeline.py`, `tiering.py`, `ranker.py`, `setup_identity.py` |
| Risk / portfolio | `src/agent/risk/directional.py`, `portfolio.py` |
| Data | `src/agent/data/yahoo_delayed.py`, `bar_cursor.py`, `base.py` |
| Paper UI | `src/agent/paper/blotter.py` |
| Runtime | `src/agent/live_main.py`, `scripts/run_supervised.py`, `watchdog_tick.py` |
| Silent Windows | `scripts/_win_silent.py`, `install_watchdog.ps1`, `install_autostart.ps1` |
| Config | `config/settings.yaml` |

---

## What NOT to do again

1. Narrow universe to MES/MNQ “for safety”
2. Lower `max_open_positions` without asking
3. Require 2–3 engines to agree globally
4. Trade A+ only (default is A+ **and** A)
5. Treat delayed bars as live wall-clock events
6. Reprocess the same Yahoo bar every minute
7. Mint A+ with inflated reason counts
8. Execute lone EMA touches as A
9. Flash PowerShell windows from watchdog/supervisor
10. Declare profitability from &lt; tens of standardized paper trades
11. Change risk dollars quietly while “fixing strategy”
12. Force qty=2 / TP1 scale-out while `default_quantity: 1`
