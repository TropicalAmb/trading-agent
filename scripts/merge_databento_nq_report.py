"""Merge Databento validation artifacts into the NQ focused research report."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

OUT = Path("data/nq_focused_research")
report_path = OUT / "nq_focused_research.json"
r = json.loads(report_path.read_text(encoding="utf-8"))
cross = json.loads((OUT / "databento_cross_check.json").read_text(encoding="utf-8"))
fin = json.loads((OUT / "databento_finalist_validation.json").read_text(encoding="utf-8"))

r["databento_cross_check"] = cross
r["databento_finalist_validation"] = fin
r["verdict"] = "NQ STRATEGY NOT YET GOOD ENOUGH"
r["verdict_reason"] = (
    "Kaggle vs Databento materially inconsistent (USE_DATABENTO_AS_TRUTH). "
    "Kaggle-selected finalists lose edge on Databento 120d holdout "
    "(best_balanced holdout WR 40% / PF~0). OOS samples remain below 100-trade bar."
)
r["databento_updated_utc"] = datetime.now(timezone.utc).isoformat()
report_path.write_text(json.dumps(r, indent=2, default=str), encoding="utf-8")

lines = [
    "# NQ Focused Research Report",
    "",
    f"**Verdict:** `{r['verdict']}`",
    "",
    f"Reason: {r['verdict_reason']}",
    "",
    f"Updated UTC: `{r['databento_updated_utc']}`",
    "",
    "## DATA",
    f"- Kaggle rows / range: `{r.get('data', {}).get('rows')}` / "
    f"`{r.get('data', {}).get('start')}` → `{r.get('data', {}).get('end')}`",
    f"- Kaggle quality ok: `{r.get('data', {}).get('ok')}`",
    f"- Kaggle warnings: `{r.get('data', {}).get('warnings')}`",
    (
        "- Databento cross-check: "
        f"overlap=`{cross.get('overlap_bars')}` "
        f"materially_inconsistent=`{cross.get('materially_inconsistent')}` "
        f"median_|close|_diff=`{(cross.get('diffs') or {}).get('close', {}).get('median_abs')}` "
        f"recommendation=`{cross.get('recommendation')}`"
    ),
    "",
    f"Operating window (Kaggle train/val only): `{r.get('chosen_operating_window')}`",
    "",
    "## PULLBACK (Kaggle holdout)",
    f"```\n{json.dumps(r.get('trigger_holdout', {}).get('PULLBACK'), indent=2, default=str)}\n```",
    "",
    "## LIQUIDITY (Kaggle holdout)",
    f"```\n{json.dumps(r.get('trigger_holdout', {}).get('LIQUIDITY'), indent=2, default=str)}\n```",
    "",
    "## BREAKOUT RETEST (Kaggle holdout)",
    f"```\n{json.dumps(r.get('trigger_holdout', {}).get('BREAKOUT_RETEST'), indent=2, default=str)}\n```",
    "",
    "## COMBINED (Kaggle holdout)",
    f"```\n{json.dumps(r.get('combined_holdout'), indent=2, default=str)}\n```",
    "",
    "## BEST HIGH-ACCURACY / BALANCED / EXPECTANCY (Kaggle-selected)",
    f"```\n{json.dumps({'high_accuracy': r.get('best_high_accuracy'), 'balanced': r.get('best_balanced'), 'expectancy': r.get('best_expectancy')}, indent=2, default=str)}\n```",
    "",
    "## CURRENT COMPLEX BOT COMPARISON",
    f"```\n{json.dumps(r.get('complex_bot_comparison'), indent=2, default=str)}\n```",
    "",
    "## ROUTER_V2 LIFT",
    f"```\n{json.dumps(r.get('router_v2_lift'), indent=2, default=str)}\n```",
    "",
    "## FINAL DATABENTO VALIDATION",
    f"```\n{json.dumps(fin, indent=2, default=str)}\n```",
    "",
    "## Notes",
    "- Yahoo remains paper diagnostics only.",
    "- Databento is source of truth for finalists after failed Kaggle cross-check.",
    "- API key lives in local `.env` only; rotate if exposed in chat.",
    "- Paper agent / live_pilot unchanged; live not activated.",
    "",
]
(OUT / "NQ_FOCUSED_RESEARCH_REPORT.md").write_text("\n".join(lines), encoding="utf-8")
print("OK verdict=", r["verdict"])
for row in fin.get("finalists", []):
    print(row["label"], row.get("holdout"))
