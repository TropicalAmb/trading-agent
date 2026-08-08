from __future__ import annotations

import argparse
import logging
import os
import sys
from typing import Any

from agent.alerts import Alerter
from agent.broker.ibkr import IBKRClient, MockIBKRClient
from agent.config import assert_safe_to_trade, load_settings
from agent.execution.directional import DirectionalExecutor
from agent.journal.store import Journal
from agent.market.bars import make_bar_source
from agent.risk.directional import DirectionalRiskEngine
from agent.strategy.sweep_retest import SweepRetestScanner, SweepSignal
from agent.webhook.server import start_webhook_server

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("sweep_agent")


def build_broker(cfg: dict[str, Any], use_mock: bool):
    if use_mock:
        return MockIBKRClient()
    b = cfg["broker"]
    return IBKRClient(
        host=b["host"],
        port=int(b["port"]),
        client_id=int(b["client_id"]),
        readonly=bool(b.get("readonly", False)),
    )


def handle_signal(
    signal: SweepSignal,
    *,
    cfg: dict[str, Any],
    broker,
    risk: DirectionalRiskEngine,
    execution: DirectionalExecutor,
    journal: Journal,
    alerter: Alerter,
    open_symbols: list[str],
    skip_session_check: bool,
) -> list[str]:
    account = broker.get_account_snapshot()
    journal.log("signal", {
        "symbol": signal.symbol,
        "side": signal.side,
        "entry": signal.entry,
        "stop": signal.stop,
        "target": signal.target,
        "confidence": signal.confidence,
        "risk_dollars": signal.risk_dollars,
        "reward_dollars": signal.reward_dollars,
        "reason": signal.reason,
    })

    ok, reasons = risk.evaluate(
        signal,
        account,
        open_symbols,
        skip_session_check=skip_session_check,
    )
    journal.log("risk", {"approved": ok, "reasons": reasons})
    if not ok:
        if cfg.get("alerts", {}).get("on_reject", True):
            alerter.send(f"Rejected {signal.symbol}: {'; '.join(reasons)}")
        return open_symbols

    result = execution.execute(signal)
    journal.log("order", result)
    if cfg.get("alerts", {}).get("on_fill", True):
        alerter.send(
            f"{result.get('status')} {signal.side} {signal.symbol} "
            f"target~${signal.reward_dollars:.0f} risk~${signal.risk_dollars:.0f} "
            f"conf={signal.confidence} dry_run={result.get('dry_run')}"
        )
    if signal.symbol not in open_symbols:
        open_symbols = open_symbols + [signal.symbol]
    return open_symbols


