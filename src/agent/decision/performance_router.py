"""Empirical StrategyPerformanceRouter — additive ranking evidence.

Does NOT invent probabilities from the global score.
Does NOT bypass hard risk / data / duplicate gates.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable, Optional


LEVEL_SPECS: list[tuple[str, tuple[str, ...]]] = [
    ("exact", ("strategy", "symbol", "session", "regime", "direction")),
    ("strategy_symbol_session_regime", ("strategy", "symbol", "session", "regime")),
    ("strategy_symbol_session", ("strategy", "symbol", "session")),
    ("strategy_symbol", ("strategy", "symbol")),
    ("strategy_global", ("strategy",)),
]


@dataclass
class RouterEvidence:
    sample_count: int = 0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    expectancy_r: float = 0.0
    avg_r: float = 0.0
    max_drawdown_r: float = 0.0
    recent_forward_performance: float = 0.0
    confidence_status: str = "insufficient"  # insufficient | adequate | preferred
    evidence_level: str = "none"
    dimensions_used: list[str] = field(default_factory=list)
    source_trade_count_total: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def usable(self) -> bool:
        return self.confidence_status in {"adequate", "preferred"} and self.sample_count > 0


def _norm_session(raw: Any) -> str:
    s = str(raw or "unknown").strip().lower().split()[0]
    aliases = {
        "ny_open": "ny_open",
        "nyopen": "ny_open",
        "newyork": "ny",
        "new_york": "ny",
        "globex": "globex_open",
        "other": "unknown",
        "": "unknown",
    }
    return aliases.get(s, s)


def _norm_regime(raw: Any) -> str:
    r = str(raw or "").strip().upper()
    if not r or r in {"NONE", "NULL", "NAN"}:
        return "UNKNOWN"
    return r


def _norm_direction(raw: Any) -> str:
    d = str(raw or "").strip().upper()
    if d in {"BUY", "LONG"}:
        return "LONG"
    if d in {"SELL", "SHORT"}:
        return "SHORT"
    return d or "UNKNOWN"


def _r_from_trade(t: dict[str, Any]) -> Optional[float]:
    if t.get("r_achieved") is not None:
        try:
            return float(t["r_achieved"])
        except (TypeError, ValueError):
            pass
    try:
        entry = float(t["entry"])
        stop = float(t["stop"])
        exit_px = t.get("exit")
        if exit_px is None:
            return None
        exit_px = float(exit_px)
        risk = abs(entry - stop)
        if risk <= 1e-12:
            return None
        side = _norm_direction(t.get("side") or t.get("direction"))
        if side == "LONG":
            return (exit_px - entry) / risk
        if side == "SHORT":
            return (entry - exit_px) / risk
    except (TypeError, ValueError, KeyError):
        return None
    return None


def _trade_dims(t: dict[str, Any]) -> dict[str, str]:
    strat = str(t.get("strategy_name") or t.get("strategy") or "unknown")
    return {
        "strategy": strat,
        "symbol": str(t.get("symbol") or "").upper(),
        "session": _norm_session(t.get("session")),
        "regime": _norm_regime(t.get("regime")),
        "direction": _norm_direction(t.get("side") or t.get("direction")),
    }


def _cell_stats(rs: list[float], *, recent_n: int = 20) -> dict[str, float]:
    if not rs:
        return {
            "sample_count": 0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "expectancy_r": 0.0,
            "avg_r": 0.0,
            "max_drawdown_r": 0.0,
            "recent_forward_performance": 0.0,
        }
    wins = [r for r in rs if r > 0]
    losses = [r for r in rs if r < 0]
    gw = sum(wins)
    gl = abs(sum(losses))
    eq = 0.0
    peak = 0.0
    max_dd = 0.0
    for r in rs:
        eq += r
        peak = max(peak, eq)
        max_dd = min(max_dd, eq - peak)
    recent = rs[-recent_n:]
    return {
        "sample_count": float(len(rs)),
        "win_rate": len(wins) / max(len(rs), 1),
        "profit_factor": (gw / gl) if gl > 1e-12 else (999.0 if gw > 0 else 0.0),
        "expectancy_r": sum(rs) / len(rs),
        "avg_r": sum(rs) / len(rs),
        "max_drawdown_r": float(max_dd),
        "recent_forward_performance": sum(recent) / len(recent),
    }


def _confidence(n: int, *, min_n: int, preferred_n: int) -> str:
    if n >= preferred_n:
        return "preferred"
    if n >= min_n:
        return "adequate"
    return "insufficient"


class StrategyPerformanceRouter:
    """Lookup historical / forward performance cells with hierarchical fallback."""

    def __init__(
        self,
        *,
        trade_paths: Iterable[str | Path] | None = None,
        shadow_path: str | Path | None = "data/shadow_trades.json",
        include_shadow: bool = True,
        min_sample: int = 30,
        preferred_sample: int = 50,
        recent_n: int = 20,
    ):
        self.trade_paths = [Path(p) for p in (trade_paths or ["data/paper_trades.json"])]
        self.shadow_path = Path(shadow_path) if shadow_path else None
        self.include_shadow = include_shadow
        self.min_sample = int(min_sample)
        self.preferred_sample = int(preferred_sample)
        self.recent_n = int(recent_n)
        self._cells: dict[tuple[str, ...], list[float]] = {}
        self._loaded_at = 0.0
        self._source_mtime = 0.0
        self._source_trade_count = 0
        self.reload(force=True)

    def _paths_mtime(self) -> float:
        mt = 0.0
        for p in self.trade_paths:
            if p.exists():
                mt = max(mt, p.stat().st_mtime)
        if self.include_shadow and self.shadow_path and self.shadow_path.exists():
            mt = max(mt, self.shadow_path.stat().st_mtime)
        return mt

    def _iter_trades(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for p in self.trade_paths:
            if not p.exists():
                continue
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                continue
            closed = data.get("closed_trades") or data.get("closed") or []
            if isinstance(closed, list):
                rows.extend([t for t in closed if isinstance(t, dict)])
        if self.include_shadow and self.shadow_path and self.shadow_path.exists():
            try:
                data = json.loads(self.shadow_path.read_text(encoding="utf-8"))
                for t in data.get("closed") or []:
                    if isinstance(t, dict):
                        t = dict(t)
                        t.setdefault("execution_mode", "SHADOW")
                        rows.append(t)
            except Exception:
                pass
        return rows

    def reload(self, *, force: bool = False) -> None:
        mt = self._paths_mtime()
        if not force and mt <= self._source_mtime and self._cells:
            return
        cells: dict[tuple[str, ...], list[float]] = {}
        n_src = 0
        for t in self._iter_trades():
            if str(t.get("source", "")) == "demo":
                continue
            if str(t.get("exit_reason", "")) in {"universe_prune", "corr_conflict_prune"}:
                continue
            r = _r_from_trade(t)
            if r is None:
                continue
            dims = _trade_dims(t)
            n_src += 1
            # Store under every hierarchical key that is fully supported
            for _level, keys in LEVEL_SPECS:
                if "regime" in keys and dims["regime"] == "UNKNOWN":
                    continue
                if "session" in keys and dims["session"] in {"", "unknown"}:
                    continue
                if "direction" in keys and dims["direction"] == "UNKNOWN":
                    continue
                if "symbol" in keys and not dims["symbol"]:
                    continue
                cell_key = tuple(dims[k] for k in keys)
                # Prefix with level name length via full key tuple including field names
                full = ( ",".join(keys),) + cell_key
                cells.setdefault(full, []).append(float(r))
        self._cells = cells
        self._source_mtime = mt
        self._source_trade_count = n_src
        self._loaded_at = time.time()

    def lookup(
        self,
        *,
        strategy: str,
        symbol: str,
        session: str | None,
        regime: str | None,
        direction: str,
    ) -> RouterEvidence:
        self.reload()
        dims = {
            "strategy": str(strategy or "unknown"),
            "symbol": str(symbol or "").upper(),
            "session": _norm_session(session),
            "regime": _norm_regime(regime),
            "direction": _norm_direction(direction),
        }
        for level, keys in LEVEL_SPECS:
            if "regime" in keys and dims["regime"] == "UNKNOWN":
                continue
            if "session" in keys and dims["session"] in {"", "unknown"}:
                continue
            if "direction" in keys and dims["direction"] == "UNKNOWN":
                continue
            if "symbol" in keys and not dims["symbol"]:
                continue
            full = (",".join(keys),) + tuple(dims[k] for k in keys)
            rs = self._cells.get(full) or []
            n = len(rs)
            if n < self.min_sample:
                continue
            st = _cell_stats(rs, recent_n=self.recent_n)
            status = _confidence(n, min_n=self.min_sample, preferred_n=self.preferred_sample)
            return RouterEvidence(
                sample_count=int(st["sample_count"]),
                win_rate=float(st["win_rate"]),
                profit_factor=float(st["profit_factor"]),
                expectancy_r=float(st["expectancy_r"]),
                avg_r=float(st["avg_r"]),
                max_drawdown_r=float(st["max_drawdown_r"]),
                recent_forward_performance=float(st["recent_forward_performance"]),
                confidence_status=status,
                evidence_level=level,
                dimensions_used=list(keys),
                source_trade_count_total=self._source_trade_count,
            )
        # Best available even if insufficient — for diagnostics only
        for level, keys in LEVEL_SPECS:
            if "regime" in keys and dims["regime"] == "UNKNOWN":
                continue
            full = (",".join(keys),) + tuple(dims[k] for k in keys)
            rs = self._cells.get(full) or []
            if not rs:
                continue
            st = _cell_stats(rs, recent_n=self.recent_n)
            return RouterEvidence(
                sample_count=int(st["sample_count"]),
                win_rate=float(st["win_rate"]),
                profit_factor=float(st["profit_factor"]),
                expectancy_r=float(st["expectancy_r"]),
                avg_r=float(st["avg_r"]),
                max_drawdown_r=float(st["max_drawdown_r"]),
                recent_forward_performance=float(st["recent_forward_performance"]),
                confidence_status="insufficient",
                evidence_level=level,
                dimensions_used=list(keys),
                source_trade_count_total=self._source_trade_count,
            )
        return RouterEvidence(source_trade_count_total=self._source_trade_count)

    def attach(self, setup: Any, cfg: dict[str, Any] | None = None) -> RouterEvidence:
        meta = dict(getattr(setup, "metadata", None) or {})
        ev = self.lookup(
            strategy=str(getattr(setup, "strategy_name", "")),
            symbol=str(getattr(setup, "symbol", "")),
            session=getattr(setup, "session", None) or meta.get("session"),
            regime=meta.get("regime"),
            direction=str(getattr(setup, "direction", "") or getattr(setup, "side", "")),
        )
        meta["router_evidence"] = ev.to_dict()
        meta["global_score_secondary"] = True
        setup.metadata = meta
        return ev


def router_from_cfg(cfg: dict[str, Any]) -> StrategyPerformanceRouter:
    rcfg = cfg.get("performance_router") or {}
    paths = list(rcfg.get("trade_paths") or ["data/paper_trades.json"])
    return StrategyPerformanceRouter(
        trade_paths=paths,
        shadow_path=rcfg.get("shadow_path")
        or (cfg.get("shadow") or {}).get("path")
        or "data/shadow_trades.json",
        include_shadow=bool(rcfg.get("include_shadow", True)),
        min_sample=int(rcfg.get("min_sample", 30)),
        preferred_sample=int(rcfg.get("preferred_sample", 50)),
        recent_n=int(rcfg.get("recent_n", 20)),
    )


def empirical_rank_tuple(setup: Any) -> tuple:
    """Primary empirical sort key (higher is better). Tier handled separately."""
    meta = getattr(setup, "metadata", None) or {}
    ev = meta.get("router_evidence") or {}
    usable = str(ev.get("confidence_status") or "") in {"adequate", "preferred"}
    n = int(ev.get("sample_count") or 0)
    e = float(ev.get("expectancy_r") or 0.0)
    pf = float(ev.get("profit_factor") or 0.0)
    wr = float(ev.get("win_rate") or 0.0)
    dd = abs(float(ev.get("max_drawdown_r") or 0.0))
    g = float(meta.get("global_score") or getattr(setup, "confidence_score", 0) or 0)
    er = float(getattr(setup, "expected_r", 0.0) or 0.0)
    # Prefer positive expectancy cells; global score is last among empirics
    return (
        1 if usable else 0,
        e,
        pf if pf < 50 else 50.0,
        n,
        wr,
        -dd,
        g,
        er,
    )
