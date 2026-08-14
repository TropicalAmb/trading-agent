# DEBUG.md — Trading Agent (known bugs, traps, fixes)

**Last updated:** 2026-08-14
**Purpose:** Prevent Cursor from reintroducing bugs we already fixed. Read with `PROJECT_MEMORY.md`.

---

## AK — Clean replay failure must demote, not be tuned around (2026-08-14)

| | |
|--|--|
| **Symptom** | A 1h VWAP-rejection engine was papered from a high legacy Databento estimate even though an independent source disagreed; the UI continued displaying the invalid win rate. |
| **Root cause** | Selection trusted contaminated parent-cache evidence and did not isolate an exact-stamp forward cohort. |
| **Fix** | Stamp `router_v1_specialists_autonomy3`; clean frozen Yahoo replay produced n=576, WR 37.5%, PF 0.83, E −0.114R (latest 20% PF 0.63), so `vwap_rejection` is disabled and `research_only`. Paper View counts only completed trades under the exact current stamp and hides invalid historical WR labels. Active forward book is NQ context + CL VWAP-prox; current-stamp n=0 means not proven and risk stays unchanged. |
| **Do not** | Retune on this failed sample, put `vwap_rejection` back in `confluence.engines`/`paper_specialist_engines`, mix old stamps into forward WR, or increase risk before adequate positive forward evidence. |

---

## AJ — Parent Databento rows and higher-timeframe look-ahead inflated research (2026-08-14)

| | |
|--|--|
| **Symptom** | Paid CL could jump among roughly $64/$68/$73/$83/$98/$113 in adjacent minutes; legacy win rates collapsed on an independent clean replay. |
| **Root cause** | `*.FUT`, `stype_in=parent` returns all outright contracts and spreads. The loader removed the symbol column and kept an arbitrary duplicate timestamp, manufacturing a non-tradable series. Research also resampled full future 15m/1h/4h closes into earlier 5m rows, and centered swings appeared before right-side confirmation. |
| **Fix** | Single-series Databento must use `[ROOT].v.0`, `stype_in=continuous`; cache metadata version `databento_continuous_v1` and ≤0.2% of minute returns above 1% are mandatory. Legacy caches are rejected before paper use. HTF features now use point-in-time partial buckets and swings shift onto their confirmation bar; prefix-invariance tests enforce no future-row influence. Corrected 180d CL quote-only was ~$0.6384; no data was downloaded. |
| **Do not** | Flatten parent results, accept a cache because its median basis happens to be close, strip instrument identity before selecting a contract, use completed future bucket values, or cite any old parent-cache win rate as valid. New spend still requires user approval. |

---

## AI — Paid Databento cache was outside the paper path (2026-08-14)

| | |
|--|--|
| **Symptom** | Roughly $25.59 of current NQ/ES/CL/GC Databento history was used for research selection but the autonomous paper provider still read Yahoo alone—even for a strategy whose Yahoo and Databento results disagree. |
| **Fact** | Local exact-root caches have ~175k 1m bars each from 2026-02-15 through 2026-08-13. They are historical, not a current live subscription; new API refreshes can spend more money. |
| **Fix** | Stamp `router_v1_specialists_autonomy2`; `DatabentoCacheYahooProvider` uses paid exact-root cache bars on timestamp-verified, ≤2% basis overlap and Yahoo only for the current tail. No-overlap/basis-fail → cached Yahoo fallback. Production proof accepted NQ/ES/GC (1,904 paid 5m bars each); CL correctly fell back because its 5.049% gap is unstable (500-bar ratio relative MAD 5.09%). Micros/MYM/M2K use their exact Yahoo contracts. Runtime metadata proves paid-bar count, cache endpoint, basis gap, and `databento_api_called: false`; heartbeat/Paper View must keep the global hybrid source instead of being overwritten by the last Yahoo-only symbol. |
| **Do not** | Leave the paid cache disconnected, silently call the Databento API, proxy full-size prices into micro trades, or splice feeds without overlap/basis checks. Current config keeps `databento_allow_api_refresh: false`; new spend still needs user approval. |

