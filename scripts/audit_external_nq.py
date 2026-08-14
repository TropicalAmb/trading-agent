from __future__ import annotations

from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent.research.external_nq_quality import audit_external_nq, write_external_audit


def main() -> int:
    path = ROOT / "data" / "reddit_nq_2010_2025.csv"
    frame, payload = audit_external_nq(path)
    out = ROOT / "data" / "external_nq_quality"
    write_external_audit(payload, out)
    if payload["status"] != "FAIL":
        frame.to_parquet(out / "external_nq_2010_2025.parquet")
    print(json.dumps({"status": payload["status"], "rows": len(frame), "report": str(out / 'EXTERNAL_NQ_QUALITY.md')}, indent=2))
    return 1 if payload["status"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
