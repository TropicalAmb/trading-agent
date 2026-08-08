from __future__ import annotations

import argparse
import json
from pathlib import Path

from agent.config import load_settings
from agent.journal.store import Journal


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Print recent trading journal events")
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument("--config", default=None)
    args = parser.parse_args(argv)

    cfg = load_settings(args.config)
    db = cfg.get("journal", {}).get("db_path", "data/journal.db")
    path = Path(db)
    if not path.is_absolute():
        repo = Path(__file__).resolve().parents[3]
        path = repo / path
    if not path.exists():
        print(f"No journal yet at {path}")
        return 0

    journal = Journal(path)
    events = journal.recent(args.limit)
    if not events:
        print("Journal empty")
        return 0

    for ev in reversed(events):
        payload = ev["payload"]
        summary = payload
        if ev["event_type"] == "scan":
            summary = {"count": payload.get("count")}
        elif ev["event_type"] == "order":
            summary = {
                "status": payload.get("status"),
                "dry_run": payload.get("dry_run"),
                "order_id": payload.get("order_id"),
            }
        elif ev["event_type"] == "risk":
            summary = {
                "approved": payload.get("approved"),
                "reasons": payload.get("reasons"),
            }
        print(f"{ev['ts']}  {ev['event_type']:12}  {json.dumps(summary, default=str)[:200]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