---

## AH — Daily-loss and bar/report truth defects (2026-08-14)

| | |
|--|--|
| **Symptom** | A historical cumulative loss could permanently trip the “daily” kill; TP1 rows inflated win/P&L summaries; Asia trades could land on the prior ET date; 1h VWAP rejection could evaluate the still-forming hour. |
| **Root cause** | `live_main` compared lifetime `realized_pnl()` to daily limits. Final scale-out rows already contain partial P&L but reports also counted TP1 rows. Shared timestamp parsing assigned UTC to naive Yahoo ET stamps. Pandas resampling returned the incomplete last 1h bucket. |
| **Fix** | `realized_pnl_today()` sums current ET-day cash events without double-counting partials; live kill uses it while logging lifetime P&L separately. Session reports count only completed trade rows and preserve naive market timestamps as ET. `vwap_rejection` requires a completed 1h bucket and passes its source timestamp to the setup. |
| **Do not** | Use lifetime realized P&L for a daily kill. Add TP1 and final-row P&L together. Treat naive provider timestamps as UTC. Fire an hourly close-rejection from a partial hour. |

---

## AG — Yahoo freeze, duplicate scans, and false healthy drought (2026-08-14)

| | |
|--|--|
| **Symptom** | Historical supervisor logs show stuck-heartbeat restarts; a nominal 40s Yahoo timeout could hang; live startup/cycles multiplied Yahoo traffic; every Friday the whole book was flat while silence health called it normal. Windows logs contained hundreds of cp1252 encoding tracebacks. |
| **Root cause** | `with ThreadPoolExecutor(): future.result(timeout=...)` waits for the worker during context exit, defeating the timeout. Startup probed all symbols, management fetched them again, then pipeline fetched them again. `skip_friday_entries: true` was a global research gate, and specialist quiet logic masked it. Pythonw inherited a legacy Windows code page. |
| **Fix** | Stamp `router_v1_specialists_autonomy1`: yfinance real 20s HTTP timeout, `threads=False`, two attempts, 30s shared snapshot cache; pipeline first cycle replaces duplicate startup probe. Runtime evaluates only NQ/CL/VWAP-rejection specialists; research engines stay offline. Friday global skip off; silence monitor emits `CONFIG_ENTRY_GATE` for global entry gates. Force UTF-8 in supervisor/runtime. |
| **Do not** | Restore the ThreadPool timeout wrapper, duplicate all-symbol probes, book-wide Friday skip, live evaluation of every research module, or classify an intentional global block as healthy selective quiet. Do not change risk/qty/universe/1m to compensate for data stalls. |

---

## AF — Paper View SPECIALIST vs LEGACY badges (2026-08-13)

| | |
|--|--|
| **Symptom** | User cannot tell if new specialists are live; blotter still looks like spray day. |
| **Fix** | Paper View: Papering NOW card; Strategy + SPECIALIST/LEGACY SPRAY badges; cohorts split; Status/Trading/Optional groups; folds v4. |
| **Do not** | Judge specialist performance from LEGACY SPRAY rows. |

---

## AE — Practical gates + vwap_rejection paper (2026-08-13)

| | |
|--|--|
| **Symptom** | Aspirational WR≥65% + n≥100 cleared zero families; user rejects babysitting losses and wants proven specialists live. |
| **Fact** | Databento 1h `vwap_rejection` R1.5: final n=86 WR~77% E~+0.84R. Yahoo 1h same definition loses. NQ/CL specialists already paper. |
| **Fix** | Stamp `router_v1_specialists_vwaprej`: paper `vwap_rejection` + NQ + CL. `GATES` practical (55%/40/1.3/0.15); `ASPIRATIONAL_GATES` 65/100 track-only. Evaluator resamples 5m→1h. |
| **Do not** | Re-enable breakout spray. Do not ignore Databento/Yahoo disagreement — prefer Databento for CME research. Do not raise target R to 1.6 for specialists. |

