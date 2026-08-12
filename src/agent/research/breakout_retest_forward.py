"""Breakout_retest forward research — OBSERVATION ONLY.

Does not change paper config, thresholds, risk, qty, or ranking.
Builds winner/loser datasets and reports for post-paperfix2 evidence.
"""

from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

from agent.execution.risk_budget import FULL_SIZE_OF, MICRO_OF
from agent.learning.shrink import shrink_rate
from agent.research.harness.metrics import trade_stats

PAPERFIX2_STAMPS = {"router_v1_paperfix2"}
# Inclusive: paperfix1 was mid-day unblock; cleanest compare starts paperfix2
POST_FIX_STAMPS = {"router_v1_paperfix2"}
PRE_FIX_PREFIXES = ("router_v1_paperfix1", "router_v1_nqctx", "router_v1_quality", "router_v1")

FEATURE_KEYS = [
    "dir_15m",
    "dir_1h",
    "dir_4h",
    "mtf_aligned",
    "above_vwap",
    "below_vwap",
    "ema_bull",
    "ema_bear",
    "overextended",
    "near_pdh",
    "near_pdl",
    "momentum_aligned",
    "agreeing_n",
    "target_r",
    "global_score",
    "local_score",
    "cascade_location",
    "cascade_thesis",
]


@dataclass
class BrRow:
    source: str
    trade_id: str
    setup_id: str
    symbol: str
    contract_class: str  # full | micro | other
    direction: str
    session: str
    regime: str
    market_timestamp: str
    config_version: str
    era: str  # post_paperfix2 | pre_paperfix2 | unknown
    tier: str
    qty: int
    entry: float
    stop: float
    target: float
    pnl_dollars: float | None
    realized_r: float | None
    win: bool | None
    exit_reason: str
    mfe_r: float | None = None
    mae_r: float | None = None
    target_before_stop: bool | None = None
    plus_1r_before_stop: bool | None = None
    features: dict[str, Any] = field(default_factory=dict)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _contract_class(symbol: str) -> str:
    s = str(symbol or "").upper()
    if s in MICRO_OF:
        return "full"
    if s in FULL_SIZE_OF:
        return "micro"
    return "other"


def _era(config_version: str) -> str:
    cv = str(config_version or "")
    if cv in POST_FIX_STAMPS or cv.endswith("paperfix2"):
        return "post_paperfix2"
    if not cv:
        return "unknown"
    return "pre_paperfix2"


def _pnl_of_trade(t: dict[str, Any]) -> float | None:
    for k in ("pnl_dollars", "realized_pnl", "pnl"):
        if t.get(k) is not None:
            try:
                return float(t[k])
            except (TypeError, ValueError):
                pass
    return None


def _r_of_trade(t: dict[str, Any], pnl: float | None) -> float | None:
    if t.get("r_multiple") is not None:
        try:
            return float(t["r_multiple"])
        except (TypeError, ValueError):
            pass
    meta = t.get("metadata") or {}
    risk = t.get("risk_dollars")
    if risk is None:
        risk = meta.get("risk_dollars")
    qty = max(1, int(t.get("qty") or t.get("quantity") or 1))
    try:
        risk_f = float(risk) if risk is not None else None
    except (TypeError, ValueError):
        risk_f = None
    # risk_dollars on blotter is often per-contract; position risk ≈ risk * qty
    if pnl is not None and risk_f and risk_f > 0:
        return pnl / (risk_f * qty) if risk_f * qty > 0 else pnl / risk_f
    entry = float(t.get("entry") or 0)
    stop = float(t.get("stop") or 0)
    pv = float(t.get("point_value") or (meta.get("point_value") or 0) or 0)
    if pnl is not None and entry and stop and pv:
        risk_pts = abs(entry - stop)
        pos_risk = risk_pts * pv * qty
        if pos_risk > 0:
            return pnl / pos_risk
    return None


def _features_from_trade(t: dict[str, Any]) -> dict[str, Any]:
    meta = t.get("metadata") or {}
    ef = dict(meta.get("entry_features") or t.get("entry_features") or {})
    # flatten common cascade bits
    cas = meta.get("cascade") or {}
    if "cascade_location" not in ef and cas:
        ef["cascade_location"] = cas.get("location")
        ef["cascade_thesis"] = cas.get("thesis")
    if "global_score" not in ef:
        ef["global_score"] = meta.get("global_score") or t.get("global_score")
    if "local_score" not in ef:
        ef["local_score"] = meta.get("strategy_local_score") or t.get("strategy_local_score")
    if "agreeing_n" not in ef:
        ag = meta.get("agreeing_engines") or []
        ef["agreeing_n"] = len(ag) if ag else ef.get("agreeing_n")
    return ef


