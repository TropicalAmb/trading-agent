"""Router v2 — additive evolution of StrategyPerformanceRouter.

Keeps hierarchical fallback + hard-risk separation.
Adds: shrunk WR, optional calibrated model probability, CI, evidence source.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Any, Optional

from agent.decision.performance_router import (
    LEVEL_SPECS,
    RouterEvidence,
    StrategyPerformanceRouter,
    _cell_stats,
    _confidence,
    _norm_direction,
    _norm_regime,
    _norm_session,
    empirical_rank_tuple,
    router_from_cfg,
)
from agent.learning.shrink import shrink_expectancy, shrink_rate


@dataclass
class RouterEvidenceV2(RouterEvidence):
    raw_win_rate: float = 0.0
    shrunk_win_rate: float = 0.0
    model_probability: float | None = None
    wr_ci95: list[float] = field(default_factory=list)
    evidence_source: str = "empirical"
    model_version: str = ""
    model_calibrated: bool = False
    cell_health: str = "ACTIVE"  # ACTIVE | DOWNWEIGHTED | SHADOW_ONLY | PAUSED_FOR_REVIEW

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _wilson_ci(wins: int, n: int, z: float = 1.96) -> list[float]:
    if n <= 0:
        return [0.0, 1.0]
    p = wins / n
    denom = 1 + z**2 / n
    centre = p + z**2 / (2 * n)
    margin = z * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2))
    lo = max(0.0, (centre - margin) / denom)
    hi = min(1.0, (centre + margin) / denom)
    return [lo, hi]


class StrategyPerformanceRouterV2(StrategyPerformanceRouter):
    """Extends v1 cells with shrinkage + optional AdaptiveTradeQualityModel."""

    def __init__(self, *args, quality_model=None, prior_strength: float = 20.0, **kwargs):
        super().__init__(*args, **kwargs)
        self.quality_model = quality_model
        self.prior_strength = float(prior_strength)
        self._global_wr = 0.5
        self._global_e = 0.0
        self._recompute_priors()

    def _recompute_priors(self) -> None:
        all_r: list[float] = []
        for rs in self._cells.values():
            all_r.extend(rs)
        if all_r:
            wins = sum(1 for r in all_r if r > 0)
            self._global_wr = wins / len(all_r)
            self._global_e = sum(all_r) / len(all_r)

    def reload(self, *, force: bool = False) -> None:
        super().reload(force=force)
        self._recompute_priors()

    def lookup_v2(
        self,
        *,
        strategy: str,
        symbol: str,
        session: str | None,
        regime: str | None,
        direction: str,
        feature_row: dict[str, Any] | None = None,
        cell_health: str = "ACTIVE",
    ) -> RouterEvidenceV2:
        self.reload()
        dims = {
            "strategy": str(strategy or "unknown"),
            "symbol": str(symbol or "").upper(),
            "session": _norm_session(session),
            "regime": _norm_regime(regime),
            "direction": _norm_direction(direction),
        }
        base = RouterEvidenceV2(source_trade_count_total=self._source_trade_count, cell_health=cell_health)
        chosen_rs: list[float] = []
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
            if len(rs) < self.min_sample and level != "strategy_global":
                # still allow smaller cells for shrunk diagnostics, but not for usable rank
                if len(rs) < 5:
                    continue
            if not rs:
                continue
            chosen_rs = rs
            st = _cell_stats(rs, recent_n=self.recent_n)
            n = int(st["sample_count"])
            wins = int(round(st["win_rate"] * n))
            shr = shrink_rate(wins, n, prior_mean=self._global_wr, prior_strength=self.prior_strength)
            e_shrunk = shrink_expectancy(rs, prior_mean=self._global_e, prior_strength=self.prior_strength)
            status = _confidence(n, min_n=self.min_sample, preferred_n=self.preferred_sample)
            # Recency blend: 70% long-term shrunk, 30% recent when n_recent>=10
            recent = float(st["recent_forward_performance"])
            long_w, recent_w = 0.75, 0.25
            blended_e = long_w * e_shrunk + recent_w * recent if n >= 10 else e_shrunk
            base = RouterEvidenceV2(
                sample_count=n,
                win_rate=shr.shrunk,
                raw_win_rate=shr.raw,
                shrunk_win_rate=shr.shrunk,
                profit_factor=float(st["profit_factor"]),
                expectancy_r=float(blended_e),
                avg_r=float(st["avg_r"]),
                max_drawdown_r=float(st["max_drawdown_r"]),
                recent_forward_performance=recent,
                confidence_status=status if n >= self.min_sample else "insufficient",
                evidence_level=level,
                dimensions_used=list(keys),
                source_trade_count_total=self._source_trade_count,
                wr_ci95=_wilson_ci(wins, n),
                evidence_source="empirical_shrunk",
                cell_health=cell_health,
            )
            if n >= self.min_sample:
                break

        # Model probability (optional; never invents from global score)
        if self.quality_model is not None and feature_row is not None:
            pred = self.quality_model.predict_row(feature_row, which="champion")
            base.model_probability = pred.predicted_win_probability
            base.model_version = pred.model_version
            base.model_calibrated = bool(pred.calibrated)
            if pred.calibrated and pred.prediction_confidence in {"medium", "high"}:
                base.evidence_source = "empirical_shrunk+calibrated_model"
        return base

    def attach_v2(self, setup: Any, cfg: dict[str, Any] | None = None) -> RouterEvidenceV2:
        meta = dict(getattr(setup, "metadata", None) or {})
        health = str(meta.get("cell_health") or "ACTIVE")
        feat = dict(meta.get("entry_features") or {})
        feat.setdefault("strategy", getattr(setup, "strategy_name", ""))
        feat.setdefault("symbol", getattr(setup, "symbol", ""))
        feat.setdefault("direction", getattr(setup, "direction", ""))
        feat.setdefault("session", getattr(setup, "session", None))
        feat.setdefault("regime", meta.get("regime"))
        feat.setdefault("global_score", meta.get("global_score"))
        feat.setdefault("local_score", meta.get("strategy_local_score"))
        feat.setdefault("tier_rank", {"A+": 4, "A": 3, "B": 2, "C": 1}.get(str(getattr(setup, "setup_tier", "")), 0))
        ev = self.lookup_v2(
            strategy=str(getattr(setup, "strategy_name", "")),
            symbol=str(getattr(setup, "symbol", "")),
            session=getattr(setup, "session", None),
            regime=meta.get("regime"),
            direction=str(getattr(setup, "direction", "")),
            feature_row=feat,
            cell_health=health,
        )
        meta["router_evidence"] = ev.to_dict()
        meta["router_version"] = "v2"
        meta["global_score_secondary"] = True
        setup.metadata = meta
        return ev


def empirical_rank_tuple_v2(setup: Any, *, profile: str = "balanced") -> tuple:
    """Ranking key for router_v2. high_confidence favors calibrated probability."""
    meta = getattr(setup, "metadata", None) or {}
    ev = meta.get("router_evidence") or {}
    usable = str(ev.get("confidence_status") or "") in {"adequate", "preferred"}
    n = int(ev.get("sample_count") or 0)
    e = float(ev.get("expectancy_r") or 0.0)
    pf = float(ev.get("profit_factor") or 0.0)
    wr = float(ev.get("shrunk_win_rate") or ev.get("win_rate") or 0.0)
    dd = abs(float(ev.get("max_drawdown_r") or 0.0))
    g = float(meta.get("global_score") or getattr(setup, "confidence_score", 0) or 0)
    er = float(getattr(setup, "expected_r", 0.0) or 0.0)
    health = str(ev.get("cell_health") or meta.get("cell_health") or "ACTIVE")
    health_pen = {"ACTIVE": 0, "DOWNWEIGHTED": -1, "SHADOW_ONLY": -5, "PAUSED_FOR_REVIEW": -9}.get(health, 0)
    mp = ev.get("model_probability")
    calibrated = bool(ev.get("model_calibrated"))
    p = float(mp) if mp is not None and calibrated else wr
    qp = meta.get("quality_predictions") or {}
    p_tgt = float(qp.get("p_win") or qp.get("p_target_before_stop") or p)
    p_1r = float(qp.get("p_1r") or qp.get("p_plus_1r_before_stop") or p)
    if str(profile).lower() == "high_confidence":
        # Spec: P(target) → P(1R) → shrunk WR → E → PF → n → DD → global
        return (
            health_pen,
            1 if usable else 0,
            p_tgt,
            p_1r,
            wr,
            e,
            pf if pf < 50 else 50.0,
            n,
            -dd,
            g,
            er,
        )
    # balanced: expectancy-first (v1 spirit) with shrunk/model as support
    return (
        health_pen,
        1 if usable else 0,
        e,
        pf if pf < 50 else 50.0,
        p,
        n,
        wr,
        -dd,
        g,
        er,
    )


def router_v2_from_cfg(cfg: dict[str, Any], *, quality_model=None) -> StrategyPerformanceRouterV2:
    rcfg = cfg.get("performance_router") or {}
    v2 = cfg.get("performance_router_v2") or {}
    paths = list(rcfg.get("trade_paths") or ["data/paper_trades.json"])
    return StrategyPerformanceRouterV2(
        trade_paths=paths,
        shadow_path=v2.get("shadow_path")
        or rcfg.get("shadow_path")
        or (cfg.get("shadow") or {}).get("path")
        or "data/shadow_trades.json",
        include_shadow=bool(rcfg.get("include_shadow", True)),
        min_sample=int(v2.get("min_sample") or rcfg.get("min_sample", 30)),
        preferred_sample=int(v2.get("preferred_sample") or rcfg.get("preferred_sample", 50)),
        recent_n=int(rcfg.get("recent_n", 20)),
        quality_model=quality_model,
        prior_strength=float(v2.get("prior_strength", 20.0)),
    )
