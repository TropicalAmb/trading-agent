"""Append a chunked Women-in-Trading Facebook research note to jsonl.

Usage:
  .venv\\Scripts\\python.exe scripts\\research_wit_append_chunk.py \\
    --chunk-id orb_third_move_6 --theme "ORB third move / first-break curiosity" \\
    --post "quote one" --post "quote two" --takeaway "summary"

Does not stop the paper agent. Never claims full-group completeness.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "research_wit_chunks.jsonl"
NOTES = ROOT / "data" / "research_wit_group_notes.md"
GROUP_URL = "https://www.facebook.com/groups/690505400576058"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--chunk-id", required=True)
    ap.add_argument("--theme", required=True)
    ap.add_argument("--query", default="")
    ap.add_argument("--post", action="append", default=[])
    ap.add_argument("--takeaway", action="append", default=[])
    args = ap.parse_args()
    if not args.post:
        raise SystemExit("need at least one --post")

    # de-dupe chunk ids
    if OUT.exists():
        for line in OUT.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                if json.loads(line).get("chunk_id") == args.chunk_id:
                    raise SystemExit(f"chunk_id already exists: {args.chunk_id}")
            except json.JSONDecodeError:
                continue

    row = {
        "chunk_id": args.chunk_id,
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "group": "Women in Day Trading",
        "url": GROUP_URL,
        "theme": args.theme,
        "query": args.query,
        "n_posts": len(args.post),
        "posts": args.post,
        "takeaways": args.takeaway,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print("appended", args.chunk_id, "->", OUT)

    # light notes touch
    if NOTES.exists():
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        with NOTES.open("a", encoding="utf-8") as f:
            f.write(f"\n{len(args.post)}. **{args.chunk_id}** — {args.theme} ({stamp})\n")
            for t in args.takeaway:
                f.write(f"   - {t}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
