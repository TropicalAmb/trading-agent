# Corrected Databento Cache Quality

Overall: **WARN**

## Dataset and grain

- Intended use: frozen strategy research and verified historical paper context
- Expected grain: one OHLCV row per available CME minute per volume-continuous root
- Source: Databento GLBX.MDP3 `ohlcv-1m`, `stype_in=continuous`, volume roll `.v.0`.

## Findings

### NQ

- Cache status: **PASS**; rows=177,188; range=2026-02-15 18:00:00-05:00 → 2026-08-14 04:55:00-04:00.
- Required-field nulls=0; duplicate timestamps=0; invalid OHLC=0; negative volume=0.
- Consecutive-minute >1% jumps=0.0011%; max consecutive-minute return=1.700%; max re-open/gap return=1.446%.
- 2–30 minute gap rate=0.0333%; one-minute gap share=99.89%.
- Yahoo overlap: PASS n=13,662; median basis=0.000%; 5m return correlation=0.9843.
- Failures: none; warnings: none.

### CL

- Cache status: **WARN**; rows=175,049; range=2026-02-15 18:00:00-05:00 → 2026-08-14 04:55:00-04:00.
- Required-field nulls=0; duplicate timestamps=0; invalid OHLC=0; negative volume=0.
- Consecutive-minute >1% jumps=0.0961%; max consecutive-minute return=5.510%; max re-open/gap return=10.913%.
- 2–30 minute gap rate=0.6021%; one-minute gap share=99.32%.
- Yahoo overlap: PASS n=13,555; median basis=0.000%; 5m return correlation=0.9490.
- Failures: none; warnings: ['elevated_2_to_30m_gap_fraction:0.006021'].

## Temporal/source conditions

- Dataset-condition status: **WARN**; days checked=181; degraded entries=6.
- Degraded dates remain usable only with this warning attached; strategy conclusions must also survive an independent-source check.

## Automated acceptance rules

- Exact `.v.0` metadata and `stype_in=continuous`.
- Unique timestamp grain, complete finite OHLCV, valid OHLC relationships, positive prices, non-negative volume.
- No more than 0.2% of truly consecutive one-minute returns above 1%; weekend/maintenance re-opens are reported separately.
- Yahoo comparison reports overlap, median relative basis, p95 basis, and 5-minute return correlation.

## Analytical use

A cache marked FAIL is quarantined. PASS/WARN caches may enter frozen research; WARN results must retain the stated caveat and cannot alone justify a profitability claim.
