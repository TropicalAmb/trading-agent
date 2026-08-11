# PROJECT MEMORY — Trading Agent (binding)

**Last updated:** 2026-08-11  
**Paper stamps:** `config_version: router_v1_readiness1`. Databento historical provider scaffolded (`DATABENTO_API_KEY` in `.env`); paper still uses Yahoo delayed. Learning / HC shadow parallel; `live_pilot.yaml` NOT activated. Do **not** promote CL `liquidity_reversal` from one paper trade.  

**Rule:** Assistants must follow this file. Do not “optimize away” user preferences.  
**Also read:** [DEBUG.md](./DEBUG.md) for bugs already fixed and traps to avoid reintroducing.

---

## Mandatory dual-file review (every change)

On **every** material change (strategy, tiering, quality gates, engines research_only↔paper, risk, quantity, sessions, runtime, ranking, cascade, lifecycle, ops):

1. Update **this file** (`PROJECT_MEMORY.md`) — stamps, engine lists, gates, preferences, change log.  
2. Update **[DEBUG.md](./DEBUG.md)** — new trap/regression row or “do not reintroduce” item.  
3. Update `.cursor/rules/trading-agent-memory.mdc` when a preference shifts.

Leaving either file stale after a fix is a process failure (it already caused hours of silent zero-fills).

---

## Non-negotiable preferences

1. **Wide symbol book** — micros **and** full-size are OK (not MES/MNQ-only, not micros-only).
2. **Many concurrent positions** — more than 8 is OK; keep `max_open_positions` high (50+).
3. **Autonomous overnight** — while agent runs, Windows sleep/hibernate/lid-suspend must stay disabled (`overnight_power`); watchdog restarts roadblocks. Lid-closed forever → still prefer VPS long-term; plugged-in laptop OK for night. Dead bot ≠ selective strategy.
4. **Scan every ~1 minute** for trades; 5-minute watchdog is **health check only**.
5. **Do not unilaterally restrict** universe, size, quantity, risk, or poll interval “for safety” without asking.
6. **Do not declare the strategy “good”** from a handful of paper trades. Collect evidence by engine/tier/session first.
7. **Implement, don’t only plan** — when asked to fix/refactor, modify code, run tests, verify live paper scan.
8. **No console flash spam** — background tasks must stay silent (Hidden + no WakeToRun + CREATE_NO_WINDOW).
9. **Selectivity over spray** — prefer fewer, worth-it paper trades (IRL style); do not “fix” quiet tape by re-enabling EMA spray.
10. **Keep memory current** — always update `PROJECT_MEMORY.md` + `DEBUG.md` with the change.
11. **Babysit-free ops** — `trade_silence_watch` must stay enabled; prolonged silence should self-diagnose. Auto-restart only for hung process / transient patterns — **never** thrash-restart known code bugs (`CODE_BUG_RESTART_WILL_NOT_FIX`). Restart ≠ patch.
12. **≤90m open-session paper drought** — if market/session is open and no paper fill for ≥90 minutes without stop/maintenance reason, treat as **pipeline/ops fault** (probe + ALERT). Do **not** auto-ease `execution_quality` or re-enable EMA paper.
13. **Paper path hard to break** — DirectionalRiskEngine instance is `risk_engine`; start must pass `scripts/preflight_paper_path.py`.

---

## Current intended universe

Include at least:

| Symbol | Type |
|--------|------|
| MES | Micro S&P |
| MNQ | Micro Nasdaq |
| MGC | Micro Gold |
| MYM | Micro Dow |
| M2K | Micro Russell |
| MCL | Micro Crude |
| ES | Full S&P |
| NQ | Full Nasdaq |
| CL | Full Crude |
| GC | Full Gold |

Symbol list lives in `config/settings.yaml`. Invalid/unavailable Yahoo tickers: log, skip that symbol, **never** crash the whole agent.

---

## Quantity (multi-lot after strategy tighten — still risk-capped)

```yaml
quantity:
  default_quantity: 2
  max_quantity: 25
  quantity_by_tier: { "A+": 3, A: 2 }
  quantity_by_symbol: {}
  quantity_by_strategy: {}
  quantity_by_agent_profile: { balanced: 2, momentum: 2, liquidity: 2, trend: 2 }
```

