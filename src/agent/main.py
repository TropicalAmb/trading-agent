from __future__ import annotations

import argparse
import logging
import os
import sys
from typing import Any

from agent.advisor.claude import ClaudeAdvisor
from agent.alerts import Alerter
from agent.broker.ibkr import IBKRClient, MockIBKRClient
from agent.config import assert_safe_to_trade, load_settings
from agent.execution.orders import ExecutionService
from agent.journal.store import Journal
from agent.management.exits import PositionBook, evaluate_exits
from agent.market_data import MarketDataService
from agent.models import DecisionAction
from agent.risk.engine import RiskEngine
from agent.strategy.credit_spreads import CreditSpreadScanner

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("agent")


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


def manage_open_positions(
    cfg: dict[str, Any],
    broker,
    book: PositionBook,
    journal: Journal,
    alerter: Alerter,
) -> None:
    open_positions = book.list_open()
    if not open_positions:
        return

    spots: dict[str, float] = {}
    for pos in open_positions:
        if pos.underlying not in spots:
            try:
                spot, _ = broker.get_spot(pos.underlying)
                spots[pos.underlying] = spot
            except Exception:
                logger.exception("Failed spot for %s", pos.underlying)

    signals = evaluate_exits(open_positions, spots, cfg)
    journal.log(
        "manage",
        {
            "open": len(open_positions),
            "signals": [s.model_dump(mode="json") for s in signals],
        },
    )

    dry_run = bool(cfg.get("execution", {}).get("dry_run", True))
    for sig in signals:
        book.close(sig.position_id, sig.mark_debit, sig.pnl)
        journal.log("exit", sig.model_dump(mode="json"))
        msg = (
            f"EXIT {sig.reason.value} id={sig.position_id} "
            f"pnl=${sig.pnl:.2f} debit={sig.mark_debit:.2f} dry_run={dry_run}"
        )
        logger.info(msg)
        if cfg.get("alerts", {}).get("on_fill", True):
            alerter.send(msg)


