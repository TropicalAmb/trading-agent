# PROJECT MEMORY — Trading Agent (binding)

**Last updated:** 2026-08-14
**Paper stamp:** `config_version: router_v1_specialists_autonomy5`. Paid NQ/CL volume-continuous `.v.0` caches are now rebuilt and audited; `databento_cache_yahoo` uses verified cached history plus Yahoo's current tail. **No strategy is presently paper-enabled:** execution-parity dual-source validation demoted both `nq_context_entry` and `cl_vwap_prox_momentum`; `vwap_rejection` and every other research module remain offline (`shadow.evaluate_research_engines_live: false`). The agent stays supervised but paper entry is intentionally fail-closed until a replacement passes every frozen gate.

**Research data (binding):** Prefer **Databento volume-continuous + Yahoo dual**. On 2026-08-14 the user approved and the system spent an estimated **$1.285970583558** to download 180d of NQ.v.0 (177,188 rows) and CL.v.0 (175,049 rows). Legacy parent caches are preserved under `data/databento/legacy_parent_20260814_autonomy4/`, never used as single-series evidence. NQ audit PASS; CL WARN (0.6021% 2–30m gaps); both have zero duplicate timestamps/invalid OHLC and strong Yahoo 5m return agreement (NQ 0.9843, CL 0.9490). Six source dates are Databento-degraded. **No further Databento download without user OK.**

**Promotion gates (practical):** WR≥55%, n≥40, PF≥1.3, E≥0.15 (`GATES` in harness metrics), plus latest PF≥1/E≥0 on **both** corrected Databento and Yahoo. Primary results simulate configured two-lot management. NQ: DB n141 WR58.9% PF1.297 E+0.105R; Yahoo n49 WR57.1% PF1.264 E+0.090R, latest n10 PF0.75 E−0.111R — FAIL. CL: DB n133 WR53.4% PF1.79 E+0.259R; Yahoo n41 WR56.1% PF1.80 E+0.248R — FAIL on DB WR. Exact-stamp `autonomy5` forward n=0; no profitability claim.

**Broad restart evidence (binding, 2026-08-14):** Reddit/primary-source restart now covers **42 coded families / 170 paid-window symbol×variant tests** plus two separately frozen regime/state models; zero passed the requested 70%+profitability+sample+dual-source gate. A public NQ 2010–2025 one-minute file was audited, not trusted blindly: 6,231 rows in a bounded 2012 100× scale-error episode were quarantined; 4,968,467 clean rows remain; aligned RTH daily returns correlate 0.9667 with Yahoo. Provenance is still unverified, so this file is permanently research-only and never a paper provider. First-pass finalists failed (VWAP holdout n138 WR52.2% PF1.338 E+0.124R; stopped daily IBS n100 WR42.0%); second-pass prior-level/OR/value-area/session families all failed, including a tempting paid NQ value-area 17/24 WR70.8% that collapsed to long holdout n144 WR35.4% E−0.168R. Public headline setups also failed: the value-area “80% rule” holdout n89 WR38.2% E−0.066R; the reported 69% NY-open three-bar setup n390 WR39.7% E−0.110R; 15m ORB retest n521 WR52.6%; premarket dual-EMA n984 WR43.0%. Pass 5 opening-state/gap/volume families all failed, including long holdouts IB/VWAP n478 WR40.0%, volume climax n357 WR40.9%, lunch reclaim n405 WR43.5%, two-test breakout n244 WR43.9%, and post-settlement n66 WR42.4%. Pass 6 added five BVC/VPIN-style **OHLCV proxies** (not true bid/ask delta/depth): pressure breakout holdout n90 WR44.4% PF1.053, toxicity failed-extension n193 WR47.1% PF1.247 (paid n23 WR47.8%, Yahoo n10 WR60.0%), and impact shock n37 WR40.5%; divergence/absorption variants were too sparse. Pass 7 added five frozen Reddit translations: MACD/EMA/VWAP momentum, two-bar NQ flag pullback, VWAP/EMA9 rejection, balance-only Keltner/Stochastic reentry, and Bollinger/Keltner/MFI squeeze. Only the flag was worth preserving as research: long holdout n74 WR58.1% PF1.839 E+0.270R, paid n14 WR64.3% PF4.008 E+0.451R, and Yahoo n8 WR75.0% PF6.011 E+0.643R; it fails the 70% long gate, Databento WR is below 70%, and Yahoo is below the frozen n≥10 current minimum, so it is not promoted or retuned. The other pass-7 holdouts were 41.8%, 43.8%, 50.0% on n2, and 46.2%. The predeclared high-precision HGB used 151,046 old development rows, selected threshold 0.55 on validation, then produced validation n139 WR49.6% and untouched holdout n188 WR45.2% PF1.08 E+0.032R; paid n39 WR46.2%, Yahoo n13 WR53.8%. Tiny recent cells remain rejected. **No research engine was promoted and paper remains `CONFIG_ENTRY_GATE:NO_VALIDATED_PAPER_STRATEGY`.** Trade-silence diagnosis recognizes generic `CONFIG_ENTRY_GATE` and suppresses stale blockers/restart suggestions. Do not lower gates, alter 1R TP1, raise risk, retune against opened holdouts, re-enable EMA research, or quote tiny-sample WR to claim success. Reproducible artifacts now also include `strategy_expansion_pass2/3/4/5/6/7` and `high_precision_state_model/` reports.

