from agent.paper.blotter import PaperBlotter


def test_session_pnl_breakdown(tmp_path):
    b = PaperBlotter(
        json_path=tmp_path / "t.json",
        html_path=tmp_path / "t.html",
        csv_path=tmp_path / "t.csv",
        starting_equity=50_000,
    )
    b.record_paper_fill(
        symbol="MES",
        side="BUY",
        entry=7700,
        stop=7680,
        target=7740,
        qty=1,
        session="asia",
        point_value=5.0,
    )
    b.manage_open({"MES": 7740.0})
    b.record_paper_fill(
        symbol="MNQ",
        side="SELL",
        entry=20000,
        stop=20050,
        target=19900,
        qty=1,
        session="ny",
        point_value=2.0,
    )
    b.manage_open({"MNQ": 20050.0})  # stop loss
    stats = b.session_pnl()
    assert stats["asia"]["trades"] == 1
    assert stats["asia"]["pnl"] == 200.0
    assert stats["ny"]["trades"] == 1
    assert stats["ny"]["pnl"] == -100.0
    html = b.render_html().read_text(encoding="utf-8")
    assert "P&L by session" in html or "P&amp;L by session" in html
    assert "Asia" in html


def test_open_and_close_records_hold_time(tmp_path):
    b = PaperBlotter(
        json_path=tmp_path / "t.json",
        html_path=tmp_path / "t.html",
        csv_path=tmp_path / "t.csv",
        starting_equity=50_000,
    )
    t = b.record_paper_fill(
        symbol="MES",
        side="BUY",
        entry=7700,
        stop=7680,
        target=7740,
        qty=1,
        session="ny_afternoon",
        point_value=5.0,
        confidence=80,
        reason="unit test",
    )
    assert t["status"] == "OPEN"
    assert len(b.open_positions()) == 1
    assert b.open_positions()[0]["risk_dollars"] == 100.0  # 20 pts * $5
    assert b.open_positions()[0]["reward_dollars"] == 200.0  # 40 pts * $5

    b.heartbeat(session="ny", prices={"MES": 7710.0}, decision="holding")
    html = (tmp_path / "t.html").read_text(encoding="utf-8")
    assert "Risk $" in html
    assert "+$50.00" in html  # 10 pts * $5 unrealized

    closed = b.manage_open({"MES": 7740.0})
    assert len(closed) == 1
    assert closed[0]["exit_reason"] == "target"
    assert closed[0]["result"] == "WIN"
    assert closed[0]["pnl_dollars"] == 200.0  # 40 pts * $5
    assert closed[0]["hold_minutes"] is not None
    assert (tmp_path / "t.csv").exists()


def test_scale_out_tp1_then_runner(tmp_path):
    b = PaperBlotter(
        json_path=tmp_path / "t.json",
        html_path=tmp_path / "t.html",
        csv_path=tmp_path / "t.csv",
    )
    # 20pt stop => TP1 at +20 = 7720; full target 7740
    b.record_paper_fill(
        symbol="MES",
        side="BUY",
        entry=7700,
        stop=7680,
        target=7740,
        qty=2,
        point_value=5.0,
        risk_dollars=100,  # per contract
    )
    scale = {"enabled": True, "tp1_r_multiple": 1.0, "move_stop_to_breakeven": True}
    events = b.manage_open({"MES": 7720.0}, scale_out=scale)
    assert len(events) == 1
    assert events[0]["exit_reason"] == "tp1"
    assert events[0]["pnl_dollars"] == 100.0  # 1 ct * 20 pts * $5
    assert len(b.open_positions()) == 1
    runner = b.open_positions()[0]
    assert runner["qty"] == 1
    assert runner["tp1_done"] is True
    assert runner["stop"] == 7700.0  # breakeven
    assert b.realized_pnl() == 100.0

    # Runner hits full target
    events2 = b.manage_open({"MES": 7740.0}, scale_out=scale)
    assert len(events2) == 1
    assert events2[0]["exit_reason"] == "target"
    # runner 40 pts * $5 = 200 + already booked partial 100 on realized
    assert events2[0]["pnl_dollars"] == 300.0  # partial 100 + runner 200
    assert b.realized_pnl() == 300.0
    assert len(b.open_positions()) == 0
    stats = b.session_pnl()
    assert stats["other"]["trades"] == 1
    assert stats["other"]["pnl"] == 300.0
    assert b.realized_pnl_today() == 300.0


