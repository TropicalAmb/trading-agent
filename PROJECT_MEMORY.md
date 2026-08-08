# PROJECT MEMORY — Trading Agent (binding)

**Last updated:** 2026-08-07  
**Rule:** Assistants must follow this file. Do not “optimize away” user preferences.  
**Also read:** [DEBUG.md](./DEBUG.md) for bugs already fixed and traps to avoid reintroducing.

---

## Non-negotiable preferences

1. **Wide symbol book** — micros **and** full-size are OK (not MES/MNQ-only, not micros-only).
2. **Many concurrent positions** — more than 8 is OK; keep `max_open_positions` high (50+).
3. **Autonomous** — must stay running overnight / with laptop closed (VPS eventually); dead bot ≠ selective strategy.
4. **Scan every ~1 minute** for trades; 5-minute watchdog is **health check only**.
5. **Do not unilaterally restrict** universe, size, quantity, risk, or poll interval “for safety” without asking.
6. **Do not declare the strategy “good”** from a handful of paper trades. Collect evidence by engine/tier/session first.
7. **Implement, don’t only plan** — when asked to fix/refactor, modify code, run tests, verify live paper scan.
8. **No console flash spam** — background tasks must stay silent (Hidden + no WakeToRun + CREATE_NO_WINDOW).

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

## Quantity (scalable — default 1 for paper)

```yaml
quantity:
  default_quantity: 1
  max_quantity: 25
  quantity_by_symbol: {}
  quantity_by_strategy: {}
  quantity_by_agent_profile: { balanced: 1, momentum: 1, liquidity: 1 }
```

- Nothing may hard-code `quantity == 1`.
- Scale-out / TP1 / runner architecture must exist, but **activates only when qty ≥ 2**.
- Do not force 2-contract scale-outs while paper default is 1.

---

## Risk posture (do not silently change numbers)

Current paper-relevant values in `config/settings.yaml`:

| Setting | Value |
|---------|-------|
| `max_open_positions` | 50 |
| `max_risk_dollars_per_trade` | 250 (**HARD** pre-trade `RISK_LIMIT`) |
| `max_total_open_risk_dollars` | 3500 |
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

1. `ema_pullback`
2. `liquidity_sweep`
3. `vwap_acceptance` (includes reclaim/rejection — no separate `vwap_reclaim`)
4. `sweep_retest`
5. `momentum`
6. `breakout_retest`
7. `trend_continuation`
8. `opening_range` (London/NY, 15m research default)
9. `vwap_orb` (optional / may remain)

Flow: engines → `TradeSetup` → **global** A+/A/B/C tiering → ranker → portfolio/risk → paper/live execution adapter.

**Do not lower `minimum_trade_tier` below A.** B stays shadow-only. Global score primary base = **32** (not 45). Every A/A+ must get `EXECUTED` or `REJECTED:<reason>` (`data/execution_decisions.jsonl`).

### Tiering (rigorous)

| Tier | Meaning | Default execute? |
|------|---------|------------------|
| A+ | Exceptional: primary signal + strong location/structure + multiple confirmations + good R:R + no overextension | Yes |
| A | Tradeable high quality | Yes (`minimum_trade_tier: A`) |
| B | Valid but incomplete — **journal + hypothetical track** | No |
| C | Weak / conflicted | No |

**Critical:** strategy-local score ≠ global trade quality.  
A lone `ema_pullback` BUY@78/82 with other engines `none` must **not** become A/A+. Cap at **B**.

- No mandatory multi-engine confluence (agreement is **bonus**).
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

**Conclusion:** not ready for live. Keep collecting standardized diagnostics by strategy/tier/session/symbol. Do not overfit to ten trades; do not abandon engines from ten trades alone.

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
| View | `data/paper_trading_view.html` |
| Logs | `data/agent_supervisor.log`, `data/agent_runtime.log`, `data/watchdog.log` |
| Tasks | `TradingAgentAutonomous` (login, **Hidden**), `TradingAgentWatchdog` (5 min, **Hidden**, **WakeToRun=false**) |

Silent helpers: `scripts/_win_silent.py`.  
Single-instance supervisor: Windows named mutex `Global\\TradingAgentSupervisorMutex`.  
Production autonomy with laptop closed → Linux VPS via `DEPLOY_VPS.md` / Docker (`restart: unless-stopped`), not “stay awake” forever.

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

- 2026-08-07: Silent Windows tasks (no terminal flash); mutex single-instance; WakeToRun off; start auto-close.
- 2026-08-07: Global tiering (lone EMA → B); setup identity; hard RISK_LIMIT; product families; day×session P&L; scan-tape candidates; post-trade + B hypothetical journals.
- 2026-08-07: Decision pipeline, delayed-bar correctness, qty default 1, Docker paper profile.
- 2026-08-07: Created after agent wrongly narrowed to MES/MNQ and low max-opens. Restored full+micro universe and high concurrency.
