"""Container / process health: heartbeat freshness (Yahoo failures must not kill health forever)."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))


def main() -> int:
    # Prefer blotter heartbeat — proves agent loop is alive even with 0 trades
    candidates = [
        ROOT / "data" / "paper_trades.json",
        Path("/app/data/paper_trades.json"),
        Path("data/paper_trades.json"),
    ]
    for path in candidates:
        if not path.exists():
            continue
        try:
            state = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        hb = state.get("heartbeat") or {}
        ts = hb.get("ts")
        if not ts:
            print("heartbeat missing — agent may still be starting")
            return 0  # allow start_period
        try:
            ht = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
            if ht.tzinfo is None:
                ht = ht.replace(tzinfo=timezone.utc)
            age = (datetime.now(timezone.utc) - ht).total_seconds()
        except Exception:
            print("heartbeat unreadable")
            return 1
        if age > 300:
            print(f"STALE heartbeat age={age:.0f}s")
            return 1
        print(f"OK heartbeat age={age:.0f}s decision={hb.get('decision')}")
        return 0

    print("no blotter yet — starting")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
