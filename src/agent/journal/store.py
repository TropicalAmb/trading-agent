from __future__ import annotations

import csv
import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class Journal:
    def __init__(self, db_path: str | Path, csv_path: str | Path | None = None):
        self.db_path = Path(db_path)
        self.csv_path = Path(csv_path) if csv_path else None
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    payload TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def log(self, event_type: str, payload: dict[str, Any]) -> None:
        ts = datetime.now(timezone.utc).isoformat()
        body = json.dumps(payload, default=str)
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO events (ts, event_type, payload) VALUES (?, ?, ?)",
                (ts, event_type, body),
            )
            conn.commit()
        logger.info("journal %s: %s", event_type, body[:300])

        if self.csv_path:
            self.csv_path.parent.mkdir(parents=True, exist_ok=True)
            write_header = not self.csv_path.exists()
            with self.csv_path.open("a", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(
                    f, fieldnames=["ts", "event_type", "payload"]
                )
                if write_header:
                    writer.writeheader()
                writer.writerow(
                    {"ts": ts, "event_type": event_type, "payload": body}
                )

    def recent(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT ts, event_type, payload FROM events ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        out = []
        for r in rows:
            out.append(
                {
                    "ts": r["ts"],
                    "event_type": r["event_type"],
                    "payload": json.loads(r["payload"]),
                }
            )
        return out
