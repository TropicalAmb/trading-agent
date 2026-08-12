"""Generate breakout_retest forward research report (observation only).

Does NOT modify paper config, risk, qty, engines, or router settings.
Safe to re-run overnight / tomorrow morning while agent keeps running.

Usage:
  .\\.venv\\Scripts\\python.exe scripts\\run_breakout_retest_forward_report.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent.research.breakout_retest_forward import (  # noqa: E402
    build_report,
    export_dataset,
    load_learning_breakouts,
    load_paper_breakouts,
    load_shadow_breakouts,
    write_markdown,
)


def main() -> int:
    et = datetime.now(ZoneInfo("America/New_York"))
    date_tag = et.strftime("%Y-%m-%d")
    out_dir = ROOT / "data" / "research"
    out_dir.mkdir(parents=True, exist_ok=True)

    payload = build_report(ROOT)
    md_path = out_dir / f"breakout_retest_forward_{date_tag}.md"
    json_path = out_dir / f"breakout_retest_forward_{date_tag}.json"
    ds_path = out_dir / f"breakout_retest_dataset_{date_tag}.jsonl"

    write_markdown(payload, md_path)
    json_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    rows = (
        load_paper_breakouts(ROOT / "data" / "paper_trades.json")
        + load_learning_breakouts(ROOT / "data" / "learning" / "candidates.jsonl")
        + load_shadow_breakouts(ROOT / "data" / "shadow_trades.json")
    )
    export_dataset(rows, ds_path)

    print(f"Wrote {md_path}")
    print(f"Wrote {json_path}")
    print(f"Wrote {ds_path} ({len(rows)} rows)")
    print(f"heartbeat_stamp={payload.get('heartbeat_stamp')}")
    print(f"post_all={payload.get('post_paperfix2_all_strategies')}")
    print(f"post_br={payload.get('post_paperfix2_breakout_retest')}")
    print(f"open_cl={payload.get('open_cl_trade')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
