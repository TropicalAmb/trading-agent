"""Unified research engine: freeze splits → train/val select → final OOS once."""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path
from typing import Any

import pandas as pd

from agent.research.harness.datasets import (
    SplitSpec,
    assign_period,
    fetch_yahoo,
    freeze_splits,
    save_split_lock,
)
from agent.research.harness.metrics import GATES, meets_gates, trade_stats
from agent.research.harness.monte_carlo import monte_carlo
from agent.research.harness.probability import calibrate_buckets, comparable_probability
from agent.research.harness.strategy_registry import build_registry
from agent.research.missed_moves import scan_missed_moves


SYMBOLS_1H = {"NQ": "NQ=F", "ES": "ES=F", "GC": "GC=F", "CL": "CL=F"}
FRICTION_NOTE = (
    "Friction: 2 ticks slip + 1 tick buffer per side (research_wit convention); "
    "fixed-R stops/targets; no lookahead on entry bar; train/val/final chronological freeze."
)


class ResearchEngine:
    def __init__(self, out_dir: Path):
        self.out_dir = Path(out_dir)
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.frames_1h: dict[str, pd.DataFrame] = {}
        self.frames_5m: dict[str, pd.DataFrame] = {}
        self.splits_1h: dict[str, SplitSpec] = {}
        self.splits_5m: dict[str, SplitSpec] = {}
        self.configs_tried = 0
        self.param_log: list[dict[str, Any]] = []

    def load_and_freeze(self) -> dict[str, Any]:
        lock_path = self.out_dir / "split_lock.json"
        print("Loading datasets...", flush=True)
        for name, ysym in SYMBOLS_1H.items():
            self.frames_1h[name] = fetch_yahoo(ysym, "1h", "365d")
            self.frames_5m[name] = fetch_yahoo(ysym, "5m", "60d")
            print(
                f"  {name}: 1h={len(self.frames_1h[name])} bars, 5m={len(self.frames_5m[name])} bars",
                flush=True,
            )
            self.splits_1h[name] = freeze_splits(self.frames_1h[name])
            if len(self.frames_5m[name]):
                self.splits_5m[name] = freeze_splits(self.frames_5m[name])
        payload = {
            "frozen_at_rule": "60/20/20 chronological by trading day; locked before optimization",
            "splits_1h": {k: asdict(v) for k, v in self.splits_1h.items()},
            "splits_5m": {k: asdict(v) for k, v in self.splits_5m.items()},
            "friction": FRICTION_NOTE,
            "gates": GATES,
        }
        save_split_lock(lock_path, payload)
        print("Split lock written:", lock_path, flush=True)
        return payload

    def _partition(self, trades, split: SplitSpec) -> dict[str, list]:
        buckets = {"train": [], "val": [], "final": []}
        for t in trades:
            buckets[assign_period(t.entry_ts, split)].append(t)
        return buckets

    def run(self) -> dict[str, Any]:
        split_info = self.load_and_freeze()
        registry = build_registry()
        families = sorted({f for _, f, _, _ in registry})
        print(f"Registry: {len(registry)} configs across {len(families)} families", flush=True)

        # Phase 1: generate all trades, score TRAIN+VAL only for selection
        candidates: list[dict[str, Any]] = []
        all_train_dicts: list[dict[str, Any]] = []
        total_bars = sum(len(df) for df in self.frames_1h.values()) + sum(
            len(df) for df in self.frames_5m.values()
        )
        train_n = val_n = final_n_all = 0

        for cfg_id, family, fn, meta in registry:
            self.configs_tried += 1
            self.param_log.append({"config": cfg_id, "family": family, "params": meta})
            is_orb = family in ("opening_range", "orb_failed")
            frames = self.frames_5m if is_orb else self.frames_1h
            splits = self.splits_5m if is_orb else self.splits_1h
            tf = "5m" if is_orb else "1h"
            print(f"[{self.configs_tried}/{len(registry)}] {cfg_id}", flush=True)

            by_period = {"train": [], "val": [], "final": []}
            by_sym_final: dict[str, list] = defaultdict(list)
            for sym, df in frames.items():
                if df is None or df.empty or sym not in splits:
                    continue
                try:
                    trades = fn(df, sym)
                except Exception as exc:
                    print(f"  FAIL {sym}: {exc}", flush=True)
                    continue
                parts = self._partition(trades, splits[sym])
                for p in ("train", "val", "final"):
                    by_period[p].extend(parts[p])
                by_sym_final[sym].extend(parts["final"])

            st_train = trade_stats(
                [t.pnl_r for t in by_period["train"]],
                [t.entry_ts for t in by_period["train"]],
            )
            st_val = trade_stats(
                [t.pnl_r for t in by_period["val"]],
                [t.entry_ts for t in by_period["val"]],
            )
            train_n += st_train["n"]
            val_n += st_val["n"]
            final_n_all += len(by_period["final"])

            for t in by_period["train"]:
                all_train_dicts.append(
                    {
                        "strategy": cfg_id,
                        "symbol": t.symbol,
                        "session": t.session,
                        "regime": t.regime,
                        "pnl_r": t.pnl_r,
                    }
                )

            # Selection on VAL (or train if val thin): positive edge + anti-cheat
            select_st = st_val if st_val["n"] >= 15 else st_train
            selected = (
                select_st["n"] >= 15
                and select_st["expectancy_r"] > 0
                and select_st["pf"] >= 1.1
                and select_st["anti_cheat_ok"]
                and select_st["wr"] >= 0.50
            )
            candidates.append(
                {
                    "config": cfg_id,
                    "family": family,
                    "timeframe": tf,
                    "params": meta,
                    "train": st_train,
                    "val": st_val,
                    "selected_for_final": selected,
                    "final_trades": by_period["final"],
                    "by_sym_final": dict(by_sym_final),
                }
            )

        selected = [c for c in candidates if c["selected_for_final"]]
        print(f"Selected for FINAL untouched test: {len(selected)} / {len(candidates)}", flush=True)

        # Phase 2: FINAL evaluation only for selected
        finalists = []
        for c in selected:
            trades = c["final_trades"]
            st = trade_stats([t.pnl_r for t in trades], [t.entry_ts for t in trades])
            mc = monte_carlo([t.pnl_r for t in trades]) if st["n"] >= 20 else {}
            # session/regime breakdown on final
            sessions = {
                s: trade_stats(
                    [t.pnl_r for t in trades if t.session == s],
                    [t.entry_ts for t in trades if t.session == s],
                )
                for s in sorted({t.session for t in trades})
            }
            regimes = {
                r: trade_stats(
                    [t.pnl_r for t in trades if t.regime == r],
                    [t.entry_ts for t in trades if t.regime == r],
                )
                for r in sorted({t.regime for t in trades})
            }
            by_sym = {
                sym: trade_stats(
                    [t.pnl_r for t in ts],
                    [t.entry_ts for t in ts],
                )
                for sym, ts in c["by_sym_final"].items()
            }
            # failure modes (simple R-based)
            losses = [t for t in trades if t.pnl_r <= 0]
            fail = {
                "n_losses": len(losses),
                "by_session": defaultdict(int),
                "by_regime": defaultdict(int),
            }
            for t in losses:
                fail["by_session"][t.session] += 1
                fail["by_regime"][t.regime] += 1
            fail["by_session"] = dict(fail["by_session"])
            fail["by_regime"] = dict(fail["by_regime"])

            prob = comparable_probability(
                all_train_dicts, strategy=c["config"], symbol="NQ", min_n=30
            )

            row = {
                "config": c["config"],
                "family": c["family"],
                "timeframe": c["timeframe"],
                "params": c["params"],
                "train": c["train"],
                "val": c["val"],
                "final": st,
                "gates": meets_gates(st),
                "monte_carlo": mc,
                "sessions": sessions,
                "regimes": regimes,
                "by_symbol": by_sym,
                "failure_clusters": fail,
                "train_probability": prob,
            }
            finalists.append(row)

        # Also evaluate FINAL for top train/val by expectancy even if not selected? NO — user said only after survive train+val
        # Rank finalists
        finalists.sort(
            key=lambda r: (
                r["gates"],
                r["final"]["wr"],
                r["final"]["expectancy_r"],
                r["final"]["pf"],
                r["final"]["n"],
            ),
            reverse=True,
        )

        # For top10 display: include best finalists; if few selected, also show best val survivors with final scored (already all selected)
        # Pareto among finalists with E>0
        edge = [r for r in finalists if r["final"]["expectancy_r"] > 0 and r["final"]["n"] >= 20]
        edge.sort(key=lambda r: r["final"]["wr"], reverse=True)
        pareto = [
            {
                "config": r["config"],
                "wr": r["final"]["wr"],
                "pf": r["final"]["pf"],
                "expectancy_r": r["final"]["expectancy_r"],
                "trades_per_week": r["final"]["trades_per_week"],
                "n": r["final"]["n"],
            }
            for r in edge[:20]
        ]

        # Probability calibration using train empirical WR as "predicted" for val outcomes
        pred, obs = [], []
        for c in candidates:
            if c["train"]["n"] < 30 or c["val"]["n"] < 10:
                continue
            p = c["train"]["wr"]
            for t in c["final_trades"][:0]:  # don't use final for calibration training
                pass
            # calibrate on VAL only
            # reconstruct val trades not stored — skip storing; use train wr vs val wr bucket at config level
            pred.append(p)
            obs.append(1 if c["val"]["wr"] >= 0.5 else 0)  # weak — better below

        # Config-level calibration: predicted=train WR, observed=val WR (as Bernoulli approx via trades)
        pred2, out2 = [], []
        for c in candidates:
            if c["train"]["n"] < 40 or c["val"]["n"] < 20:
                continue
            # expand to trade-level using val n
            for _ in range(c["val"]["wins"]):
                pred2.append(c["train"]["wr"])
                out2.append(1)
            for _ in range(c["val"]["losses"]):
                pred2.append(c["train"]["wr"])
                out2.append(0)
        calibration = (
            calibrate_buckets(pred2, out2, min_n=30)
            if len(out2) >= 30
            else {"status": "INSUFFICIENT", "buckets": {}, "mae": None}
        )

        # Missed-move analysis (research-only; empty candidates ⇒ all large moves "undetected")
        missed: dict[str, Any] = {}
        try:
            nq = self.frames_1h.get("NQ")
            if nq is not None and len(nq):
                moves = scan_missed_moves(
                    nq.tail(500),
                    symbol="NQ",
                    candidates_by_bar={},
                    horizons=(6, 12),
                    atr_threshold=2.0,
                )
                missed = {
                    "large_directional_moves": len(moves),
                    "undetected": sum(1 for m in moves if not m.had_any_candidate),
                    "detected_a_plus_a": sum(1 for m in moves if m.had_a_or_better),
                    "detected_b_only": sum(1 for m in moves if m.had_b and not m.had_a_or_better),
                    "note": "Offline harness used empty candidates_by_bar — establishes move frequency baseline on NQ 1h tail.",
                }
        except Exception as exc:
            missed = {"error": str(exc)}

        champions = [r for r in finalists if r["gates"]]
        # strip heavy trade lists for JSON
        for r in finalists:
            r.pop("final_trades", None)

        # best by market / session from finalists
        def best_sym(sym: str):
            scored = []
            for r in finalists:
                st = (r.get("by_symbol") or {}).get(sym)
                if st and st["n"] >= 15:
                    scored.append((r, st))
            if not scored:
                return None
            scored.sort(key=lambda x: (x[1]["wr"], x[1]["expectancy_r"], x[1]["n"]), reverse=True)
            r, st = scored[0]
            return {"config": r["config"], "family": r["family"], "final": st}

        def best_sess(prefix: str):
            scored = []
            for r in finalists:
                for s, st in (r.get("sessions") or {}).items():
                    if prefix in s and st["n"] >= 12:
                        scored.append((r["config"], s, st))
            if not scored:
                return None
            scored.sort(key=lambda x: (x[2]["wr"], x[2]["expectancy_r"]), reverse=True)
            cfg, s, st = scored[0]
            return {"config": cfg, "session": s, "final": st}

        summary = {
            "verdict": (
                "CANDIDATE MEETS STANDARD"
                if champions
                else "NO CANDIDATE MEETS STANDARD"
            ),
            "gates": GATES,
            "friction": FRICTION_NOTE,
            "research_scale": {
                "strategy_families": len(families),
                "family_list": families,
                "total_configurations": self.configs_tried,
                "historical_bars": total_bars,
                "train_trades": train_n,
                "validation_trades": val_n,
                "final_untouched_oos_trades_selected_path": sum(
                    r["final"]["n"] for r in finalists
                ),
                "final_trades_all_configs_generated": final_n_all,
                "selected_for_final": len(selected),
            },
            "split_lock": split_info,
            "champions": [
                {
                    "config": c["config"],
                    "family": c["family"],
                    "final": c["final"],
                    "monte_carlo": c["monte_carlo"],
                }
                for c in champions
            ],
            "top10_finalists": [
                {
                    "strategy": r["config"],
                    "family": r["family"],
                    "timeframe": r["timeframe"],
                    "symbol": "MULTI",
                    "session": "ALL",
                    "regime": "ALL",
                    "entry": r["params"],
                    "exit": f"{r['params'].get('target_r')}R",
                    "final_oos_n": r["final"]["n"],
                    "wr": r["final"]["wr"],
                    "wr_ci95": r["final"]["wr_ci95"],
                    "pf": r["final"]["pf"],
                    "expectancy_r": r["final"]["expectancy_r"],
                    "max_dd_r": r["final"]["max_dd_r"],
                    "trades_per_week": r["final"]["trades_per_week"],
                    "avg_win_r": r["final"]["avg_win_r"],
                    "avg_loss_r": r["final"]["avg_loss_r"],
                    "worst_r": r["final"]["worst_r"],
                    "gates": r["gates"],
                    "anti_cheat_ok": r["final"]["anti_cheat_ok"],
                }
                for r in finalists[:10]
            ],
            "best_by_market": {
                "NQ": best_sym("NQ"),
                "ES": best_sym("ES"),
                "GC": best_sym("GC"),
                "CL": best_sym("CL"),
            },
            "best_by_session": {
                "ASIA": best_sess("ASIA"),
                "LONDON": best_sess("LONDON"),
                "NY": best_sess("NY"),
            },
            "pareto": pareto,
            "monte_carlo_top": finalists[0]["monte_carlo"] if finalists else {},
            "calibration": calibration,
            "missed_moves": missed,
            "failure_modes_top": finalists[0]["failure_clusters"] if finalists else {},
            "paper_bot_frozen": True,
            "paper_bot_modified": False,
            "recommended_champion": champions[0] if champions else None,
            "closest_misses": [
                {
                    "config": r["config"],
                    "final": r["final"],
                    "why_failed": [
                        *(["wr"] if r["final"]["wr"] < GATES["min_wr"] else []),
                        *(["pf"] if r["final"]["pf"] < GATES["min_pf"] else []),
                        *(["E"] if r["final"]["expectancy_r"] < GATES["min_expectancy_r"] else []),
                        *(["n"] if r["final"]["n"] < GATES["min_n"] else []),
                        *(["anti_cheat"] if not r["final"]["anti_cheat_ok"] else []),
                    ],
                }
                for r in finalists[:5]
                if not r["gates"]
            ],
        }

        out_json = self.out_dir / "full_research_program.json"
        out_json.write_text(
            json.dumps({"summary": summary, "finalists": finalists[:40], "param_log_n": len(self.param_log)}, indent=2),
            encoding="utf-8",
        )
        return summary