Learning / HC shadow parallel; `live_pilot.yaml` NOT activated. Do **not** re-enable breakout/EMA spray without user ask.  

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
12. **≤90m open-session paper drought** — if market/session is open and no paper fill for ≥90 minutes without stop/maintenance reason, treat as **pipeline/ops fault** (probe + ALERT), **except** when `trade_drought_policy.specialists_only_selective_quiet` is on and only paper specialists can fill — then no-setup silence is `HEALTHY_SELECTIVE_QUIET` (still ALERT on code/stale/supersede). Do **not** auto-ease `execution_quality` or re-enable EMA/location spray.
13. **Paper path hard to break** — DirectionalRiskEngine instance is `risk_engine`; start must pass `scripts/preflight_paper_path.py`.
14. **Intentional global gates are not health** — an open-market drought caused by `skip_friday_entries`, NY-open delay, or a global session window must be `CONFIG_ENTRY_GATE` ALERT, never `HEALTHY_SELECTIVE_QUIET`. The current book-wide Friday filter is off; the real CME Friday close remains enforced.
15. **Use paid Databento correctly** — keep the `databento_cache_yahoo` adapter, but accept only audited `.v.0` continuous caches; reject legacy parent-symbol files rather than mixing contracts. Do not substitute full-size prices for micro contracts. `databento_allow_api_refresh: false`; every new download/spend requires explicit user approval.

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
- Do not restore a book-wide Friday entry skip from a result that belongs to one ORB variant. Friday remains tradable until the configured CME weekend close.
- Respect CME maintenance (~17:00–18:00 ET) and weekend close.
- Do **not** impose one strategy’s NY opening window on all engines.
- **`nq_context_entry` only** is gated to 09:30–12:00 ET BUY pullbacks — that is not a book-wide NY filter.

### Time stop (paper manage)

- Growth-plan **active**: `max_hold_minutes: 120`, `time_stop_only_if_losing: true` (cut stale losers; winners can run).
- Hold duration must use wall **`received_at` / `ts`**, never delayed market-bar `opened_at` (bug Z — caused instant scratches on 2026-08-12 MES/MYM/MNQ fills).

### EMA spray verdict (do not re-litigate)

- **Not successful.** Spray episode ~64 closes / ~+$93; ~39 were `ema_pullback`; big winners canceled by many small losers. User rejected as not IRL → stays `research_only`. Do not re-enable to “look busy.”

---

## Strategy / decision pipeline (locked)

`active_strategy: decision_pipeline`

Engines (independent; propose only — do not place orders):

