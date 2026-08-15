"""Quote or explicitly download Databento TBBO for NQ/CL research.

The default action is quote-only.  A paid request requires all three flags:
``--download --confirm-spend USER_APPROVED --max-cost-usd <positive cap>``.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
load_dotenv(ROOT / ".env")

from agent.research.databento_order_flow import (  # noqa: E402
    APPROVAL_PHRASE,
    CONTINUOUS_SYMBOLS,
    SpendGuardError,
    TBBORequest,
    guarded_tbbo_download,
)

OUT = ROOT / "data" / "databento_order_flow" / "raw"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Quote-first Databento TBBO cache tool; does not download by default"
    )
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--symbols", default="NQ,CL")
    parser.add_argument(
        "--end",
        help="Exclusive UTC end in ISO 8601; defaults to the current completed minute",
    )
    parser.add_argument("--download", action="store_true")
    parser.add_argument("--confirm-spend", default="")
    parser.add_argument("--max-cost-usd", type=float, default=0.0)
    parser.add_argument("--output", type=Path)
    return parser


def _parse_end(raw: str | None) -> datetime:
    if raw:
        value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if value.tzinfo is None:
            raise ValueError("--end must include a timezone")
        return value.astimezone(timezone.utc)
    return datetime.now(timezone.utc).replace(second=0, microsecond=0)


def _request(args: argparse.Namespace) -> TBBORequest:
    if not 1 <= int(args.days) <= 30:
        raise ValueError("--days must be between 1 and 30")
    roots = [item.strip().upper() for item in args.symbols.split(",") if item.strip()]
    unknown = sorted(set(roots) - set(CONTINUOUS_SYMBOLS))
    if unknown:
        raise ValueError(f"Unsupported roots: {unknown}; allowed: NQ,CL")
    end = _parse_end(args.end)
    return TBBORequest(
        symbols=tuple(CONTINUOUS_SYMBOLS[root] for root in roots),
        start=end - timedelta(days=int(args.days)),
        end=end,
    )


def _default_output(request: TBBORequest) -> Path:
    symbols = "_".join(symbol.split(".", 1)[0] for symbol in request.symbols)
    start = request.start.strftime("%Y%m%dT%H%MZ")
    end = request.end.strftime("%Y%m%dT%H%MZ")
    return OUT / f"GLBX_{symbols}_{start}_{end}.tbbo.dbn.zst"


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        request = _request(args)
    except ValueError as exc:
        print(f"REFUSED: {exc}")
        return 2

    api_key = (os.getenv("DATABENTO_API_KEY") or "").strip()
    if not api_key:
        print("DATABENTO_API_KEY missing")
        return 3

    import databento as db

    client = db.Historical(api_key)
    output = args.output or _default_output(request)
    try:
        result = guarded_tbbo_download(
            client,
            request,
            output_path=output,
            download=bool(args.download),
            confirmation=str(args.confirm_spend),
            max_cost_usd=float(args.max_cost_usd),
        )
    except SpendGuardError as exc:
        print(f"REFUSED: {exc}")
        return 4
    except Exception as exc:
        print(f"FAILED: {type(exc).__name__}: {exc}")
        return 5

    print(
        f"QUOTE dataset={request.dataset} schema={request.schema} "
        f"symbols={','.join(request.symbols)} cost=${result.quoted_cost_usd:.6f}"
    )
    if not result.downloaded:
        print(
            "QUOTE ONLY: no paid data downloaded. To spend, fresh approval must be "
            f"translated to --download --confirm-spend {APPROVAL_PHRASE} "
            "--max-cost-usd <cap>."
        )
        return 0

    manifest = {
        "dataset": request.dataset,
        "schema": request.schema,
        "stype_in": request.stype_in,
        "symbols": list(request.symbols),
        "start": request.start.isoformat(),
        "end": request.end.isoformat(),
        "quoted_cost_usd": result.quoted_cost_usd,
        "downloaded_utc": datetime.now(timezone.utc).isoformat(),
        "output": str(result.output_path),
        "note": "Raw TBBO; no strategy promotion or profitability claim",
    }
    manifest_path = Path(result.output_path).with_suffix(".manifest.json")
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"DOWNLOADED {result.output_path}")
    print(f"MANIFEST {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