---

## AD — Research must dual Databento+Yahoo; spend lock (2026-08-13)

| | |
|--|--|
| **Symptom** | S&D/PA screened on Yahoo only while user pays Databento credits; unclear whether FAIL is real. |
| **Fact** | Paper scans stay Yahoo delayed. Research truth is Databento GLBX when cached. Book caches NQ/ES/CL/GC 1m ~180d on disk (~$25.59 est.). `fetch_ohlcv_df` previously forced `close>=5000` for all symbols (would empty CL). |
| **Fix** | Symbol-specific close floors; `scripts/cache_databento_book.py` + `run_dual_source_hardening.py`. Prefer dual reports before promote. |
| **Do not** | Re-download Databento without user OK. Do not promote from Yahoo-only. Do not call Databento API inside hardening once caches exist. Do not paper S&D from Databento WATCH (~51% WR) or `vwap_rejection` until n/WR gates clear on dual sources. |

---

## AC — Location spray beat specialists; S&D/PA failed gates (2026-08-13)

| | |
|--|--|
| **Symptom** | Aug12 breakout winners (+~$1k engine day) then Aug13 wipe (breakout ~−$2.8k); blotter ~−$1.75k; user demands researched edge / S&D-PA bare bones. |
| **Fact** | Researched paper specialists barely filled; `breakout_retest` dominated paper at WR~34%. New Yahoo S&D/PA screen (`data/sd_pa_research/SD_PA_RESEARCH_REPORT.md`) verdict **FAIL** — no config met WR≥65/n≥100/E gates (best family finals ~31–41% WR, negative E). |
| **Fix** | Stamp `router_v1_specialists_only`: only `nq_context_entry` + `cl_vwap_prox_momentum` paperable; location engines → `research_only`. `trade_drought_policy.specialists_only_selective_quiet: true` → no-setup silence is HEALTHY_SELECTIVE_QUIET (bugs/stale/supersede still ALERT). |
| **Do not** | Re-enable `breakout_retest`/location paper from one green afternoon. Do not promote S&D/PA from tiny cells (e.g. CL NY_MID BUY n=17). Do not ease quality gates or EMA spray to “look busy.” |

---

## AB — Overnight forward research ≠ permission to retune (2026-08-12)

| | |
|--|--|
| **Symptom** | Strong paperfix2 winners (ES/CL/GC breakout targets) tempt same-day filter/promotion changes. |
| **Fact** | User locked `router_v1_paperfix2` for clean overnight Asia/London forward sample. Breakout_retest is priority **research family**, not promoted. |
| **Fix / process** | Observation tools only: `scripts/run_breakout_retest_forward_report.py` → `data/research/breakout_retest_forward_<DATE>.md`. Re-run tomorrow morning. No risk/qty/threshold/engine/router_v2/family-policy changes unless a genuine software defect. |
| **Do not** | Auto-tune from 3 overnight wins or losses. Do not restart agent for research convenience. |

---

## AA — Micros monopolized family slot vs ES/NQ (2026-08-12)

| | |
|--|--|
| **Symptom** | Universe has ES+NQ but paper fills skew MES/MNQ; ES rejected `product family limit … MES already has …`. |
| **Fact** | `max_same_direction_per_family: 1` is correct (MES+ES = same bet). Micros often ranked/filled first → full-size blocked for the rest of the hold. Not a universe cut. |
| **Fix** | `prefer_full_size_in_family: true` + ranker collapses family+side to full-size when both paperable (`router_v1_paperfix2`). Remap full→micro only when hard $ risk cannot fit 1 contract. |
| **Do not** | Remove ES/NQ from universe, or raise family max to 2 without user ask (that doubles the same underlying). |