**Paper-executable engines (specialists):**
1. `cl_vwap_prox_momentum` (clean frozen Yahoo screen n=41, WR 41.5%, PF 1.28, E +0.174R; latest 20% n=9, PF 1.44; forward proof pending)
2. `nq_context_entry` (clean frozen Yahoo screen n=48, WR 60.4%, PF 1.73, E +0.292R; latest 20% n=10, WR 50%; forward proof pending)

**Research/shadow only:**  
`vwap_rejection`, `ema_pullback`, `trend_continuation`, `trend_pullback`, `liquidity_reversal`, `vwap_reclaim`, `indicator_parity`, `nq_ny_open_momentum`,
`liquidity_sweep`, `vwap_acceptance`, `sweep_retest`, `momentum`, `breakout_retest`, `opening_range`, `vwap_orb`, `vwap_mss`

**Paper specialists** (`paper_specialist_engines`): the two above — tier floor A when cascade OK; exempt from global `execution_quality.min_expected_r` (NQ **1.15R**, CL **2.0R**). Still hard risk / lifecycle / SHADOW gated. Current-stamp forward n=0, so no profitability claim and no risk increase.

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

`execution_quality` (enabled): min R 1.6, min reward $150, reject `POOR_LOCATION` for **thin** engines, require non-MIXED cascade thesis for non-specialists. Location engines may fire alone; may paper with MIXED thesis and may paper when cascade marks VWAP-distance `POOR_LOCATION` (`location_may_trade_away_from_vwap`) — breakout/OR/sweep often legitimately print away from VWAP. Thin engines need 2 agreeing engines. Paper location `target_r_multiple` aligned to ≥1.6 so strategy targets are not permanently below the gate. Does not narrow universe or lower max positions.
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
The hybrid paper feed makes **no Databento API calls**. It first requires continuous-cache metadata (`[ROOT].v.0`, `stype_in=continuous`, `databento_continuous_v1`) plus a continuity audit, then timestamp overlap and ≤2% median basis gap before splicing. All current legacy parent caches fail before use, so Yahoo supplies exact-symbol bars. Yahoo fetches use a real 20-second HTTP timeout, two attempts, `threads=False`, and a 30-second shared in-cycle cache. Do not restore a `with ThreadPoolExecutor(...): future.result(timeout=...)` wrapper or a duplicate startup download.

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