def load_paper_breakouts(paper_path: Path) -> list[BrRow]:
    if not paper_path.exists():
        return []
    state = json.loads(paper_path.read_text(encoding="utf-8"))
    rows: list[BrRow] = []
    for t in state.get("trades") or []:
        if str(t.get("strategy_name") or "") != "breakout_retest":
            continue
        if str(t.get("status") or "").upper() == "OPEN" or not t.get("closed_at"):
            # still include open for tracking separately
            pass
        pnl = _pnl_of_trade(t)
        closed = bool(t.get("closed_at")) and str(t.get("status") or "").upper() != "OPEN"
        win = None
        if closed and pnl is not None:
            win = pnl > 0
        cv = str(t.get("config_version") or (t.get("metadata") or {}).get("config_version") or "")
        rows.append(
            BrRow(
                source="paper",
                trade_id=str(t.get("id") or t.get("trade_id") or ""),
                setup_id=str((t.get("metadata") or {}).get("setup_id") or t.get("setup_id") or ""),
                symbol=str(t.get("symbol") or "").upper(),
                contract_class=_contract_class(str(t.get("symbol") or "")),
                direction=str(t.get("side") or "").upper(),
                session=str(t.get("session") or ""),
                regime=str((t.get("metadata") or {}).get("regime") or ""),
                market_timestamp=str(t.get("opened_at") or t.get("market_timestamp") or ""),
                config_version=cv,
                era=_era(cv),
                tier=str(t.get("setup_tier") or ""),
                qty=int(t.get("qty") or 1),
                entry=float(t.get("entry") or 0),
                stop=float(t.get("stop") or 0),
                target=float(t.get("target") or 0),
                pnl_dollars=pnl,
                realized_r=_r_of_trade(t, pnl),
                win=win,
                exit_reason=str(t.get("exit_reason") or ("OPEN" if not closed else "")),
                mfe_r=_safe_float((t.get("metadata") or {}).get("mfe_r")),
                mae_r=_safe_float((t.get("metadata") or {}).get("mae_r")),
                features=_features_from_trade(t),
            )
        )
    return rows


def load_learning_breakouts(path: Path) -> list[BrRow]:
    if not path.exists():
        return []
    rows: list[BrRow] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        if str(r.get("strategy") or r.get("strategy_name") or "") != "breakout_retest":
            continue
        fr = str(r.get("final_result") or "").upper()
        if fr not in {"WIN", "LOSS"}:
            continue
        win = fr == "WIN"
        rr = _safe_float(r.get("realized_r"))
        feats = dict(r.get("entry_features") or {})
        # flat feature columns on newer schema
        for k in FEATURE_KEYS:
            if k not in feats and r.get(k) is not None:
                feats[k] = r.get(k)
        cv = str(r.get("config_version") or "")
        rows.append(
            BrRow(
                source="learning",
                trade_id=str(r.get("candidate_id") or r.get("setup_id") or ""),
                setup_id=str(r.get("setup_id") or ""),
                symbol=str(r.get("symbol") or "").upper(),
                contract_class=_contract_class(str(r.get("symbol") or "")),
                direction=str(r.get("side") or r.get("direction") or "").upper(),
                session=str(r.get("session") or ""),
                regime=str(r.get("regime") or ""),
                market_timestamp=str(r.get("market_timestamp") or ""),
                config_version=cv,
                era=_era(cv),
                tier=str(r.get("tier") or ""),
                qty=int(r.get("quantity") or 1),
                entry=float(r.get("entry") or 0),
                stop=float(r.get("stop") or 0),
                target=float(r.get("target") or 0),
                pnl_dollars=None,
                realized_r=rr,
                win=win,
                exit_reason=str(r.get("exit_reason") or fr),
                mfe_r=_safe_float(r.get("mfe_r")),
                mae_r=_safe_float(r.get("mae_r")),
                target_before_stop=_safe_bool(r.get("target_before_stop")),
                plus_1r_before_stop=_safe_bool(r.get("plus_1r_before_stop")),
                features=feats,
            )
        )
    return rows