---

## Z — Time stop used market-bar clock → instant scratches (2026-08-12)

| | |
|--|--|
| **Symptom** | Fresh paper fills (MES/MYM/MNQ breakout qty=3) exit `time_stop` within minutes for tiny losses. |
| **Fact** | `opened_at` stores **market bar time** (honest for delayed Yahoo). Hold math did `now(UTC) - opened_at` and treated naive ET bar stamps as UTC → brand-new fills looked 2–4h old. With `time_stop_only_if_losing: true`, one tick of slippage → scratch. |
| **Fix** | Hold clock uses `received_at` / `ts` (wall), not market `opened_at`. Intentional max hold remains growth_plan **120m** for losers only. |
| **Do not** | Measure hold from delayed market timestamps. Do not remove time stops entirely without user ask. |

---

## Y — London flat while scanning: mis-gates ≠ “only NQ trades” (2026-08-12)

| | |
|--|--|
| **Symptom** | CME open (London), agent scanning, 0 paper fills for hours; silence ALERT `RESEARCH_SUPERSEDE_DOMINANT`; user expects multi-engine book to paper whenever a market is open. |
| **Fact** | NQ `nq_context_entry` quiet outside 09:30–12:00 ET is **correct**. Paper A/A+ from `breakout_retest` / `opening_range` still died on (1) `EXECUTION_QUALITY:POOR_LOCATION` — cascade VWAP-distance kill wrongly applied to structural location engines; (2) `EXECUTION_QUALITY:R<1.6` while engine `target_r_multiple` was still **1.5** (permanent mismatch). Many “supersedes” were research-vs-research ledger noise. |
| **Fix** | Stamp `router_v1_paperfix1`: `location_may_trade_away_from_vwap` skips POOR kill for `LOCATION_STRATEGIES`; align paper location targets ≥1.6; `_classify_reject` only counts RESEARCH_SUPERSEDE when **loser is paperable** and winner is research_only. Also: `DirectionalRiskEngine` must compare **position** reward (`per_contract × qty`) to `execution_quality`/`confluence` floors — not per-contract vs stale `sweep_retest` $90 (killed A+ qty=3 with $240 position reward as “$80 < $90”). `active_strategy: decision_pipeline` must mirror EQ/confluence into sweep keys. |
| **Do not** | Treat NQ NY window as the only trading window. Do not re-enable EMA spray or ease min R/$ to “force” fills. Do not restart forever on research-vs-research supersede counts. Do not compare per-contract dollars to position-level floors. |

---

## X — Paper View “HEALTHY / NO NEW BAR” ≠ proof of life (2026-08-12)

| | |
|--|--|
| **Symptom** | Agent View shows primary text like `AGENT HEALTHY — NO NEW MARKET BAR` while the bot has been dead for hours. |
| **Fact** | That string is the **last scan decision**, frozen in `paper_trades.json` until the next heartbeat rewrite. Overnight 2026-08-11 ~19:47 ET → 2026-08-12 ~08:02 ET: ~12h no scheduler tick; supervisor eventually restarted (`scheduler_heartbeat_stuck_*`). |
| **Fix** | Big run-status banner on Paper View: **ACTIVELY RUNNING** / **DEGRADED** / **NOT ACTIVELY RUNNING (STUCK)** from heartbeat age (warn 90s / stuck 150s). Idle between 5m bars still shows ACTIVELY RUNNING with plain-English note. **At a glance** card separates *scanning* vs *paper trading* (open positions / entry signals / flat). Dense sections collapsed by default. |
| **Do not** | Treat “NO NEW BAR” or supervisor `state=running` alone as proof of scanning — check heartbeat age / banner color. Keep overnight AC + `overnight_power`. Flat ≠ broken outside NQ 09:30–12:00 ET window. |

---

## W — NQ research must not restart the architecture loop (2026-08-11)

