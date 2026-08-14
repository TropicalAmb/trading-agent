from __future__ import annotations

import argparse
import logging
import os
import sys
from typing import Any

# Windows pythonw inherits a legacy code page unless forced. Reconfigure before
# logging so arrows and other diagnostics never generate hundreds of cp1252
# logging tracebacks that obscure the actual crash.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    except (AttributeError, OSError):
        pass

from agent.alerts import Alerter
from agent.broker.ibkr import IBKRClient, MockIBKRClient
from agent.broker.tradovate import TradovateClient
from agent.config import assert_safe_to_trade, load_settings
from agent.data.bar_cursor import BarCursorStore
from agent.data.yahoo_delayed import make_provider
from agent.decision.adapters import setup_to_signal
from agent.decision.execution_decisions import ExecutionDecisionLedger
from agent.decision.pipeline import DecisionPipeline
from agent.execution.directional import DirectionalExecutor
from agent.journal.store import Journal
from agent.market.bars import log_market_data_status, make_bar_source
from agent.paper.blotter import PaperBlotter
from agent.risk.directional import DirectionalRiskEngine
from agent.risk.portfolio import ExposureIntent, PortfolioCoordinator, PortfolioState
from agent.schedule.sessions import active_session_name, session_ok
from agent.trade_mode import apply_trade_mode
from agent.strategy.confluence import ConfluenceScanner
from agent.strategy.sweep_retest import SweepRetestScanner, evaluate_sweep_retest
from agent.strategy.vwap_acceptance import VwapAcceptanceScanner, evaluate_vwap_acceptance
from agent.strategy.vwap_orb import VwapOrbScanner, evaluate_vwap_orb
from agent.webhook.server import start_webhook_server

# Log to stdout so PowerShell does not paint normal INFO lines red (stderr = red)
_handler = logging.StreamHandler(sys.stdout)
_handler.setFormatter(
    logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
)
logging.basicConfig(level=logging.INFO, handlers=[_handler], force=True)
logger = logging.getLogger("live_agent")


def build_broker(cfg: dict[str, Any], use_mock: bool):
    if use_mock:
        return MockIBKRClient()
    backend = (
        os.getenv("BROKER_BACKEND")
        or cfg.get("broker_backend")
        or "ibkr"
    ).lower()
    if backend == "tradovate":
        return TradovateClient(demo=cfg.get("mode", "paper") != "live")
    if backend == "ibkr":
        b = cfg.get("broker", {})
        host = os.getenv("IBKR_HOST", b.get("host", "127.0.0.1"))
        port = int(os.getenv("IBKR_PORT", b.get("port", 4002)))
        client_id = int(os.getenv("IBKR_CLIENT_ID", b.get("client_id", 1)))
        return IBKRClient(
            host=host,
            port=port,
            client_id=client_id,
            readonly=bool(b.get("readonly", False)),
        )
    raise RuntimeError(f"Unknown broker_backend: {backend}")


def build_scanner(cfg: dict[str, Any]):
    name = cfg.get("active_strategy", "decision_pipeline")
    bars = make_bar_source(cfg)
    if name in {"decision_pipeline", "tiered"}:
        # Pipeline owns scanning; keep ConfluenceScanner only for legacy diagnose fallback
        return ConfluenceScanner(cfg, bars), "decision_pipeline"
    if name == "sweep_retest":
        return SweepRetestScanner(cfg, bars), name
    if name == "vwap_orb":
        return VwapOrbScanner(cfg, bars), "vwap_orb"
    if name == "vwap_acceptance":
        return VwapAcceptanceScanner(cfg, bars), "vwap_acceptance"
    return ConfluenceScanner(cfg, bars), "confluence"


def _local_signal(cfg: dict[str, Any], strat_name: str, symbol: str):
    bars = make_bar_source(cfg)
    if strat_name == "confluence":
        return ConfluenceScanner(cfg, bars).scan_symbol(symbol)
    meta = cfg.get("instruments", {}).get(symbol, {})
    pv = float(meta.get("point_value", 5.0))
    raw = bars(symbol)
    if strat_name == "sweep_retest":
        return evaluate_sweep_retest(symbol, raw, cfg, point_value=pv)
    if strat_name == "vwap_orb":
        return evaluate_vwap_orb(symbol, raw, cfg, point_value=pv)
    return evaluate_vwap_acceptance(symbol, raw, cfg, point_value=pv)


def _blotter_risk_context(
    blotter: PaperBlotter,
) -> tuple[dict[str, str], dict[str, Any]]:
    from datetime import datetime, timezone

    def _aware(dt: datetime) -> datetime:
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    open_sides: dict[str, str] = {}
    for p in blotter.open_positions():
        open_sides[str(p["symbol"]).upper()] = str(p["side"]).upper()
    last_fill: dict[str, datetime] = {}
    for t in list(blotter._state.get("trades", [])) + list(
        blotter._state.get("closed_trades", [])
    ):
        sym = str(t.get("symbol", "")).upper()
        ts = t.get("opened_at") or t.get("closed_at") or t.get("ts")
        if not sym or not ts:
            continue
        try:
            dt = _aware(datetime.fromisoformat(str(ts).replace("Z", "+00:00")))
        except ValueError:
            continue
        prev = last_fill.get(sym)
        if prev is None or dt > _aware(prev):
            last_fill[sym] = dt
    return open_sides, last_fill