def load_shadow_breakouts(path: Path) -> list[BrRow]:
    if not path.exists():
        return []
    state = json.loads(path.read_text(encoding="utf-8"))
    rows: list[BrRow] = []
    for t in state.get("closed") or []:
        if str(t.get("strategy") or t.get("strategy_name") or "") != "breakout_retest":
            continue
        pnl = _safe_float(t.get("pnl_dollars"))
        rr = _safe_float(t.get("r_achieved") or t.get("pnl_r"))
        win = None
        if rr is not None:
            win = rr > 0
        elif pnl is not None:
            win = pnl > 0
        cv = str(t.get("config_version") or "")
        rows.append(
            BrRow(
                source="shadow",
                trade_id=str(t.get("id") or ""),
                setup_id=str(t.get("setup_id") or ""),
                symbol=str(t.get("symbol") or "").upper(),
                contract_class=_contract_class(str(t.get("symbol") or "")),
                direction=str(t.get("side") or "").upper(),
                session=str(t.get("session") or ""),
                regime=str(t.get("regime") or ""),
                market_timestamp=str(t.get("opened_at") or ""),
                config_version=cv,
                era=_era(cv),
                tier=str(t.get("tier") or ""),
                qty=int(t.get("qty") or 1),
                entry=float(t.get("entry") or 0),
                stop=float(t.get("stop") or 0),
                target=float(t.get("target") or 0),
                pnl_dollars=pnl,
                realized_r=rr,
                win=win,
                exit_reason=str(t.get("exit_reason") or t.get("result") or ""),
                mfe_r=_safe_float(t.get("mfe_r")),
                mae_r=_safe_float(t.get("mae_r")),
                features={},
            )
        )
    return rows


def _safe_float(v: Any) -> float | None:
    try:
        if v is None or v == "":
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def _safe_bool(v: Any) -> bool | None:
    if v is None:
        return None
    if isinstance(v, bool):
        return v
    s = str(v).lower()
    if s in {"1", "true", "yes"}:
        return True
    if s in {"0", "false", "no"}:
        return False
    return None


def cohort_stats(rows: Iterable[BrRow], *, use_r: bool = True) -> dict[str, Any]:
    closed = [r for r in rows if r.win is not None]
    if not closed:
        return {"n": 0, "wins": 0, "losses": 0, "wr": 0.0, "pf": 0.0, "expectancy_r": 0.0, "pnl": 0.0}
    wins = sum(1 for r in closed if r.win)
    losses = len(closed) - wins
    wr = wins / len(closed)
    rs = [float(r.realized_r) for r in closed if r.realized_r is not None]
    st = trade_stats(rs) if rs else {"pf": 0.0, "expectancy_r": 0.0, "max_dd_r": 0.0}
    pnl = sum(float(r.pnl_dollars or 0) for r in closed if r.pnl_dollars is not None)
    # dollar PF if R missing
    gp = sum(float(r.pnl_dollars) for r in closed if r.pnl_dollars and r.pnl_dollars > 0)
    gl = abs(sum(float(r.pnl_dollars) for r in closed if r.pnl_dollars and r.pnl_dollars < 0))
    pf_usd = (gp / gl) if gl > 0 else (float("inf") if gp > 0 else 0.0)
    return {
        "n": len(closed),
        "wins": wins,
        "losses": losses,
        "wr": round(wr, 4),
        "pf": round(float(st.get("pf") or 0), 4) if rs else round(pf_usd if math.isfinite(pf_usd) else 0.0, 4),
        "expectancy_r": round(float(st.get("expectancy_r") or 0), 4) if rs else None,
        "max_dd_r": round(float(st.get("max_dd_r") or 0), 4) if rs else None,
        "pnl": round(pnl, 2),
        "avg_win_usd": round(gp / wins, 2) if wins and gp else 0.0,
        "avg_loss_usd": round(-(gl / losses), 2) if losses and gl else 0.0,
        "n_with_r": len(rs),
    }


def cell_label(n: int) -> str:
    if n >= 100:
        return "VALIDATED"
    if n >= 40:
        return "DEVELOPING"
    if n >= 20:
        return "EARLY"
    return "ANECDOTAL"


