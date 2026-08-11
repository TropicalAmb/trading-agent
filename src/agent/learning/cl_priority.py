"""CL priority learning cell — investigate without promoting from one trade.

IMPORTANT:
- Recent successful CL *paper* trade was ``cl_vwap_prox_momentum``, not liquidity_reversal.
- OOS simple_liquidity_reversal (~49% WR / PF 1.45 / E +0.23R) stays research evidence only.
- Do NOT make liquidity_reversal globally dominant from a single winner.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

from agent.learning.shrink import shrink_rate


def _parse_ts(s: Any) -> Optional[datetime]:
    if s is None or s == "":
        return None
    try:
        dt = datetime.fromisoformat(str(s).replace("Z", "+00:00").replace(" ", "T"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def _r_from_trade(t: dict[str, Any]) -> Optional[float]:
    if t.get("r_achieved") is not None:
        try:
            return float(t["r_achieved"])
        except Exception:
            pass
    try:
        entry = float(t["entry"])
        stop = float(t["stop"])
        exit_px = float(t.get("exit") or t.get("exit_price") or 0)
        side = str(t.get("side") or t.get("direction") or "BUY").upper()
        risk = abs(entry - stop)
        if risk <= 1e-12:
            return None
        pnl_pts = (exit_px - entry) if side in {"BUY", "LONG"} else (entry - exit_px)
        return pnl_pts / risk
    except Exception:
        return None


def load_cl_paper_trades(root: Path) -> list[dict[str, Any]]:
    path = root / "data" / "paper_trades.json"
    if not path.exists():
        return []
    data = json_load(path)
    trades = list(data.get("trades") or [])
    out = []
    for t in trades:
        sym = str(t.get("symbol") or "").upper()
        if sym not in {"CL", "MCL"}:
            continue
        strat = str(t.get("strategy_name") or t.get("strategy") or "")
        if not t.get("closed_at") and str(t.get("status") or "").upper() not in {"CLOSED", ""}:
            # include closed only for outcome analysis; keep opens tagged
            pass
        out.append(t)
    return out


def load_cl_shadow_trades(root: Path, *, strategy_substr: str = "liquidity_reversal") -> list[dict[str, Any]]:
    path = root / "data" / "shadow_trades.json"
    if not path.exists():
        return []
    data = json_load(path)
    rows = list(data.get("closed") or []) + list(data.get("open") or [])
    out = []
    for t in rows:
        sym = str(t.get("symbol") or "").upper()
        if sym not in {"CL", "MCL"}:
            continue
        strat = str(t.get("strategy") or t.get("strategy_name") or "").lower()
        if strategy_substr.lower() not in strat:
            continue
        out.append(t)
    return out


def json_load(path: Path) -> dict[str, Any]:
    import json

    return json.loads(path.read_text(encoding="utf-8"))


def entry_snapshot_from_trade(t: dict[str, Any]) -> dict[str, Any]:
    """Best-effort entry-time snapshot from stored trade metadata (no lookahead fields)."""
    meta = t.get("metadata") if isinstance(t.get("metadata"), dict) else {}
    feats = dict(meta.get("entry_features") or t.get("entry_features") or {})
    reason = str(t.get("reason") or meta.get("reason") or "")
    snap = {
        "symbol": str(t.get("symbol") or "").upper(),
        "strategy": str(t.get("strategy_name") or t.get("strategy") or ""),
        "direction": str(t.get("side") or t.get("direction") or "").upper(),
        "session": t.get("session") or meta.get("session") or feats.get("session"),
        "regime": meta.get("regime") or feats.get("regime"),
        "entry_market_time": t.get("opened_at") or t.get("market_timestamp"),
        "entry": t.get("entry"),
        "stop": t.get("stop"),
        "target": t.get("target"),
        "qty": t.get("qty") or t.get("quantity"),
        "expected_r": t.get("expected_r") or feats.get("target_r"),
        "risk_dollars": t.get("risk_dollars"),
        "reward_dollars": t.get("reward_dollars"),
        "global_score": meta.get("global_score") or t.get("confidence") or feats.get("global_score"),
        "local_score": meta.get("strategy_local_score") or feats.get("local_score"),
        "tier": t.get("setup_tier") or t.get("tier") or meta.get("tier"),
        "agreeing_engines": meta.get("agreeing_engines") or _parse_agreeing(reason),
        "reason": reason,
        "dir_15m": feats.get("dir_15m"),
        "dir_1h": feats.get("dir_1h"),
        "dir_4h": feats.get("dir_4h"),
        "mtf_aligned": feats.get("mtf_aligned"),
        "above_vwap": feats.get("above_vwap"),
        "below_vwap": feats.get("below_vwap"),
        "ema_bull": feats.get("ema_bull"),
        "ema_bear": feats.get("ema_bear"),
        "overextended": feats.get("overextended"),
        "near_pdh": feats.get("near_pdh"),
        "near_pdl": feats.get("near_pdl"),
        "momentum_aligned": feats.get("momentum_aligned"),
        "vwap_dist_atr": feats.get("vwap_dist_atr") or feats.get("abs_dist_vwap_atr"),
        "stop_dist_atr": feats.get("stop_dist_atr"),
        "atr": feats.get("atr"),
        "atr_pctile": feats.get("atr_pctile"),
        "body_atr": feats.get("body_atr"),
        "cascade": meta.get("cascade"),
        "router_evidence": meta.get("router_evidence") or t.get("router_evidence"),
        "config_version": t.get("config_version") or meta.get("config_version"),
        "setup_id": meta.get("setup_id") or t.get("setup_id"),
        "mfe_pts": t.get("mfe_pts") or t.get("mfe"),
        "mae_pts": t.get("mae_pts") or t.get("mae"),
        "pnl_dollars": t.get("pnl_dollars") or t.get("pnl"),
        "exit_reason": t.get("exit_reason"),
        "result": t.get("result") or t.get("final_result"),
        "realized_r": _r_from_trade(t),
        "features_source": "trade.metadata.entry_features" if feats else "trade.fields_only",
        "anecdotal_warning": (
            "Single-trade traits are anecdotal until confirmed vs a loss cohort."
        ),
    }
    return snap


def _parse_agreeing(reason: str) -> list[str]:
    if "agreement:" not in reason:
        return []
    try:
        part = reason.split("agreement:", 1)[1]
        part = part.split("|")[0].strip()
        return [x.strip() for x in part.split(",") if x.strip()]
    except Exception:
        return []


def split_wins_losses(trades: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    wins, losses = [], []
    for t in trades:
        if not t.get("closed_at") and str(t.get("status") or "").upper() == "OPEN":
            continue
        pnl = t.get("pnl_dollars")
        if pnl is None:
            pnl = t.get("pnl")
        r = _r_from_trade(t)
        try:
            pnl_f = float(pnl) if pnl is not None else None
        except Exception:
            pnl_f = None
        if pnl_f is not None:
            if pnl_f > 0:
                wins.append(t)
            elif pnl_f < 0:
                losses.append(t)
        elif r is not None:
            if r > 0:
                wins.append(t)
            elif r < 0:
                losses.append(t)
    return wins, losses


def _rate(xs: list[Any], pred) -> dict[str, Any]:
    vals = [pred(x) for x in xs]
    vals = [v for v in vals if v is not None]
    if not vals:
        return {"n": 0, "rate": None}
    return {"n": len(vals), "rate": float(np.mean(vals))}


def _median(xs: list[float]) -> Optional[float]:
    if not xs:
        return None
    return float(np.median(xs))


def compare_win_loss_traits(
    wins: list[dict[str, Any]],
    losses: list[dict[str, Any]],
) -> dict[str, Any]:
    """Actual pre-entry trait rates — no invented filters."""

    def snaps(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [entry_snapshot_from_trade(t) for t in rows]

    W, L = snaps(wins), snaps(losses)

    def session_share(rows: list[dict], name: str) -> Optional[float]:
        if not rows:
            return None
        return sum(1 for r in rows if str(r.get("session") or "").lower() == name.lower()) / len(rows)

    def mtf_ge2(rows: list[dict]) -> Optional[float]:
        vals = []
        for r in rows:
            m = r.get("mtf_aligned")
            if m is None:
                continue
            vals.append(1.0 if int(m) >= 2 else 0.0)
        return float(np.mean(vals)) if vals else None

    def flag_rate(rows: list[dict], key: str) -> Optional[float]:
        vals = []
        for r in rows:
            if r.get(key) is None:
                continue
            vals.append(1.0 if int(r.get(key) or 0) else 0.0)
        return float(np.mean(vals)) if vals else None

    def med_feat(rows: list[dict], key: str) -> Optional[float]:
        vals = []
        for r in rows:
            try:
                if r.get(key) is not None:
                    vals.append(float(r[key]))
            except Exception:
                pass
        return _median(vals)

    def direction_share(rows: list[dict], d: str) -> Optional[float]:
        if not rows:
            return None
        return sum(1 for r in rows if str(r.get("direction") or "").upper() in {d, "LONG" if d == "BUY" else "SHORT"}) / len(rows)

    comparison = {
        "n_wins": len(W),
        "n_losses": len(L),
        "features_available_warning": (
            "Many shadow/paper rows lack full entry_features; rates use available fields only."
        ),
        "winners": {
            "pct_london": session_share(W, "london"),
            "pct_asia": session_share(W, "asia"),
            "pct_ny": session_share(W, "ny"),
            "pct_mtf_aligned_ge2": mtf_ge2(W),
            "pct_above_vwap": flag_rate(W, "above_vwap"),
            "pct_below_vwap": flag_rate(W, "below_vwap"),
            "pct_ema_bull": flag_rate(W, "ema_bull"),
            "pct_overextended": flag_rate(W, "overextended"),
            "pct_near_pdh": flag_rate(W, "near_pdh"),
            "pct_near_pdl": flag_rate(W, "near_pdl"),
            "pct_buy": direction_share(W, "BUY"),
            "median_global_score": med_feat(W, "global_score"),
            "median_expected_r": med_feat(W, "expected_r"),
            "median_vwap_dist_atr": med_feat(W, "vwap_dist_atr"),
            "median_realized_r": med_feat(W, "realized_r"),
        },
        "losers": {
            "pct_london": session_share(L, "london"),
            "pct_asia": session_share(L, "asia"),
            "pct_ny": session_share(L, "ny"),
            "pct_mtf_aligned_ge2": mtf_ge2(L),
            "pct_above_vwap": flag_rate(L, "above_vwap"),
            "pct_below_vwap": flag_rate(L, "below_vwap"),
            "pct_ema_bull": flag_rate(L, "ema_bull"),
            "pct_overextended": flag_rate(L, "overextended"),
            "pct_near_pdh": flag_rate(L, "near_pdh"),
            "pct_near_pdl": flag_rate(L, "near_pdl"),
            "pct_buy": direction_share(L, "BUY"),
            "median_global_score": med_feat(L, "global_score"),
            "median_expected_r": med_feat(L, "expected_r"),
            "median_vwap_dist_atr": med_feat(L, "vwap_dist_atr"),
            "median_realized_r": med_feat(L, "realized_r"),
        },
    }
    # Deltas where both sides have data
    deltas = {}
    for k in comparison["winners"]:
        w, l = comparison["winners"][k], comparison["losers"][k]
        if w is not None and l is not None:
            deltas[k] = float(w) - float(l)
    comparison["deltas_winner_minus_loser"] = deltas
    return comparison


def cell_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    rs = []
    wins = 0
    for t in rows:
        r = _r_from_trade(t)
        if r is None:
            pnl = t.get("pnl_dollars", t.get("pnl"))
            try:
                r = 1.0 if float(pnl) > 0 else (-1.0 if float(pnl) < 0 else 0.0)
            except Exception:
                continue
        rs.append(r)
        if r > 0:
            wins += 1
    n = len(rs)
    if n == 0:
        return {"n": 0}
    wr = wins / n
    avg = float(np.mean(rs))
    pos = sum(x for x in rs if x > 0)
    neg = abs(sum(x for x in rs if x < 0))
    pf = (pos / neg) if neg > 1e-12 else (999.0 if pos > 0 else 0.0)
    # max DD in R (path of cumulative R)
    cum = np.cumsum(rs)
    peak = np.maximum.accumulate(cum)
    dd = float(np.min(cum - peak)) if len(cum) else 0.0
    shr = shrink_rate(wins, n, prior_mean=0.50, prior_strength=20.0)
    return {
        "n": n,
        "wr": wr,
        "raw_wr": wr,
        "shrunk_wr": shr.shrunk,
        "pf": pf,
        "expectancy_r": avg,
        "max_dd_r": dd,
        "category": (
            "VALIDATED" if n >= 100 else "DEVELOPING" if n >= 40 else "EARLY" if n >= 20 else "INSUFFICIENT"
        ),
    }


def find_subcells(
    trades: list[dict[str, Any]],
    *,
    min_n: int = 20,
) -> list[dict[str, Any]]:
    buckets: dict[tuple, list[dict[str, Any]]] = defaultdict(list)
    for t in trades:
        snap = entry_snapshot_from_trade(t)
        session = str(snap.get("session") or "unknown")
        regime = str(snap.get("regime") or "unknown")
        direction = str(snap.get("direction") or "unknown")
        mtf = snap.get("mtf_aligned")
        mtf_bucket = (
            "mtf3"
            if mtf is not None and int(mtf) >= 3
            else "mtf2"
            if mtf is not None and int(mtf) == 2
            else "mtf_le1"
            if mtf is not None
            else "mtf_unk"
        )
        vwap_state = (
            "above_vwap"
            if snap.get("above_vwap")
            else "below_vwap"
            if snap.get("below_vwap")
            else "vwap_unk"
        )
        for key in [
            ("session", session),
            ("regime", regime),
            ("direction", direction),
            ("session+direction", f"{session}|{direction}"),
            ("session+regime", f"{session}|{regime}"),
            ("mtf", mtf_bucket),
            ("vwap", vwap_state),
            ("session+mtf", f"{session}|{mtf_bucket}"),
            ("session+vwap", f"{session}|{vwap_state}"),
        ]:
            buckets[key].append(t)
    cells = []
    for (dim, val), rows in buckets.items():
        m = cell_metrics(rows)
        if m.get("n", 0) < min_n:
            continue
        cells.append({"dimension": dim, "value": val, **m})
    cells.sort(key=lambda x: (x.get("expectancy_r") or -999, x.get("pf") or 0), reverse=True)
    return cells


def find_recent_cl_paper_winner(root: Path) -> Optional[dict[str, Any]]:
    """Largest recent CL paper winner by pnl (any paperable CL strategy)."""
    trades = load_cl_paper_trades(root)
    closed = [t for t in trades if t.get("closed_at") or str(t.get("status") or "").upper() == "CLOSED"]
    best = None
    best_pnl = None
    for t in closed:
        try:
            pnl = float(t.get("pnl_dollars") or t.get("pnl") or 0)
        except Exception:
            continue
        if pnl <= 0:
            continue
        if best_pnl is None or pnl > best_pnl:
            best_pnl = pnl
            best = t
    return best


def load_learning_rows(root: Path, *, symbol: str | None = None, strategy: str | None = None) -> list[dict[str, Any]]:
    path = root / "data" / "learning" / "candidates.jsonl"
    if not path.exists():
        return []
    import json

    sym_ok = None
    if symbol:
        s = symbol.upper()
        sym_ok = {"CL", "MCL"} if s == "CL" else {s}
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except Exception:
            continue
        if sym_ok is not None and str(r.get("symbol") or "").upper() not in sym_ok:
            continue
        if strategy and strategy.lower() not in str(r.get("strategy") or "").lower():
            continue
        out.append(r)
    return out


def enrich_winner_from_learning_store(root: Path, trade: dict[str, Any]) -> dict[str, Any]:
    snap = entry_snapshot_from_trade(trade)
    # Prefer learning-store OPEN/resolved row features
    rows = load_learning_rows(root, symbol="CL", strategy=str(trade.get("strategy_name") or ""))
    ts = str(trade.get("market_timestamp") or trade.get("opened_at") or "")[:16]
    match = None
    for r in rows:
        rts = str(r.get("market_timestamp") or r.get("timestamp") or "")[:16]
        if ts and rts == ts:
            match = r
            break
    if match is None and rows:
        # latest matching strategy
        match = rows[-1]
    if match:
        feats = dict(match.get("features") or match.get("entry_features") or {})
        for k, v in feats.items():
            if snap.get(k) is None:
                snap[k] = v
        for k in ("session", "regime", "global_score", "tier", "mtf_aligned", "dir_15m", "dir_1h", "dir_4h"):
            if snap.get(k) is None and match.get(k) is not None:
                snap[k] = match.get(k)
        snap["features_source"] = "learning_store+trade"
        snap["learning_candidate_id"] = match.get("candidate_id")
    # Parse agreeing engines from reason
    if not snap.get("agreeing_engines"):
        snap["agreeing_engines"] = _parse_agreeing(str(trade.get("reason") or ""))
    # Derived R:R
    try:
        risk = abs(float(trade["entry"]) - float(trade["stop"]))
        reward = abs(float(trade["target"]) - float(trade["entry"]))
        snap["rr"] = reward / risk if risk > 0 else None
        snap["stop_distance"] = risk
    except Exception:
        pass
    return snap


def backtest_cl_liquidity_reversal(
    root: Path,
    *,
    period: str = "60d",
    interval: str = "5m",
) -> list[dict[str, Any]]:
    """Historical CL liquidity_reversal trades for subcell search (research only)."""
    try:
        from agent.research.harness.datasets import fetch_yahoo
        from agent.strategy.liquidity_reversal import evaluate_liquidity_reversal
        from agent.schedule.sessions import active_session_name
    except Exception:
        return []

    cfg_path = root / "config" / "settings.yaml"
    try:
        import yaml

        cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    except Exception:
        cfg = {}
    try:
        df = fetch_yahoo("CL=F", interval, period)
    except Exception:
        return []
    if df is None or len(df) < 80:
        return []
    trades: list[dict[str, Any]] = []
    i = 40
    while i < len(df) - 2:
        window = df.iloc[: i + 1]
        sig = evaluate_liquidity_reversal("CL", window, cfg, point_value=1000.0)
        if sig is None:
            i += 1
            continue
        entry, stop, target = float(sig.entry), float(sig.stop), float(sig.target)
        side = sig.side
        # Forward path to stop/target (no lookahead features — outcome only)
        j = i + 1
        result_r = None
        exit_reason = None
        while j < min(len(df), i + 48):
            hi = float(df["high"].iloc[j])
            lo = float(df["low"].iloc[j])
            if side == "BUY":
                if lo <= stop:
                    result_r = -1.0
                    exit_reason = "stop"
                    break
                if hi >= target:
                    result_r = abs(target - entry) / max(abs(entry - stop), 1e-9)
                    exit_reason = "target"
                    break
            else:
                if hi >= stop:
                    result_r = -1.0
                    exit_reason = "stop"
                    break
                if lo <= target:
                    result_r = abs(entry - target) / max(abs(stop - entry), 1e-9)
                    exit_reason = "target"
                    break
            j += 1
        if result_r is None:
            i += 1
            continue
        ts = df.index[i]
        try:
            tspy = ts.to_pydatetime() if hasattr(ts, "to_pydatetime") else ts
            if getattr(tspy, "tzinfo", None) is None:
                tspy = tspy.replace(tzinfo=timezone.utc)
            sess = active_session_name(cfg, tspy) or "unknown"
        except Exception:
            sess = "unknown"
        # Entry-time context features from window only
        last = window.iloc[-1]
        atr_s = (window["high"] - window["low"]).rolling(14).mean()
        atr = float(atr_s.iloc[-1] or 0) or 1e-9
        vwap = float((window["close"] * window.get("volume", 1)).sum() / max(float(window.get("volume", pd.Series([1]*len(window))).sum() or 1), 1))
        # simpler session vwap proxy
        try:
            typ = (window["high"] + window["low"] + window["close"]) / 3.0
            vwap = float((typ * window["volume"]).sum() / max(float(window["volume"].sum()), 1e-9)) if "volume" in window else float(typ.mean())
        except Exception:
            vwap = float(window["close"].mean())
        close = float(last["close"])
        o, h, l = float(last["open"]), float(last["high"]), float(last["low"])
        body = abs(close - o) / atr
        upper = (h - max(close, o)) / atr
        lower = (min(close, o) - l) / atr
        trades.append(
            {
                "symbol": "CL",
                "strategy": "liquidity_reversal",
                "side": side,
                "direction": side,
                "session": sess,
                "entry": entry,
                "stop": stop,
                "target": target,
                "closed_at": str(df.index[j]) if j < len(df) else str(ts),
                "opened_at": str(ts),
                "market_timestamp": str(ts),
                "exit_reason": exit_reason,
                "r_achieved": result_r,
                "pnl": result_r,
                "status": "CLOSED",
                "metadata": {
                    "entry_features": {
                        "session": sess,
                        "above_vwap": int(close > vwap),
                        "below_vwap": int(close < vwap),
                        "vwap_dist_atr": (close - vwap) / atr,
                        "body_atr": body,
                        "upper_wick_atr": upper,
                        "lower_wick_atr": lower,
                        "atr": atr,
                        "rejection": int((upper if side == "SELL" else lower) >= 0.25),
                        "sweep_magnitude_atr": (h - float(window["high"].iloc[-13:-1].max()) if side == "SELL" else float(window["low"].iloc[-13:-1].min()) - l) / atr,
                    },
                    "regime": "UNKNOWN",
                },
                "result": "WIN" if result_r > 0 else "LOSS",
            }
        )
        i = j + 1  # no overlapping entries
    return trades


def build_cl_priority_report(root: Path | None = None, *, run_hist_bt: bool = True) -> dict[str, Any]:
    root = root or Path(__file__).resolve().parents[3]
    paper_winner = find_recent_cl_paper_winner(root)
    paper_winner_snap = (
        enrich_winner_from_learning_store(root, paper_winner) if paper_winner else None
    )

    # All CL paper trades by strategy (for specialist cohort)
    paper_all = load_cl_paper_trades(root)
    paper_closed = [t for t in paper_all if t.get("closed_at")]
    paper_by_strat: dict[str, list] = defaultdict(list)
    for t in paper_closed:
        paper_by_strat[str(t.get("strategy_name") or t.get("strategy") or "unknown")].append(t)

    # Priority shadow cell: CL liquidity_reversal (live shadows — thin)
    lr_shadows = load_cl_shadow_trades(root, strategy_substr="liquidity_reversal")
    lr_closed = [t for t in lr_shadows if t.get("closed_at") or str(t.get("status") or "").upper() == "CLOSED"]
    lr_wins, lr_losses = split_wins_losses(lr_closed)
    lr_compare_live = compare_win_loss_traits(lr_wins, lr_losses)

    # Historical research backtest for proper subcell n
    hist = backtest_cl_liquidity_reversal(root) if run_hist_bt else []
    hist_wins, hist_losses = split_wins_losses(hist)
    lr_compare = compare_win_loss_traits(hist_wins, hist_losses) if hist else lr_compare_live
    lr_cells = find_subcells(hist if hist else lr_closed, min_n=20)
    # Also include EARLY cells at n>=20 already; add developing view at n>=15 for reporting only
    lr_cells_early = find_subcells(hist if hist else lr_closed, min_n=15)
    lr_overall = cell_metrics(hist) if hist else cell_metrics(lr_closed)

    # Stronger than prior OOS simple_liquidity_reversal reference (~49.1% WR / E +0.23R)
    # Prefer material lift vs this hist baseline; EARLY still flagged separately.
    strong = [
        c
        for c in lr_cells
        if (c.get("wr") or 0) >= 0.491
        and (c.get("expectancy_r") or -9) > 0.0
        and (c.get("pf") or 0) >= 1.2
    ]
    # Relative best cells even if below the 49.1% OOS ref (honest reporting)
    relative_best = sorted(
        lr_cells,
        key=lambda c: (c.get("expectancy_r") or -9, c.get("wr") or 0),
        reverse=True,
    )[:15]

    specialist = paper_by_strat.get("cl_vwap_prox_momentum") or []
    sp_wins, sp_losses = split_wins_losses(specialist)
    sp_compare = compare_win_loss_traits(sp_wins, sp_losses) if (sp_wins or sp_losses) else {}
    sp_cells = find_subcells(specialist, min_n=5) if len(specialist) >= 5 else []

    anecdotal = []
    useful = []
    if paper_winner_snap:
        anecdotal.append(
            {
                "note": (
                    "Paper winner strategy is cl_vwap_prox_momentum (NOT liquidity_reversal). "
                    "Traits below are anecdotal until confirmed vs a same-strategy loss cohort."
                ),
                "winner_strategy": paper_winner_snap.get("strategy"),
            }
        )
        for k in (
            "session",
            "mtf_aligned",
            "above_vwap",
            "dir_15m",
            "dir_1h",
            "dir_4h",
            "near_pdl",
            "agreeing_engines",
            "global_score",
            "tier",
        ):
            anecdotal.append(
                {"trait": k, "value": paper_winner_snap.get(k), "status": "anecdotal_single_trade"}
            )
    # Statistically useful = large winner-minus-loser deltas in HIST LR cohort
    for k, delta in (lr_compare.get("deltas_winner_minus_loser") or {}).items():
        if abs(float(delta)) >= 0.10:
            useful.append(
                {
                    "trait": k,
                    "delta": delta,
                    "winners": (lr_compare.get("winners") or {}).get(k),
                    "losers": (lr_compare.get("losers") or {}).get(k),
                    "status": "statistical_candidate",
                    "cohort": "CL_liquidity_reversal_historical",
                }
            )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "policy": {
            "do_not_promote_from_one_trade": True,
            "keep_multi_strategy_mix": True,
            "liquidity_reversal_global_dominance": False,
            "priority_learning_cell": "CL|liquidity_reversal",
            "oos_reference_simple_liquidity_reversal": {
                "wr": 0.491,
                "pf": 1.45,
                "expectancy_r": 0.23,
                "note": "Prior OOS evidence — not overridden by one paper trade",
            },
        },
        "recent_cl_paper_winner": {
            "warning": (
                "This paper winner is cl_vwap_prox_momentum (validated specialist), "
                "NOT liquidity_reversal. Do not treat as LR promotion evidence."
            ),
            "trade_id": (paper_winner or {}).get("id") or (paper_winner or {}).get("order_id"),
            "snapshot": paper_winner_snap,
            "anecdotal_traits": anecdotal,
            "statistically_useful_traits": useful,
        },
        "cl_liquidity_reversal_live_shadow": {
            "n_closed": len(lr_closed),
            "overall": cell_metrics(lr_closed),
            "winner_vs_loser": lr_compare_live,
            "note": "Live paper-shadow sample is thin; historical BT used for subcells.",
        },
        "cl_liquidity_reversal_historical": {
            "n_closed": len(hist),
            "overall": lr_overall,
            "winner_vs_loser": lr_compare,
            "subcells": lr_cells,
            "subcells_incl_borderline": lr_cells_early,
            "stronger_than_global_ref": strong,
            "relative_best_subcells": relative_best,
            "validated_cells": [c for c in lr_cells if c.get("category") == "VALIDATED"],
            "developing_cells": [c for c in lr_cells if c.get("category") == "DEVELOPING"],
            "early_cells": [c for c in lr_cells if c.get("category") == "EARLY"],
            "execution_note": "EARLY cells must not control paper execution. Relative-best cells are diagnostic only.",
            "note": (
                "This hist BT of live liquidity_reversal rules (~40% WR) is not identical to "
                "prior research simple_liquidity_reversal OOS (~49.1% WR). Keep LR research_only."
            ),
        },
        "cl_vwap_prox_momentum_paper": {
            "n_closed": len(specialist),
            "overall": cell_metrics(specialist) if specialist else {"n": 0},
            "winner_vs_loser": sp_compare,
            "subcells": sp_cells,
        },
        "paper_cl_by_strategy": {k: cell_metrics(v) for k, v in paper_by_strat.items()},
        "learning_store": {
            "cl_rows": len(load_learning_rows(root, symbol="CL")),
            "cl_liquidity_reversal_rows": len(
                load_learning_rows(root, symbol="CL", strategy="liquidity_reversal")
            ),
        },
    }
