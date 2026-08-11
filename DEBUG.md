# DEBUG.md — Trading Agent (known bugs, traps, fixes)

**Last updated:** 2026-08-11  
**Purpose:** Prevent Cursor from reintroducing bugs we already fixed. Read with `PROJECT_MEMORY.md`.

---

## V — Live pilot file ≠ live activation (`readiness1`, 2026-08-11)

| | |
|--|--|
| **Symptom** | Presence of `config/live_pilot.yaml` or `BrokerRealtimeProvider` looks like live is on. |
| **Fact** | Paper `settings.yaml` remains `mode: paper` / `dry_run: true` / Yahoo delayed. `live_pilot.yaml` is `activation_status: NOT_ACTIVATED`. Realtime provider raises until MD websocket + credentials exist. |
| **Do not** | Set `ALLOW_LIVE_TRADING` or flip live_pilot without realtime health + broker-sim success + explicit user approval. Never auto-promote models to LIVE. |

---

## U — One CL paper winner ≠ promote liquidity_reversal (`quality2i`, 2026-08-11)

| | |
|--|--|
| **Symptom** | Largest CL paper P&L (~$270, `PAPER-00151`) tempts pivoting the book to CL `liquidity_reversal`. |
| **Fact** | Winner strategy was **`cl_vwap_prox_momentum`**, not `liquidity_reversal`. Live LR shadows were all losses; hist BT of current LR rules ~40% WR / ~breakeven E. Prior OOS simple_LR (~49% WR) stays research evidence only. |
| **Fix / policy** | Keep multi-strategy mix. LR remains `research_only` + **priority learning cell**. Paper stays `execution_profile: balanced` / router_v1. HC/router_v2 shadow-only until material OOS proof (`DEPLOY_ROUTER_V2.json` false). |
| **Also fixed** | Paper fills dropped `metadata`/`setup_id` → learning outcomes could not join; now persisted via `record_paper_fill(..., metadata=)`. |
| **Do not** | Globally boost LR ranking, enable `performance_router_v2.enabled`, or change risk/qty from one trade. |

---

## Mandatory: update this file + PROJECT_MEMORY on every change

**User rule (binding):** Whenever code, config, strategy, risk, tiering, runtime, or ops behavior changes, the assistant must **review and update both**:

1. `DEBUG.md` — new traps, regressions, symptoms → root cause → fix location  
2. `PROJECT_MEMORY.md` — current stamps, engine lists, quality gates, preference changes  

Do **not** ship a fix and leave these stale. Same duty applies to `.cursor/rules/trading-agent-memory.mdc` when preferences change.  
“I’ll document later” is how the research-only supersede bug repeated hours of zero fills.

---

## P — `risk` UnboundLocalError kills paper fills (2026-08-10) — CRITICAL

| | |
|--|--|
| **Symptom** | A/A+ location setups rejected as `EXECUTION_ERROR:cannot access local variable 'risk' where it is not associated with a value`. Example: MYM `vwap_acceptance` A at 16:00 ET on `quality2b`. |
| **Root cause** | In `live_main.cycle`, lifecycle close path assigned `risk = float(risk_dollars…)`, making `risk` a **local** for the whole `cycle()` and shadowing the `DirectionalRiskEngine` from `main()`. Any `handle_signal(..., risk=risk)` then raises UnboundLocalError if that assignment did not run first (or leaves a float if it did). |
| **Fix** | Engine instance is `risk_engine` (never `risk`). Lifecycle dollars use `trade_risk_dollars`. `handle_signal(..., risk_engine=…)`. Keep `cfg["risk"]` config key. |
| **Prevention** | `scripts/preflight_paper_path.py` on every `start_agent` (fail start if path broken). Tests: `tests/test_live_main_risk_engine.py`. |
| **Do not reintroduce** | Any local named `risk` inside `cycle()` / nested handlers that close over the risk engine. |

### Ops failure around bug P (own it)

- `trade_silence_watch` **did** see `EXECUTION_ERROR` and watchdog **did** auto-restart (~22:02Z).
- That restart loaded the **same broken code** — so the bot stayed broken until a **code patch** landed.
- Lesson: process restart ≠ bugfix. UnboundLocalError / NameError / ImportError class errors are now classified `CODE_BUG_RESTART_WILL_NOT_FIX` → **ALERT banner, no restart thrash**.

- quality2d/2e: under 90m selective quiet = OK (no blotter ALERT); ≥90m open-session drought = actionable fault; silence clock resets on config_version change.

---

## T — Laptop sleep kills overnight paper (`quality2h`, 2026-08-10)

| | |
|--|--|
| **Symptom** | User steps away; morning shows no overnight fills / multi-hour heartbeat gaps. |
| **Root cause** | Display-off is OK, but **system sleep / Modern Standby / lid sleep / battery standby (was 5m DC)** freezes Python. Stay-awake thread flags alone were incomplete. |
| **Fix** | `scripts/overnight_power.py` armed by supervisor: `SetThreadExecutionState` + powercfg standby/hibernate=0 (AC+DC) + lid Do Nothing; restored on `stop_agent`. Watchdog cooldown-restarts drought/stale/supersede/exec; CODE_BUG still no thrash. |
| **Do not** | Promise “high profit” by easing gates / EMA spray. Prefer plugged-in overnight. |