def segment_stats(rows: list[BrRow], key_fn) -> list[dict[str, Any]]:
    groups: dict[Any, list[BrRow]] = defaultdict(list)
    for r in rows:
        if r.win is None:
            continue
        groups[key_fn(r)].append(r)
    out = []
    # global prior for shrink
    all_closed = [r for r in rows if r.win is not None]
    g_wr = (sum(1 for r in all_closed if r.win) / len(all_closed)) if all_closed else 0.5
    for key, lst in sorted(groups.items(), key=lambda kv: (-len(kv[1]), str(kv[0]))):
        st = cohort_stats(lst)
        shr = shrink_rate(st["wins"], st["n"], prior_mean=g_wr, prior_strength=20.0)
        out.append(
            {
                "cell": key,
                "evidence": cell_label(st["n"]),
                **st,
                "raw_wr": round(shr.raw, 4),
                "shrunk_wr": round(shr.shrunk, 4),
                "prior_mean": round(g_wr, 4),
            }
        )
    return out


def feature_compare(winners: list[BrRow], losers: list[BrRow]) -> list[dict[str, Any]]:
    """Compare pre-entry features; label sample strength."""
    rows_out: list[dict[str, Any]] = []
    for key in FEATURE_KEYS:
        wv = [_num_or_cat(r.features.get(key)) for r in winners]
        lv = [_num_or_cat(r.features.get(key)) for r in losers]
        wv = [x for x in wv if x is not None]
        lv = [x for x in lv if x is not None]
        if not wv and not lv:
            continue
        # numeric vs categorical
        if all(isinstance(x, (int, float)) for x in wv + lv):
            w_med = _median([float(x) for x in wv]) if wv else None
            l_med = _median([float(x) for x in lv]) if lv else None
            # WR-style: fraction of winners with value >= overall median of all
            rows_out.append(
                {
                    "feature": key,
                    "winner_n": len(wv),
                    "loser_n": len(lv),
                    "winner_median": w_med,
                    "loser_median": l_med,
                    "diff_median": (round(w_med - l_med, 4) if w_med is not None and l_med is not None else None),
                    "evidence": cell_label(min(len(wv), len(lv))),
                }
            )
        else:
            # frequency of most common winner value
            wc = Counter(str(x) for x in wv)
            lc = Counter(str(x) for x in lv)
            keys = sorted(set(wc) | set(lc))
            for cat in keys:
                w_f = wc.get(cat, 0) / len(wv) if wv else 0.0
                l_f = lc.get(cat, 0) / len(lv) if lv else 0.0
                rows_out.append(
                    {
                        "feature": f"{key}={cat}",
                        "winner_n": len(wv),
                        "loser_n": len(lv),
                        "winner_freq": round(w_f, 4),
                        "loser_freq": round(l_f, 4),
                        "diff_freq": round(w_f - l_f, 4),
                        "evidence": cell_label(min(len(wv), len(lv))),
                    }
                )
    return rows_out


def _num_or_cat(v: Any) -> Any:
    if v is None or v == "":
        return None
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(v)
    except (TypeError, ValueError):
        return str(v)


def _median(xs: list[float]) -> float | None:
    if not xs:
        return None
    xs = sorted(xs)
    m = len(xs) // 2
    if len(xs) % 2:
        return round(xs[m], 4)
    return round((xs[m - 1] + xs[m]) / 2, 4)


def hierarchy_shrink(rows: list[BrRow], target: BrRow) -> list[dict[str, Any]]:
    """Shrink hierarchy for one trade's cell path."""
    closed = [r for r in rows if r.win is not None]
    levels = [
        ("strat+sym+sess+regime+dir", lambda r: (r.symbol, r.session, r.regime, r.direction)),
        ("strat+sym+sess+regime", lambda r: (r.symbol, r.session, r.regime)),
        ("strat+sym+sess", lambda r: (r.symbol, r.session)),
        ("strat+sym", lambda r: (r.symbol,)),
        ("strat", lambda r: ()),
    ]
    out = []
    parent_wr = 0.5
    for name, key_fn in reversed(levels):
        # compute from broadest first for prior chain
        pass
    # forward with cascading prior
    prior = 0.5
    for name, key_fn in reversed(levels):
        key = key_fn(target)
        cell = [r for r in closed if key_fn(r) == key]
        if not cell and name != "strat":
            out.append({"level": name, "n": 0, "raw_wr": None, "shrunk_wr": None, "prior": prior})
            continue
        if name == "strat":
            cell = closed
        wins = sum(1 for r in cell if r.win)
        shr = shrink_rate(wins, len(cell), prior_mean=prior, prior_strength=20.0)
        out.append(
            {
                "level": name,
                "key": key,
                "n": len(cell),
                "raw_wr": round(shr.raw, 4),
                "shrunk_wr": round(shr.shrunk, 4),
                "prior": round(prior, 4),
            }
        )
        prior = shr.shrunk
    return list(reversed(out))