- Nothing may hard-code `quantity == 1`.
- Target qty is tier-based; `fit_quantity_to_risk` shrinks to the effective account risk budget.
- Risk is **never unlimited**. Effective cap = min(`risk_per_trade_pct*equity`, `max_account_risk_per_trade`, `max_risk_dollars_per_trade`).
- If even 1 contract exceeds budget: prefer micro of same family, else reject / SHADOW research — do not disable the cap.
- Scale-out / TP1 / runner architecture activates when qty ≥ 2.

---

## Risk posture (do not silently change numbers)

Current paper-relevant values in `config/settings.yaml`:

| Setting | Value |
|---------|-------|
| `max_open_positions` | 50 |
| `risk_per_trade_pct` | 0.01 |
| `max_account_risk_per_trade` | 500 |
| `max_risk_dollars_per_trade` | 500 (finite; never 0) |
| `max_total_open_risk_dollars` | 3500 |
| `max_correlated_risk_dollars` | 1500 |
| `daily_loss_kill_dollars` | 4000 |
| `daily_loss_kill_pct` | 0.08 |
| `symbol_cooldown_minutes` | 45 |
| `block_opposite_correlated` | true |

Product families (micro ↔ full = same opportunity):

- SP500: MES, ES  
- NASDAQ: MNQ, NQ  
- GOLD: MGC, GC  
- CRUDE: MCL, CL  

Cross-index opposite block group still includes MES/MNQ/MYM/M2K/ES/NQ.  
If you believe a risk value should change: **REPORT IT** — do not silently edit.

---

## Sessions

- Trade **Asia, London, New York** / Globex whenever exchange is open.
- Session is metadata/analytics + optional strategy context — **not** a global trade kill-switch.
- Respect CME maintenance (~17:00–18:00 ET) and weekend close.
- Do **not** impose one strategy’s NY opening window on all engines.

---

## Strategy / decision pipeline (locked)

`active_strategy: decision_pipeline`

Engines (independent; propose only — do not place orders):

**Paper-executable engines:**
1. `liquidity_sweep`
2. `vwap_acceptance` (kept; location/acceptance VWAP)
3. `sweep_retest`
4. `momentum`
5. `breakout_retest`
6. `opening_range` (London/NY; NY 5m first_break + VWAP align; London retest)
7. `vwap_orb`
8. `vwap_mss` (VWAP + MSS close-through + MTF3)
9. `cl_vwap_prox_momentum` (validated CL specialist)

**Research/shadow only (still evaluated, not paper-executed):**  
`ema_pullback`, `trend_continuation`, `trend_pullback`, `liquidity_reversal`, `vwap_reclaim`, `indicator_parity`, `nq_ny_open_momentum`

Flow: engines → `TradeSetup` → **global** A+/A/B/C tiering (metadata/gates) → **StrategyPerformanceRouter** empirical rank among executables → portfolio/risk → paper/live execution adapter.

**Agreement selection (`boost_for_agreement`):** keep best **paperable** setup per symbol+side. Research/shadow engines may still contribute to `agreeing_engines` (bonus) but **must never** win the slot and supersede a paper-executable competitor (bug M in `DEBUG.md` / stamp `quality2b`).

**Router (additive):** segment by strategy × symbol × session × regime × direction; hierarchical fallback; min exact-cell n=30 (preferred 50+). Global score remains for diagnostics; does **not** bypass hard risk/data/duplicate gates. Nonselected valid competitors stay shadow-tracked.

**Paper promotion bar (soft, edge-first):** expectancy > 0, PF ≥ 1.2, n ≥ 30, anti-cheat OK. WR is tracked; ≥65% remains an aspirational research target, **not** a paper blocker (`PAPER_GATES` / `meets_paper_gates` in research harness).

**Do not lower `minimum_trade_tier` below A.** B stays shadow-only. Global score primary base = **32** (not 45). Every A/A+ must get `EXECUTED` or `REJECTED:<reason>` (`data/execution_decisions.jsonl`).

### Tiering (rigorous)