def test_daily_session_market_timestamp_naive_is_et(tmp_path):
    b = PaperBlotter(
        json_path=tmp_path / "t.json",
        html_path=tmp_path / "t.html",
        csv_path=tmp_path / "t.csv",
    )
    b._state["closed_trades"] = [
        {
            "id": "x",
            "market_timestamp": "2026-08-13 00:30:00",
            "closed_at": "2026-08-13T05:00:00+00:00",
            "session": "asia",
            "pnl_dollars": 25.0,
            "partial_pnl_dollars": 0.0,
            "exit_reason": "target",
        }
    ]
    daily = b.daily_session_pnl()
    assert daily["2026-08-13"]["asia"]["pnl"] == 25.0


def test_time_stop_skips_winners(tmp_path):
    b = PaperBlotter(
        json_path=tmp_path / "t.json",
        html_path=tmp_path / "t.html",
        csv_path=tmp_path / "t.csv",
    )
    t = b.record_paper_fill(
        symbol="MES",
        side="BUY",
        entry=7700,
        stop=7680,
        target=7740,
        qty=1,
        point_value=5.0,
    )
    # Pretend it has been open a long time
    from datetime import datetime, timedelta, timezone

    old = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()
    # Hold clock uses received_at/ts (wall), not market-bar opened_at
    t["opened_at"] = old
    t["received_at"] = old
    t["ts"] = old
    pos = b.open_positions()[0]
    pos["opened_at"] = old
    pos["received_at"] = old
    pos["ts"] = old
    b._save()

    # In profit — should NOT time stop
    ev = b.manage_open(
        {"MES": 7715.0},
        max_hold_minutes=60,
        time_stop_only_if_losing=True,
    )
    assert ev == []
    assert len(b.open_positions()) == 1

    # Underwater — SHOULD time stop
    ev2 = b.manage_open(
        {"MES": 7690.0},
        max_hold_minutes=60,
        time_stop_only_if_losing=True,
    )
    assert len(ev2) == 1
    assert ev2[0]["exit_reason"] == "time_stop"


def test_time_stop_ignores_stale_market_bar_opened_at(tmp_path):
    """Delayed Yahoo market timestamps must not invent hours of hold time."""
    b = PaperBlotter(
        json_path=tmp_path / "t.json",
        html_path=tmp_path / "t.html",
        csv_path=tmp_path / "t.csv",
    )
    from datetime import datetime, timedelta, timezone

    b.record_paper_fill(
        symbol="MES",
        side="BUY",
        entry=7700,
        stop=7680,
        target=7740,
        qty=1,
        point_value=5.0,
        market_timestamp=(datetime.now(timezone.utc) - timedelta(hours=3)).strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
        received_timestamp=datetime.now(timezone.utc).isoformat(),
    )
    # Slightly underwater right after fill — must NOT time-stop from bar lag
    ev = b.manage_open(
        {"MES": 7695.0},
        max_hold_minutes=60,
        time_stop_only_if_losing=True,
    )
    assert ev == []
    assert len(b.open_positions()) == 1


def test_profit_protection_prevents_full_giveback(tmp_path):
    """Near target then reverse should stop out near locked profit, not original stop."""
    b = PaperBlotter(
        json_path=tmp_path / "t.json",
        html_path=tmp_path / "t.html",
        csv_path=tmp_path / "t.csv",
    )
    b.record_paper_fill(
        symbol="MES",
        side="BUY",
        entry=7700,
        stop=7680,  # 20pt risk
        target=7740,  # 40pt target
        qty=1,
        point_value=5.0,
    )
    prot = {
        "enabled": True,
        "move_be_at_r": 0.75,
        "near_target_frac": 0.70,
        "lock_profit_frac": 0.50,
        "trail_after_r": 1.0,
        "trail_giveback_r": 0.40,
    }
    # Push to 75% of target (30 pts) — should lock stop around 50% (7720) and/or trail
    b.manage_open({"MES": 7730.0}, profit_protection=prot)
    pos = b.open_positions()[0]
    assert pos["stop"] >= 7720.0  # locked, not still 7680

    # Reverse hard — should exit at raised stop, not original -20pt loss
    events = b.manage_open({"MES": 7719.0}, profit_protection=prot)
    assert len(events) == 1
    assert events[0]["exit_reason"] == "stop"
    assert events[0]["pnl_dollars"] >= 0  # at worst scratch / small winner, not -$100