def forensic_snapshot(row: BrRow, all_rows: list[BrRow]) -> dict[str, Any]:
    return {
        "trade_id": row.trade_id,
        "symbol": row.symbol,
        "contract_class": row.contract_class,
        "direction": row.direction,
        "session": row.session,
        "regime": row.regime,
        "tier": row.tier,
        "qty": row.qty,
        "pnl_dollars": row.pnl_dollars,
        "realized_r": row.realized_r,
        "exit_reason": row.exit_reason,
        "market_timestamp": row.market_timestamp,
        "config_version": row.config_version,
        "features": row.features,
        "shrink_hierarchy": hierarchy_shrink(all_rows, row),
        "label": "ANECDOTAL TODAY" if row.era == "post_paperfix2" else "HISTORICAL",
    }


def verify_time_stop_from_trades(paper_path: Path) -> list[dict[str, Any]]:
    """Flag possible time-stop clock violations (received vs opened gap)."""
    if not paper_path.exists():
        return []
    state = json.loads(paper_path.read_text(encoding="utf-8"))
    issues = []
    for t in state.get("trades") or []:
        if str(t.get("exit_reason") or "") != "time_stop":
            continue
        opened = str(t.get("opened_at") or "")
        received = str(t.get("received_at") or t.get("ts") or "")
        closed = str(t.get("closed_at") or "")
        hold = t.get("hold_minutes")
        cv = t.get("config_version")
        # Heuristic: hold_minutes >> wall hold from received→closed while stamp is post-fix
        issues.append(
            {
                "id": t.get("id"),
                "symbol": t.get("symbol"),
                "opened_at": opened,
                "received_at": received,
                "closed_at": closed,
                "hold_minutes": hold,
                "config_version": cv,
                "era": _era(str(cv or "")),
                "note": (
                    "pre-fix stamps may show inflated hold_minutes; "
                    "post_paperfix2 should age from received_at"
                ),
            }
        )
    return issues


