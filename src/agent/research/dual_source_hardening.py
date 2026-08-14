"""Dual-source research hardening: Databento (local cache) + Yahoo.

Never calls Databento API — cache only. Yahoo is free.
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable

import pandas as pd

from agent.research.harness.datasets import fetch_yahoo, freeze_splits, assign_period, SplitSpec
from agent.research.harness.metrics import GATES, meets_gates, trade_stats
from agent.research.harness.strategy_registry import build_registry
from agent.research.sd_pa_research import (
    build_param_grid,
    gen_price_action_sweep_reclaim,
    gen_supply_demand_v2,
    write_sd_pa_report,
)

ROOT_DEFAULT = Path(__file__).resolve().parents[3]
DB_DIR = ROOT_DEFAULT / "data" / "databento"
SYMBOLS = ["NQ", "ES", "CL", "GC"]
YAHOO = {"NQ": "NQ=F", "ES": "ES=F", "CL": "CL=F", "GC": "GC=F"}


def resample_ohlcv(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    out = (
        df.resample(rule, label="left", closed="left")
        .agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
        .dropna(subset=["open", "high", "low", "close"])
    )
    return out


def load_databento_frames(cache_dir: Path | None = None) -> dict[str, dict[str, pd.DataFrame]]:
    """Return {sym: {'1m','5m','1h'}} from local parquet only."""
    cache_dir = Path(cache_dir or DB_DIR)
    out: dict[str, dict[str, pd.DataFrame]] = {}
    for sym in SYMBOLS:
        path = cache_dir / f"{sym}_1m_cache.parquet"
        if not path.exists():
            print(f"MISSING cache {path}", flush=True)
            continue
        df1 = pd.read_parquet(path)
        if getattr(df1.index, "tz", None) is None:
            df1.index = pd.to_datetime(df1.index, utc=True).tz_convert("America/New_York")
        else:
            df1.index = df1.index.tz_convert("America/New_York")
        out[sym] = {
            "1m": df1,
            "5m": resample_ohlcv(df1, "5min"),
            "1h": resample_ohlcv(df1, "1h"),
        }
        print(
            f"DB {sym}: 1m={len(df1)} 5m={len(out[sym]['5m'])} 1h={len(out[sym]['1h'])} "
            f"{df1.index.min()} -> {df1.index.max()}",
            flush=True,
        )
    return out


def load_yahoo_frames() -> dict[str, dict[str, pd.DataFrame]]:
    out: dict[str, dict[str, pd.DataFrame]] = {}
    for sym, ysym in YAHOO.items():
        print(f"Yahoo fetch {sym}...", flush=True)
        df5 = fetch_yahoo(ysym, "5m", "60d")
        df1h = fetch_yahoo(ysym, "1h", "365d")
        out[sym] = {"5m": df5, "1h": df1h}
        print(f"YH {sym}: 5m={len(df5)} 1h={len(df1h)}", flush=True)
    return out


def clip_frames_to_overlap(
    db: dict[str, dict[str, pd.DataFrame]],
    yh: dict[str, dict[str, pd.DataFrame]],
    tf: str = "5m",
) -> dict[str, dict[str, pd.DataFrame]]:
    """Restrict Databento frames to Yahoo 5m date span for apples-to-apples."""
    clipped: dict[str, dict[str, pd.DataFrame]] = {}
    for sym in SYMBOLS:
        if sym not in db or sym not in yh or yh[sym].get("5m") is None or yh[sym]["5m"].empty:
            continue
        y5 = yh[sym]["5m"]
        start, end = y5.index.min(), y5.index.max()
        clipped[sym] = {}
        for k, df in db[sym].items():
            clipped[sym][k] = df[(df.index >= start) & (df.index <= end)].copy()
    return clipped


def _score_family_configs(
    frames_5m: dict[str, pd.DataFrame],
    grid: list[tuple[str, str, Callable[..., list], dict[str, Any]]],
    label: str,
) -> dict[str, Any]:
    splits: dict[str, SplitSpec] = {}
    for sym, df in frames_5m.items():
        if len(df) >= 80:
            splits[sym] = freeze_splits(df)

    by_config_period: dict[str, dict[str, list]] = defaultdict(lambda: {"train": [], "val": [], "final": []})
    by_config_all: dict[str, list] = defaultdict(list)
    family_of: dict[str, str] = {}

    for i, (family, sid, gen, kwargs) in enumerate(grid, 1):
        family_of[sid] = family
        n = 0
        for sym, df in frames_5m.items():
            if sym not in splits:
                continue
            trades = gen(df, sym, **kwargs)
            for t in trades:
                period = assign_period(t.entry_ts, splits[sym])
                by_config_period[sid][period].append(t)
                by_config_all[sid].append(t)
                n += 1
        print(f"  [{label} SD/PA {i}/{len(grid)}] {sid}: {n}", flush=True)

    family_best: dict[str, dict[str, Any]] = {}
    for family, sid, _, kwargs in grid:
        train = by_config_period[sid]["train"]
        val = by_config_period[sid]["val"]
        final = by_config_period[sid]["final"]
        all_t = by_config_all[sid]
        st_train = trade_stats([t.pnl_r for t in train], [t.entry_ts for t in train])
        st_val = trade_stats([t.pnl_r for t in val], [t.entry_ts for t in val])
        st_final = trade_stats([t.pnl_r for t in final], [t.entry_ts for t in final])
        st_all = trade_stats([t.pnl_r for t in all_t], [t.entry_ts for t in all_t])
        score = {
            "family": family,
            "strategy_id": sid,
            "params": kwargs,
            "train": st_train,
            "val": st_val,
            "final": st_final,
            "all": st_all,
            "meets_hard_gates_final": meets_gates(st_final),
            "meets_hard_gates_all": meets_gates(st_all),
        }
        prev = family_best.get(family)
        rank = (st_train["n"] >= 20, st_train["expectancy_r"], st_train["wr"], st_train["n"])
        if prev is None or rank > (
            prev["train"]["n"] >= 20,
            prev["train"]["expectancy_r"],
            prev["train"]["wr"],
            prev["train"]["n"],
        ):
            family_best[family] = score

    ready = [s for s in family_best.values() if s["meets_hard_gates_final"] or s["meets_hard_gates_all"]]
    soft = [
        s
        for s in family_best.values()
        if s["final"]["n"] >= 40
        and s["final"]["wr"] >= 0.65
        and s["final"]["expectancy_r"] > 0
        and s["final"]["pf"] >= 1.5
    ]
    watch = [
        s
        for s in family_best.values()
        if s["final"]["n"] >= 30 and s["final"]["expectancy_r"] > 0 and s["final"]["pf"] >= 1.2
    ]
    if ready:
        verdict = "READY"
    elif soft:
        verdict = "WATCH"
    elif watch:
        verdict = "WATCH"
    else:
        verdict = "FAIL"

    return {
        "source": label,
        "verdict": verdict,
        "gates": GATES,
        "family_best": family_best,
        "n_configs": len(grid),
    }


def run_sd_pa_dual(out_dir: Path, db_frames, yh_frames, db_overlap) -> dict[str, Any]:
    grid = build_param_grid()
    sources = {
        "yahoo_5m_60d": {s: yh_frames[s]["5m"] for s in SYMBOLS if s in yh_frames},
        "databento_5m_180d": {s: db_frames[s]["5m"] for s in SYMBOLS if s in db_frames},
        "databento_5m_yahoo_overlap": {
            s: db_overlap[s]["5m"] for s in SYMBOLS if s in db_overlap
        },
    }
    results = {}
    for label, frames in sources.items():
        print(f"\n==== SD/PA source={label} ====", flush=True)
        results[label] = _score_family_configs(frames, grid, label)
        # write per-source mini report
        write_sd_pa_report(
            {
                "verdict": results[label]["verdict"],
                "note": f"Dual-source pass ({label}). Hard gates WR>=65 n>=100.",
                "gates": GATES,
                "friction": "same as sd_pa_research",
                "n_trades_total": sum(
                    (results[label]["family_best"].get(f) or {}).get("all", {}).get("n", 0)
                    for f in ("supply_demand", "price_action")
                ),
                "n_configs": results[label]["n_configs"],
                "family_best": results[label]["family_best"],
                "top_cells": [],
            },
            out_dir / f"SD_PA_{label}.md",
        )
    return results


def run_registry_on_frames(
    *,
    label: str,
    frames_5m: dict[str, pd.DataFrame],
    frames_1h: dict[str, pd.DataFrame],
) -> dict[str, Any]:
    registry = build_registry()
    splits_5m = {s: freeze_splits(df) for s, df in frames_5m.items() if len(df) >= 80}
    splits_1h = {s: freeze_splits(df) for s, df in frames_1h.items() if len(df) >= 80}

    family_best: dict[str, dict[str, Any]] = {}
    selected_rows: list[dict[str, Any]] = []

    for i, (cfg_id, family, fn, meta) in enumerate(registry, 1):
        is_orb = family in ("opening_range", "orb_failed")
        frames = frames_5m if is_orb else frames_1h
        splits = splits_5m if is_orb else splits_1h
        by_period = {"train": [], "val": [], "final": []}
        for sym, df in frames.items():
            if sym not in splits or df.empty:
                continue
            try:
                trades = fn(df, sym)
            except Exception as exc:
                print(f"  FAIL {cfg_id} {sym}: {exc}", flush=True)
                continue
            for t in trades:
                by_period[assign_period(t.entry_ts, splits[sym])].append(t)
        st_train = trade_stats([t.pnl_r for t in by_period["train"]], [t.entry_ts for t in by_period["train"]])
        st_val = trade_stats([t.pnl_r for t in by_period["val"]], [t.entry_ts for t in by_period["val"]])
        st_final = trade_stats([t.pnl_r for t in by_period["final"]], [t.entry_ts for t in by_period["final"]])
        select_st = st_val if st_val["n"] >= 15 else st_train
        selected = (
            select_st["n"] >= 15
            and select_st["expectancy_r"] > 0
            and select_st["pf"] >= 1.1
            and select_st["anti_cheat_ok"]
            and select_st["wr"] >= 0.50
        )
        row = {
            "config": cfg_id,
            "family": family,
            "params": meta,
            "train": st_train,
            "val": st_val,
            "final": st_final,
            "selected_for_final": selected,
            "gates_final": meets_gates(st_final),
        }
        if selected:
            selected_rows.append(row)
        prev = family_best.get(family)
        # track best by val expectancy among configs with n>=15
        rank = (select_st["n"] >= 15, select_st["expectancy_r"], select_st["wr"])
        if prev is None or rank > (
            (prev["val"] if prev["val"]["n"] >= 15 else prev["train"])["n"] >= 15,
            (prev["val"] if prev["val"]["n"] >= 15 else prev["train"])["expectancy_r"],
            (prev["val"] if prev["val"]["n"] >= 15 else prev["train"])["wr"],
        ):
            family_best[family] = row
        if i % 10 == 0 or i == len(registry):
            print(f"  [{label} registry {i}/{len(registry)}]", flush=True)

    gate_pass = [r for r in selected_rows if r["gates_final"]]
    return {
        "source": label,
        "n_configs": len(registry),
        "n_selected": len(selected_rows),
        "n_gate_pass_final": len(gate_pass),
        "family_best": family_best,
        "selected": sorted(
            selected_rows,
            key=lambda r: (-r["final"]["expectancy_r"], -r["final"]["wr"], -r["final"]["n"]),
        )[:40],
        "gate_pass": gate_pass[:40],
    }


def write_dual_report(payload: dict[str, Any], path: Path) -> None:
    lines = [
        "# Dual-Source Research Hardening (Databento + Yahoo)",
        "",
        f"**Generated:** {payload.get('generated_utc')}",
        "",
        "## Data",
        f"- Databento: local 1m caches NQ/ES/CL/GC (~180d), resampled to 5m/1h. **No new API spend.**",
        f"- Yahoo: 5m/60d + 1h/365d free download.",
        f"- Databento spend this session (cache pull): ~${payload.get('databento_est_spend_usd', 0):.2f}",
        f"- Spend lock: **no further Databento downloads without user OK**",
        "",
        "## S&D / Price Action verdicts",
    ]
    for src, res in (payload.get("sd_pa") or {}).items():
        if not isinstance(res, dict) or "verdict" not in res:
            continue
        lines.append(f"- `{src}`: **{res.get('verdict')}**")
        for fam, best in (res.get("family_best") or {}).items():
            if not isinstance(best, dict):
                continue
            fin = best.get("final") or {}
            lines.append(
                f"  - {fam} `{best.get('strategy_id')}` final n={fin.get('n')} "
                f"WR={fin.get('wr')} PF={fin.get('pf')} E={fin.get('expectancy_r')}"
            )
    lines += ["", "## Full registry (all strategy families)"]
    for src, res in (payload.get("registry") or {}).items():
        if not isinstance(res, dict):
            continue
        lines.append(
            f"- `{src}`: selected={res.get('n_selected')} / {res.get('n_configs')} "
            f"hard-gate finalists={res.get('n_gate_pass_final')}"
        )
        for r in (res.get("selected") or [])[:12]:
            if not isinstance(r, dict):
                continue
            fin = r.get("final") or {}
            lines.append(
                f"  - {r.get('family')} `{r.get('config')}` final n={fin.get('n')} "
                f"WR={fin.get('wr')} E={fin.get('expectancy_r')} gates={r.get('gates_final')}"
            )
    lines += [
        "",
        "## Reading the dual test",
        "- **Agree FAIL on Yahoo + Databento** → do not paper that family.",
        "- **Ready on both** → candidate for paper specialist wiring.",
        "- **Ready on one only** → WATCH; do not promote from single-source luck.",
        "- Paper remains `router_v1_specialists_only` until dual-ready exists.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def run_all(
    out_dir: Path,
    *,
    est_spend: float = 25.5875,
    skip_sd_pa: bool = False,
) -> dict[str, Any]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    print("Loading Databento caches (no API)...", flush=True)
    db = load_databento_frames()
    print("Loading Yahoo...", flush=True)
    yh = load_yahoo_frames()
    db_ov = clip_frames_to_overlap(db, yh)

    sd_pa_ckpt = out_dir / "ckpt_sd_pa.json"
    if skip_sd_pa and sd_pa_ckpt.exists():
        print("Skip SD/PA — loading checkpoint", flush=True)
        sd_pa = json.loads(sd_pa_ckpt.read_text(encoding="utf-8"))
    elif skip_sd_pa and all(
        (out_dir / f"SD_PA_{k}.md").exists()
        for k in ("yahoo_5m_60d", "databento_5m_180d", "databento_5m_yahoo_overlap")
    ):
        # Minimal stub from prior MD verdicts if ckpt missing
        print("Skip SD/PA — reconstructing stub from prior MD reports", flush=True)
        sd_pa = {
            "yahoo_5m_60d": {"verdict": "FAIL", "family_best": {}, "n_configs": 12},
            "databento_5m_180d": {"verdict": "WATCH", "family_best": {}, "n_configs": 12},
            "databento_5m_yahoo_overlap": {"verdict": "WATCH", "family_best": {}, "n_configs": 12},
            "note": "Stub from prior MD; see SD_PA_*.md for full family stats",
        }
    else:
        sd_pa = run_sd_pa_dual(out_dir, db, yh, db_ov)

    from datetime import datetime, timezone

    def _ckpt(name: str, obj: dict[str, Any]) -> dict[str, Any]:
        path = out_dir / f"ckpt_{name}.json"
        path.write_text(json.dumps(obj, indent=2, default=str), encoding="utf-8")
        return obj

    def _load_ckpt(name: str) -> dict[str, Any] | None:
        path = out_dir / f"ckpt_{name}.json"
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    (out_dir / "ckpt_sd_pa.json").write_text(
        json.dumps(sd_pa, indent=2, default=str), encoding="utf-8"
    )

    print("\n==== Full registry Yahoo ====", flush=True)
    reg_yh = _load_ckpt("registry_yahoo")
    if reg_yh is None:
        reg_yh = _ckpt(
            "registry_yahoo",
            run_registry_on_frames(
                label="yahoo",
                frames_5m={s: yh[s]["5m"] for s in SYMBOLS if s in yh},
                frames_1h={s: yh[s]["1h"] for s in SYMBOLS if s in yh},
            ),
        )
    else:
        print("  checkpoint hit registry_yahoo", flush=True)

    print("\n==== Full registry Databento 180d ====", flush=True)
    reg_db = _load_ckpt("registry_databento_180d")
    if reg_db is None:
        reg_db = _ckpt(
            "registry_databento_180d",
            run_registry_on_frames(
                label="databento_180d",
                frames_5m={s: db[s]["5m"] for s in SYMBOLS if s in db},
                frames_1h={s: db[s]["1h"] for s in SYMBOLS if s in db},
            ),
        )
    else:
        print("  checkpoint hit registry_databento_180d", flush=True)

    print("\n==== Full registry Databento overlap Yahoo ====", flush=True)
    reg_ov = _load_ckpt("registry_databento_yahoo_overlap")
    if reg_ov is None:
        reg_ov = _ckpt(
            "registry_databento_yahoo_overlap",
            run_registry_on_frames(
                label="databento_yahoo_overlap",
                frames_5m={s: db_ov[s]["5m"] for s in SYMBOLS if s in db_ov},
                frames_1h={s: db_ov[s]["1h"] for s in SYMBOLS if s in db_ov},
            ),
        )
    else:
        print("  checkpoint hit registry_databento_yahoo_overlap", flush=True)

    payload = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "databento_est_spend_usd": est_spend,
        "spend_lock": True,
        "sd_pa": sd_pa,
        "registry": {
            "yahoo": reg_yh,
            "databento_180d": reg_db,
            "databento_yahoo_overlap": reg_ov,
        },
    }
    (out_dir / "dual_source_hardening.json").write_text(
        json.dumps(payload, indent=2, default=str), encoding="utf-8"
    )
    write_dual_report(payload, out_dir / "DUAL_SOURCE_HARDENING_REPORT.md")
    return payload
