"""Execute the complete high-confidence research program.

Does NOT modify config/settings.yaml or restart the paper agent.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import yaml

from agent.research.harness.engine import ResearchEngine
from agent.research.harness.reports import write_markdown


def risk_snapshot() -> dict:
    cfg = yaml.safe_load((ROOT / "config" / "settings.yaml").read_text(encoding="utf-8"))
    risk = cfg.get("risk") or {}
    qty = cfg.get("quantity") or {}
    return {
        "risk_per_trade_pct": risk.get("risk_per_trade_pct"),
        "max_account_risk_per_trade": risk.get("max_account_risk_per_trade"),
        "max_risk_dollars_per_trade": risk.get("max_risk_dollars_per_trade"),
        "max_total_open_risk_dollars": risk.get("max_total_open_risk_dollars"),
        "max_daily_loss_dollars": risk.get("max_daily_loss_dollars")
        or risk.get("daily_loss_kill_dollars"),
        "max_correlated_risk_dollars": risk.get("max_correlated_risk_dollars"),
        "daily_loss_kill_pct": risk.get("daily_loss_kill_pct"),
        "default_quantity": qty.get("default_quantity"),
        "quantity_by_tier": qty.get("quantity_by_tier"),
        "minimum_trade_tier": (cfg.get("tiering") or {}).get("minimum_trade_tier"),
        "note": "READ-ONLY snapshot. Research program does not modify these values.",
    }


def main() -> int:
    out = ROOT / "data" / "research_program"
    engine = ResearchEngine(out)
    summary = engine.run()
    risk = risk_snapshot()
    summary["current_risk_config"] = risk
    write_markdown(summary, out / "FULL_RESEARCH_REPORT.md", risk)
    # rewrite json with risk
    payload_path = out / "full_research_program.json"
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    payload["summary"] = summary
    payload_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print("\n==== VERDICT ====", flush=True)
    print(summary["verdict"], flush=True)
    print("Report:", out / "FULL_RESEARCH_REPORT.md", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
