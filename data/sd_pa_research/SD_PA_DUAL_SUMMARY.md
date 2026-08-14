# S&D / PA Dual-Source Summary

Full dual hardening report: [`data/dual_source_hardening/DUAL_SOURCE_HARDENING_REPORT.md`](../dual_source_hardening/DUAL_SOURCE_HARDENING_REPORT.md)

## Verdicts

| Source | Verdict | Best supply/demand (final) | Best price_action (final) |
|--------|---------|----------------------------|---------------------------|
| Yahoo 5m ~60d | **FAIL** | n=174 WR~41% E~-0.16R | n=112 WR~31% E~-0.20R |
| Databento 5m ~180d | **WATCH** | n=411 WR~51% E~+0.40R PF~1.91 | n=472 WR~44% E~+0.13R |
| Databento ∩ Yahoo overlap | **WATCH** | n=176 WR~52% E~+0.45R PF~2.05 | n=177 WR~30% E~-0.11R |

## Takeaway

- Yahoo-only made S&D look dead; **Databento shows mild positive expectancy** but **not** WR≥65 / hard gates.
- Price action sweep-reclaim stays weak across sources.
- **Do not paper S&D/PA.** Refine later on **local caches only** (no new Databento spend).
- Paper stays `router_v1_specialists_only`.
