# Women in Day Trading (FB) — research notes (chunked)

Group: https://www.facebook.com/groups/690505400576058 (~26.7k)

Chunks are appended over time in `research_wit_chunks.jsonl` (not one giant scrape).
Append helper: `scripts/research_wit_append_chunk.py`

## Chunks completed

1. **sd_liquidity_1** — supply/demand + liquidity; 5m zone / 1m entry; Matt Donlevy S/D
2. **session_futures_2** — ≥3 confirmations; Friday pain; futures over forex; no no-stop trading
3. **orb_structure_3** — A+ 5m ORB: leave → retest (1:2) → continuation; daily context; MYM 15m ORB; some first-break experiments
4. **discipline_icc_sd_4** — ICC+S&D+FVG common; pick one personality fit; FOMO/FOMC rule breaks wipe accounts; sniper = 3 alignments; no-stop called out; S/D WR ~53–57% when mixed
5. **accuracy_wr_5** — social “90% WR premarket ORB wait 15m” claim; OOS wait15 ≈57% (claim fails). Structure/phase > single criterion.
6. **friday_discipline_6** (2026-08-09) — reconfirms Friday cook / no-Friday + no-before-10am personal rules
7. **orb_first_break_curiosity_7** (2026-08-09) — members experiment 15m/5m first-break without retest on MNQ/MGC; A+ framing still leave→retest
8. **gold_asia_structure_8** (2026-08-09) — Gold Asia builds structure/bias not always completes move; futures preferred vs forex; 5m ORB taught as starter for gold newcomers
9. **sniper_3align_9** (2026-08-10) — full “THE SNIPER ENTRY SYSTEM”: ONLY enter when (1) HTF trend 1H/4H, (2) key S/R zone, (3) engulf / pin / momentum candle. Max 1–3 trades/day. Prop-eval blowups from S/D backtest≠live also noted.
10. **reddit_field_10** (2026-08-10) — Reddit/algo field (API often 403; web aggregate): realistic systems often 45–60% WR; edge from R:R + 1–2% risk; 70%+ social claims treated skeptically; overfitting / costs kill live.

## High-WR focus pass (2026-08-10)

Script: `scripts/run_high_wr_focus_pass.py` → `data/high_wr_focus/HIGH_WR_FOCUS_REPORT.md`

Sniper-style filters (MTF3 + zone + candle confirm / session / product) on expanded history. **No robust ≥65% with large n.**

| Config | FINAL WR | E | PF | n | Notes |
|--------|----------|---|----|---|-------|
| london_mtf3_R1.0 | **60.7%** | +0.21R | 1.58 | **305** | Best large-n accuracy lift vs ~57% book |
| gc_mtf3_R1.0 | 62.3% | +0.27R | 1.84 | 106 | Gold-only stronger; narrower book |
| nymid_mtf3_R1.0 | 61.5% | +0.18R | 1.47 | 65 | Mid-NY window; thinner |
| gc_london_mtf3_R1.0 | **65.2%** | +0.32R | 2.03 | 46 | Hits 65% headline; **thin n**, not ship-ready alone |
| sniper_mtf3_retest (book) | 56.2% | +0.11R | 1.26 | 901 | Confirms ~57% book-wide ceiling so far |

**Verdict:** session/product filters can push **~61%** (London MTF3, n=305). Still short of a durable ≥65% book edge. Keep researching; do not declare victory at mid-50s.

## Accuracy hunt (multi-strategy, not ORB-only)

Scripts: `research_accuracy_hunt.py` (104 configs), `research_high_wr_pass.py` (38 configs).

| Config | OOS WR | E | n | Notes |
|--------|--------|---|---|-------|
| Prior live ORB5 first_break skipFri | 56.4% | +0.334R | 39 | Strong $ edge, WR mid |
| ORB5 + VWAP align | 56.8% | +0.340R | 37 | Slightly cleaner |
| ES-only ORB5 + VWAP | **62.5%** | +0.389R | 16 | Best accuracy+edge combo; **thin n**, CI crosses 0 |
| Premarket ORB (no wait) | **63.9%** | +0.085R | 36 | Higher WR, **weak edge**, CI crosses 0 |
| FB “wait 15m → 90% WR” | ~57% | +0.11R | 35 | Claim **not** validated OOS |
| VWAP+MSS+MTF3 (expanded FINAL) | ~55–57% | +0.11R | 500+ | Edge-positive; failed hard ≥65% gate |

**Paper promotion (soft, 2026-08-09):** expectancy > 0, PF ≥ 1.2, n ≥ 30, anti-cheat OK. WR tracked, not a hard blocker.

**Live applied:**
- `opening_range.require_vwap_align: true`, NY 5m first_break, London retest, skip Friday
- `vwap_orb` enabled
- `vwap_mss` enabled (`vwap_mss_v1`, MTF3 + VWAP reclaim/retest)
- `config_version: opt_v2`

## Precise backtest method

`scripts/research_wit_precise_backtest.py` + `scripts/research_wit_orb_focus.py`

- Yahoo 5m × 60d (NQ/ES/GC)
- Walk-forward 4 folds (OOS only for ranking)
- Friction ≈ 2 ticks slip + 1 tick buffer
- Max 1 ORB trade/day
- Bootstrap 95% CI on OOS expectancy

## Strongest quantitative result (combined book)

**ORB 5m first_break + skip Friday + 1.5R**

| Metric | Value |
|--------|-------|
| OOS n | 39 |
| PF | 1.861 |
| Expectancy | +0.334R |
| Win rate | 56.4% |
| CI95(E) | **[+0.015, +0.694]** |
| Max DD | -2.12R |

## Scrape honesty

Infinite-scroll FB groups are not fully scraped. Chunked keyword/theme passes only.
Scrape resumed 2026-08-09 (chunks 6–8). More chunks still needed; do not claim completeness.

## Still to chunk later

- HTJ / Trades by Sci deeper threads + comments
- Explicit position-sizing / contract-count discussions (search thin)
- ORB “third move” continuation comment threads (partial via chunk 7)
- Prop vs live psychology (partial in chunk 4 / sniper chunk 9)
- More Reddit futures-specific threads (browser; API blocked)
- Follow-up: London-session MTF3 ablation + GC session combo with costs stress

## Files

- `data/research_wit_chunks.jsonl`
- `scripts/research_wit_append_chunk.py`
- `data/research_wit_precise_backtest.json`
- `data/research_wit_orb_focus.json`

3. **sniper_3align_9** — THE SNIPER ENTRY SYSTEM (HIGH ACCURACY) — 3 must align (2026-08-10)
   - Sniper = HTF trend + key zone + candle confirm. Maps to our MTF3 + structure/VWAP zone + engulf/reject filters.
   - Backtest≠live discipline failures dominate group pain; keep paper forward testing.

3. **reddit_field_10** — Reddit/algo field notes (web research; API blocked) (2026-08-10)
   - Reddit consensus: do not require 65%+ for a system to be real; chase confirmation quality + risk. User still wants higher WR — pursue via sniper filters, not fantasy claims.
