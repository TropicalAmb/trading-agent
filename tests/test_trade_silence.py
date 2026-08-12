from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from agent.ops.trade_silence import (
    BLOCKER_CODE_BUG,
    BLOCKER_PIPELINE_DROUGHT,
    BLOCKER_RESEARCH_SUPERSEDE,
    diagnose_trade_silence,
    run_trade_silence_watch,
)


def _cfg(**extra):
    cfg = {
        "schedule": {
            "timezone": "America/New_York",
            "maintenance_start": "17:00",
            "maintenance_end": "18:00",
            "weekend_open": "18:00",
            "weekend_close": "17:00",
        },
        "observability": {"scheduler_stuck_seconds": 150},
        "shadow": {"path": "data/shadow_trades.json"},
        "trade_silence_watch": {
            "enabled": True,
            "warn_after_minutes": 90,
            "alert_after_minutes": 90,
            "lookback_decisions": 100,
            "path": "data/trade_silence_status.json",
            "log_path": "data/trade_silence.log",
            "decisions_path": "data/execution_decisions.jsonl",
            "auto_restart_on_bug_patterns": True,
            "bug_window_minutes": 60,
        },
        "trade_drought_policy": {
            "enabled": True,
            "max_quiet_minutes": 90,
            "on_drought": "diagnose_and_escalate",
        },
        "execution_quality": {
            "enabled": True,
            "min_expected_r": 1.6,
            "min_reward_dollars": 150,
            "reject_poor_cascade_location": True,
            "require_non_mixed_thesis": True,
        },
        "research_only_engines": [
            "ema_pullback",
            "trend_continuation",
            "trend_pullback",
            "liquidity_reversal",
            "vwap_reclaim",
        ],
        "tiering": {"minimum_trade_tier": "A"},
        "config_version": "test",
    }
    cfg.update(extra)
    return cfg


def _seed_regime(data: Path, started: datetime, cfg_ver: str = "test") -> None:
    (data / "trade_silence_regime.json").write_text(
        json.dumps(
            {"config_version": cfg_ver, "started_at": started.isoformat()},
            indent=2,
        ),
        encoding="utf-8",
    )


def _copy_preflight(tmp_path: Path) -> None:
    """Preflight is loaded from root/scripts — point root at tmp with real script copy."""
    import shutil

    scripts = tmp_path / "scripts"
    scripts.mkdir(exist_ok=True)
    src = Path(__file__).resolve().parents[1] / "scripts" / "preflight_paper_path.py"
    shutil.copy(src, scripts / "preflight_paper_path.py")
    # live_main AST check needs src/agent/live_main.py
    live_src = Path(__file__).resolve().parents[1] / "src" / "agent" / "live_main.py"
    dest = tmp_path / "src" / "agent"
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copy(live_src, dest / "live_main.py")


def test_under_90m_quiet_is_ok(tmp_path: Path):
    data = tmp_path / "data"
    data.mkdir()
    _copy_preflight(tmp_path)
    now = datetime(2026, 8, 10, 19, 0, tzinfo=timezone.utc)
    _seed_regime(data, now - timedelta(minutes=30))
    (data / "paper_trades.json").write_text(
        json.dumps(
            {
                "trades": [
                    {
                        "opened_at": (now - timedelta(minutes=30)).isoformat(),
                        "symbol": "MES",
                    }
                ],
                "heartbeat": {"ts": now.isoformat()},
            }
        ),
        encoding="utf-8",
    )
    (data / "execution_decisions.jsonl").write_text("", encoding="utf-8")
    cfg = _cfg()
    cfg["trade_silence_watch"]["decisions_path"] = str(data / "execution_decisions.jsonl")
    report = diagnose_trade_silence(root=tmp_path, cfg=cfg, now=now)
    assert report.severity == "OK"
    assert report.blocker_codes == []