def handle_signal(
    signal: Any,
    *,
    cfg: dict[str, Any],
    broker,
    risk_engine: DirectionalRiskEngine,
    execution: DirectionalExecutor,
    journal: Journal,
    alerter: Alerter,
    open_symbols: list[str],
    skip_session_check: bool,
    source: str = "agent",
    blotter: PaperBlotter | None = None,
) -> tuple[list[str], str | None, str | None]:
    """Returns (open_symbols, reject_reason_or_None, order_id_or_None)."""
    account = broker.get_account_snapshot()
    journal.log(
        "signal",
        {
            "symbol": signal.symbol,
            "side": signal.side,
            "entry": signal.entry,
            "stop": signal.stop,
            "target": signal.target,
            "confidence": signal.confidence,
            "risk_dollars": signal.risk_dollars,
            "reward_dollars": signal.reward_dollars,
            "reason": signal.reason,
        },
    )
    open_sides, last_fill = ({}, {})
    if blotter is not None:
        open_sides, last_fill = _blotter_risk_context(blotter)
    ok, reasons = risk_engine.evaluate(
        signal,
        account,
        open_symbols,
        skip_session_check=skip_session_check,
        open_sides=open_sides,
        last_fill_ts=last_fill,
    )
    # DirectionalRiskEngine expects SweepSignal-like; OrbSignal duck-types fine
    journal.log("risk", {"approved": ok, "reasons": reasons})
    if not ok:
        if cfg.get("alerts", {}).get("on_reject", True):
            alerter.send(f"Rejected {signal.symbol}: {'; '.join(reasons)}")
        code = "RISK_LIMIT"
        joined = " ".join(reasons).lower()
        if "session" in joined or "weekend" in joined or "closed" in joined:
            code = "MARKET_CLOSED"
        elif "cooldown" in joined:
            code = "SYMBOL_COOLDOWN"
        elif "position" in joined or "already open" in joined:
            code = "POSITION_EXISTS"
        elif "stale" in joined:
            code = "DATA_STALE"
        return open_symbols, f"{code}:{' | '.join(reasons)}", None

    result = execution.execute(signal, source=source)
    journal.log("order", result)
    if cfg.get("alerts", {}).get("on_fill", True):
        alerter.send(
            f"{result.get('status')} {signal.side} {signal.symbol} "
            f"target~${signal.reward_dollars:.0f} risk~${signal.risk_dollars:.0f} "
            f"conf={signal.confidence} → open data/paper_trading_view.html"
        )
    if signal.symbol not in open_symbols:
        open_symbols = open_symbols + [signal.symbol]
    return open_symbols, None, str(result.get("order_id") or "")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Live futures agent (Tradovate/Topstep)")
    parser.add_argument("--config", default=None)
    parser.add_argument("--mock", action="store_true")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--skip-session-check", action="store_true")
    parser.add_argument("--webhook", action="store_true")
    parser.add_argument(
        "--demo-paper-trade",
        action="store_true",
        help="Book one sample paper fill so you can verify Paper Trading View",
    )
    parser.add_argument(
        "--tv-alerts-only",
        action="store_true",
        help="Only trade when a TradingView webhook arrives (no autonomous scan loop)",
    )
    args = parser.parse_args(argv)

    cfg = load_settings(args.config)
    assert_safe_to_trade(cfg)
    # Directional risk reads sweep_retest.* keys — mirror active engine limits
    active = cfg.get("active_strategy", "confluence")
    if active == "confluence":
        src = cfg.get("confluence") or {}
    elif active == "decision_pipeline":
        # Paper path uses execution_quality + confluence floors, not a lone engine block
        src = {
            **(cfg.get("confluence") or {}),
            **(cfg.get("execution_quality") or {}),
        }
    else:
        src = cfg.get(active) or {}
    cfg["sweep_retest"] = {
        **cfg.get("sweep_retest", {}),
        "max_risk_dollars": src.get(
            "max_risk_dollars",
            cfg.get("risk", {}).get("max_risk_dollars_per_trade", 250),
        ),
        "min_reward_dollars": src.get("min_reward_dollars", 75),
        "min_confidence": src.get("min_confidence", 55),
    }

    use_mock = args.mock or os.getenv("USE_MOCK_BROKER", "").lower() in {
        "1",
        "true",
        "yes",
    }
    journal = Journal(
        cfg.get("journal", {}).get("db_path", "data/journal.db"),
        cfg.get("journal", {}).get("csv_export", "data/decisions.csv"),
    )
    alerter = Alerter(cfg)
    risk_engine = DirectionalRiskEngine(cfg)
    broker = build_broker(cfg, use_mock=use_mock)
    try:
        broker.connect()
    except Exception as exc:
        logger.error("Broker connect failed: %s", exc)
        if not use_mock:
            logger.error("Set Tradovate .env vars, or run with --mock")
            return 1
        raise

    scanner, strat_name = build_scanner(cfg)
    agent_id = str(cfg.get("agent_id", "agent_1"))
    provider = make_provider(cfg)
    bar_cursor = BarCursorStore(
        cfg.get("market_data", {}).get("bar_cursor_path", "data/bar_cursors.json")
    )
    pipeline = DecisionPipeline(cfg, provider, bar_cursor, agent_id=agent_id)
    exec_ledger = ExecutionDecisionLedger(
        cfg.get("execution_decisions_path") or "data/execution_decisions.jsonl"
    )
    portfolio = PortfolioCoordinator(cfg)
    use_pipeline = str(cfg.get("active_strategy", "confluence")) in {
        "confluence",
        "decision_pipeline",
        "tiered",
    }
    blotter = PaperBlotter(
        cfg.get("paper", {}).get("json_path", "data/paper_trades.json"),
        cfg.get("paper", {}).get("html_path", "data/paper_trading_view.html"),
        float(cfg.get("paper", {}).get("starting_equity", 50_000)),
        cfg.get("paper", {}).get("csv_path", "data/trade_journal.csv"),
    )
    # Drop legacy full-size / out-of-universe opens so paper learning isn't polluted
    allowed = {str(s).upper() for s in cfg.get("universe", {}).get("symbols", [])}
    for p in list(blotter.open_positions()):
        sym = str(p.get("symbol", "")).upper()
        tid = p.get("trade_id") or p.get("id")
        if not tid:
            continue
        if sym not in allowed:
            entry = float(p.get("entry") or 0)
            blotter.close_trade(tid, exit_price=entry, exit_reason="universe_prune")
            logger.info("Pruned out-of-universe open %s %s", sym, tid)
    # If opposite correlated indexes are both open, keep earliest, flat the rest at entry
    if cfg.get("risk", {}).get("block_opposite_correlated", False):
        opens = blotter.open_positions()
        for group in cfg.get("risk", {}).get("correlation_groups", []):
            g = {str(x).upper() for x in group}
            in_g = [p for p in opens if str(p.get("symbol", "")).upper() in g]
            if len(in_g) < 2:
                continue
            sides = {str(p.get("side", "")).upper() for p in in_g}
            if len(sides) < 2:
                continue
            in_g.sort(key=lambda p: str(p.get("opened_at") or ""))
            keep = in_g[0]
            for p in in_g[1:]:
                tid = p.get("trade_id") or p.get("id")
                if not tid:
                    continue
                blotter.close_trade(
                    tid,
                    exit_price=float(p.get("entry") or 0),
                    exit_reason="corr_conflict_prune",
                )
                logger.info(
                    "Pruned correlated conflict %s (kept %s)",
                    p.get("symbol"),
                    keep.get("symbol"),
                )
    blotter.render_html()
    execution = DirectionalExecutor(broker, cfg, blotter=blotter)
    open_symbols: list[str] = [p["symbol"] for p in blotter.open_positions()]

    symbols = list(cfg.get("universe", {}).get("symbols") or ["MES", "MNQ"])
    logger.info(
        "Agent strategy=%s broker=%s mock_broker=%s mode=%s dry_run=%s symbols=%s",
        strat_name,
        cfg.get("broker_backend", "ibkr"),
        use_mock,
        cfg.get("mode"),
        cfg.get("execution", {}).get("dry_run"),
        symbols,
    )
    logger.info(
        "Daily Paper Trading View: %s  (NOT TradingView's Paper Trading panel)",
        blotter.html_path.resolve(),
    )
    # DecisionPipeline's first cycle is the market-data proof. A separate
    # all-symbol startup probe used to add ten more Yahoo downloads before the
    # first heartbeat, amplifying rate limits and restart loops.
    if use_pipeline:
        logger.info("Market data check deferred to first paper cycle (single shared snapshot).")
    else:
        try:
            log_market_data_status(symbols, logger)
        except Exception as exc:
            logger.error("Startup market data probe failed; cycles will retry: %s", exc)

    if args.demo_paper_trade:
        from datetime import datetime, timezone

        from agent.strategy.sweep_retest import SweepSignal

        demo = SweepSignal(
            symbol="MES",
            side="BUY",
            entry=7740.0,
            stop=7720.0,
            target=7780.0,
            confidence=99,
            reason="demo paper fill to verify Paper Trading View",
            pdh=7800.0,
            pdl=7700.0,
            ts=datetime.now(timezone.utc),
            risk_dollars=100,
            reward_dollars=200,
        )
        result = execution.execute(demo, source="demo")
        journal.log("demo_paper", result)
        logger.info("Demo paper fill booked → open %s", blotter.html_path.resolve())
        if args.once:
            broker.disconnect()
            return 0

    pending_tv: dict[str, str] = {}  # symbol -> BUY/SELL from alert

    def on_tv(payload: dict[str, Any]) -> None:
        nonlocal open_symbols, pending_tv
        action = str(payload.get("action") or payload.get("side") or "").upper()
        symbol = str(payload.get("symbol") or cfg["universe"]["symbols"][0]).upper()
        price = payload.get("price") or payload.get("close")
        if "BUY" in action:
            side = "BUY"
        elif "SELL" in action:
            side = "SELL"
        else:
            journal.log("webhook_ignore", payload)
            return
        pending_tv[symbol] = side
        journal.log(
            "tv_alert",
            {"symbol": symbol, "side": side, "price": price, "payload": payload},
        )
        alerter.send(f"TV ALERT {side} {symbol} price={price}")
        logger.info("TradingView REAL alert %s %s price=%s", side, symbol, price)

        # Prefer local strategy confirmation; if none, still book paper from TV price
        # so you can verify the TradingView → agent pipe end-to-end.
        sig = _local_signal(cfg, strat_name, symbol)
        require = bool(cfg.get("require_tv_alert_confluence", False))
        if sig is None or sig.side != side:
            if require:
                alerter.send(
                    f"TV {side} {symbol}: waiting — {strat_name} has not confirmed same side"
                )
                journal.log(
                    "webhook_no_confirm",
                    {
                        "symbol": symbol,
                        "tv_side": side,
                        "local": None if sig is None else sig.side,
                    },
                )
                return
            from datetime import datetime, timezone

            from agent.strategy.sweep_retest import SweepSignal

            try:
                px = float(price) if price is not None else float(
                    make_bar_source(cfg)(symbol).iloc[-1]["close"]
                )
            except Exception:
                px = 0.0
            if px <= 0:
                journal.log("webhook_bad_price", payload)
                return
            # ~$100 risk / ~$150 reward style bracket from TV print
            meta = cfg.get("instruments", {}).get(symbol, {})
            pv = float(meta.get("point_value", 5.0))
            stop_pts = 100.0 / pv
            tgt_pts = 150.0 / pv
            if side == "BUY":
                stop, target = px - stop_pts, px + tgt_pts
            else:
                stop, target = px + stop_pts, px - tgt_pts
            sig = SweepSignal(
                symbol=symbol,
                side=side,
                entry=px,
                stop=stop,
                target=target,
                confidence=80,
                reason=f"tradingview alert @ {px}",
                pdh=px,
                pdl=px,
                ts=datetime.now(timezone.utc),
                risk_dollars=100,
                reward_dollars=150,
            )
            logger.info("TV alert booked as paper (no local confirm) %s %s @ %s", side, symbol, px)

        open_symbols, _rej, _oid = handle_signal(
            sig,
            cfg=cfg,
            broker=broker,
            risk_engine=risk_engine,
            execution=execution,
            journal=journal,
            alerter=alerter,
            open_symbols=open_symbols,
            skip_session_check=True if args.tv_alerts_only else args.skip_session_check,
            source="tradingview",
            blotter=blotter,
        )
        pending_tv.pop(symbol, None)

    want_webhook = (
        args.webhook
        or args.tv_alerts_only
        or (cfg.get("webhook", {}).get("enabled") and not args.once)
    )
    if want_webhook:
        wh = cfg.get("webhook", {})
        start_webhook_server(
            on_tv,
            host=wh.get("host", "0.0.0.0"),
            port=int(wh.get("port", 8787)),
            secret=os.getenv("WEBHOOK_SECRET"),
        )
        logger.info(
            "TradingView webhook ready: POST http://127.0.0.1:%s/tv?secret=...",
            int(wh.get("port", 8787)),
        )

    if args.tv_alerts_only and not args.once:
        logger.info("TV-alerts-only mode: waiting for TradingView webhooks (Ctrl+C to stop)")
        try:
            import time

            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            logger.info("shutdown")
        finally:
            broker.disconnect()
        return 0

    def cycle() -> None:
        nonlocal open_symbols
        try:
            account = broker.get_account_snapshot()
            journal.log("account_snapshot", account.model_dump(mode="json"))

            # Scalp-first until realized profits unlock swing mode
            trade_mode = apply_trade_mode(cfg, blotter.realized_pnl())
            logger.info(
                "trade_mode=%s realized=%s unlock_swing_at=%s",
                trade_mode,
                blotter.realized_pnl(),
                cfg.get("growth_plan", {}).get("swing_unlock_realized_pnl", 2000),
            )

            # Manage open paper trades: stop / target / time — build learning journal
            prices: dict[str, float] = {}
            bar_paths: dict[str, dict[str, Any]] = {}
            from agent.runtime.scan_status import parse_interval_seconds, stale_threshold_seconds

            interval = (
                cfg.get("market_data", {}).get("bar_interval")
                or cfg.get("sweep_retest", {}).get("bar_interval", "5m")
            )
            period = (
                cfg.get("market_data", {}).get("bar_period")
                or cfg.get("sweep_retest", {}).get("bar_period", "10d")
            )
            sched_min = max(1, int(cfg.get("schedule", {}).get("poll_interval_minutes", 1)))
            try:
                feed_source = provider.health().source
            except Exception:
                feed_source = str(cfg.get("market_data", {}).get("provider") or "unknown")
            feed_meta: dict[str, Any] = {
                "source": feed_source,
                "is_realtime": False,
                "estimated_delay_seconds": None,
                "expected_delay_seconds": float(
                    cfg.get("market_data", {}).get("expected_delay_seconds", 900)
                ),
                "stale_threshold_seconds": stale_threshold_seconds(cfg, bar_interval=interval),
                "last_market_bar": None,
                "bar_interval": interval,
                "bar_interval_seconds": parse_interval_seconds(interval),
                "bar_interval_label": interval,
                "scheduler_interval_minutes": sched_min,
                "scheduler_interval_label": f"{sched_min}m",
            }
            for sym in symbols:
                try:
                    bar = provider.get_latest_bar(sym, interval=interval, period=period)
                    prices[sym] = float(bar.close)
                    bar_paths[sym] = {
                        "open": float(bar.open),
                        "high": float(bar.high),
                        "low": float(bar.low),
                        "close": float(bar.close),
                        "timestamp": bar.timestamp.isoformat(),
                        "source": bar.source,
                    }
                    feed_meta["is_realtime"] = bar.is_realtime
                    feed_meta["estimated_delay_seconds"] = bar.estimated_delay_seconds
                    feed_meta["last_market_bar"] = bar.timestamp.isoformat()
                    feed_meta["bar_interval"] = (bar.metadata or {}).get(
                        "bar_interval", interval
                    )
                    feed_meta["last_fetch_attempt"] = getattr(
                        provider, "_last_fetch_attempt", None
                    )
                    if feed_meta["last_fetch_attempt"] is not None:
                        feed_meta["last_fetch_attempt"] = feed_meta[
                            "last_fetch_attempt"
                        ].isoformat()
                    ls = getattr(provider, "_last_success", None)
                    feed_meta["last_successful_fetch"] = (
                        ls.isoformat() if ls is not None else None
                    )
                except Exception as exc:
                    logger.warning("price for manage %s failed: %s", sym, exc)
            closed = blotter.manage_open(
                prices,
                bar_paths=bar_paths,
                max_hold_minutes=float(cfg.get("schedule", {}).get("max_hold_minutes") or 0)
                or None,
                scale_out=cfg.get("execution", {}).get("scale_out"),
                profit_protection=cfg.get("execution", {}).get("profit_protection"),
                time_stop_only_if_losing=bool(
                    cfg.get("schedule", {}).get("time_stop_only_if_losing", True)
                ),
            )
            try:
                from agent.journal.shadow import ShadowTracker
                from agent.risk.circuit_breakers import CircuitBreakerStore
                from agent.research.exit_models import ExitModelJournal, evaluate_exit_suite

                shadow_path = (
                    cfg.get("shadow", {}).get("path") or "data/shadow_trades.json"
                )
                ShadowTracker(shadow_path).mark_bars(
                    bar_paths or {k: {"high": v, "low": v, "close": v} for k, v in prices.items()},
                    cfg=cfg,
                    bar_interval_minutes=max(
                        1.0, parse_interval_seconds(interval) / 60.0
                    ),
                )
                cbs = CircuitBreakerStore(
                    cfg.get("circuit_breakers", {}).get("path", "data/circuit_breakers.json")
                )
                exit_j = ExitModelJournal()
            except Exception:
                cbs = None
                exit_j = None
            for t in closed:
                journal.log("trade_closed", t)
                try:
                    from agent.learning.loop import record_outcome_for_setup

                    record_outcome_for_setup(
                        cfg,
                        setup_id=str(t.get("setup_id") or ""),
                        trade=t,
                    )
                except Exception:
                    pass
                if cbs is not None and t.get("exit_reason") != "tp1":
                    try:
                        cbs.record_close(
                            str(t.get("strategy_name") or "unknown"),
                            str(t.get("session") or "other"),
                            float(t.get("pnl_dollars") or 0),
                            cfg,
                        )
                    except Exception:
                        pass
                # Strategy lifecycle equity (R) — kill/drift; not single-loss panic
                if t.get("exit_reason") != "tp1" and bool(
                    (cfg.get("strategy_lifecycle") or {}).get("enabled", True)
                ):
                    try:
                        from agent.risk.strategy_lifecycle import StrategyLifecycleStore

                        lc = StrategyLifecycleStore(
                            (cfg.get("strategy_lifecycle") or {}).get(
                                "path", "data/strategy_lifecycle.json"
                            )
                        )
                        # Do NOT name this `risk` — that shadows DirectionalRiskEngine
                        # in cycle() and causes EXECUTION_ERROR UnboundLocalError on fills.
                        trade_risk_dollars = float(t.get("risk_dollars") or 0) or abs(
                            float(t.get("entry") or 0) - float(t.get("stop") or 0)
                        ) * float(
                            (cfg.get("instruments") or {})
                            .get(str(t.get("symbol") or ""), {})
                            .get("point_value", 1.0)
                        )
                        pnl = float(t.get("pnl_dollars") or 0)
                        pnl_r = (
                            (pnl / trade_risk_dollars) if trade_risk_dollars > 1e-9 else 0.0
                        )
                        lc.record_forward_trade(
                            str(t.get("strategy_name") or "unknown"),
                            str(t.get("symbol") or ""),
                            pnl_r,
                            cfg=cfg,
                        )
                    except Exception:
                        pass
                if exit_j is not None and t.get("exit_reason") != "tp1":
                    try:
                        # Path extremes approx from MAE/MFE if present
                        entry = float(t.get("entry") or 0)
                        mfe = float(t.get("mfe_pts") or 0)
                        mae = float(t.get("mae_pts") or 0)
                        side = str(t.get("side") or "BUY")
                        if side == "BUY":
                            path = {"high": entry + mfe, "low": entry - mae}
                        else:
                            path = {"high": entry + mae, "low": entry - mfe}
                        exit_j.record(evaluate_exit_suite(t, path))
                    except Exception:
                        pass
                kind = "TP1 PARTIAL" if t.get("exit_reason") == "tp1" else "CLOSED"
                alerter.send(
                    f"{kind} {t.get('result')} {t.get('side')} {t.get('symbol')} "
                    f"pnl=${t.get('pnl_dollars')} hold={t.get('hold_minutes')}m "
                    f"via {t.get('exit_reason')}"
                )
            open_symbols = [p["symbol"] for p in blotter.open_positions()]

            ok_sess, sess_info = session_ok(cfg)
            paper_realized = blotter.realized_pnl()
            paper_realized_today = blotter.realized_pnl_today()
            open_risk = blotter.open_risk_dollars()
            risk_cfg = cfg.get("risk", {})
            kill_dollars = float(risk_cfg.get("daily_loss_kill_dollars", 4000))
            kill_pct = float(risk_cfg.get("daily_loss_kill_pct", 0.08))
            start_eq = float(cfg.get("paper", {}).get("starting_equity", 50_000))
            max_open_risk = float(risk_cfg.get("max_total_open_risk_dollars", 3500))
            halted_new = False
            halt_reason = ""
            if paper_realized_today <= -kill_dollars:
                halted_new = True
                halt_reason = f"daily loss kill ${abs(paper_realized_today):.0f} >= ${kill_dollars:.0f}"
            elif start_eq > 0 and (-paper_realized_today / start_eq) >= kill_pct:
                halted_new = True
                halt_reason = f"daily loss kill {(-paper_realized_today/start_eq):.1%} >= {kill_pct:.1%}"
            elif open_risk >= max_open_risk:
                halted_new = True
                halt_reason = f"open risk ${open_risk:.0f} >= max ${max_open_risk:.0f}"

            logger.info(
                "cycle session=%s prices=%s open=%s realized_total=%s realized_today=%s open_risk=%s halt_new=%s",
                sess_info if ok_sess else f"FLAT/{sess_info}",
                {k: round(v, 2) for k, v in prices.items()},
                open_symbols,
                paper_realized,
                paper_realized_today,
                open_risk,
                halt_reason or "no",
            )
            if not ok_sess and not args.skip_session_check:
                journal.log("decision", {"action": "pass", "reason": sess_info})
                blotter.heartbeat(
                    session=f"{sess_info} | mode={trade_mode}",
                    prices=prices,
                    decision=f"pass: {sess_info}",
                    signals_found=0,
                )
                return

            if halted_new:
                journal.log("halt", {"reason": halt_reason, "realized": paper_realized})
                blotter.heartbeat(
                    session=f"{sess_info} | mode={trade_mode}",
                    prices=prices,
                    decision=f"HALTED new entries — {halt_reason} (open trades still managed)",
                    signals_found=0,
                )
                alerter.send(f"Agent halted new entries: {halt_reason}")
                return

            signals = []
            engine_votes: dict[str, list[str]] = {}
            symbol_reports: dict[str, Any] = {}
            all_candidates: list[dict[str, Any]] = []
            setups: list[Any] = []
            try:
                if use_pipeline:
                    cycle_out = pipeline.scan_cycle()
                    symbol_reports = cycle_out.get("symbol_reports") or {}
                    # Convert per-symbol engine dicts into vote lines for tape
                    for sym, rep in symbol_reports.items():
                        lines = []
                        for ename, er in (rep.get("engines") or {}).items():
                            if er.get("result") in (None, "none"):
                                lines.append(
                                    f"{ename}:— ({er.get('because') or 'none'})"
                                )
                            else:
                                lines.append(
                                    f"{ename}:{er.get('result')}@{er.get('confidence')} "
                                    f"tier={er.get('tier')} ({er.get('because','')})"
                                )
                        if not lines and rep.get("reason"):
                            lines = [str(rep.get("reason"))]
                        engine_votes[sym] = lines
                    # Journal rejected / B / C setups with hypothetical levels
                    try:
                        from agent.journal.diagnostics import HypotheticalBTracker
                        from agent.journal.shadow import ShadowTracker

                        b_tracker = HypotheticalBTracker()
                        shadow = ShadowTracker()
                    except Exception:
                        b_tracker = None
                        shadow = None
                    def _open_shadow_row(row: dict) -> None:
                        if shadow is None:
                            return
                        opened = shadow.open_shadow(row)
                        if opened is None:
                            journal.log(
                                "rejected_setup",
                                {
                                    "symbol": row.get("symbol"),
                                    "strategy": row.get("strategy")
                                    or row.get("strategy_name"),
                                    "reason": "SUPPRESSED_DUPLICATE_SETUP",
                                    "setup_id": row.get("setup_id"),
                                    "structural_key": row.get("structural_key"),
                                },
                            )
                            return
                        try:
                            from agent.learning.loop import record_candidate_snapshot

                            record_candidate_snapshot(
                                cfg,
                                row={
                                    **row,
                                    "entry_features": row.get("entry_features")
                                    or row.get("features")
                                    or {},
                                },
                                router_decision=str(
                                    row.get("nonselected_reason") or "SHADOW"
                                ),
                                executed_or_shadow="SHADOW",
                            )
                        except Exception:
                            pass

                    for js in cycle_out.get("journal_only") or []:
                        journal.log(
                            "rejected_setup",
                            {
                                "symbol": js.symbol,
                                "side": js.direction,
                                "tier": js.setup_tier,
                                "confidence": js.confidence_score,
                                "strategy_local_score": (js.metadata or {}).get(
                                    "strategy_local_score"
                                ),
                                "global_score": (js.metadata or {}).get("global_score"),
                                "router_evidence": (js.metadata or {}).get(
                                    "router_evidence"
                                ),
                                "strategy": js.strategy_name,
                                "entry": js.entry,
                                "stop": js.stop,
                                "target": js.target,
                                "reason": f"tier_filter:{js.setup_tier}",
                                "reasons": js.reasons,
                                "setup_id": (js.metadata or {}).get("setup_id"),
                                "market_timestamp": str(js.market_timestamp),
                                "received_timestamp": str(js.received_timestamp),
                                "estimated_delay_seconds": js.estimated_delay_seconds,
                                "agent_id": js.agent_id,
                                "session": js.session,
                            },
                        )
                        if js.setup_tier == "B":
                            row = {
                                "symbol": js.symbol,
                                "side": js.direction,
                                "tier": js.setup_tier,
                                "confidence": js.confidence_score,
                                "strategy": js.strategy_name,
                                "strategy_name": js.strategy_name,
                                "entry": js.entry,
                                "stop": js.stop,
                                "target": js.target,
                                "expected_r": js.expected_r,
                                "market_timestamp": str(js.market_timestamp),
                                "received_timestamp": str(js.received_timestamp),
                                "session": js.session,
                                "agent_id": js.agent_id,
                                "global_score": (js.metadata or {}).get("global_score"),
                                "strategy_local_score": (js.metadata or {}).get(
                                    "strategy_local_score"
                                ),
                                "score_breakdown": (js.metadata or {}).get(
                                    "score_breakdown"
                                ),
                                "regime": (js.metadata or {}).get("regime"),
                                "router_evidence": (js.metadata or {}).get(
                                    "router_evidence"
                                ),
                                "point_value": (js.metadata or {}).get("point_value", 5.0),
                                "quantity": js.quantity,
                                "config_version": (js.metadata or {}).get(
                                    "config_version"
                                ),
                                "paper_config_version": (js.metadata or {}).get(
                                    "paper_config_version"
                                )
                                or (js.metadata or {}).get("config_version"),
                                "strategy_version": (js.metadata or {}).get(
                                    "strategy_version"
                                ),
                                "cascade_log": (js.metadata or {}).get("cascade_log"),
                                "cascade_decision": (js.metadata or {}).get(
                                    "cascade_decision"
                                ),
                                "lifecycle_state": (js.metadata or {}).get(
                                    "lifecycle_state"
                                ),
                                "setup_id": (js.metadata or {}).get("setup_id"),
                                "structural_key": (js.metadata or {}).get(
                                    "structural_key"
                                ),
                            }
                            if b_tracker is not None:
                                b_tracker.record(row)
                            _open_shadow_row(row)
                    # Shadow nonselected valid competitors (A+/A/B) for comparison data
                    for row in cycle_out.get("nonselected_valid") or []:
                        journal.log(
                            "rejected_setup",
                            {
                                "symbol": row.get("symbol"),
                                "side": row.get("side") or row.get("direction"),
                                "tier": row.get("tier"),
                                "strategy": row.get("strategy"),
                                "global_score": row.get("global_score"),
                                "router_evidence": row.get("router_evidence"),
                                "reason": row.get("nonselected_reason")
                                or "NONSELECTED_VALID_SHADOW",
                                "setup_id": row.get("setup_id"),
                                "structural_key": row.get("structural_key"),
                            },
                        )
                        _open_shadow_row(row)
                    setups = cycle_out.get("executable") or []
                    all_candidates = cycle_out.get("all_candidates") or []
                    last_eval_cands = cycle_out.get("last_evaluated_candidates") or all_candidates
                    cs = cycle_out.get("cycle_status") or {}
                    feed_meta["bar_interval"] = cycle_out.get("bar_interval") or interval
                    feed_meta["bar_interval_seconds"] = cycle_out.get(
                        "bar_interval_seconds"
                    )
                    exec_ledger.begin_cycle()
                    # Superseded A/A+ must get an explicit rejection (not silent drop)
                    for row in cycle_out.get("superseded") or []:
                        loser = row.get("loser") or {}
                        # Reconstruct minimal object for ledger
                        class _S:
                            pass

                        s = _S()
                        s.symbol = loser.get("symbol")
                        s.strategy_name = loser.get("strategy")
                        s.direction = "BUY"  # filled below from candidates
                        s.setup_tier = loser.get("tier")
                        s.market_timestamp = ""
                        s.metadata = {
                            "setup_id": loser.get("setup_id"),
                            "global_score": loser.get("global_score"),
                            "config_version": cfg.get("config_version"),
                        }
                        for c in all_candidates:
                            if c.get("setup_id") == loser.get("setup_id"):
                                s.direction = c.get("direction") or "BUY"
                                s.market_timestamp = c.get("market_timestamp") or ""
                                s.metadata["strategy_local_score"] = c.get(
                                    "strategy_local_score"
                                )
                                break
                        exec_ledger.reject(
                            s,
                            str(row.get("reason") or "AGREEMENT_SUPERSEDED"),
                            config_version=str(cfg.get("config_version")),
                        )
                    signals = [setup_to_signal(s) for s in setups]
                    if not signals:
                        primary = cs.get("primary") or (
                            "PASS — NO PAPERABLE CANDIDATE >= A"
                        )
                        detail = cs.get("detail") or ""
                        decision = primary if primary.startswith(
                            ("AGENT", "PASS", "BLOCKED", "ERROR", "MARKET")
                        ) else f"PASS — {primary}"
                        if all_candidates and "NO CANDIDATE" in decision:
                            decision = (
                                f"{decision} | current_scan_candidates={len(all_candidates)}"
                            )
                        elif last_eval_cands and not all_candidates:
                            decision = (
                                f"{decision} | last_evaluated_candidates="
                                f"{len(last_eval_cands)}"
                            )
                        journal.log(
                            "decision",
                            {
                                "action": "pass",
                                "reason": primary,
                                "detail": detail,
                                "scan_state": cs.get("scan_state"),
                                "symbol_reports": {
                                    k: {
                                        "decision": v.get("decision"),
                                        "reason": v.get("reason"),
                                        "engines": v.get("engines"),
                                        "candidates": v.get("candidates"),
                                        "last_candidates": v.get("last_candidates"),
                                    }
                                    for k, v in symbol_reports.items()
                                },
                            },
                        )
                        last_bar = None
                        for c in last_eval_cands:
                            if c.get("market_timestamp"):
                                last_bar = c.get("market_timestamp")
                                break
                        blotter.heartbeat(
                            session=f"{sess_info} | mode={trade_mode}",
                            prices=prices,
                            decision=decision,
                            signals_found=0,
                            engine_votes=engine_votes,
                            symbol_reports=symbol_reports,
                            feed_meta={
                                **feed_meta,
                                "status_detail": detail,
                                "scan_state": cs.get("scan_state"),
                                "last_evaluated_market_bar": last_bar,
                            },
                            candidates=all_candidates,
                            last_evaluated_candidates=last_eval_cands,
                        )
                        return
                else:
                    if hasattr(scanner, "diagnose_votes"):
                        engine_votes = scanner.diagnose_votes()
                    signals = scanner.scan_universe()
            except Exception as exc:
                logger.exception("scan failed (will retry next cycle): %s", exc)
                journal.log("scan_error", {"error": str(exc)})
                blotter.heartbeat(
                    session=f"{sess_info} | mode={trade_mode}",
                    prices=prices,
                    decision=f"scan error — retry next minute: {exc}",
                    signals_found=0,
                    engine_votes=engine_votes,
                    symbol_reports=symbol_reports,
                    feed_meta=feed_meta,
                )
                return
            journal.log(
                "scan",
                {
                    "strategy": strat_name,
                    "session": active_session_name(cfg),
                    "agent_id": agent_id,
                    "count": len(signals),
                    "signals": [
                        {
                            "symbol": s.symbol,
                            "side": s.side,
                            "confidence": s.confidence,
                            "tier": getattr(s, "setup_tier", None),
                            "strategy": getattr(s, "strategy_name", None),
                            "reward_dollars": s.reward_dollars,
                            "risk_dollars": s.risk_dollars,
                            "market_timestamp": str(
                                getattr(s, "market_timestamp", "") or ""
                            ),
                        }
                        for s in signals
                    ],
                    "engine_votes": engine_votes,
                    "symbol_reports": symbol_reports,
                },
            )
            if not signals:
                journal.log("decision", {"action": "pass", "reason": "no signals"})
                blotter.heartbeat(
                    session=f"{sess_info} | mode={trade_mode}",
                    prices=prices,
                    decision=f"pass: no setups ({trade_mode} mode)",
                    signals_found=0,
                    engine_votes=engine_votes,
                    symbol_reports=symbol_reports,
                    feed_meta=feed_meta,
                )
                return

            # Ranked setups; take as many as portfolio + risk allow
            signals = sorted(
                signals,
                key=lambda s: (
                    {"A+": 4, "A": 3, "B": 2, "C": 1}.get(
                        str(getattr(s, "setup_tier", "")), 0
                    ),
                    s.confidence,
                ),
                reverse=True,
            )
            exec_cands = all_candidates or [
                {
                    "symbol": s.symbol,
                    "strategy": getattr(s, "strategy_name", ""),
                    "direction": s.side,
                    "tier": getattr(s, "setup_tier", ""),
                    "local_score": (getattr(s, "metadata", None) or {}).get(
                        "strategy_local_score"
                    ),
                    "strategy_local_score": (getattr(s, "metadata", None) or {}).get(
                        "strategy_local_score"
                    ),
                    "global_score": (getattr(s, "metadata", None) or {}).get(
                        "global_score", s.confidence
                    ),
                    "setup_id": (getattr(s, "metadata", None) or {}).get("setup_id"),
                    "score_breakdown": (getattr(s, "metadata", None) or {}).get(
                        "score_breakdown"
                    ),
                    "regime": (getattr(s, "metadata", None) or {}).get("regime"),
                    "market_timestamp": str(
                        getattr(s, "market_timestamp", "") or ""
                    ),
                }
                for s in signals
            ]
            max_open = int(cfg.get("risk", {}).get("max_open_positions", 50))
            port_state = PortfolioState(opens=list(blotter.open_positions()))
            aa_setups = list(setups) if use_pipeline else []
            for chosen in signals:
                src = next(
                    (
                        s
                        for s in (setups or [])
                        if s.symbol == chosen.symbol
                        and s.direction == chosen.side
                        and str(s.strategy_name)
                        == str(getattr(chosen, "strategy_name", "") or s.strategy_name)
                    ),
                    next(
                        (
                            s
                            for s in (setups or [])
                            if s.symbol == chosen.symbol and s.direction == chosen.side
                        ),
                        None,
                    ),
                )
                meta = dict(
                    getattr(chosen, "metadata", None)
                    or ((src.metadata if src is not None else None) or {})
                )
                setattr(chosen, "metadata", meta)
                if src is not None:
                    setattr(chosen, "setup_tier", src.setup_tier)
                    setattr(chosen, "strategy_name", src.strategy_name)
                    setattr(chosen, "market_timestamp", src.market_timestamp)

                if len(open_symbols) >= max_open:
                    exec_ledger.reject(chosen, "POSITION_LIMIT", config_version=str(cfg.get("config_version")))
                    journal.log(
                        "decision",
                        {"action": "pass", "reason": "max open positions reached"},
                    )
                    break
                if chosen.symbol in open_symbols:
                    exec_ledger.reject(chosen, "POSITION_EXISTS", config_version=str(cfg.get("config_version")))
                    continue
                intent = ExposureIntent(
                    agent_id=str(getattr(chosen, "agent_id", agent_id)),
                    symbol=str(chosen.symbol),
                    direction=str(chosen.side),
                    quantity=int(getattr(chosen, "quantity", 1) or 1),
                    strategy=str(getattr(chosen, "strategy_name", "") or ""),
                    setup_tier=str(getattr(chosen, "setup_tier", "") or ""),
                )
                ok_port, port_reason = portfolio.check(intent, port_state)
                if not ok_port:
                    reason = "PORTFOLIO_CONFLICT"
                    pr = str(port_reason).lower()
                    if "correlated" in pr:
                        reason = "CORRELATED_EXPOSURE"
                    elif "duplicate" in pr:
                        reason = "DUPLICATE_SETUP"
                    elif "opposite" in pr:
                        reason = "AGENT_CONFLICT"
                    elif "family" in pr:
                        reason = "CORRELATED_EXPOSURE"
                    exec_ledger.reject(chosen, f"{reason}:{port_reason}", config_version=str(cfg.get("config_version")))
                    journal.log(
                        "rejected_setup",
                        {
                            "symbol": chosen.symbol,
                            "side": chosen.side,
                            "tier": getattr(chosen, "setup_tier", None),
                            "reason": port_reason,
                            "agent_id": intent.agent_id,
                        },
                    )
                    continue
                if cfg.get("require_tv_alert_confluence"):
                    tv_side = pending_tv.get(chosen.symbol)
                    if tv_side != chosen.side:
                        exec_ledger.reject(
                            chosen,
                            "TV_ALERT_REQUIRED",
                            config_version=str(cfg.get("config_version")),
                        )
                        continue
                # opt_v1+ actual trades must carry global pipeline fields
                tier = str(getattr(chosen, "setup_tier", "") or "").upper()
                missing = []
                if not getattr(chosen, "strategy_name", None):
                    missing.append("strategy_name")
                if meta.get("global_score") is None:
                    missing.append("global_score")
                if tier not in {"A", "A+"}:
                    missing.append("setup_tier")
                if not str(meta.get("config_version") or cfg.get("config_version") or ""):
                    missing.append("config_version")
                if not getattr(chosen, "market_timestamp", None):
                    missing.append("market_timestamp")
                if not (meta.get("setup_id") or meta.get("setup_fingerprint")):
                    missing.append("setup_id")
                if missing:
                    exec_ledger.reject(
                        chosen,
                        f"INVALID_DECISION_RECORD:{','.join(missing)}",
                        config_version=str(cfg.get("config_version")),
                    )
                    journal.log(
                        "INVALID_DECISION_RECORD",
                        {
                            "symbol": getattr(chosen, "symbol", None),
                            "missing": missing,
                            "tier": tier,
                        },
                    )
                    logger.error("INVALID_DECISION_RECORD missing=%s", missing)
                    continue
                try:
                    open_symbols, reject_reason, order_id = handle_signal(
                        chosen,
                        cfg=cfg,
                        broker=broker,
                        risk_engine=risk_engine,
                        execution=execution,
                        journal=journal,
                        alerter=alerter,
                        open_symbols=open_symbols,
                        skip_session_check=args.skip_session_check,
                        blotter=blotter,
                    )
                except Exception as exc:
                    exec_ledger.reject(
                        chosen,
                        f"EXECUTION_ERROR:{exc}",
                        config_version=str(cfg.get("config_version")),
                    )
                    logger.exception("handle_signal failed for %s", chosen.symbol)
                    continue
                if reject_reason:
                    exec_ledger.reject(
                        chosen,
                        reject_reason,
                        config_version=str(cfg.get("config_version")),
                    )
                else:
                    exec_ledger.executed(
                        chosen,
                        str(order_id or "PAPER"),
                        config_version=str(cfg.get("config_version")),
                    )
                    portfolio.claim(intent, port_state)
                    port_state.opens = list(blotter.open_positions())
                    if use_pipeline and setups:
                        for st in setups:
                            if (
                                st.symbol == chosen.symbol
                                and st.direction == chosen.side
                            ):
                                pipeline.mark_setup_traded(st)
                                try:
                                    from agent.learning.loop import (
                                        record_candidate_snapshot,
                                    )

                                    record_candidate_snapshot(
                                        cfg,
                                        setup=st,
                                        router_decision="EXECUTED",
                                        executed_or_shadow="ACTUAL",
                                    )
                                except Exception:
                                    pass
                                break

            # Invariant: every A/A+ executable must have a terminal decision
            if use_pipeline and aa_setups:
                unresolved = exec_ledger.unresolved(aa_setups)
                for u in unresolved:
                    logger.error("UNRESOLVED_EXECUTABLE_CANDIDATE %s %s", u.symbol, u.strategy_name)
                    journal.log(
                        "UNRESOLVED_EXECUTABLE_CANDIDATE",
                        {
                            "symbol": u.symbol,
                            "strategy": u.strategy_name,
                            "tier": u.setup_tier,
                            "setup_id": (u.metadata or {}).get("setup_id"),
                        },
                    )
                    exec_ledger.reject(
                        u,
                        "UNRESOLVED_EXECUTABLE_CANDIDATE",
                        config_version=str(cfg.get("config_version")),
                    )
            # Active-market opportunity stats (exclude weekend/maintenance)
            try:
                from agent.research.opportunity_stats import OpportunityStatsStore

                n_exec = sum(
                    1
                    for d in exec_ledger._cycle
                    if d.decision == "EXECUTED"
                )
                bars_n = 0
                if use_pipeline:
                    bars_n = int((cycle_out.get("cycle_status") or {}).get("bars_processed") or 0)
                    if bars_n <= 0:
                        # Count symbols that advanced a bar this cycle
                        bars_n = sum(
                            1
                            for r in symbol_reports.values()
                            if (r.get("decision") or "")
                            not in {"NO_NEW_BAR", "DATA_STALE", "ERROR"}
                        )
                OpportunityStatsStore().record_cycle(
                    session_reason=str(sess_info),
                    bars_processed=max(bars_n, 1 if signals or all_candidates else 0),
                    candidates=list(all_candidates or exec_cands or []),
                    executions=n_exec,
                    active=bool(ok_sess),
                )
            except Exception:
                logger.exception("opportunity stats update failed")

            # Attach decisions to heartbeat candidates
            decisions = exec_ledger.latest(30)
            blotter.heartbeat(
                session=f"{sess_info} | mode={trade_mode}",
                prices=prices,
                decision=(
                    f"AGENT HEALTHY — BAR PROCESSED | executable={len(signals)} | "
                    f"decisions={len(exec_ledger._cycle)}"
                ),
                signals_found=len(signals),
                engine_votes=engine_votes,
                symbol_reports=symbol_reports,
                feed_meta={
                    **feed_meta,
                    "scan_state": "BAR_PROCESSED",
                    "status_detail": f"Executable A+/A setups: {len(signals)}",
                    "execution_decisions": decisions[:20],
                },
                candidates=exec_cands,
                last_evaluated_candidates=exec_cands,
            )
        except Exception:
            logger.exception("cycle failed")
            alerter.send("Agent cycle failed")

    if args.once:
        cycle()
        broker.disconnect()
        return 0

    try:
        from apscheduler.schedulers.blocking import BlockingScheduler
        from apscheduler.triggers.interval import IntervalTrigger

        sched = cfg.get("schedule", {})
        tz = sched.get("timezone", "America/New_York")
        interval = max(1, int(sched.get("poll_interval_minutes", 5)))
        scheduler = BlockingScheduler(timezone=tz)
        if sched.get("run_once_on_start", True):
            cycle()
        # IntervalTrigger avoids APScheduler cron bugs with sun-fri ranges.
        # Session windows inside cycle() decide when new entries are allowed.
        scheduler.add_job(
            cycle,
            IntervalTrigger(minutes=interval, timezone=tz),
            id="live_cycle",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        logger.info(
            "Scheduler ON — every %s minute(s). Entries only in Asia/London/NY windows. Ctrl+C to stop.",
            interval,
        )
        scheduler.start()
    except KeyboardInterrupt:
        logger.info("shutdown")
    except Exception:
        logger.exception("Scheduler crashed — this is a bug; restart Start Trading Agent")
        raise
    finally:
        broker.disconnect()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