| | |
|--|--|
| **Symptom** | Mega-spec for “prove one NQ strategy” gets answered by another universal multi-engine / ML rebuild. |
| **Fact** | User ordered **STOP THE STRATEGY ITERATION LOOP**. Preserve provider/supervisor/paper/risk/learning/router/shadow/journal/dashboard/replay/broker/live_pilot/tests. Simplify **primary research target** only: `NQ_CONTEXT_ENTRY` on NQ 1m (Kaggle broad + Databento finalists). |
| **Do not** | Rebuild backend, stop paper agent, activate live, promote router_v2 to paper, or engineer WR to 70%. Report honest frontier + `READY FOR DEMO` / `NOT YET GOOD ENOUGH`. |
| **Data trap** | Building a DataFrame with `index=timestamps` from Series that still have `RangeIndex` → **all-NaN OHLC** (silent). Always `.to_numpy()` when assigning columns onto a new DatetimeIndex. |
| **Data trap 2** | Kaggle `Dataset_NQ_1min_2022_2025` is **not** CME-grade vs Databento GLBX.MDP3 (median ~258pt abs close gap; ~0 RTH return corr). Finalists must be validated on Databento; do not declare demo-ready from Kaggle WR alone. |
| **Data trap 3** | Databento `NQ.FUT` parent can mix **calendar-spread prints (~$200–300)** into OHLCV. Always filter `close >= 5000` (or outright symbol match) before research or stops explode. Cache filtered parquet under `data/databento/`. |
| **WR trap** | Soft “comfortable” (mean fold ≥65%, min fold ≥55%, holdout n≥40) can still hide a weak fold (~61%). For “consistently ≥65%”, require **min fold WR ≥65%** too (`scripts/run_nq_wr65_strict.py` / `run_nq_wr65_lock.py`). |
| **Report trap** | Writing research MD with `≥` under Windows default cp1252 → `UnicodeEncodeError`. Always `Path.write_text(..., encoding="utf-8")`. |
| **Spend** | Do not bulk-download years of 1m blindly. Prefer local cache + incremental ≤60–90d pulls after `metadata.get_cost`. |
| **Secrets** | Never commit `DATABENTO_API_KEY`. If pasted in chat, rotate the key in the Databento portal. |
| **Locked champion (research)** | PULLBACK BUY-only `0930_1200` signal_close 1.15R zone0.30 stop0.55 vwap0.20 cd2 — holdout n=57 WR≈74% minF≈68%. |
| **Paper wire (`router_v1_nqctx1`)** | Live evaluator `evaluate_nq_context_entry` + YAML engines/`paper_specialist_engines`. Do **not** put in `research_only_engines`. Do **not** silently raise target to 1.6R to pass global quality — specialists are exempt from min_expected_r; champion is 1.15R. Do not tweak champion params during forward sample. |

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
| Yahoo hang | Real yfinance HTTP timeout (`threads=False`), bounded retries, per-symbol isolation, shared in-cycle cache; never the ThreadPool context-manager pseudo-timeout |
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
Stamp check: `config_version` should be `router_v1_specialists_autonomy3` (NQ context + CL VWAP-prox only; legacy parent caches rejected, Yahoo fallback until corrected `.v.0` caches are approved; all other engines offline-only).

When diagnosing **zero paper trades**: check (1) heartbeat/`NO_NEW_BAR`, (2) shadow open count, (3) `AGREEMENT_SUPERSEDED_BY_*` in `execution_decisions.jsonl` (only paperable-loser→research is a steal), (4) `execution_quality` / MIXED / POOR_LOCATION rejects, (5) instant `time_stop` on new fills → bug Z wall-clock hold, (6) not just “markets quiet.”

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
15. Call a book-wide schedule block `HEALTHY_SELECTIVE_QUIET`, or use lifetime P&L as the daily kill input
16. Pay for Databento history, then leave it disconnected from paper—or trigger new paid API refreshes without explicit approval
