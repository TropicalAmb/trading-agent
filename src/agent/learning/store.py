"""Persistent learning memory — candidate feature snapshots + outcomes."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional


class LearningStore:
    """JSONL learning table. Append-only outcomes; updates by candidate_id."""

    def __init__(self, path: str | Path = "data/learning/candidates.jsonl"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("", encoding="utf-8")

    def append(self, row: dict[str, Any]) -> dict[str, Any]:
        from agent.learning.schema import strip_post_entry_leakage

        out = strip_post_entry_leakage(dict(row))
        out.setdefault("candidate_id", str(uuid.uuid4()))
        out.setdefault("recorded_at", datetime.now(timezone.utc).isoformat())
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(out, default=str) + "\n")
        return out

    def iter_rows(self) -> Iterable[dict[str, Any]]:
        if not self.path.exists():
            return
        with self.path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue

    def all_rows(self) -> list[dict[str, Any]]:
        return list(self.iter_rows())

    def update_outcome(self, candidate_id: str, outcome: dict[str, Any]) -> bool:
        rows = self.all_rows()
        found = False
        for r in rows:
            if str(r.get("candidate_id")) == str(candidate_id):
                r.update(outcome)
                r["outcome_updated_at"] = datetime.now(timezone.utc).isoformat()
                found = True
                break
        if not found:
            return False
        with self.path.open("w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, default=str) + "\n")
        return True

    def find_open_by_setup(self, setup_id: str) -> Optional[dict[str, Any]]:
        sid = str(setup_id or "")
        if not sid:
            return None
        for r in reversed(self.all_rows()):
            if str(r.get("setup_id") or "") == sid and r.get("final_result") in (None, "", "OPEN"):
                return r
        return None