---

## S — MIXED thesis hard-killed good location A (`quality2g`, 2026-08-10)

| | |
|--|--|
| **Symptom** | MYM `liquidity_sweep` A BUY (~$220 / R≈2.2) never papered; only research shadows fired. |
| **Root cause** | `require_non_mixed_thesis` treated imperfect MTF as a hard reject. User: factors won’t always agree; research belongs in backtests; location A should trade. |
| **Fix** | `location_may_trade_mixed_thesis: true` — location engines exempt from MIXED hard-block; cascade still journaled. EMA/trend stay research_only. R≥1.6 / reward≥$150 stay. |
| **Do not reintroduce** | Hard-blocking location A solely for MIXED MTF; re-enabling EMA paper spray. |

---

## R — Paperable A vanished as “NO CANDIDATE” (`quality2f`, 2026-08-10) — CRITICAL

| | |
|--|--|
| **Symptom** | Bot “alive”, shadows open, blotter/PASS says `NO CANDIDATE >= A` while `last_evaluation` shows A tiers (e.g. MYM `liquidity_sweep` A). Zero `execution_decisions` rows for the real blocker. |
| **Root cause** | (1) `require_non_mixed_thesis` correctly blocked counter-trend BUY vs all-bearish MTF, but reject never hit the ledger — `select_executable_detailed` dropped via `can_execute` before sizing/ledger. (2) Cascade defaulted thesis to `MIXED` when features missing → false hard-blocks. (3) Research A scores made status look like “candidates exist but mysteriously no trade.” |
| **Fix** | `execution_reject_reason()`; agreement pool keeps paperable A before quality; pipeline ledgers `EXECUTION_QUALITY:*`; cascade unknown thesis = `""` not MIXED; cycle status distinguishes research-only vs quality-filtered. |
| **Do not reintroduce** | Silent `can_execute` drops of A/A+; cascade `MIXED` default on missing features; PASS copy that implies no A when A research/quality-blocked exists. |

---

## Q — 90m open-session paper drought = fault (`quality2e`, 2026-08-10)

| | |
|--|--|
| **Preference** | ≤90 minutes with no paper while Globex session open (london/ny/asia) and not user-stopped = **something is up**, not “healthy selective quiet forever.” |
| **Impl** | `trade_drought_policy` in settings + `trade_silence.py`. At ≥`max_quiet_minutes` (90): run paper-path preflight; classify `CODE_BUG_*` / `RESEARCH_SUPERSEDE_*` / `EXECUTION_ERROR_*` / `DATA_STALE_STUCK` / `PIPELINE_DROUGHT`. |
| **Severity** | Quiet **under** 90m → OK/INFO (no banner). At 90m+ open → **ALERT** with drought/blocker code. |
| **Actions** | Diagnose + escalate; watchdog may restart once for hung HB / supersede / transient exec. **Never** soft-relax gates or re-enable EMA spray. Never restart-loop CODE_BUG. |
| **Do not** | Treat long `HEALTHY_SELECTIVE_QUIET` as acceptable past 90m; auto-ease `execution_quality`. |

---

## O — Trade silence autonomous watch (2026-08-10)

| | |
|--|--|
| **Need** | User should not babysit; prolonged no-fill can mean a bug (e.g. research supersede) not “quiet markets.” |
| **Impl** | `src/agent/ops/trade_silence.py` — live heartbeat + 5-min watchdog. Status JSON + log; blotter banner only for actionable faults. |
| **Thresholds** | WARN/ALERT aligned to drought clock (≥90m open-session). Under 90m selective quiet = no banner. |
| **Auto-restart** | Hung HB / RESEARCH_SUPERSEDE / transient EXEC_ERROR (cooldown 60m). Never restart CODE_BUG class. |
| **Do not** | Scare with ALERT for under-90m healthy quiet; re-enable EMA spray; ease gates on drought. |

---

## How to operate when debugging

1. Inspect the **actual repo** first — do not invent a new architecture.
2. Prefer fixing existing modules over rewriting.
3. After fixes: run `pytest tests/`, then a real `--once` paper scan, then confirm heartbeat on the blotter.
4. If zero trades: prove it with per-symbol engine reasons **and** `data/execution_decisions.jsonl` reject reasons — never hand-wave “quiet market.”
5. Do **not** silently change risk/universe/quantity/poll to “make it look better.”
6. Update `DEBUG.md` + `PROJECT_MEMORY.md` in the same turn as the fix.

---

## M — Research/shadow engines steal paper slot (2026-08-10) — CRITICAL

