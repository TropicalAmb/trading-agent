"""Audit corrected Databento caches and write an inspectable quality report."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys

import pandas as pd
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
load_dotenv(ROOT / ".env")

from agent.research.databento_cache_quality import (
    audit_continuous_cache,
    compare_with_yahoo_5m,
)
from agent.research.harness.datasets import fetch_yahoo


def _dataset_conditions(start: str, end: str) -> dict:
    key = (os.getenv("DATABENTO_API_KEY") or "").strip()
    if not key:
        return {"status": "UNAVAILABLE", "reason": "DATABENTO_API_KEY missing"}
    try:
        import databento as db

        rows = db.Historical(key).metadata.get_dataset_condition(
            dataset="GLBX.MDP3",
            start_date=pd.Timestamp(start).date().isoformat(),
            end_date=pd.Timestamp(end).date().isoformat(),
        )
        degraded = [r for r in rows if str(r.get("condition") or "").lower() != "available"]
        return {
            "status": "WARN" if degraded else "PASS",
            "days_checked": len(rows),
            "degraded_days": degraded,
        }
    except Exception as exc:
        return {"status": "UNAVAILABLE", "reason": f"{type(exc).__name__}:{exc}"}


def main() -> int:
    cache_dir = ROOT / "data" / "databento"
    audits = {}
    comparisons = {}
    yahoo_symbols = {"NQ": "NQ=F", "CL": "CL=F"}
    for root, ticker in yahoo_symbols.items():
        path = cache_dir / f"{root}_1m_cache.parquet"
        meta_path = cache_dir / f"{root}_1m_cache_meta.json"
        frame = pd.read_parquet(path)
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        audit = audit_continuous_cache(frame, meta, root=root)
        audits[root] = audit
        yahoo = fetch_yahoo(ticker, "5m", "60d")
        comparisons[root] = compare_with_yahoo_5m(frame, yahoo)
        meta["large_jump_fraction"] = audit.get("large_jump_fraction_gt_1pct")
        meta["quality_audit"] = {
            "status": audit["status"],
            "audited_utc": datetime.now(timezone.utc).isoformat(),
            "duplicate_timestamps": audit.get("duplicate_timestamps"),
            "invalid_ohlc_rows": audit.get("invalid_ohlc_rows"),
            "large_jump_fraction_gt_1pct": audit.get("large_jump_fraction_gt_1pct"),
            "within_session_2_to_30m_gap_fraction": audit.get(
                "within_session_2_to_30m_gap_fraction"
            ),
            "yahoo_comparison": comparisons[root],
        }
        meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    starts = [a["start"] for a in audits.values() if a.get("start")]
    ends = [a["end"] for a in audits.values() if a.get("end")]
    conditions = _dataset_conditions(min(starts), max(ends)) if starts and ends else {}
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "intended_use": "frozen strategy research and verified historical paper context",
        "expected_grain": "one OHLCV row per available CME minute per volume-continuous root",
        "audits": audits,
        "yahoo_5m_comparisons": comparisons,
        "databento_dataset_conditions": conditions,
    }
    statuses = [a.get("status") for a in audits.values()]
    payload["overall_status"] = "FAIL" if "FAIL" in statuses else (
        "WARN" if "WARN" in statuses or conditions.get("status") == "WARN" else "PASS"
    )
    json_path = cache_dir / "CORRECTED_CACHE_QUALITY.json"
    md_path = cache_dir / "CORRECTED_CACHE_QUALITY.md"
    json_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    lines = [
        "# Corrected Databento Cache Quality",
        "",
        f"Overall: **{payload['overall_status']}**",
        "",
        "## Dataset and grain",
        "",
        f"- Intended use: {payload['intended_use']}",
        f"- Expected grain: {payload['expected_grain']}",
        "- Source: Databento GLBX.MDP3 `ohlcv-1m`, `stype_in=continuous`, volume roll `.v.0`.",
        "",
        "## Findings",
        "",
    ]
    for root, audit in audits.items():
        comp = comparisons[root]
        lines += [
            f"### {root}",
            "",
            f"- Cache status: **{audit['status']}**; rows={audit['rows']:,}; range={audit['start']} → {audit['end']}.",
            f"- Required-field nulls={sum(audit['null_counts'].values())}; duplicate timestamps={audit['duplicate_timestamps']}; invalid OHLC={audit['invalid_ohlc_rows']}; negative volume={audit['negative_volume_rows']}.",
            f"- Consecutive-minute >1% jumps={audit['large_jump_fraction_gt_1pct']:.4%}; max consecutive-minute return={audit['max_absolute_minute_return']:.3%}; max re-open/gap return={audit['max_absolute_gap_return']:.3%}.",
            f"- 2–30 minute gap rate={audit['within_session_2_to_30m_gap_fraction']:.4%}; one-minute gap share={audit['one_minute_gap_share']:.2%}.",
            f"- Yahoo overlap: {comp.get('status')} n={comp.get('overlap_bars', 0):,}; median basis={float(comp.get('median_relative_basis_gap') or 0):.3%}; 5m return correlation={float(comp.get('five_minute_return_correlation') or 0):.4f}.",
            f"- Failures: {audit['failures'] or 'none'}; warnings: {audit['warnings'] or 'none'}.",
            "",
        ]
    degraded = conditions.get("degraded_days") or []
    lines += [
        "## Temporal/source conditions",
        "",
        f"- Dataset-condition status: **{conditions.get('status', 'UNAVAILABLE')}**; days checked={conditions.get('days_checked', 0)}; degraded entries={len(degraded)}.",
        "- Degraded dates remain usable only with this warning attached; strategy conclusions must also survive an independent-source check.",
        "",
        "## Automated acceptance rules",
        "",
        "- Exact `.v.0` metadata and `stype_in=continuous`.",
        "- Unique timestamp grain, complete finite OHLCV, valid OHLC relationships, positive prices, non-negative volume.",
        "- No more than 0.2% of truly consecutive one-minute returns above 1%; weekend/maintenance re-opens are reported separately.",
        "- Yahoo comparison reports overlap, median relative basis, p95 basis, and 5-minute return correlation.",
        "",
        "## Analytical use",
        "",
        "A cache marked FAIL is quarantined. PASS/WARN caches may enter frozen research; WARN results must retain the stated caveat and cannot alone justify a profitability claim.",
    ]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json_path)
    print(md_path)
    return 1 if payload["overall_status"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