def build_report(root: Path) -> dict[str, Any]:
    paper_path = root / "data" / "paper_trades.json"
    learn_path = root / "data" / "learning" / "candidates.jsonl"
    shadow_path = root / "data" / "shadow_trades.json"

    paper = load_paper_breakouts(paper_path)
    learning = load_learning_breakouts(learn_path)
    shadow = load_shadow_breakouts(shadow_path)

    # All paper trades for stamp cohorts (not only breakout)
    all_paper_closed = []
    if paper_path.exists():
        state = json.loads(paper_path.read_text(encoding="utf-8"))
        for t in state.get("trades") or []:
            if not t.get("closed_at") or str(t.get("status") or "").upper() == "OPEN":
                continue
            pnl = _pnl_of_trade(t)
            if pnl is None:
                continue
            cv = str(t.get("config_version") or (t.get("metadata") or {}).get("config_version") or "")
            all_paper_closed.append(
                {
                    "strategy": t.get("strategy_name"),
                    "symbol": t.get("symbol"),
                    "session": t.get("session"),
                    "pnl": pnl,
                    "win": pnl > 0,
                    "era": _era(cv),
                    "config_version": cv,
                    "r": _r_of_trade(t, pnl),
                }
            )

    post_all = [t for t in all_paper_closed if t["era"] == "post_paperfix2"]
    pre_all = [t for t in all_paper_closed if t["era"] == "pre_paperfix2"]

    def _usd_cohort(items: list[dict[str, Any]]) -> dict[str, Any]:
        if not items:
            return {"n": 0, "wins": 0, "wr": 0.0, "pf": 0.0, "pnl": 0.0, "expectancy_r": None}
        wins = sum(1 for x in items if x["win"])
        gp = sum(x["pnl"] for x in items if x["pnl"] > 0)
        gl = abs(sum(x["pnl"] for x in items if x["pnl"] < 0))
        rs = [float(x["r"]) for x in items if x.get("r") is not None]
        st = trade_stats(rs) if rs else {}
        return {
            "n": len(items),
            "wins": wins,
            "losses": len(items) - wins,
            "wr": round(wins / len(items), 4),
            "pf": round((gp / gl) if gl > 0 else 0.0, 4),
            "pnl": round(sum(x["pnl"] for x in items), 2),
            "expectancy_r": round(float(st.get("expectancy_r") or 0), 4) if rs else None,
            "max_dd_r": round(float(st.get("max_dd_r") or 0), 4) if rs else None,
        }

    post_br = [r for r in paper if r.era == "post_paperfix2" and r.win is not None]
    pre_br = [r for r in paper if r.era == "pre_paperfix2" and r.win is not None]
    winners = [r for r in post_br if r.win]
    losers = [r for r in post_br if not r.win]

    # Named forensics
    want_ids = {"PAPER-00198", "PAPER-00210", "PAPER-00213", "PAPER-00209"}
    forensics = []
    hist_pool = paper + learning
    for r in paper:
        if r.trade_id in want_ids:
            forensics.append(forensic_snapshot(r, hist_pool))

    open_cl = None
    if paper_path.exists():
        for o in (json.loads(paper_path.read_text(encoding="utf-8")).get("open_positions") or []):
            if str(o.get("symbol")) == "CL" and str(o.get("strategy_name")) == "breakout_retest":
                open_cl = {
                    "trade_id": o.get("trade_id") or o.get("id"),
                    "side": o.get("side"),
                    "qty": o.get("qty"),
                    "entry": o.get("entry"),
                    "stop": o.get("stop"),
                    "target": o.get("target"),
                    "opened_at": o.get("opened_at"),
                    "session": o.get("session"),
                    "risk_dollars": o.get("risk_dollars"),
                    "reward_dollars": o.get("reward_dollars"),
                    "status": "OPEN",
                }

    # Session splits for post breakout
    by_session = segment_stats(post_br, lambda r: r.session or "unknown")
    by_symbol = segment_stats(post_br, lambda r: r.symbol)
    by_contract = segment_stats(post_br, lambda r: r.contract_class)
    # Historical learning segments (resolved WIN/LOSS only)
    learn_by_sym = segment_stats(learning, lambda r: r.symbol)
    learn_by_sess = segment_stats(learning, lambda r: r.session or "unknown")

    feat_cmp = feature_compare(winners, losers)
    # Historical feature compare when n allows
    hist_w = [r for r in learning if r.win]
    hist_l = [r for r in learning if r.win is False]
    hist_feat = feature_compare(hist_w, hist_l)

    # Agent health
    hb = {}
    if paper_path.exists():
        hb = (json.loads(paper_path.read_text(encoding="utf-8")).get("heartbeat") or {})

    payload = {
        "generated_at": _now_iso(),
        "active_stamp_expected": "router_v1_paperfix2",
        "heartbeat_stamp": hb.get("config_version"),
        "research_only": True,
        "no_config_changes": True,
        "paper_agent_health": {
            "scan_state": hb.get("scan_state"),
            "decision": hb.get("decision"),
            "ts": hb.get("ts"),
            "session": hb.get("session"),
        },
        "post_paperfix2_all_strategies": _usd_cohort(post_all),
        "pre_paperfix2_all_strategies": _usd_cohort(pre_all),
        "post_paperfix2_breakout_retest": cohort_stats(post_br),
        "pre_paperfix2_breakout_retest": cohort_stats(pre_br),
        "breakout_by_symbol_post": by_symbol,
        "breakout_by_session_post": by_session,
        "breakout_by_contract_post": by_contract,
        "learning_breakout_by_symbol": learn_by_sym,
        "learning_breakout_by_session": learn_by_sess,
        "learning_breakout_overall": cohort_stats(learning),
        "shadow_breakout_overall": cohort_stats(shadow),
        "feature_compare_post_fix2": feat_cmp,
        "feature_compare_learning_historical": hist_feat,
        "forensics": forensics,
        "open_cl_trade": open_cl,
        "time_stop_audit": verify_time_stop_from_trades(paper_path),
        "counts": {
            "paper_breakout_rows": len(paper),
            "learning_resolved_breakout": len(learning),
            "shadow_closed_breakout": len(shadow),
            "post_br_closed": len(post_br),
        },
        "answers_preview": _answers_preview(post_all, post_br, by_symbol, by_session, open_cl, winners, losers),
    }
    return payload


