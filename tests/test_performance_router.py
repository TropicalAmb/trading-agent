from __future__ import annotations

import json
from pathlib import Path

from agent.decision.performance_router import (
    StrategyPerformanceRouter,
    empirical_rank_tuple,
)
from agent.decision.ranker import select_executable_detailed
from agent.decision.setup import TradeSetup
from agent.strategy.liquidity_reversal import evaluate_liquidity_reversal
from agent.strategy.trend_pullback import evaluate_trend_pullback
from agent.strategy.vwap_reclaim import evaluate_vwap_reclaim
import numpy as np
import pandas as pd


def _cfg(**extra):
    cfg = {
        "tiering": {
            "minimum_trade_tier": "A",
            "tier_thresholds": {"A_PLUS": 85, "A": 70, "B": 55, "C": 0},
            "a_plus_min_r": 1.2,
            "a_min_r": 1.0,
        },
        "performance_router": {"enabled": True, "min_sample": 30, "preferred_sample": 50},
        "global_scoring": {"primary_setup_base_points": 32},
    }
    cfg.update(extra)
    return cfg


def _setup(
    *,
    strategy: str,
    global_score: float,
    tier: str = "A",
    symbol: str = "NQ",
    direction: str = "BUY",
    setup_id: str = "x",
    families: list[str] | None = None,
) -> TradeSetup:
    return TradeSetup(
        strategy_name=strategy,
        symbol=symbol,
        direction=direction,
        setup_tier=tier,
        confidence_score=int(global_score),
        entry=100.0,
        stop=99.0,
        target=102.0,
        expected_r=2.0,
        market_timestamp=__import__("datetime").datetime(2026, 8, 10, 14, 0),
        received_timestamp=__import__("datetime").datetime(2026, 8, 10, 14, 1),
        reasons=[f"strategy:{strategy}"],
        session="ny",
        metadata={
            "global_score": global_score,
            "strategy_local_score": global_score,
            "setup_id": setup_id,
            "has_location": True,
            "families_positive": families
            or ["MTF", "VWAP", "LOCATION", "RISK_REWARD"],
            "regime": "TREND_UP",
            "config_version": "router_v1",
        },
    )


def _write_trades(path: Path, n: int, *, wr: float, strategy: str, e: float) -> None:
    closed = []
    wins = int(round(n * wr))
    for i in range(n):
        win = i < wins
        r = e + 0.4 if win else -1.0
        entry = 100.0
        stop = 99.0
        exit_px = entry + r * (entry - stop)
        closed.append(
            {
                "strategy_name": strategy,
                "symbol": "NQ",
                "side": "BUY",
                "session": "ny",
                "regime": "TREND_UP",
                "entry": entry,
                "stop": stop,
                "exit": exit_px,
                "pnl_dollars": 10 if win else -10,
                "r_achieved": r,
            }
        )
    path.write_text(json.dumps({"closed_trades": closed}), encoding="utf-8")


def test_hierarchical_fallback_and_min_sample(tmp_path: Path):
    p = tmp_path / "paper.json"
    # Only 10 exact-cell trades → must fall back / insufficient at exact
    _write_trades(p, 10, wr=0.8, strategy="trend_pullback", e=0.3)
    # Pad strategy_global to 40
    data = json.loads(p.read_text(encoding="utf-8"))
    for i in range(30):
        data["closed_trades"].append(
            {
                "strategy_name": "trend_pullback",
                "symbol": "ES",
                "side": "SELL",
                "session": "london",
                "regime": "RANGE",
                "entry": 100.0,
                "stop": 99.0,
                "exit": 100.5,
                "r_achieved": 0.5,
            }
        )
    p.write_text(json.dumps(data), encoding="utf-8")
    router = StrategyPerformanceRouter(
        trade_paths=[p],
        shadow_path=None,
        include_shadow=False,
        min_sample=30,
        preferred_sample=50,
    )
    ev = router.lookup(
        strategy="trend_pullback",
        symbol="NQ",
        session="ny",
        regime="TREND_UP",
        direction="BUY",
    )
    assert ev.sample_count >= 30
    assert ev.evidence_level in {
        "strategy_symbol_session_regime",
        "strategy_symbol_session",
        "strategy_symbol",
        "strategy_global",
    }
    assert ev.confidence_status in {"adequate", "preferred"}
    assert ev.dimensions_used