def test_over_90m_open_is_pipeline_drought_alert(tmp_path: Path):
    data = tmp_path / "data"
    data.mkdir()
    _copy_preflight(tmp_path)
    now = datetime(2026, 8, 10, 19, 0, tzinfo=timezone.utc)
    _seed_regime(data, now - timedelta(hours=3))
    (data / "paper_trades.json").write_text(
        json.dumps(
            {
                "trades": [
                    {
                        "opened_at": (now - timedelta(hours=3)).strftime(
                            "%Y-%m-%d %H:%M:%S"
                        ),
                        "symbol": "MES",
                    }
                ],
                "heartbeat": {
                    "ts": now.isoformat(),
                    "scan_state": "NO_NEW_BAR",
                    "decision": "AGENT HEALTHY",
                },
            }
        ),
        encoding="utf-8",
    )
    (data / "execution_decisions.jsonl").write_text("", encoding="utf-8")
    (data / "shadow_trades.json").write_text(json.dumps({"open": []}), encoding="utf-8")
    cfg = _cfg()
    cfg["trade_silence_watch"]["decisions_path"] = str(data / "execution_decisions.jsonl")
    cfg["shadow"]["path"] = str(data / "shadow_trades.json")
    report = diagnose_trade_silence(root=tmp_path, cfg=cfg, now=now)
    assert report.severity == "ALERT"
    assert BLOCKER_PIPELINE_DROUGHT in report.blocker_codes
    # Cooldown restart once to clear stuck runtime (not gate easing)
    assert report.auto_restart_suggested is True


def test_research_supersede_alerts(tmp_path: Path):
    data = tmp_path / "data"
    data.mkdir()
    _copy_preflight(tmp_path)
    now = datetime(2026, 8, 10, 19, 0, tzinfo=timezone.utc)
    last_open = (now - timedelta(hours=4)).strftime("%Y-%m-%d %H:%M:%S")
    _seed_regime(data, now - timedelta(hours=5))
    (data / "paper_trades.json").write_text(
        json.dumps(
            {
                "trades": [
                    {
                        "symbol": "MGC",
                        "strategy_name": "ema_pullback",
                        "opened_at": last_open,
                        "status": "closed",
                    }
                ],
                "open_positions": [],
                "heartbeat": {"ts": now.isoformat(), "scan_state": "NO_NEW_BAR"},
            }
        ),
        encoding="utf-8",
    )
    lines = []
    for _ in range(20):
        lines.append(
            json.dumps(
                {
                    "decision": "REJECTED",
                    "reason": "AGREEMENT_SUPERSEDED_BY_ema_pullback",
                    "cycle_ts": now.isoformat(),
                    "symbol": "MGC",
                    "strategy": "liquidity_sweep",
                }
            )
        )
    (data / "execution_decisions.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (data / "shadow_trades.json").write_text(
        json.dumps({"open": [{"symbol": "MGC"}], "closed": []}), encoding="utf-8"
    )
    cfg = _cfg()
    cfg["trade_silence_watch"]["decisions_path"] = str(data / "execution_decisions.jsonl")
    cfg["shadow"]["path"] = str(data / "shadow_trades.json")
    report = diagnose_trade_silence(root=tmp_path, cfg=cfg, now=now)
    assert report.severity == "ALERT"
    assert BLOCKER_RESEARCH_SUPERSEDE in report.blocker_codes
    assert report.auto_restart_suggested is True


def test_market_closed_ok(tmp_path: Path):
    data = tmp_path / "data"
    data.mkdir()
    now = datetime(2026, 8, 9, 16, 0, tzinfo=timezone.utc)  # weekend
    (data / "paper_trades.json").write_text(
        json.dumps(
            {
                "trades": [],
                "open_positions": [],
                "heartbeat": {"ts": now.isoformat()},
            }
        ),
        encoding="utf-8",
    )
    (data / "execution_decisions.jsonl").write_text("", encoding="utf-8")
    cfg = _cfg()
    cfg["trade_silence_watch"]["decisions_path"] = str(data / "execution_decisions.jsonl")
    report = diagnose_trade_silence(root=tmp_path, cfg=cfg, now=now)
    assert report.severity == "OK"
    assert "MARKET_CLOSED" in report.blocker_codes