def _answers_preview(
    post_all, post_br, by_symbol, by_session, open_cl, winners, losers
) -> dict[str, Any]:
    st_all = None
    # rebuild simple
    if post_all:
        wins = sum(1 for x in post_all if x["win"])
        gp = sum(x["pnl"] for x in post_all if x["pnl"] > 0)
        gl = abs(sum(x["pnl"] for x in post_all if x["pnl"] < 0))
        st_all = {
            "n": len(post_all),
            "wr": round(wins / len(post_all), 4),
            "pf": round((gp / gl) if gl else 0, 4),
            "pnl": round(sum(x["pnl"] for x in post_all), 2),
        }
    br = cohort_stats(post_br)
    strongest_sym = by_symbol[0] if by_symbol else None
    strongest_sess = by_session[0] if by_session else None
    shared = []
    if winners:
        # features where all three big winners agree if present
        ids = {w.trade_id for w in winners}
        big = [w for w in winners if w.trade_id in {"PAPER-00198", "PAPER-00210", "PAPER-00213"}]
        if len(big) >= 2:
            for k in FEATURE_KEYS:
                vals = {str(b.features.get(k)) for b in big if b.features.get(k) is not None}
                if len(vals) == 1:
                    shared.append({k: next(iter(vals))})
    return {
        "1_clean_paperfix2_wr": (st_all or {}).get("wr"),
        "2_clean_paperfix2_pf": (st_all or {}).get("pf"),
        "3_clean_expectancy_r": br.get("expectancy_r"),
        "4_breakout_post_wr": br.get("wr"),
        "5_breakout_post_pf": br.get("pf"),
        "6_strongest_symbol_cell": strongest_sym,
        "7_strongest_session_cell": strongest_sess,
        "8_shared_traits_big_winners_anecdotal": shared,
        "10_feature_rows_post": len(feature_compare(winners, losers)),
        "13_open_cl": open_cl,
        "17_verdict": (
            "ANECDOTAL — post_paperfix2 breakout n is small; do not promote. "
            "Collect overnight Asia/London before judging."
        ),
    }