def run_cycle(
    cfg: dict[str, Any],
    broker,
    scanner: CreditSpreadScanner,
    advisor: ClaudeAdvisor,
    risk: RiskEngine,
    execution: ExecutionService,
    journal: Journal,
    alerter: Alerter,
    book: PositionBook,
    *,
    skip_session_check: bool = False,
) -> None:
    account = broker.get_account_snapshot()
    # Merge tracked book into account open underlyings for risk correlation
    tracked = book.list_open()
    if tracked:
        underlyings = sorted(set(account.open_underlyings) | {p.underlying for p in tracked})
        account.open_underlyings = underlyings
        account.open_positions = max(account.open_positions, len(underlyings))

    journal.log("account_snapshot", account.model_dump(mode="json"))

    # Always manage exits first
    manage_open_positions(cfg, broker, book, journal, alerter)

    # Refresh after exits
    tracked = book.list_open()
    underlyings = sorted(set(account.open_underlyings) | {p.underlying for p in tracked})
    account.open_underlyings = underlyings
    account.open_positions = len(underlyings)

    pre = risk.evaluate(None, account, skip_session_check=skip_session_check)
    if pre.halt_trading or pre.kill_switch:
        journal.log("kill_switch", {"reasons": pre.reasons})
        if cfg.get("alerts", {}).get("on_kill_switch", True):
            alerter.send(f"KILL SWITCH: {'; '.join(pre.reasons)}")
        return

    candidates = scanner.scan_universe()
    journal.log(
        "scan",
        {
            "count": len(candidates),
            "candidates": [c.model_dump(mode="json") for c in candidates[:20]],
        },
    )

    if not candidates:
        journal.log("decision", {"action": "pass", "reason": "no candidates"})
        return

    decision = advisor.decide(candidates, account)
    journal.log("advisor", decision.model_dump(mode="json"))

    if decision.action != DecisionAction.TRADE or decision.candidate_index is None:
        journal.log("decision", {"action": "pass", "rationale": decision.rationale})
        return

    chosen = candidates[decision.candidate_index]
    verdict = risk.evaluate(chosen, account, skip_session_check=skip_session_check)
    journal.log("risk", verdict.model_dump(mode="json"))

    if verdict.kill_switch:
        if cfg.get("alerts", {}).get("on_kill_switch", True):
            alerter.send(f"KILL SWITCH: {'; '.join(verdict.reasons)}")
        return

    if not verdict.approved or verdict.sized_candidate is None:
        journal.log(
            "reject",
            {"reasons": verdict.reasons, "candidate": chosen.model_dump(mode="json")},
        )
        if cfg.get("alerts", {}).get("on_reject", True):
            alerter.send(f"Rejected: {'; '.join(verdict.reasons)}")
        return

    result = execution.execute(verdict.sized_candidate)
    journal.log("order", result.model_dump(mode="json"))

    # Track for management even on dry_run so demo/paper can practice exits
    if result.status in {"DRY_RUN", "Submitted", "Filled", "PreSubmitted"} or result.dry_run:
        pos = book.open_from_candidate(verdict.sized_candidate)
        journal.log("position_opened", pos.model_dump(mode="json"))

    if cfg.get("alerts", {}).get("on_fill", True):
        alerter.send(
            f"Order {result.status} dry_run={result.dry_run} "
            f"{verdict.sized_candidate.underlying} {verdict.sized_candidate.spread_type.value} "
            f"credit={verdict.sized_candidate.credit:.2f}"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Autonomous credit-spread trading agent")
    parser.add_argument("--config", default=None, help="Path to settings.yaml")
    parser.add_argument("--mock", action="store_true", help="Use MockIBKR")
    parser.add_argument("--once", action="store_true", help="Single cycle then exit")
    parser.add_argument(
        "--skip-session-check",
        action="store_true",
        help="Allow outside RTH (testing)",
    )
    args = parser.parse_args(argv)

    cfg = load_settings(args.config)
    assert_safe_to_trade(cfg)
    cfg.setdefault(
        "management",
        {
            "profit_take_frac_of_credit": 0.50,
            "stop_loss_mult_of_credit": 2.0,
            "time_exit_dte": 21,
            "force_close_dte": 7,
        },
    )

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
    book = PositionBook(journal_cfg.get("positions_db_path", "data/positions.db"))
    alerter = Alerter(cfg)
    risk = RiskEngine(cfg)
    advisor = ClaudeAdvisor(cfg)

    broker = build_broker(cfg, use_mock=use_mock)
    try:
        broker.connect()
    except Exception as exc:
        logger.error("Broker connect failed: %s", exc)
        if not use_mock:
            logger.error(
                "Is IB Gateway/TWS running? Or run: .\\scripts\\run-demo.ps1"
            )
            return 1
        raise

    market = MarketDataService(broker, cfg)
    scanner = CreditSpreadScanner(market, cfg)
    execution = ExecutionService(broker, cfg)

    logger.info(
        "Starting agent mode=%s dry_run=%s mock=%s",
        cfg.get("mode"),
        cfg.get("execution", {}).get("dry_run"),
        use_mock,
    )

    def cycle() -> None:
        try:
            run_cycle(
                cfg,
                broker,
                scanner,
                advisor,
                risk,
                execution,
                journal,
                alerter,
                book,
                skip_session_check=args.skip_session_check,
            )
        except Exception:
            logger.exception("Cycle failed")
            alerter.send("Agent cycle failed — see logs")

    if args.once:
        cycle()
        broker.disconnect()
        return 0

    try:
        from apscheduler.schedulers.blocking import BlockingScheduler
        from apscheduler.triggers.cron import CronTrigger

        sched = cfg.get("schedule", {})
        tz = sched.get("timezone", "America/New_York")
        interval = int(sched.get("poll_interval_minutes", 15))
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
            id="trading_cycle",
            replace_existing=True,
        )
        logger.info("Scheduler started (every %s min, tz=%s)", interval, tz)
        scheduler.start()
    except KeyboardInterrupt:
        logger.info("Shutting down")
    finally:
        broker.disconnect()
    return 0


if __name__ == "__main__":
    sys.exit(main())