| | |
|--|--|
| **Symptom** | Healthy agent, candidates/shadows present, **hours of zero paper fills** after demoting `ema_pullback` / `trend_continuation` to research_only. `execution_decisions.jsonl` full of `REJECTED` / `AGREEMENT_SUPERSEDED_BY_ema_pullback` or `…_trend_continuation`. |
| **Root cause** | `boost_for_agreement` in `decision/ranker.py` picked the empirically “best” setup per symbol+side **including research_only engines**. Winner was shadow → `can_execute` false → paper location engines discarded as superseded → **no trade**. |
| **Fix** | Prefer **paperable** pool first; research engines may still appear in `agreeing_engines` (bonus) but **must not win the slot** when any non-research competitor exists. Config stamp `router_v1_quality2b`. Test: `test_research_only_cannot_steal_paper_slot`. |
| **Do not reintroduce** | Ranking research_only / `execution_mode=SHADOW` above executable engines in agreement selection. |

```text
BAD:  best = max(all_engines_including_shadow, key=empirical_rank)
GOOD: paperable = [s for s in group if not research_only(s)]; best = max(paperable or group, …)
GOOD: shadow still listed in agreeing_engines for evidence boost
```

---

## N — EMA spray / soft-location A mint (2026-08-10)

| | |
|--|--|
| **Symptom** | ~64 paper fills / ~+$93 realized; dozens of tiny time_stop scrapes; user: “not how I trade IRL.” |
| **Root cause** | Lone `ema_pullback` reached A/A+ via soft PDH/PDL `has_location` + inflated context families; executed as if high quality. |
| **Fix** | `ema_pullback` + `trend_continuation` → `research_only_engines`. `execution_quality`: min R 1.6, min reward $150, non-MIXED thesis; soft prior-day alone cannot promote lone EMA. Soft location tagged `location_source: soft_prior_day` in `global_score.py`. |
| **Do not** | Re-enable EMA paper without explicit user ask + evidence. |

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

## Tiering / quality traps (do not reintroduce)

```text
BAD:  assign_tier(..., reason_count=max(2, len(reasons)))  # mints fake A+
BAD:  lone ema_pullback conf=82 → execute as A
BAD:  soft near_pdl/near_pdh unlocks A for EMA (location_source soft_prior_day)
BAD:  research_only winner supersedes paper location engine → zero fills
GOOD: strategy_local_score in metadata; global tier separate
GOOD: ema_pullback is research_only (shadow/journal); do not paper without user ask
GOOD: execution_quality gates scrapes (R / $ reward / thesis) without narrowing universe
GOOD: paperable pool wins agreement; shadow only agrees as bonus
```

Agreement across engines **boosts** confidence. Location engines may fire alone; thin non-location engines need a partner under `execution_quality.min_agreeing_engines`. Validated `paper_specialist_engines` are exempt from some gates.

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

Expect tests green (`pytest tests/ -q`).  
Live once-scan should show DELAYED feed, per-symbol engine reasons; EMA research_only → shadow/PASS not paper EXECUTED.

When diagnosing **zero paper trades**: check (1) heartbeat/`NO_NEW_BAR`, (2) shadow open count, (3) `AGREEMENT_SUPERSEDED_BY_*` in `execution_decisions.jsonl`, (4) `execution_quality` / MIXED thesis rejects — not just “markets quiet.”

---

## Files most often involved in regressions

| Area | Paths |
|------|-------|
| Pipeline / tiers / quality | `src/agent/decision/pipeline.py`, `tiering.py`, `ranker.py`, `global_score.py`, `cascade.py`, `setup_identity.py` |
| Risk / portfolio / lifecycle | `src/agent/risk/directional.py`, `portfolio.py`, `strategy_lifecycle.py` |
| Data | `src/agent/data/yahoo_delayed.py`, `bar_cursor.py`, `base.py` |
| Paper UI | `src/agent/paper/blotter.py` |
| Runtime | `src/agent/live_main.py`, `scripts/run_supervised.py`, `watchdog_tick.py` |
| Silent Windows | `scripts/_win_silent.py`, `install_watchdog.ps1`, `install_autostart.ps1` |
| Config | `config/settings.yaml`, `config/agent_profiles/*.yaml` |
| Memory (must stay current) | `PROJECT_MEMORY.md`, `DEBUG.md`, `.cursor/rules/trading-agent-memory.mdc` |

---

## What NOT to do again

1. Narrow universe to MES/MNQ “for safety”
2. Lower `max_open_positions` without asking
3. Require 2–3 engines to agree globally for **all** engines (location engines may be alone; thin engines may need a partner)
4. Trade A+ only unless user explicitly asks (default remains A+ **and** A)
5. Treat delayed bars as live wall-clock events
6. Reprocess the same Yahoo bar every minute
7. Mint A+ with inflated reason counts
8. Execute lone EMA / re-enable `ema_pullback` paper without user ask
9. Flash PowerShell windows from watchdog/supervisor
10. Declare profitability from &lt; tens of standardized paper trades
11. Change risk dollars quietly while “fixing strategy”
12. Hard-code `quantity == 1` in logic (config owns qty; scale-out only if qty≥2)
13. Let research_only / SHADOW engines win `boost_for_agreement` over paperable setups
14. Ship code/config changes without updating **both** `DEBUG.md` and `PROJECT_MEMORY.md`