| Tier | Meaning | Default execute? |
|------|---------|------------------|
| A+ | Exceptional: primary signal + strong location/structure + multiple confirmations + good R:R + no overextension | Yes |
| A | Tradeable high quality | Yes (`minimum_trade_tier: A`) |
| B | Valid but incomplete — **journal + hypothetical track** | No |
| C | Weak / conflicted | No |

**Critical:** strategy-local score ≠ global trade quality.  
`ema_pullback` is **research_only** after paper spray (dozens of fills for ~breakeven). Soft PDH/PDL must not mint A for EMA if ever re-enabled.

`execution_quality` (enabled): min R 1.6, min reward $150, reject `POOR_LOCATION`, require non-MIXED cascade thesis for non-specialists. Location engines may fire alone; thin engines need 2 agreeing engines. Does not narrow universe or lower max positions.
- Multiple A/A+ setups may open in one cycle if portfolio risk allows.
- Setup identity (`data/setup_identities.json`) suppresses re-entry from the **same** structural setup (not a blind cooldown-only fix).

---

## Market data (paper now)

- Provider: `YahooDelayedFuturesProvider` behind `MarketDataProvider`.
- Always store separately: `market_bar_timestamp`, `received_timestamp`, `estimated_feed_delay`.
- Strategies / paper fills / session attribution for analysis use **market bar time**, not wall clock.
- `BarCursorStore`: process each completed bar **exactly once**; catch up chronologically when practical.
- Same delayed Yahoo bar on next minute scan → heartbeat + `NO_NEW_BAR`, no new signal.
- Stale → `DATA_STALE` pass. Timeouts/retries/backoff. One symbol failure must not freeze others.
- Dashboard must show **DELAYED FEED** clearly.

---

## Paper journal diagnosis (do not dismiss)

Observed before tiering fix (approx):

- Realized ≈ −$566 on ~10 substantive closes (1W / 8L / 1BE), PF ≈ 0.38  
- London especially poor  
- Many fills were lone EMA pullbacks overvalued as A  

**2026-08-10 spray episode:** ~64 closed / ~+$93 realized; ~39 `ema_pullback`; eight ≥$100 winners ≈ canceled by ~50 small losers. User rejected this as not IRL trading → `quality2` demotion + `execution_quality` gates. Then **zero paper for hours** while shadows fired — root cause was research engines stealing agreement (fixed in `quality2b`).

**Conclusion:** not ready for live. Keep collecting standardized diagnostics by strategy/tier/session/symbol. Do not overfit to ten trades; do not abandon engines from ten trades alone. Do not reintroduce spray to “look busy.”

---

## Dashboard requirements

Must auto-refresh and show: system status, scan tape (every candidate when count > 0), open/closed trades, account summary, **session P&L cumulative AND day×session**, strategy/tier performance.  
If tape says “found N setups”, list those N candidates — no hidden counts.

---

## Multi-agent

Supported via `agent_id`, `config/agent_profiles/`, Docker Compose profiles.  
`PortfolioCoordinator` blocks duplicate/opposite exposure and product-family doubles unless config allows.

---

## Ops (Windows laptop)

| Action | How |
|--------|-----|
| Start | Desktop **Start Trading Agent** → `scripts/start_agent.py` |
| Stop | Desktop **Stop Trading Agent** → `scripts/stop_agent.py` |
| View | `data/paper_trading_view.html` (includes **TRADE SILENCE** banner when WARN/ALERT) |
| Silence status | `data/trade_silence_status.json`, `data/trade_silence.log` |
| Preflight | `scripts/preflight_paper_path.py` (also via `start_agent`; drought probe in watchdog) |
| Overnight power | `scripts/overnight_power.py` — armed by supervisor; restored by `stop_agent` (`data/overnight_power_state.json`) |
| Logs | `data/agent_supervisor.log`, `data/agent_runtime.log`, `data/watchdog.log` |
| Tasks | `TradingAgentAutonomous` (login, **Hidden**), `TradingAgentWatchdog` (5 min, **Hidden**, **WakeToRun=false** — also runs silence check) |

Silent helpers: `scripts/_win_silent.py`.  
Single-instance supervisor: Windows named mutex `Global\\TradingAgentSupervisorMutex`.  
Overnight on this laptop: stay-awake + no sleep while running (prefer AC power). Long-term always-on → VPS (`DEPLOY_VPS.md`).