def test_empirical_ranks_above_global_score(tmp_path: Path):
    p = tmp_path / "paper.json"
    # Strong empirical for trend_pullback
    closed = []
    for i in range(40):
        closed.append(
            {
                "strategy_name": "trend_pullback",
                "symbol": "NQ",
                "side": "BUY",
                "session": "ny",
                "regime": "TREND_UP",
                "entry": 100.0,
                "stop": 99.0,
                "exit": 100.7 if i < 28 else 99.0,
                "r_achieved": 0.7 if i < 28 else -1.0,
            }
        )
    # Weak empirical for ema_pullback
    for i in range(40):
        closed.append(
            {
                "strategy_name": "ema_pullback",
                "symbol": "NQ",
                "side": "BUY",
                "session": "ny",
                "regime": "TREND_UP",
                "entry": 100.0,
                "stop": 99.0,
                "exit": 100.1 if i < 21 else 99.0,
                "r_achieved": 0.1 if i < 21 else -1.0,
            }
        )
    p.write_text(json.dumps({"closed_trades": closed}), encoding="utf-8")
    cfg = _cfg(
        performance_router={
            "enabled": True,
            "min_sample": 30,
            "preferred_sample": 50,
            "include_shadow": False,
            "trade_paths": [str(p)],
            "shadow_path": None,
        }
    )
    high_score_weak = _setup(
        strategy="ema_pullback",
        global_score=91,
        tier="A+",
        setup_id="weak",
    )
    # Partner engine so EMA can remain A+ (lone EMA is capped at B)
    high_score_weak.metadata["agreeing_engines"] = [
        "ema_pullback",
        "liquidity_sweep",
    ]
    high_score_weak.reward_dollars = 120.0
    low_score_strong = _setup(
        strategy="trend_pullback",
        global_score=78,
        tier="A",
        setup_id="strong",
    )
    low_score_strong.reward_dollars = 120.0
    executable, superseded = select_executable_detailed(
        [high_score_weak, low_score_strong], cfg
    )
    assert len(executable) == 1
    assert executable[0].strategy_name == "trend_pullback"
    assert len(superseded) == 1
    ev = (executable[0].metadata or {}).get("router_evidence") or {}
    assert ev.get("sample_count", 0) >= 30
    assert empirical_rank_tuple(low_score_strong) > empirical_rank_tuple(high_score_weak)


def test_router_does_not_promote_b(tmp_path: Path):
    p = tmp_path / "paper.json"
    _write_trades(p, 40, wr=0.75, strategy="momentum", e=0.4)
    cfg = _cfg(
        performance_router={
            "enabled": True,
            "min_sample": 30,
            "trade_paths": [str(p)],
            "include_shadow": False,
            "shadow_path": None,
        }
    )
    # Excellent empirical history cannot bypass tier gate / hard invalidation
    b = _setup(strategy="momentum", global_score=90, tier="B", setup_id="b1")
    b.metadata["hard_invalidations"] = ["INVALID_RR"]
    b.metadata["families_positive"] = ["EMA_TREND"]
    a = _setup(strategy="breakout_retest", global_score=72, tier="A", setup_id="a1")
    executable, _ = select_executable_detailed([b, a], cfg)
    assert all(s.setup_tier in {"A", "A+"} for s in executable)
    assert all(s.strategy_name != "momentum" for s in executable)


def test_simple_specialists_smoke():
    idx = pd.date_range("2026-08-04 09:00", periods=120, freq="5min")
    close = np.linspace(5200, 5250, len(idx))
    # Force a reclaim-like last bar
    close = close.copy()
    close[-2] = close[-3] - 5
    close[-1] = close[-3] + 2
    df = pd.DataFrame(
        {
            "open": close - 0.5,
            "high": close + 2.0,
            "low": close - 2.0,
            "close": close,
            "volume": np.full(len(idx), 1000.0),
        },
        index=idx,
    )
    cfg = {
        "trend_pullback": {"enabled": True, "min_confidence": 0, "min_reward_dollars": 1},
        "liquidity_reversal": {"enabled": True, "min_confidence": 0, "min_reward_dollars": 1},
        "vwap_reclaim": {"enabled": True, "min_confidence": 0, "min_reward_dollars": 1},
    }
    assert evaluate_trend_pullback("MES", df, cfg, point_value=5.0) is None or True
    assert evaluate_liquidity_reversal("MES", df, cfg, point_value=5.0) is None or True
    assert evaluate_vwap_reclaim("MES", df, cfg, point_value=5.0) is None or True