- 2026-08-14: **Pass-7 Reddit indicator/flag/squeeze expansion — profitable flag evidence, no 70% promotion** — froze five materially distinct families and ten variants before results: NQ MACD/9-21 EMA/VWAP/volume momentum, NQ two-bar EMA9 flag pullback, NQ VWAP/EMA9 rejection, balance-only Keltner/Stochastic reentry, and Bollinger/Keltner/MFI squeeze breakout. Added shared prefix-invariant EMA/MACD/ADX/Stochastic/MFI/Bollinger features plus deterministic daily caps/cooldowns. The flag finalist was profitable but below the requested hit-rate gate: long holdout n74 WR58.1% PF1.839 E+0.270R; paid corrected Databento n14 WR64.3% PF4.008 E+0.451R; independent Yahoo n8 WR75.0% PF6.011 E+0.643R. Yahoo n8 is below the frozen n≥10 current gate and the 15-year holdout is not 70%; retuning after opening this holdout is prohibited. Momentum holdout n674 WR41.8%, VWAP rejection n32 WR43.8%, Keltner n2 WR50.0%, squeeze n353 WR46.2% (paid WR25.6%). Master screen is now 42 families / 170 paid cells, zero passing. Full regression is 250 passed and paper-path preflight passes. No new Databento API call/spend and no paper/config/risk/quantity/universe/session/poll/watchdog change.
- 2026-08-14: **Pass-6 OHLCV microstructure-proxy expansion — no promotion** — added five frozen BVC/VPIN-style families and ten variants: six-bar CVD/price divergence, pressure absorption reversal, pressure breakout, toxicity failed-extension, and price-impact shock reversal. One-minute price changes are classified with prior-only volatility and aggregated into completed five-minute signed-volume/pressure/toxicity/impact **proxies**; they do not claim true aggressor delta, queue imbalance, cancellations, or depth. Vectorized unchanged predicates after interrupting a pre-result slow run. Fixed independent Yahoo compatibility: five-minute Yahoo bars are classified directly instead of being incorrectly rejected for lacking four one-minute rows; external selection and paid semantics were unchanged. Long/paid/Yahoo evidence rejected every family; best current cell was toxicity Yahoo 6/10 WR60% PF1.65, contradicted by long holdout n193 WR47.1% PF1.247 and paid n23 WR47.8%. Master screen is now 37 families / 150 paid tests, zero passing. No new Databento download/spend and no paper/config/risk/quantity/universe/session/poll/watchdog change.
- 2026-08-14: **Pass-5 opening-state/gap/volume expansion — no promotion** — added seven frozen, source-backed families and 14 variants: NQ opening-shock reversal, gap reject-then-go, compressed initial-balance/VWAP retest, volume-climax rejection, lunch VWAP reclaim, two-test range breakout, and NQ post-settlement/gap/first-15m alignment. Prefix-invariance coverage proves future bars cannot alter earlier candidates. Long-history selection plus corrected paid Databento and independent Yahoo checks rejected every family; large untouched holdouts were IB/VWAP n478 WR40.0% PF0.807, volume climax n357 WR40.9% PF0.961, lunch reclaim n405 WR43.5% PF1.146, tested range n244 WR43.9% PF0.934, and post-settlement n66 WR42.4% PF1.157. Master screen is now 32 families / 130 paid-window symbol×variant tests with zero passing. No additional Databento API call/spend and no paper/config/risk/quantity/universe/session/poll/watchdog change; paper remains fail-closed.
- 2026-08-14: **25-family expansion + high-precision state model — still no honest 70% promotion** — added prior-day failure, 30/60m OR retest/midpoint, conditional overnight, prior-value-area breakout, overnight-range retest, session-extreme reversal, weekly failed auction, classical value-area 80% rotation, NY-open drive/pause/continuation, 15m ORB retest, and premarket dual-EMA engulfing families. Consolidated paid screen is 25 families / 102 NQ/CL symbol×variant tests. The only paid 70% cell (NQ value-area continuation 17/24) failed the 144-trade long holdout at 35.4%. Public 80%/69% claims and the shallow HGB state model likewise failed protected long and current-source checks. Fixed 30m value-area ATR timing to use the last completed underlying 5m bar after resampling; no result existed before that fix. Added pass2/3/4 and high-precision reports/scripts/tests. Hardened `scripts/healthcheck.py` so Unicode market-status text is replacement-encoded for the active Windows console instead of raising `UnicodeEncodeError`; this changes diagnostics only. No strategy/config/risk/quantity/universe/session/poll/watchdog change; paper stays fail-closed.
- 2026-08-14: **13-family Reddit/long-history restart — no honest 70% promotion** — encoded 13 source-backed families and 54 paid-window symbol×variant tests; added balanced value-area, stopped daily-IBS, long-history selection, and a development-only nonlinear regime router. Audited the public 2010–2025 NQ file, quarantining 6,231 mis-scaled rows without rewriting them; clean daily returns agree 96.67% with Yahoo but unverified provenance keeps it research-only. Corrected Yahoo daily date localization, workspace-local yfinance cache placement, unfinished-entry feature use, overlapping-trade inflation, and large-sample binomial overflow. All family holdouts and the regime router failed the requested 70%+profitability+sample gates; no engine/config/risk/quantity/universe/session/poll/watchdog change was made. Paper remains fail-closed. Fixed silence-monitor precedence so the generic `CONFIG_ENTRY_GATE:NO_VALIDATED_PAPER_STRATEGY` heartbeat overrides stale risk/quality rejects and never recommends a futile restart.
- 2026-08-14: **`router_v1_specialists_autonomy5` corrected paid data + execution-parity fail-close** — user approved an estimated $1.285970583558 Databento pull. Downloaded/audited 180d NQ.v.0 (177,188 rows, PASS) and CL.v.0 (175,049 rows, WARN for 0.6021% short-gap rate); preserved invalid parents under `legacy_parent_20260814_autonomy4`; no duplicate timestamps, null OHLCV, or malformed OHLC. Added persistent cache QA plus source-condition/Yahoo agreement reporting. Found and fixed research execution leakage: one-minute exits had been allowed inside the still-forming five-minute signal bar, and holding time changed with bar granularity. Frozen primary metrics now replay the actual quantity-two paper manager (1R half, next-bar stop tightening, 120m losing-only time stop, friction). Dual evidence is required. NQ fails PF/E and latest Yahoo; CL misses DB WR (53.4% vs 55%). Both are disabled/research-only. Fixed the explicit-empty engine fallback so `engines: []` cannot resurrect legacy EMA/sweep/momentum/VWAP modules; heartbeat reports `CONFIG_ENTRY_GATE:NO_VALIDATED_PAPER_STRATEGY` rather than ambiguous no-candidate health. No gates/risk/quantity/universe/max positions/poll interval were changed; paper entry is fail-closed pending a genuinely passing replacement.
- 2026-08-14: **`router_v1_specialists_autonomy4` evidence/risk/exit repair** — the losing CL trade exposed six concrete defects: CL was paper-enabled despite frozen n=41 WR41.5% PF1.28 failing promotion; negative advisory predictions were not backed by a hard frozen-evidence gate; quantity was sized before paper slippage widened risk; paper management saw only delayed closes instead of completed-bar OHLC; cascade/entry snapshots recomputed contradictory HTF directions; and last-evaluation state preserved retired/empty candidates across config changes. CL is now disabled/research-only and only NQ can paper. A fail-closed artifact gate enforces n≥40/WR≥55%/PF≥1.3/E≥0.15. Paper sizing re-fits after friction and records actual risk; OHLC stop/target/TP1 paths are processed once with stop-first same-bar ordering and no entry-bar replay; TP1 uses config; hold time uses received time; cascade consumes the same MarketContext snapshot. Candidate/engine observability is now scoped to the config stamp and active book, and an evaluated empty bar clears the prior candidate. Frozen NQ n=49: no-scale WR59.2% PF1.64 E+0.265R; configured 1R half-exit WR59.2% PF1.48 E+0.197R and latest slice remains positive. A tempting 0.30R half-exit produced WR75.5% but PF1.05/E+0.013R and latest E−0.261R, so it was explicitly rejected. Corrected NQ.v.0+CL.v.0 180d quote-only was $1.2855; no download/spend. Full suite 218 passed. Risk caps/default quantity/universe/max positions/1m/paper mode unchanged.
- 2026-08-14: **Windows recovery registration re-verified; no new watchdog layer** — the watchdog implementation and scheduled execution already existed; pre-refresh `watchdog.log` contained successful five-minute ticks through 10:54 ET. A sandboxed Task Scheduler query was incorrectly read as authoritative absence. Running the existing installer replaced the same fixed task names (it did not stack duplicates). Elevated verification found exactly one Hidden, `WakeToRun=false`, `IgnoreNew` `TradingAgentWatchdog` and one `TradingAgentAutonomous`; the watchdog returned `0` and the live heartbeat stayed healthy. Future checks must use elevated task state plus execution history before changing registration. Runtime/strategy/risk/quantity/universe/max positions/1m/paper mode unchanged.
- 2026-08-14: **`router_v1_specialists_autonomy3` source/anti-leakage reset** — discovered the paid cache query used `stype_in=parent` (`*.FUT`), returning all outright/spread instruments, then discarded symbols and kept one arbitrary row per minute. Quarantined all four legacy caches; corrected download/quote code to volume-continuous `.v.0`; added metadata + >1% minute-jump guards. Fixed look-ahead leakage in 15m/1h/4h features and centered swings with prefix-invariance tests. Clean frozen Yahoo replay: NQ n48 WR60.4% PF1.73 E+0.292R; CL-only n41 WR41.5% PF1.28 E+0.174R; VWAP rejection n576 PF0.83 E−0.114R → demoted. Current-stamp forward n=0. Corrected CL cache quote-only ~$0.6384; no spend/download. Risk/quantity/universe/max positions/1m/paper mode unchanged.
- 2026-08-14: **`router_v1_specialists_autonomy2` paid-data runtime** — user explicitly required using the Databento data already purchased. Paper provider is now `databento_cache_yahoo`: NQ/ES/GC local 1m caches feed exact full-size history, Databento overrides only verified Yahoo overlap, and Yahoo supplies the current tail. CL's cache showed an unstable ~5.05% continuous-contract gap (500-bar ratio relative MAD ~5.09%) and is correctly Yahoo-only until the cache construction is repaired/rebuilt with explicit approval. Unsafe/no-overlap splices fall back to Yahoo; micros/MYM/M2K are never proxied from full-size caches. Heartbeat/Paper View reports the hybrid provider globally and retains each symbol's exact source. `databento_allow_api_refresh: false` means zero new spend/API calls. Risk/quantity/universe/1m/paper mode unchanged.
- 2026-08-14: **`router_v1_specialists_autonomy1` reliability + truth pass** — live loop evaluates only the 3 paper specialists; research modules remain offline. Removed duplicate startup/management/pipeline Yahoo downloads with real HTTP timeout + 30s snapshot cache; UTF-8 runtime logging prevents Windows cp1252 tracebacks. Removed book-wide Friday skip and made global config droughts ALERT instead of false healthy quiet. Daily kill now uses current ET-day realized cash events, not lifetime P&L; TP1 and day/session reports no longer double-count partials or shift naive ET market timestamps. `vwap_rejection` uses only completed 1h buckets. Risk/quantity/universe/1m/paper mode unchanged.
- 2026-08-13: **Paper View readability** — “Papering NOW” card lists the 3 live specialists; closed/open tables show Strategy + SPECIALIST vs LEGACY SPRAY badges; cohorts split specialists vs spray; sections grouped Status / Trading / Optional. Fold state key `paper_view_folds_v4`.
- 2026-08-13: **`router_v1_specialists_vwaprej`** — user: run what works; soften impossible 65%/n100. Practical `GATES` → WR≥55% n≥40 PF≥1.3 E≥0.15; aspirational 65/100 retained separately. Wired live `vwap_rejection` (1h resample) as paper specialist alongside NQ+CL. Databento R1.5 final n=86 WR~77% E~+0.84R clears practical gates; Yahoo 1h same rule **fails** — promote on Databento truth. Breakout spray still research_only.
- 2026-08-13: **Databento book cache + dual hardening** — user OK ~$26 credit pull: NQ/ES/CL/GC 180d cached (est. **$25.59**). Spend lock. Dual pass report under `data/dual_source_hardening/`.
- 2026-08-13: **`router_v1_specialists_only`** — stop Aug13 location bleed: paper only `nq_context_entry` + `cl_vwap_prox_momentum`; demote breakout/sweep/VWAP/OR/MSS/momentum to research_only. Drought `specialists_only_selective_quiet`. Prior Yahoo-only S&D/PA FAIL kept as historical; dual-source pass is the hardening authority.
- 2026-08-12: **Breakout_retest forward research pass (observation only)** — locked `router_v1_paperfix2` overnight (no strategy/risk/qty/engine/router changes). Added `scripts/run_breakout_retest_forward_report.py` + `src/agent/research/breakout_retest_forward.py` for winner/loser datasets, PRE vs POST-fix2 cohorts, shrunk cells, forensics. Paper View adds display-only clean WR cohorts. Agent kept running; do not auto-tune from overnight tiny samples.
- 2026-08-12: **`router_v1_paperfix2`** — prefer full-size over micro within product family (ES/NQ before MES/MNQ same side) so family max=1 does not silently micros-only the book. Still one opportunity per family; risk remap NQ→MNQ only when hard $ risk binds.
- 2026-08-12: **Time-stop clock fix** — hold duration uses wall `received_at`/`ts`, not delayed market-bar `opened_at` (was instantly scratching new multi-lot breakouts). Still multi-engine paper book; NQ specialist is one engine only. EMA stays research_only (spray was not successful).
- 2026-08-12: **`router_v1_paperfix1`** — London/full-book paper path: location engines exempt from cascade VWAP-distance `POOR_LOCATION` kill; paper location targets ≥1.6R; silence watch only flags RESEARCH_SUPERSEDE when a **paperable** loser is beaten by research_only; risk engine uses **position** reward vs EQ/confluence floor (fixes multi-lot A+ dying as `$80 < $90`). NQ window ≠ only trade window. EMA stays research_only; risk/qty/universe unchanged.
- 2026-08-12: **Paper View simplified** — top “At a glance” (running vs paper-trading vs flat) + equity/open; dense learning/tech sections collapsed by default (`paper_view_folds_v3`). Keep all detail available on expand.
- 2026-08-12: **Paper View run banner** — big ACTIVELY RUNNING / DEGRADED / NOT ACTIVELY RUNNING (STUCK) banner on `paper_trading_view.html` so wall-clock scan health is unmistakable vs “NO NEW BAR” idle. Shows config stamp. Overnight ~12h heartbeat freeze (19:47→08:02 ET) auto-recovered by supervisor; prefer AC + overnight_power.
- 2026-08-11: **`router_v1_nqctx1`** — wire `nq_context_entry` as paper specialist (PULLBACK BUY-only `0930_1200` signal_close 1.15R zone0.30 stop0.55 vwap0.20 cd2). Pipeline/cascade/lifecycle/fit evidence + NQ→MNQ remap. Specialists exempt from global min R 1.6. `nq_ny_open_momentum` stays research_only. Live not activated.
- 2026-08-11: **NQ WR≥65% locked (strict)** — Databento cache (~224k bars, 2025-04-16→2025-12-11). Champion `NQ_CONTEXT_ENTRY` **PULLBACK BUY-only** `0930_1200` / `signal_close` / `1.15R` / zone=0.30 / stop=0.55 / vwap_buf=0.20 / cd=2. Holdout **n=57 WR≈73.7% PF≈4.9 E≈+0.64R**; mean fold WR≈75.2%; **min fold WR≈68.4%** (all folds ≥65%); val n=288 WR≈76%. Soft boost earlier: `1000_1200` 1.0R family also comfortable (n=42 WR≈69%). Reports: `data/nq_focused_research/NQ_WR65_STRICT_REPORT.md`, `NQ_WR65_BOOST_REPORT.md`. Verdict **`NQ STRATEGY READY FOR DEMO`**. Paper/risk/universe/live unchanged — research lock only; do not auto-enable as paper engine.
- 2026-08-11: **Databento finetune (cheap)** — cached NQ 1m locally (`data/databento/NQ_1m_cache.parquet`, ~180d, ~$0.90 total). Filtered junk ~$233 spread prints. Structural exits removed from selection. PULLBACK next_bar shows **val** edge (~53% WR / PF~1.7 / E~+0.3R) but holdout still thin/negative → verdict remains **NOT YET GOOD ENOUGH**. No large Databento spends; paper unchanged.
- 2026-08-11: **Databento API live** — local `.env` key only. Kaggle vs Databento NQ 1m **materially inconsistent** → `USE_DATABENTO_AS_TRUTH`. Kaggle-selected `NQ_CONTEXT_ENTRY` finalists **fail** on Databento 120d holdout (balanced cell WR~40% / PF~0). Verdict remains **NOT YET GOOD ENOUGH**. Paper unchanged.
- 2026-08-11: **NQ-focused research pass (stop strategy-iteration spray)** — primary research target = prove one NQ NY-morning family `NQ_CONTEXT_ENTRY` (PULLBACK / LIQUIDITY / BREAKOUT_RETEST only). Kaggle 1m loader (`tgtanalytics` Dataset_NQ_1min_2022_2025) + quality audit + Databento `fetch_ohlcv_df` / cross-check; walk-forward + holdout via `scripts/run_nq_focused_research.py` → `data/nq_focused_research/`. Yahoo kept for paper diagnostics only. Git tag `baseline-before-nq-focused-research`. Paper/risk/universe/router_v2 enablement unchanged; live not activated.
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