def write_markdown(payload: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    a = payload.get("answers_preview") or {}
    post = payload.get("post_paperfix2_all_strategies") or {}
    br = payload.get("post_paperfix2_breakout_retest") or {}
    lines = [
        f"# Breakout Retest Forward Report",
        "",
        f"**Generated:** {payload.get('generated_at')}",
        f"**Active stamp (expected):** `{payload.get('active_stamp_expected')}`",
        f"**Heartbeat stamp:** `{payload.get('heartbeat_stamp')}`",
        "",
        "> RESEARCH + OBSERVATION ONLY. No paper config / risk / qty / engine changes in this pass.",
        "",
        "## A. Paper agent health",
        "",
        "```json",
        json.dumps(payload.get("paper_agent_health"), indent=2),
        "```",
        "",
        "## B. Post-paperfix2 total performance (all strategies)",
        "",
        _stats_md(post),
        "",
        "## C. Breakout_retest total performance (post-paperfix2 paper fills)",
        "",
        _stats_md(br),
        "",
        f"Pre-paperfix2 breakout (contaminated / prior stamps): {_stats_md(payload.get('pre_paperfix2_breakout_retest') or {})}",
        "",
        "## D. Breakout_retest by symbol (post-paperfix2)",
        "",
        _cells_md(payload.get("breakout_by_symbol_post") or []),
        "",
        "## E. Breakout_retest by session (post-paperfix2)",
        "",
        _cells_md(payload.get("breakout_by_session_post") or []),
        "",
        "## F–H. Forensic snapshots (ES +475 / CL +390 / GC +990)",
        "",
        "Label: **ANECDOTAL TODAY** unless historical support noted in shrink hierarchy.",
        "",
    ]
    for f in payload.get("forensics") or []:
        lines += [
            f"### {f.get('trade_id')} — {f.get('symbol')} {f.get('direction')} PnL={f.get('pnl_dollars')} ({f.get('exit_reason')})",
            "",
            f"- session={f.get('session')} regime={f.get('regime')} tier={f.get('tier')} qty={f.get('qty')} contract={f.get('contract_class')}",
            f"- R≈{f.get('realized_r')} stamp={f.get('config_version')}",
            f"- features: `{json.dumps(f.get('features') or {}, sort_keys=True)}`",
            f"- shrink hierarchy: `{json.dumps(f.get('shrink_hierarchy') or [], sort_keys=True)}`",
            "",
        ]
    lines += [
        "## I. Winner vs loser feature comparison (post-paperfix2 paper)",
        "",
        "_n is small — treat as ANECDOTAL unless evidence column says otherwise._",
        "",
        _feat_md(payload.get("feature_compare_post_fix2") or []),
        "",
        "### Historical learning-store feature compare (resolved WIN/LOSS)",
        "",
        _feat_md(payload.get("feature_compare_learning_historical") or []),
        "",
        "## J–K. High-performance cells + shrunk WR",
        "",
        "### Learning-store by symbol (includes shadow/non-exec resolved)",
        "",
        _cells_md(payload.get("learning_breakout_by_symbol") or []),
        "",
        f"Learning overall: {_stats_md(payload.get('learning_breakout_overall') or {})}",
        "",
        f"Shadow closed breakout: {_stats_md(payload.get('shadow_breakout_overall') or {})}",
        "",
        "## L–M. Asia / London",
        "",
        "Overnight forward sample still collecting. Current post-fix2 session cells:",
        "",
        _cells_md(payload.get("breakout_by_session_post") or []),
        "",
        "## N. Open CL trade",
        "",
        "```json",
        json.dumps(payload.get("open_cl_trade"), indent=2),
        "```",
        "",
        "## O. Software / runtime issues",
        "",
        "No strategy changes applied this pass. Monitor heartbeat / supervisor separately.",
        "",
        "## P. Full-size family preference",
        "",
        "Policy unchanged (`prefer_full_size_in_family: true`). Contract-class cells (post paper):",
        "",
        _cells_md(payload.get("breakout_by_contract_post") or []),
        "",
        "## Q. Time-stop fix verification",
        "",
        "Recent time_stop exits (audit; inflated hold_minutes on pre-fix stamps expected):",
        "",
        "```json",
        json.dumps(payload.get("time_stop_audit") or [], indent=2)[:8000],
        "```",
        "",
        "## R. Learning-store counts",
        "",
        "```json",
        json.dumps(payload.get("counts"), indent=2),
        "```",
        "",
        "## S. Discovery patterns worth further research (NOT deploy)",
        "",
        "1. Post-fix2 target hits clustered on full-size ES/CL/GC — **dollar size ≠ R-edge**; compare R/WR by contract_class.",
        "2. Many MNQ breakout stops same day — check session/regime/MTF vs winners before any filter.",
        "3. Available entry_features are compact (MTF/VWAP/EMA flags). Deeper structure (level type, retest depth) needs richer logging — do not invent fields.",
        "4. Do not promote breakout_retest from today's anecdotal n.",
        "",
        "## Direct answers (preview — refresh after overnight)",
        "",
        "```json",
        json.dumps(a, indent=2),
        "```",
        "",
        "## Policy lock",
        "",
        "- Keep `router_v1_paperfix2` overnight.",
        "- No auto-tune from Asia/London tiny samples.",
        "- Re-run: `python scripts/run_breakout_retest_forward_report.py`",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def _stats_md(st: dict[str, Any]) -> str:
    if not st or not st.get("n"):
        return "_n=0 — no closed trades in this cohort yet._"
    return (
        f"- n={st.get('n')} wins={st.get('wins')} losses={st.get('losses')} "
        f"WR={st.get('wr')} PF={st.get('pf')} E[R]={st.get('expectancy_r')} "
        f"PnL=${st.get('pnl')} maxDD_R={st.get('max_dd_r')} "
        f"(evidence={cell_label(int(st.get('n') or 0))})"
    )


def _cells_md(cells: list[dict[str, Any]]) -> str:
    if not cells:
        return "_none_"
    lines = [
        "| Cell | Evidence | n | WR | shrunk WR | PF | E[R] | PnL |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for c in cells:
        lines.append(
            f"| `{c.get('cell')}` | {c.get('evidence')} | {c.get('n')} | {c.get('wr')} | "
            f"{c.get('shrunk_wr')} | {c.get('pf')} | {c.get('expectancy_r')} | {c.get('pnl')} |"
        )
    return "\n".join(lines)


def _feat_md(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "_no comparable features_"
    lines = [
        "| Feature | Evidence | winner_n | loser_n | stats |",
        "|---|---|---:|---:|---|",
    ]
    for r in rows[:80]:
        if "diff_median" in r:
            stats = f"w_med={r.get('winner_median')} l_med={r.get('loser_median')} diff={r.get('diff_median')}"
        else:
            stats = f"w_freq={r.get('winner_freq')} l_freq={r.get('loser_freq')} diff={r.get('diff_freq')}"
        lines.append(
            f"| `{r.get('feature')}` | {r.get('evidence')} | {r.get('winner_n')} | {r.get('loser_n')} | {stats} |"
        )
    return "\n".join(lines)


def export_dataset(rows: list[BrRow], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(asdict(r), default=str) + "\n")