---

## Explicitly out of scope until user asks

- Live broker orders (`mode: paper`, `ALLOW_LIVE_TRADING` must stay false until user says otherwise)
- Options / multi-leg strategies
- Claiming TradingView.com shows external bot orders
- Paying for real-time futures API (swap adapter later — do not rewrite engines)

---

## Locked architecture summary

- Paper execution = one adapter; live broker = another later (same strategy path).
- Config controls behavior (`config/settings.yaml`, agent profiles) — no magic numbers scattered for tier/risk/universe/poll.
- Tests in `tests/` guard non-regression (scan=1m, sessions, universe, tiers, risk, delayed bars, paper≠live, etc.).
- Post-trade diagnostics: `data/post_trade_diagnostics.jsonl`  
- Hypothetical B setups: `data/hypothetical_b_setups.jsonl`

---

## Change log

- 2026-08-11: Session-open momentum walk-forward cull (`scripts/run_session_open_walkforward_cull.py`) — Yahoo 5m/60d research only. KEEP: NQ asia + NQ/ES ny_open. X_OUT: NQ/ES london open (WR<50%). Paper unchanged; Databento still preferred for longer history.
- 2026-08-11: **`router_v1_quality2i`** — adaptive closed learning loop: persist entry_features/setup_id on paper fills; HC shadow parallel + v2 evidence attach without enabling v2 paper ranking; CL priority learning report (`data/cl_priority_learning/`); discovery shadow registry; dashboard Adaptive Learning + Why CL Winner sections. No risk/qty/universe change. router_v2 **not** deployed to paper.
- 2026-08-10: **`router_v1_quality2h`** — overnight power arm (sleep/lid); drought/roadblock cooldown auto-restart; CODE_BUG still no thrash.
- 2026-08-10: **`router_v1_quality2g`** — location engines may paper with MIXED thesis (factors won’t always agree); EMA stays research_only; R/$ gates stay.
- 2026-08-10: **`router_v1_quality2f`** — ledger `EXECUTION_QUALITY:*` for filtered paperable A; cascade unknown≠MIXED; clearer PASS status (research-only vs quality).
- 2026-08-10: **`router_v1_quality2e`** — `risk_engine` rename + start preflight; `trade_drought_policy` max_quiet_minutes=90 → PIPELINE_DROUGHT ALERT (no gate easing); under-90m quiet stays non-actionable.
- 2026-08-10: **`router_v1_quality2d`** — silence banner suppressed for healthy selective quiet; regime clock on config_version; CODE_BUG no restart thrash.
- 2026-08-10: **Bug P / `quality2c`** — `live_main.cycle` shadowed `risk` → EXECUTION_ERROR; renamed `trade_risk_dollars`.
- 2026-08-10: **`trade_silence_watch`** — autonomous no-fill diagnostics (live heartbeat + watchdog); blotter banner; auto-restart on RESEARCH_SUPERSEDE / EXEC_ERROR / stale HB (cooldown 60m). Tests in `tests/test_trade_silence.py`.
- 2026-08-10: **`router_v1_quality2b`** — research/shadow cannot steal paper agreement slot (`ranker.boost_for_agreement`); test `test_research_only_cannot_steal_paper_slot`. Dual-file update duty made explicit.
- 2026-08-10: **`router_v1_quality2`** — IRL selectivity: `ema_pullback` + `trend_continuation` research_only; `execution_quality` min R 1.6 / min reward $150 / non-MIXED thesis; soft PDH/PDL cannot mint EMA A.
- 2026-08-10: CL specialist paper path + cascade + lifecycle (`router_v1_clpaper1` lineage); NQ specialist stays shadow.
- 2026-08-07: Silent Windows tasks (no terminal flash); mutex single-instance; WakeToRun off; start auto-close.
- 2026-08-07: Global tiering (lone EMA → B); setup identity; hard RISK_LIMIT; product families; day×session P&L; scan-tape candidates; post-trade + B hypothetical journals.
- 2026-08-07: Decision pipeline, delayed-bar correctness, qty default 1, Docker paper profile.
- 2026-08-07: Created after agent wrongly narrowed to MES/MNQ and low max-opens. Restored full+micro universe and high concurrency.
