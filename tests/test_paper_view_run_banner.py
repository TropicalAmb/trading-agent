"""Paper View run-status banner clarity."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from agent.paper.blotter import PaperBlotter


def test_run_banner_actively_running(tmp_path: Path):
    jp = tmp_path / "paper_trades.json"
    hp = tmp_path / "view.html"
    b = PaperBlotter(jp, hp, starting_equity=50_000)
    now = datetime.now(timezone.utc)
    b._state["heartbeat"] = {
        "ts": now.isoformat(),
        "session": "london",
        "prices": {"NQ": 29800.0},
        "decision": "AGENT HEALTHY — NO NEW MARKET BAR",
        "scan_state": "NO_NEW_BAR",
        "signals_found": 0,
        "config_version": "router_v1_nqctx1",
        "candidates": [],
        "last_evaluated_candidates": [],
    }
    b._save()
    html = b.render_html().read_text(encoding="utf-8")
    assert "ACTIVELY RUNNING" in html
    assert "run-banner ok" in html
    assert "router_v1_nqctx1" in html
    assert "At a glance" in html


def test_run_banner_stuck(tmp_path: Path):
    jp = tmp_path / "paper_trades.json"
    hp = tmp_path / "view.html"
    b = PaperBlotter(jp, hp, starting_equity=50_000)
    stale = datetime.now(timezone.utc) - timedelta(hours=3)
    b._state["heartbeat"] = {
        "ts": stale.isoformat(),
        "session": "asia",
        "prices": {},
        "decision": "AGENT HEALTHY — NO NEW MARKET BAR",
        "scan_state": "NO_NEW_BAR",
        "signals_found": 0,
        "candidates": [],
        "last_evaluated_candidates": [],
    }
    b._save()
    html = b.render_html().read_text(encoding="utf-8")
    assert "NOT ACTIVELY RUNNING (STUCK)" in html
    assert "run-banner bad" in html


def test_at_a_glance_separates_scan_vs_trade(tmp_path: Path):
    jp = tmp_path / "paper_trades.json"
    hp = tmp_path / "view.html"
    b = PaperBlotter(jp, hp, starting_equity=50_000)
    now = datetime.now(timezone.utc)
    b._state["heartbeat"] = {
        "ts": now.isoformat(),
        "session": "london | mode=active",
        "prices": {"NQ": 29800.0},
        "decision": "AGENT HEALTHY — NO NEW MARKET BAR",
        "scan_state": "NO_NEW_BAR",
        "signals_found": 0,
        "config_version": "router_v1_nqctx1",
        "candidates": [],
        "last_evaluated_candidates": [],
    }
    b._state["open_positions"] = []
    b._save()
    html = b.render_html().read_text(encoding="utf-8")
    assert "At a glance" in html
    assert "SCANNING — flat" in html or "PAPER TRADING" in html
    assert "Technical status" in html
    assert html.count('data-fold="open_positions"') == 1