def test_code_bug_does_not_suggest_restart(tmp_path: Path):
    data = tmp_path / "data"
    data.mkdir()
    _copy_preflight(tmp_path)
    now = datetime(2026, 8, 10, 20, 30, tzinfo=timezone.utc)
    last_open = (now - timedelta(hours=4)).strftime("%Y-%m-%d %H:%M:%S")
    _seed_regime(data, now - timedelta(hours=5))
    (data / "paper_trades.json").write_text(
        json.dumps(
            {
                "trades": [{"opened_at": last_open, "symbol": "MYM"}],
                "heartbeat": {"ts": now.isoformat()},
            }
        ),
        encoding="utf-8",
    )
    (data / "execution_decisions.jsonl").write_text(
        json.dumps(
            {
                "decision": "REJECTED",
                "reason": (
                    "EXECUTION_ERROR:cannot access local variable 'risk' "
                    "where it is not associated with a value"
                ),
                "cycle_ts": now.isoformat(),
                "symbol": "MYM",
                "strategy": "vwap_acceptance",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (data / "shadow_trades.json").write_text(json.dumps({"open": []}), encoding="utf-8")
    cfg = _cfg()
    cfg["trade_silence_watch"]["decisions_path"] = str(data / "execution_decisions.jsonl")
    cfg["shadow"]["path"] = str(data / "shadow_trades.json")
    report = diagnose_trade_silence(root=tmp_path, cfg=cfg, now=now)
    assert BLOCKER_CODE_BUG in report.blocker_codes
    assert report.auto_restart_suggested is False
    assert report.severity == "ALERT"


def test_persist_status(tmp_path: Path):
    data = tmp_path / "data"
    data.mkdir()
    _copy_preflight(tmp_path)
    now = datetime(2026, 8, 10, 19, 0, tzinfo=timezone.utc)
    _seed_regime(data, now - timedelta(minutes=10))
    (data / "paper_trades.json").write_text(
        json.dumps(
            {
                "trades": [
                    {
                        "opened_at": (now - timedelta(minutes=30)).isoformat(),
                        "symbol": "MES",
                    }
                ],
                "heartbeat": {"ts": now.isoformat()},
            }
        ),
        encoding="utf-8",
    )
    (data / "execution_decisions.jsonl").write_text("", encoding="utf-8")
    cfg = _cfg()
    cfg["trade_silence_watch"]["path"] = "data/trade_silence_status.json"
    cfg["trade_silence_watch"]["decisions_path"] = str(data / "execution_decisions.jsonl")
    report = run_trade_silence_watch(tmp_path, cfg, now=now)
    assert report.severity == "OK"
    assert (data / "trade_silence_status.json").exists()


def test_research_vs_research_supersede_is_not_steal(tmp_path: Path):
    """Research beating research must not set RESEARCH_SUPERSEDE_DOMINANT."""
    data = tmp_path / "data"
    data.mkdir()
    _copy_preflight(tmp_path)
    now = datetime(2026, 8, 10, 19, 0, tzinfo=timezone.utc)
    last_open = (now - timedelta(hours=4)).strftime("%Y-%m-%d %H:%M:%S")
    _seed_regime(data, now - timedelta(hours=5))
    (data / "paper_trades.json").write_text(
        json.dumps(
            {
                "trades": [
                    {
                        "symbol": "MGC",
                        "strategy_name": "liquidity_sweep",
                        "opened_at": last_open,
                        "status": "closed",
                    }
                ],
                "open_positions": [],
                "heartbeat": {"ts": now.isoformat(), "scan_state": "NO_NEW_BAR"},
            }
        ),
        encoding="utf-8",
    )
    lines = []
    for _ in range(20):
        lines.append(
            json.dumps(
                {
                    "decision": "REJECTED",
                    "reason": "AGREEMENT_SUPERSEDED_BY_trend_pullback",
                    "cycle_ts": now.isoformat(),
                    "symbol": "MGC",
                    "strategy": "ema_pullback",
                }
            )
        )
    (data / "execution_decisions.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    cfg = _cfg()
    cfg["trade_silence_watch"]["decisions_path"] = str(data / "execution_decisions.jsonl")
    report = diagnose_trade_silence(root=tmp_path, cfg=cfg, now=now)
    assert BLOCKER_RESEARCH_SUPERSEDE not in report.blocker_codes
    assert report.severity == "ALERT"
    assert BLOCKER_PIPELINE_DROUGHT in report.blocker_codes