def run_scan_cycle(
    cfg: dict[str, Any],
    scanner: SweepRetestScanner,
    broker,
    risk: DirectionalRiskEngine,
    execution: DirectionalExecutor,
    journal: Journal,
    alerter: Alerter,
    open_symbols: list[str],
    *,
    skip_session_check: bool,
) -> list[str]:
    account = broker.get_account_snapshot()
    journal.log("account_snapshot", account.model_dump(mode="json"))

    signals = scanner.scan_universe()
    journal.log(
        "scan",
        {
            "count": len(signals),
            "signals": [
                {
                    "symbol": s.symbol,
                    "side": s.side,
                    "confidence": s.confidence,
                    "reward_dollars": s.reward_dollars,
                    "risk_dollars": s.risk_dollars,
                }
                for s in signals
            ],
        },
    )
    if not signals:
        journal.log("decision", {"action": "pass", "reason": "no sweep-retest signals"})
        return open_symbols

    # Take best confidence signal only (1 contract discipline)
    best = signals[0]
    return handle_signal(
        best,
        cfg=cfg,
        broker=broker,
        risk=risk,
        execution=execution,
        journal=journal,
        alerter=alerter,
        open_symbols=open_symbols,
        skip_session_check=skip_session_check,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Autonomous Sweep Retest agent (your TradingView logic)"
    )
    parser.add_argument("--config", default=None)
    parser.add_argument("--mock", action="store_true")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--skip-session-check", action="store_true")
    parser.add_argument(
        "--webhook",
        action="store_true",
        help="Listen for TradingView alerts on /tv",
    )
    args = parser.parse_args(argv)

    cfg = load_settings(args.config)
    assert_safe_to_trade(cfg)

    use_mock = args.mock or os.getenv("USE_MOCK_BROKER", "").lower() in {
        "1",
        "true",
        "yes",
    }

    journal_cfg = cfg.get("journal", {})
    journal = Journal(
        journal_cfg.get("db_path", "data/journal.db"),
        journal_cfg.get("csv_export", "data/decisions.csv"),
    )
    alerter = Alerter(cfg)
    risk = DirectionalRiskEngine(cfg)
    broker = build_broker(cfg, use_mock=use_mock)

    try:
        broker.connect()
    except Exception as exc:
        logger.error("Broker connect failed: %s", exc)
        if not use_mock:
            logger.error("Start IB Gateway paper, or use --mock for signal dry-run.")
            return 1
        raise

    scanner = SweepRetestScanner(cfg, make_bar_source(cfg))
    execution = DirectionalExecutor(broker, cfg)
    open_symbols: list[str] = []

    def on_tv(payload: dict[str, Any]) -> None:
        nonlocal open_symbols
        action = str(payload.get("action") or payload.get("side") or "").upper()
        symbol = str(payload.get("symbol") or cfg["universe"]["symbols"][0]).upper()
        if "BUY" in action:
            side = "BUY"
        elif "SELL" in action:
            side = "SELL"
        else:
            journal.log("webhook_ignore", payload)
            return

        # Build a signal from live bars + forced side from TV
        bars = make_bar_source(cfg)(symbol)
        from agent.strategy.sweep_retest import evaluate_sweep_retest

        meta = cfg.get("instruments", {}).get(symbol, {})
        sig = evaluate_sweep_retest(
            symbol, bars, cfg, point_value=float(meta.get("point_value", 5.0))
        )
        if sig is None or sig.side != side:
            # Still allow TV to force the side with fresh marks
            if sig is None:
                journal.log(
                    "webhook_no_local_confirm",
                    {"payload": payload, "note": "TV fired but local rules not confirming"},
                )
                alerter.send(f"TV {side} {symbol} ignored — local rules did not confirm")
                return
        open_symbols = handle_signal(
            sig,
            cfg=cfg,
            broker=broker,
            risk=risk,
            execution=execution,
            journal=journal,
            alerter=alerter,
            open_symbols=open_symbols,
            skip_session_check=args.skip_session_check,
        )

    logger.info(
        "Sweep agent mode=%s dry_run=%s mock=%s symbols=%s",
        cfg.get("mode"),
        cfg.get("execution", {}).get("dry_run"),
        use_mock,
        cfg.get("universe", {}).get("symbols"),
    )

    if args.webhook or cfg.get("webhook", {}).get("enabled") and not args.once:
        wh = cfg.get("webhook", {})
        start_webhook_server(
            on_tv,
            host=wh.get("host", "0.0.0.0"),
            port=int(wh.get("port", 8787)),
            secret=os.getenv("WEBHOOK_SECRET"),
        )

    def cycle() -> None:
        nonlocal open_symbols
        try:
            open_symbols = run_scan_cycle(
                cfg,
                scanner,
                broker,
                risk,
                execution,
                journal,
                alerter,
                open_symbols,
                skip_session_check=args.skip_session_check,
            )
        except Exception:
            logger.exception("Sweep cycle failed")
            alerter.send("Sweep agent cycle failed")

    if args.once:
        cycle()
        broker.disconnect()
        return 0

    try:
        from apscheduler.schedulers.blocking import BlockingScheduler
        from apscheduler.triggers.cron import CronTrigger

        sched = cfg.get("schedule", {})
        tz = sched.get("timezone", "America/New_York")
        interval = int(sched.get("poll_interval_minutes", 5))
        scheduler = BlockingScheduler(timezone=tz)
        if sched.get("run_once_on_start", True):
            cycle()
        scheduler.add_job(
            cycle,
            CronTrigger(
                day_of_week="mon-fri",
                minute=f"*/{max(1, interval)}",
                timezone=tz,
            ),
            id="sweep_cycle",
            replace_existing=True,
        )
        logger.info("Scheduler + webhook running")
        scheduler.start()
    except KeyboardInterrupt:
        logger.info("Shutting down")
    finally:
        broker.disconnect()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
