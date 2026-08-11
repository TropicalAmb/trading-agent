"""Markdown report writer for full research program."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_markdown(summary: dict[str, Any], path: Path, risk_snapshot: dict[str, Any]) -> None:
    rs = summary.get("research_scale") or {}
    lines = [
        "# Full Research Program — Final Report",
        "",
        f"## Verdict",
        "",
        f"**{summary.get('verdict')}**",
        "",
        "Gates: `" + json.dumps(summary.get("gates")) + "`",
        "",
        "Friction: " + str(summary.get("friction")),
        "",
        "## A. Research scale",
        "",
        f"- Strategy families: **{rs.get('strategy_families')}**",
        f"- Total configurations: **{rs.get('total_configurations')}**",
        f"- Historical bars: **{rs.get('historical_bars')}**",
        f"- Train trades: **{rs.get('train_trades')}**",
        f"- Validation trades: **{rs.get('validation_trades')}**",
        f"- Final untouched OOS trades (selected path): **{rs.get('final_untouched_oos_trades_selected_path')}**",
        f"- Selected for final: **{rs.get('selected_for_final')}**",
        f"- Families: {', '.join(rs.get('family_list') or [])}",
        "",
        "## B. Top 10 finalists (FINAL OOS only)",
        "",
        "| Strategy | Fam | TF | n | WR | CI95 | PF | E[R] | MaxDD | /wk | AvgW | AvgL | Worst | Gates |",
        "|----------|-----|----|---|----|------|----|------|-------|-----|------|------|-------|-------|",
    ]
    for t in summary.get("top10_finalists") or []:
        lines.append(
            f"| {t['strategy']} | {t['family']} | {t['timeframe']} | {t['final_oos_n']} | "
            f"{t['wr']:.1%} | {t['wr_ci95']} | {t['pf']} | {t['expectancy_r']} | {t['max_dd_r']} | "
            f"{t['trades_per_week']} | {t['avg_win_r']} | {t['avg_loss_r']} | {t['worst_r']} | {t['gates']} |"
        )
    lines += [
        "",
        "## C. High-confidence gate",
        "",
        f"**{summary.get('verdict')}**",
        "",
        "### Closest misses",
        "",
    ]
    for m in summary.get("closest_misses") or []:
        lines.append(f"- `{m['config']}` final={m['final']} failed={m['why_failed']}")
    lines += [
        "",
        "## D. Best by market (final OOS, n≥15)",
        "",
        json.dumps(summary.get("best_by_market"), indent=2),
        "",
        "## E. Best by session",
        "",
        json.dumps(summary.get("best_by_session"), indent=2),
        "",
        "## F. WR / frequency Pareto",
        "",
        json.dumps(summary.get("pareto"), indent=2),
        "",
        "## G. Monte Carlo (top finalist)",
        "",
        json.dumps(summary.get("monte_carlo_top"), indent=2),
        "",
        "## H. Probability calibration (train→val)",
        "",
        json.dumps(summary.get("calibration"), indent=2),
        "",
        "## I. Missed-move analysis",
        "",
        json.dumps(summary.get("missed_moves"), indent=2),
        "",
        "## J. Failure-mode clusters (top finalist)",
        "",
        json.dumps(summary.get("failure_modes_top"), indent=2),
        "",
        "## K. Paper bot freeze confirmation",
        "",
        f"- paper_bot_frozen: **{summary.get('paper_bot_frozen')}**",
        f"- paper_bot_modified: **{summary.get('paper_bot_modified')}**",
        "",
        "## L. Current exact risk config (read-only snapshot)",
        "",
        json.dumps(risk_snapshot, indent=2),
        "",
        "## M. Recommended champion candidate",
        "",
        json.dumps(summary.get("recommended_champion"), indent=2),
        "",
        "_Not activated. Awaiting explicit approval._",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
