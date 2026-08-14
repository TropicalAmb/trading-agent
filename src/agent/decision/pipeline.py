"""Collect engine proposals → TradeSetup → global tier → rank.

Strategies propose. Tiering uses GLOBAL quality evidence.
Lone EMA pullback cannot mint A/A+ without independent confirmation.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

from agent.data.base import Bar, MarketDataProvider
from agent.data.bar_cursor import BarCursorStore
from agent.context.market_context import build_market_context
from agent.context.regime import MarketRegimeClassifier
from agent.decision.champion import champion_name
from agent.decision.global_score import format_score_breakdown, score_setup
from agent.decision.ranker import (
    select_executable_detailed,
    select_journal_only,
)
from agent.decision.setup import TradeSetup
from agent.decision.setup_identity import (
    SetupIdentityStore,
    setup_fingerprint,
    structural_setup_key,
)
from agent.decision.tiering import (
    LOCATION_STRATEGIES,
    assign_tier_for_setup,
    can_execute,
    execution_reject_reason,
)
from agent.execution.risk_budget import suggest_micro_symbol
from agent.execution.sizing import (
    fit_quantity_to_risk,
    hard_cap_from_cfg,
    resolve_trade_quantity,
)
from agent.risk.circuit_breakers import CircuitBreakerStore, StrategyHealth
from agent.runtime.observability_store import LastEvaluationStore
from agent.runtime.scan_status import classify_cycle, parse_interval_seconds
from agent.schedule.sessions import active_session_name

logger = logging.getLogger(__name__)


def _expected_r(entry: float, stop: float, target: float, side: str) -> float:
    risk = abs(entry - stop)
    reward = abs(target - entry)
    if risk <= 1e-12:
        return 0.0
    return reward / risk


def _from_engine_signal(
    *,
    strategy_name: str,
    sig: Any,
    latest: Bar,
    cfg: dict[str, Any],
    agent_id: str,
    session: Optional[str],
    point_value: float,
    qty: int,
) -> TradeSetup:
    side = str(getattr(sig, "side", getattr(sig, "direction", ""))).upper()
    entry = float(sig.entry)
    stop = float(sig.stop)
    target = float(sig.target)
    conf = int(getattr(sig, "confidence", getattr(sig, "confidence_score", 0)))
    reason = str(getattr(sig, "reason", strategy_name))
    er = _expected_r(entry, stop, target, side)
    reasons = [f"strategy:{strategy_name}", reason]
    # Provisional tier — final tier assigned after agreement / context enrichment
    risk_d = abs(entry - stop) * point_value * qty
    reward_d = abs(target - entry) * point_value * qty
    level = getattr(sig, "level", None) or getattr(sig, "pdh", None) or getattr(sig, "pdl", None)
    # Most engines act on the latest provider bar. Resampled specialists can
    # explicitly identify the completed source bar that produced their signal.
    signal_bar_ts = getattr(sig, "market_bar_timestamp", None)
    return TradeSetup(
        strategy_name=strategy_name,
        symbol=str(sig.symbol).upper(),
        direction=side,
        setup_tier="C",
        confidence_score=conf,
        entry=entry,
        stop=stop,
        target=target,
        expected_r=er,
        market_timestamp=signal_bar_ts or latest.timestamp,
        received_timestamp=latest.received_time,
        reasons=reasons,
        session=session,
        agent_id=agent_id,
        quantity=qty,
        risk_dollars=risk_d,
        reward_dollars=reward_d,
        feed_source=latest.source,
        is_realtime=latest.is_realtime,
        estimated_delay_seconds=latest.estimated_delay_seconds,
        metadata={
            "point_value": point_value,
            "strategy_local_score": conf,
            "reference_level": float(level) if level is not None else entry,
            "processing_timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )


def _enrich_context(setups: list[TradeSetup]) -> list[TradeSetup]:
    """Mark multi-engine agreement and location evidence before global tiering."""
    from collections import defaultdict

    by_sym_side: dict[tuple[str, str], list[TradeSetup]] = defaultdict(list)
    for s in setups:
        by_sym_side[(s.symbol.upper(), s.direction.upper())].append(s)

    out: list[TradeSetup] = []
    for (_sym, _side), group in by_sym_side.items():
        names = [x.strategy_name for x in group]
        has_location = any(n in LOCATION_STRATEGIES for n in names)
        for s in group:
            meta = dict(s.metadata or {})
            meta["agreeing_engines"] = names
            meta["has_location"] = has_location or s.strategy_name in LOCATION_STRATEGIES
            # Contradictions: opposite engine vote on same symbol handled upstream
            s.metadata = meta
            if len(names) >= 2:
                s.reasons = list(s.reasons) + [f"agreement:{','.join(names)}"]
                # Agreement is a bonus, not a rewrite of strategy-local score
                s.confidence_score = min(98, s.confidence_score + 4 * (len(names) - 1))
            out.append(s)
    return out


class DecisionPipeline:
    def __init__(
        self,
        cfg: dict[str, Any],
        provider: MarketDataProvider,
        cursor: BarCursorStore,
        *,
        agent_id: str = "agent_1",
        identity_store: SetupIdentityStore | None = None,
    ):
        self.cfg = cfg
        self.provider = provider
        self.cursor = cursor
        self.agent_id = agent_id
        engines = cfg.get("confluence", {}).get("engines") or [
            "ema_pullback",
            "liquidity_sweep",
            "vwap_acceptance",
            "sweep_retest",
            "momentum",
        ]
        research_only = list(cfg.get("research_only_engines") or [])
        runtime_research = bool(
            (cfg.get("shadow") or {}).get("evaluate_research_engines_live", True)
        )
        # Offline research modules remain available even when live shadow
        # evaluation is disabled. This keeps the paper runtime focused on the
        # validated book without deleting experiments or their evidence.
        runtime_names = list(engines) + (research_only if runtime_research else [])
        seen = set()
        names: list[str] = []
        for n in runtime_names:
            if n not in seen:
                seen.add(n)
                names.append(n)
        self.engine_names = names
        self.research_only_engines = set(research_only)
        id_path = (
            cfg.get("market_data", {}).get("setup_identity_path")
            or "data/setup_identities.json"
        )
        self.identities = identity_store or SetupIdentityStore(Path(id_path))
        self.regime_clf = MarketRegimeClassifier()
        self.circuits = CircuitBreakerStore(
            cfg.get("circuit_breakers", {}).get("path", "data/circuit_breakers.json")
        )
        from agent.risk.strategy_lifecycle import StrategyLifecycleStore

        lc_path = (cfg.get("strategy_lifecycle") or {}).get(
            "path", "data/strategy_lifecycle.json"
        )
        self.lifecycle = StrategyLifecycleStore(lc_path)
        self.config_version = str(cfg.get("config_version") or "opt_v1")
        obs_path = (
            cfg.get("market_data", {}).get("last_evaluation_path")
            or "data/last_evaluation.json"
        )
        self.last_eval = LastEvaluationStore(Path(obs_path))
        self.last_eval.ensure_scope(
            config_version=self.config_version,
            active_strategies=self.engine_names,
        )

    def _qty(self, symbol: str, strategy: str, *, tier: str | None = None) -> int:
        profile = self.cfg.get("agent_profile") or self.cfg.get("agent_id") or self.agent_id
        return resolve_trade_quantity(
            self.cfg,
            symbol=symbol,
            strategy=strategy,
            agent_id=str(profile),
            tier=tier,
        )

    def _size_setup(self, setup: TradeSetup) -> TradeSetup:
        """Apply tier target qty, then shrink to fit hard risk cap.

        If even 1 contract exceeds budget: for CL specialist remap to MCL
        (same stop distance, never widen stop). Otherwise SHADOW observe.
        """
        pv = float(
            (setup.metadata or {}).get("point_value")
            or self.cfg.get("instruments", {}).get(setup.symbol, {}).get("point_value", 5.0)
        )
        hard = hard_cap_from_cfg(self.cfg)
        max_q = int((self.cfg.get("quantity") or {}).get("max_quantity", 25))
        desired = resolve_trade_quantity(
            self.cfg,
            symbol=setup.symbol,
            strategy=setup.strategy_name,
            agent_id=setup.agent_id or self.agent_id,
            tier=setup.setup_tier,
        )
        qty = fit_quantity_to_risk(
            desired_qty=desired,
            entry=setup.entry,
            stop=setup.stop,
            point_value=pv,
            hard_cap_dollars=hard,
            max_quantity=max_q,
        )
        meta = dict(setup.metadata or {})
        # Specialists: remap to micro when full-size cannot fit $ risk (stop unchanged)
        spec_cfg = self.cfg.get(setup.strategy_name) or {}
        prefer_micro = bool(spec_cfg.get("prefer_micro_when_risk_exceeded", False))
        if (
            qty < 1
            and prefer_micro
            and setup.strategy_name
            in {"cl_vwap_prox_momentum", "nq_context_entry"}
        ):
            micro = suggest_micro_symbol(setup.symbol)
            if micro and micro.upper() != setup.symbol.upper():
                mpv = float(
                    self.cfg.get("instruments", {}).get(micro, {}).get("point_value", 100.0)
                )
                mqty = fit_quantity_to_risk(
                    desired_qty=max(desired, 1),
                    entry=setup.entry,
                    stop=setup.stop,
                    point_value=mpv,
                    hard_cap_dollars=hard,
                    max_quantity=max_q,
                )
                if mqty >= 1:
                    meta["remapped_from"] = setup.symbol
                    setup.symbol = micro.upper()
                    pv = mpv
                    qty = mqty
                    meta["contract_remap"] = f"{meta['remapped_from']}→{setup.symbol}"
        setup.quantity = int(qty)
        setup.risk_dollars = abs(setup.entry - setup.stop) * pv * max(qty, 0)
        setup.reward_dollars = abs(setup.target - setup.entry) * pv * max(qty, 0)
        meta["point_value"] = pv
        meta["desired_quantity"] = desired
        meta["sized_quantity"] = qty
        meta["risk_cap_dollars"] = hard
        if qty < 1:
            meta["sizing_reject"] = f"RISK_LIMIT even 1 contract > ${hard:.0f}"
            meta["execution_mode"] = "SHADOW"
            micro = suggest_micro_symbol(setup.symbol)
            if micro:
                meta["suggest_micro"] = micro
                meta["sizing_reject"] += f" (prefer {micro} or reject)"
        # Refresh cascade RISK line after sizing
        if meta.get("cascade_log"):
            try:
                from agent.decision.cascade import format_cascade_summary

                setup.metadata = meta
                # temporarily attach sized fields
                cas = dict(meta.get("cascade") or {})
                risk_line = (
                    f"RISK: PASS — {setup.symbol} {qty} contract(s), "
                    f"${setup.risk_dollars:.0f} risk (cap ${hard:.0f})"
                    if qty >= 1
                    else f"RISK: FAIL — exceeds ${hard:.0f} even at 1 lot"
                )
                log = [x for x in list(meta.get("cascade_log") or []) if not str(x).startswith("RISK")]
                # replace RISK READY line
                log = [x for x in log if not str(x).startswith("RISK:")]
                log.append(risk_line)
                if qty >= 1 and meta.get("cascade_decision") == "EXECUTE_PAPER":
                    log.append("Decision: EXECUTE PAPER")
                    meta["cascade_decision"] = "EXECUTE_PAPER"
                elif qty < 1:
                    log.append("Decision: SHADOW — risk cap")
                    meta["cascade_decision"] = "SHADOW"
                meta["cascade_log"] = log
                cas["layer_log"] = log
                meta["cascade"] = cas
                meta["cascade_summary"] = format_cascade_summary(setup)
            except Exception:
                pass
        setup.metadata = meta
        return setup

    def _hard_risk_ok(self, setup: TradeSetup) -> tuple[bool, str]:
        hard = hard_cap_from_cfg(self.cfg)
        # Position-level risk already includes quantity
        if setup.quantity < 1:
            return False, (setup.metadata or {}).get("sizing_reject") or "RISK_LIMIT qty=0"
        if setup.risk_dollars > hard + 1e-9:
            return False, f"RISK_LIMIT ${setup.risk_dollars:.2f} > ${hard:.2f}"
        return True, "ok"

    def _eval_engines(
        self,
        symbol: str,
        df,
        point_value: float,
        *,
        engine_dfs: dict[str, Any] | None = None,
    ) -> list[tuple[str, Any, Optional[str]]]:
        from agent.strategy.breakout_retest import evaluate_breakout_retest
        from agent.strategy.ema_pullback import evaluate_ema_pullback
        from agent.strategy.liquidity_reversal import evaluate_liquidity_reversal
        from agent.strategy.liquidity_sweep import evaluate_liquidity_sweep
        from agent.strategy.momentum import evaluate_momentum
        from agent.strategy.opening_range import evaluate_opening_range
        from agent.strategy.sweep_retest import evaluate_sweep_retest
        from agent.strategy.trend_continuation import evaluate_trend_continuation
        from agent.strategy.trend_pullback import evaluate_trend_pullback
        from agent.strategy.vwap_acceptance import evaluate_vwap_acceptance
        from agent.strategy.vwap_mss import evaluate_vwap_mss
        from agent.strategy.vwap_orb import evaluate_vwap_orb
        from agent.strategy.vwap_reclaim import evaluate_vwap_reclaim
        from agent.strategy.vwap_rejection import evaluate_vwap_rejection
        from agent.strategy.indicator_parity import evaluate_indicator_parity
        from agent.strategy.specialist_momentum import (
            evaluate_cl_vwap_prox_momentum,
            evaluate_nq_ny_open_momentum,
        )
        from agent.strategy.nq_context_entry import evaluate_nq_context_entry

        fns: dict[str, Callable] = {
            "ema_pullback": evaluate_ema_pullback,
            "liquidity_sweep": evaluate_liquidity_sweep,
            "vwap_acceptance": evaluate_vwap_acceptance,
            "sweep_retest": evaluate_sweep_retest,
            "vwap_orb": evaluate_vwap_orb,
            "vwap_mss": evaluate_vwap_mss,
            "momentum": evaluate_momentum,
            "breakout_retest": evaluate_breakout_retest,
            "trend_continuation": evaluate_trend_continuation,
            "opening_range": evaluate_opening_range,
            # Additive simple specialists (same TradeSetup interface)
            "trend_pullback": evaluate_trend_pullback,
            "liquidity_reversal": evaluate_liquidity_reversal,
            "vwap_reclaim": evaluate_vwap_reclaim,
            "vwap_rejection": evaluate_vwap_rejection,
            "indicator_parity": evaluate_indicator_parity,
            "cl_vwap_prox_momentum": evaluate_cl_vwap_prox_momentum,
            "nq_ny_open_momentum": evaluate_nq_ny_open_momentum,
            "nq_context_entry": evaluate_nq_context_entry,
        }
        engine_dfs = engine_dfs or {}
        out: list[tuple[str, Any, Optional[str]]] = []
        for name in self.engine_names:
            fn = fns.get(name)
            if not fn:
                out.append((name, None, "unknown_engine"))
                continue
            try:
                use_df = engine_dfs.get(name, df)
                sig = fn(symbol, use_df, self.cfg, point_value=point_value)
                if sig is None:
                    out.append((name, None, "no_setup"))
                else:
                    out.append((name, sig, None))
            except Exception as exc:
                logger.exception("engine %s failed %s", name, symbol)
                out.append((name, None, f"error:{exc}"))
        return out

    def scan_cycle(self) -> dict[str, Any]:
        """Run one full decision cycle. Returns diagnostics + executable setups."""
        symbols = list(self.cfg.get("universe", {}).get("symbols") or [])
        interval = (
            self.cfg.get("market_data", {}).get("bar_interval")
            or self.cfg.get("sweep_retest", {}).get("bar_interval", "5m")
        )
        period = (
            self.cfg.get("market_data", {}).get("bar_period")
            or self.cfg.get("sweep_retest", {}).get("bar_period", "10d")
        )
        session = active_session_name(self.cfg)
        received = datetime.now(timezone.utc)

        symbol_reports: dict[str, Any] = {}
        raw_setups: list[TradeSetup] = []
        suppressed: list[dict[str, Any]] = []

        for symbol in symbols:
            report: dict[str, Any] = {
                "symbol": symbol,
                "engines": {},
                "candidates": [],
                "decision": "PASS",
                "reason": "",
            }
            try:
                bars = self.provider.get_bars(symbol, interval=interval, period=period)
            except TimeoutError as exc:
                report["reason"] = f"DATA_TIMEOUT:{exc}"
                report["decision"] = "PASS"
                prev = self.last_eval.get_symbol(symbol)
                if prev:
                    report["regime"] = prev.get("regime")
                    report["market_context"] = prev.get("market_context")
                    report["last_candidates"] = prev.get("candidates") or []
                    report["last_evaluated_market_bar"] = prev.get("market_bar")
                    report["context_age_minutes"] = self.last_eval.context_age_minutes(symbol)
                symbol_reports[symbol] = report
                logger.warning("symbol %s data timeout: %s", symbol, exc)
                continue
            except Exception as exc:
                msg = str(exc)
                if "DATA_TIMEOUT" in msg or "timeout" in msg.lower():
                    report["reason"] = f"DATA_TIMEOUT:{exc}"
                else:
                    report["reason"] = f"DATA_ERROR:{exc}"
                report["decision"] = "PASS"
                prev = self.last_eval.get_symbol(symbol)
                if prev:
                    report["regime"] = prev.get("regime")
                    report["market_context"] = prev.get("market_context")
                    report["last_candidates"] = prev.get("candidates") or []
                    report["last_evaluated_market_bar"] = prev.get("market_bar")
                    report["context_age_minutes"] = self.last_eval.context_age_minutes(symbol)
                symbol_reports[symbol] = report
                logger.warning("symbol %s data failed: %s", symbol, exc)
                continue

            if not bars:
                report["reason"] = "DATA_EMPTY"
                symbol_reports[symbol] = report
                continue

            latest = bars[-1]
            report["market_time"] = latest.timestamp.isoformat()
            report["received_time"] = latest.received_time.isoformat()
            report["price"] = latest.close
            report["delay_sec"] = round(latest.estimated_delay_seconds, 1)
            report["is_realtime"] = latest.is_realtime
            report["source"] = latest.source
            report["bar_interval"] = (latest.metadata or {}).get("bar_interval", interval)
            report["bar_interval_seconds"] = (latest.metadata or {}).get(
                "bar_interval_seconds", parse_interval_seconds(interval)
            )

            if latest.is_stale:
                report["reason"] = "DATA_STALE"
                report["decision"] = "PASS"
                prev = self.last_eval.get_symbol(symbol)
                if prev:
                    report["regime"] = prev.get("regime")
                    report["market_context"] = prev.get("market_context")
                    report["last_candidates"] = prev.get("candidates") or []
                    report["last_evaluated_market_bar"] = prev.get("market_bar")
                    report["context_age_minutes"] = self.last_eval.context_age_minutes(symbol)
                symbol_reports[symbol] = report
                continue

            last = self.cursor.get(symbol)
            pending = []
            for b in bars:
                bt = b.timestamp.replace(tzinfo=None) if b.timestamp.tzinfo else b.timestamp
                if last is None:
                    if b is latest:
                        pending.append(b)
                    continue
                lt = last.replace(tzinfo=None) if last.tzinfo else last
                if bt > lt:
                    pending.append(b)

            if not pending:
                report["reason"] = "NO_NEW_BAR"
                report["decision"] = "PASS"
                # Persist last valid context/candidates — do not clear on wait ticks
                prev = self.last_eval.get_symbol(symbol)
                if prev:
                    report["engines"] = prev.get("engines") or {}
                    report["regime"] = prev.get("regime")
                    report["market_context"] = prev.get("market_context")
                    report["last_candidates"] = prev.get("candidates") or []
                    report["candidates"] = []  # current scan has none
                    report["last_evaluated_market_bar"] = prev.get("market_bar")
                    report["context_age_minutes"] = self.last_eval.context_age_minutes(symbol)
                    report["scan_state"] = "NO_NEW_BAR"
                symbol_reports[symbol] = report
                continue

            pending = pending[-3:]
            pv = float(self.cfg.get("instruments", {}).get(symbol, {}).get("point_value", 5.0))
            sym_setups: list[TradeSetup] = []
            # Accumulate engine votes across pending bars (last vote wins per engine)
            engine_votes: dict[str, dict[str, Any]] = {}

            # Strategy-specific 1m bars for indicator_parity (does not change book 5m path)
            engine_dfs_base: dict[str, Any] = {}
            if "indicator_parity" in self.engine_names:
                ip_cfg = self.cfg.get("indicator_parity") or {}
                ip_interval = str(ip_cfg.get("bar_interval") or "1m")
                ip_period = str(ip_cfg.get("bar_period") or "7d")
                try:
                    ip_bars = self.provider.get_bars(
                        symbol, interval=ip_interval, period=ip_period
                    )
                    if ip_bars:
                        engine_dfs_base["indicator_parity"] = self.provider.to_dataframe(
                            ip_bars
                        )
                except Exception as exc:
                    logger.warning(
                        "indicator_parity 1m fetch failed %s: %s (fallback to book bars)",
                        symbol,
                        exc,
                    )

            for bar in pending:
                df_all = self.provider.to_dataframe(bars)
                try:
                    df = df_all.loc[: bar.timestamp]
                except Exception:
                    df = df_all
                if len(df) < 30:
                    self.cursor.set(symbol, bar.timestamp)
                    continue
                engine_dfs = dict(engine_dfs_base)
                if "indicator_parity" in engine_dfs:
                    try:
                        engine_dfs["indicator_parity"] = engine_dfs[
                            "indicator_parity"
                        ].loc[: bar.timestamp]
                    except Exception:
                        pass
                engine_results = self._eval_engines(
                    symbol, df, pv, engine_dfs=engine_dfs
                )
                for name, sig, why in engine_results:
                    if sig is None:
                        # Do not erase a real vote from an earlier pending bar
                        prev = engine_votes.get(name) or {}
                        if prev.get("result") not in (None, "none", ""):
                            continue
                        engine_votes[name] = {
                            "result": "none",
                            "because": why or "no_setup",
                            "market_bar": bar.timestamp.isoformat(),
                        }
                        continue
                    # Provisional 1-lot for fingerprinting; final qty after tier + risk fit
                    setup = _from_engine_signal(
                        strategy_name=name,
                        sig=sig,
                        latest=bar,
                        cfg=self.cfg,
                        agent_id=self.agent_id,
                        session=session,
                        point_value=pv,
                        qty=1,
                    )
                    ok_risk, risk_why = self._hard_risk_ok(setup)
                    if not ok_risk:
                        engine_votes[name] = {
                            "result": "none",
                            "because": risk_why,
                            "tier": "C",
                            "confidence": setup.confidence_score,
                            "market_bar": bar.timestamp.isoformat(),
                        }
                        suppressed.append(
                            {
                                "symbol": symbol,
                                "strategy": name,
                                "reason": risk_why,
                                "tier": "C",
                            }
                        )
                        continue
                    level = (setup.metadata or {}).get("reference_level")
                    fp = setup_fingerprint(
                        symbol=setup.symbol,
                        strategy=setup.strategy_name,
                        direction=setup.direction,
                        market_bar_ts=setup.market_timestamp,
                        entry=setup.entry,
                        level=level,
                    )
                    sk = structural_setup_key(
                        symbol=setup.symbol,
                        strategy=setup.strategy_name,
                        direction=setup.direction,
                        level=level,
                        entry=setup.entry,
                    )
                    setup.metadata["setup_fingerprint"] = fp
                    setup.metadata["setup_id"] = fp
                    setup.metadata["structural_key"] = sk
                    horizon_m = float(
                        (self.cfg.get("shadow") or {}).get("research_horizon_minutes", 180)
                    )
                    if self.identities.already_traded(fp) or self.identities.already_traded(sk):
                        engine_votes[name] = {
                            "result": "none",
                            "because": "SUPPRESSED_DUPLICATE_SETUP",
                            "tier": setup.setup_tier,
                            "confidence": setup.confidence_score,
                            "strategy_local_score": (setup.metadata or {}).get(
                                "strategy_local_score"
                            ),
                            "market_bar": bar.timestamp.isoformat(),
                            "setup_id": fp,
                        }
                        suppressed.append(
                            {
                                "symbol": symbol,
                                "strategy": name,
                                "reason": "SUPPRESSED_DUPLICATE_SETUP",
                                "fingerprint": fp,
                                "structural_key": sk,
                            }
                        )
                        continue
                    if self.identities.already_seen(sk, max_age_seconds=horizon_m * 60.0):
                        engine_votes[name] = {
                            "result": "none",
                            "because": "SUPPRESSED_DUPLICATE_SETUP",
                            "tier": setup.setup_tier,
                            "confidence": setup.confidence_score,
                            "strategy_local_score": (setup.metadata or {}).get(
                                "strategy_local_score"
                            ),
                            "market_bar": bar.timestamp.isoformat(),
                            "setup_id": fp,
                        }
                        suppressed.append(
                            {
                                "symbol": symbol,
                                "strategy": name,
                                "reason": "SUPPRESSED_DUPLICATE_SETUP",
                                "fingerprint": fp,
                                "structural_key": sk,
                            }
                        )
                        continue
                    # Cooldown so next 5m bar of same zone does not open another shadow
                    self.identities.mark_seen(sk)
                    # Keep latest setup per strategy within this symbol catch-up
                    sym_setups = [
                        s for s in sym_setups if s.strategy_name != name
                    ]
                    sym_setups.append(setup)
                    # Strip obsolete conf= from reason — scores are separate fields
                    because = setup.reasons[-1] if setup.reasons else ""
                    if " conf=" in because:
                        because = because.split(" conf=")[0]
                    engine_votes[name] = {
                        "result": setup.direction,
                        "tier": "pending",
                        "confidence": setup.confidence_score,
                        "strategy_local_score": setup.confidence_score,
                        "because": because,
                        "market_bar": bar.timestamp.isoformat(),
                        "entry": setup.entry,
                        "stop": setup.stop,
                        "target": setup.target,
                        "setup_id": fp,
                    }
                self.cursor.set(symbol, bar.timestamp)

            report["engines"] = engine_votes
            report["market_time"] = pending[-1].timestamp.isoformat()
            report["received_time"] = pending[-1].received_time.isoformat()
            report["price"] = pending[-1].close
            report["delay_sec"] = round(pending[-1].estimated_delay_seconds, 1)

            # Market context / regime from last evaluated df (completed bars only)
            try:
                df_ctx = self.provider.to_dataframe(bars)
                df_ctx = df_ctx.loc[: pending[-1].timestamp]
            except Exception:
                df_ctx = self.provider.to_dataframe(bars)
            regime = self.regime_clf.classify(df_ctx)
            ctx = build_market_context(df_ctx, cfg=self.cfg, regime_result=regime)
            report["regime"] = {
                "regime": regime.regime.value,
                "confidence": regime.confidence,
                "reasons": list(regime.reasons),
            }
            report["market_context"] = {
                "direction_15m": ctx.direction_15m,
                "direction_1h": ctx.direction_1h,
                "direction_4h": ctx.direction_4h,
                "above_vwap": ctx.above_vwap,
                "below_vwap": ctx.below_vwap,
                "ema_bull": ctx.ema_bull,
                "ema_bear": ctx.ema_bear,
                "overextended_long": ctx.overextended_long,
                "overextended_short": ctx.overextended_short,
            }
            report["last_evaluated_market_bar"] = report["market_time"]
            report["context_age_minutes"] = 0.0
            report["scan_state"] = "BAR_PROCESSED"
            self.last_eval.update_symbol(
                symbol,
                {
                    "market_bar": report["market_time"],
                    "evaluated_at": datetime.now(timezone.utc).isoformat(),
                    "regime": report.get("regime"),
                    "market_context": report.get("market_context"),
                    "candidates": [],
                    "engines": report.get("engines") or {},
                },
            )

            if not sym_setups:
                report["reason"] = "no candidate from any engine"
                report["decision"] = "PASS"
                symbol_reports[symbol] = report
                continue

            enriched = _enrich_context(sym_setups)

            scored: list[TradeSetup] = []
            for s in enriched:
                hard: list[str] = []
                if latest.is_stale:
                    hard.append("DATA_STALE")
                health = self.circuits.status(s.strategy_name, session or "other", self.cfg)
                if health == StrategyHealth.PAUSED_TEMP:
                    hard.append("STRATEGY_PAUSED_TEMP")
                    s.metadata = dict(s.metadata or {})
                    s.metadata["circuit_state"] = health.value
                gs = score_setup(s, ctx, self.cfg, hard_invalidations=hard)
                meta = dict(s.metadata or {})
                meta["global_score"] = gs.score
                meta["families_positive"] = list(gs.families_positive)
                meta["has_location"] = gs.has_location or bool(meta.get("has_location"))
                meta["hard_invalidations"] = list(gs.hard_invalidations)
                meta["contradictions"] = list(gs.contradictions)
                meta["score_breakdown"] = format_score_breakdown(gs)
                meta["score_components"] = [
                    {"name": c.name, "points": c.points, "reason": c.reason, "family": c.family}
                    for c in gs.components
                ]
                meta["regime"] = ctx.regime.value
                meta["regime_confidence"] = ctx.regime_confidence
                meta["config_version"] = self.config_version
                # Per-strategy version (CL specialist keeps explicit v1 stamp)
                strat_ver_cfg = (self.cfg.get(s.strategy_name) or {}).get("strategy_version")
                meta["strategy_version"] = str(
                    strat_ver_cfg or champion_name(self.cfg, s.strategy_name)
                )
                # Global paper stamp (book-level) for before/after journals
                meta["book_strategy_version"] = str(
                    self.cfg.get("strategy_version") or meta["strategy_version"]
                )
                meta["paper_config_version"] = self.config_version
                if s.strategy_name in self.research_only_engines:
                    meta["research_only"] = True
                    meta["execution_mode"] = "SHADOW"
                # Strategy lifecycle (kill/drift) — additive; does not replace circuit breakers
                try:
                    lc_state = self.lifecycle.get_state(s.strategy_name, s.symbol)
                    meta["lifecycle_state"] = lc_state
                    if lc_state in {"SHADOW_ONLY", "HARD_PAUSED"}:
                        meta["execution_mode"] = "SHADOW"
                        meta["cell_health"] = lc_state
                        hard = list(meta.get("hard_invalidations") or [])
                        hard.append(f"LIFECYCLE_{lc_state}")
                        meta["hard_invalidations"] = hard
                    elif lc_state == "WATCH":
                        meta["lifecycle_watch"] = True
                except Exception:
                    meta["lifecycle_state"] = "ACTIVE"
                # Five-layer cascade (context + optional POOR_FIT hard reject)
                s.metadata = meta
                if bool((self.cfg.get("trade_cascade") or {}).get("enabled", True)):
                    try:
                        from agent.decision.cascade import attach_cascade_to_setup

                        s = attach_cascade_to_setup(
                            s,
                            df_ctx,
                            self.cfg,
                            lifecycle_state=str(meta.get("lifecycle_state") or "ACTIVE"),
                            market_context=ctx,
                        )
                        meta = dict(s.metadata or {})
                    except Exception:
                        pass
                # Entry-time feature snapshot for learning loop (no lookahead)
                try:
                    from agent.learning.features import snapshot_entry_features

                    meta["entry_features"] = snapshot_entry_features(
                        s,
                        ctx,
                        agreeing_n=len(list(meta.get("agreeing_engines") or [])),
                    )
                except Exception:
                    pass
                s.metadata = meta
                # Keep strategy-local score; confidence_score becomes global for ranking display
                s.confidence_score = int(round(gs.score))
                s.setup_tier = assign_tier_for_setup(s, self.cfg)
                self._size_setup(s)
                meta = dict(s.metadata or {})
                s.metadata = meta
                if s.strategy_name in report["engines"]:
                    report["engines"][s.strategy_name]["tier"] = s.setup_tier
                    report["engines"][s.strategy_name]["global_score"] = gs.score
                    report["engines"][s.strategy_name]["strategy_local_score"] = meta.get(
                        "strategy_local_score"
                    )
                    report["engines"][s.strategy_name]["breakdown"] = meta["score_breakdown"]
                    report["engines"][s.strategy_name]["quantity"] = s.quantity
                    report["engines"][s.strategy_name]["desired_quantity"] = meta.get(
                        "desired_quantity"
                    )
                if s.quantity < 1:
                    # Finite risk kept — observe as SHADOW research, do not execute
                    meta["execution_mode"] = "SHADOW"
                    s.metadata = meta
                    suppressed.append(
                        {
                            "symbol": symbol,
                            "strategy": s.strategy_name,
                            "reason": meta.get("sizing_reject") or "RISK_LIMIT qty=0 → SHADOW",
                            "tier": s.setup_tier,
                        }
                    )
                scored.append(s)

            scored.sort(
                key=lambda s: (
                    {"A+": 4, "A": 3, "B": 2, "C": 1}.get(s.setup_tier, 0),
                    float((s.metadata or {}).get("global_score") or s.confidence_score),
                ),
                reverse=True,
            )
            report["candidates"] = [
                {
                    "symbol": s.symbol,
                    "strategy": s.strategy_name,
                    "direction": s.direction,
                    "tier": s.setup_tier,
                    "confidence": s.confidence_score,
                    "strategy_local_score": (s.metadata or {}).get("strategy_local_score"),
                    "local_score": (s.metadata or {}).get("strategy_local_score"),
                    "global_score": (s.metadata or {}).get("global_score"),
                    "router_evidence": (s.metadata or {}).get("router_evidence"),
                    "entry_features": (s.metadata or {}).get("entry_features"),
                    "quality_predictions": (s.metadata or {}).get("quality_predictions"),
                    "router_v1_decision": (s.metadata or {}).get("router_v1_decision"),
                    "high_confidence_shadow": (s.metadata or {}).get("high_confidence_shadow"),
                    "regime": (s.metadata or {}).get("regime"),
                    "score_breakdown": (s.metadata or {}).get("score_breakdown"),
                    "setup_id": (s.metadata or {}).get("setup_id"),
                    "structural_key": (s.metadata or {}).get("structural_key"),
                    "expected_r": round(s.expected_r, 2),
                    "quantity": s.quantity,
                    "desired_quantity": (s.metadata or {}).get("desired_quantity"),
                    "risk_dollars": round(s.risk_dollars, 2),
                    "reward_dollars": round(float(s.reward_dollars or 0), 2),
                    "cascade": (s.metadata or {}).get("cascade"),
                    "execution_reject_reason": execution_reject_reason(s, self.cfg),
                    "research_only": bool((s.metadata or {}).get("research_only")),
                    "execution_mode": (s.metadata or {}).get("execution_mode"),
                    "entry": s.entry,
                    "stop": s.stop,
                    "target": s.target,
                    "market_timestamp": s.market_timestamp.isoformat()
                    if hasattr(s.market_timestamp, "isoformat")
                    else str(s.market_timestamp),
                    "received_timestamp": s.received_timestamp.isoformat()
                    if hasattr(s.received_timestamp, "isoformat")
                    else str(s.received_timestamp),
                }
                for s in scored
            ]
            report["last_candidates"] = list(report["candidates"])
            report["last_evaluated_market_bar"] = report["market_time"]
            report["context_age_minutes"] = 0.0
            report["scan_state"] = "BAR_PROCESSED"
            # Persist for NO_NEW_BAR ticks
            self.last_eval.update_symbol(
                symbol,
                {
                    "market_bar": report["market_time"],
                    "evaluated_at": datetime.now(timezone.utc).isoformat(),
                    "regime": report.get("regime"),
                    "market_context": report.get("market_context"),
                    "candidates": report["candidates"],
                    "engines": report.get("engines") or {},
                },
            )
            raw_setups.extend(scored)

            best = scored[0]
            if can_execute(best, self.cfg):
                report["decision"] = "CANDIDATE"
                report["reason"] = (
                    f"{best.setup_tier} via {best.strategy_name} "
                    f"global={(best.metadata or {}).get('global_score')} "
                    f"local={(best.metadata or {}).get('strategy_local_score')}"
                )
                report["chosen"] = {
                    "strategy": best.strategy_name,
                    "tier": best.setup_tier,
                    "side": best.direction,
                    "confidence": best.confidence_score,
                    "strategy_local_score": (best.metadata or {}).get("strategy_local_score"),
                    "global_score": (best.metadata or {}).get("global_score"),
                    "breakdown": (best.metadata or {}).get("score_breakdown"),
                    "setup_id": (best.metadata or {}).get("setup_id"),
                }
            else:
                report["decision"] = "PASS"
                g = (best.metadata or {}).get("global_score")
                report["reason"] = (
                    f"no candidate >= {self.cfg.get('tiering', {}).get('minimum_trade_tier', 'A')} "
                    f"(best={best.setup_tier} {best.strategy_name} "
                    f"global={g} local={(best.metadata or {}).get('strategy_local_score')})"
                )
            symbol_reports[symbol] = report

        # Agreement boost + empirical router rank; capture superseded A/A+ (must not vanish)
        executable, superseded = select_executable_detailed(raw_setups, self.cfg)
        for s in executable:
            s.setup_tier = assign_tier_for_setup(s, self.cfg)
            self._size_setup(s)
        quality_rejected: list[tuple[TradeSetup, str]] = []
        kept_exec: list[TradeSetup] = []
        for s in executable:
            if s.quantity < 1:
                quality_rejected.append(
                    (
                        s,
                        str(
                            (s.metadata or {}).get("sizing_reject")
                            or "RISK_LIMIT:qty=0"
                        ),
                    )
                )
                continue
            reason = execution_reject_reason(s, self.cfg)
            if reason is None:
                kept_exec.append(s)
            else:
                quality_rejected.append((s, reason))
                meta = dict(s.metadata or {})
                meta["nonselected_reason"] = reason
                s.metadata = meta
        executable = kept_exec
        journal_only = select_journal_only(raw_setups, self.cfg)

        # Flat list of every candidate responsible for setup counts
        all_candidates = []
        for rep in symbol_reports.values():
            all_candidates.extend(rep.get("candidates") or [])
        # Attach router evidence onto candidate report rows after ranking stage
        by_id = {
            (s.metadata or {}).get("setup_id"): s
            for s in raw_setups
            if (s.metadata or {}).get("setup_id")
        }
        for c in all_candidates:
            sid = c.get("setup_id")
            if sid and sid in by_id:
                c["router_evidence"] = (by_id[sid].metadata or {}).get("router_evidence")
                c["global_score"] = (by_id[sid].metadata or {}).get("global_score", c.get("global_score"))
        processed_bar = any(
            str((report or {}).get("scan_state") or "") == "BAR_PROCESSED"
            for report in symbol_reports.values()
        )
        if all_candidates or processed_bar:
            bar_times = [
                c.get("market_timestamp")
                for c in all_candidates
                if c.get("market_timestamp")
            ]
            self.last_eval.set_last_candidates(
                all_candidates,
                market_bar=bar_times[0] if bar_times else None,
                allow_empty=processed_bar,
            )
        last_candidates = all_candidates or self.last_eval.last_candidates()
        cycle_status = classify_cycle(
            symbol_reports, executable_count=len(executable)
        )

        def _shadow_row(s: TradeSetup, *, reason: str) -> dict[str, Any]:
            return {
                "symbol": s.symbol,
                "side": s.direction,
                "direction": s.direction,
                "tier": s.setup_tier,
                "confidence": s.confidence_score,
                "strategy": s.strategy_name,
                "strategy_name": s.strategy_name,
                "entry": s.entry,
                "stop": s.stop,
                "target": s.target,
                "expected_r": s.expected_r,
                "quantity": s.quantity,
                "point_value": (s.metadata or {}).get("point_value", 5.0),
                "market_timestamp": str(s.market_timestamp),
                "received_timestamp": str(s.received_timestamp),
                "session": s.session,
                "agent_id": s.agent_id,
                "global_score": (s.metadata or {}).get("global_score"),
                "strategy_local_score": (s.metadata or {}).get("strategy_local_score"),
                "score_breakdown": (s.metadata or {}).get("score_breakdown"),
                "regime": (s.metadata or {}).get("regime"),
                "router_evidence": (s.metadata or {}).get("router_evidence"),
                "config_version": (s.metadata or {}).get("config_version"),
                "strategy_version": (s.metadata or {}).get("strategy_version"),
                "setup_id": (s.metadata or {}).get("setup_id"),
                "structural_key": (s.metadata or {}).get("structural_key"),
                "nonselected_reason": reason,
                "shadow_track": True,
            }

        nonselected_valid = [
            _shadow_row(a, reason=f"AGREEMENT_SUPERSEDED_BY_{b.strategy_name}")
            for a, b in superseded
            if can_execute(a, self.cfg) or str(a.setup_tier).upper() in {"A", "A+", "B"}
        ]
        for s, reason in quality_rejected:
            if str(s.setup_tier).upper() in {"A", "A+", "B"}:
                nonselected_valid.append(_shadow_row(s, reason=reason))

        superseded_rows = [
            {
                "loser": {
                    "symbol": a.symbol,
                    "strategy": a.strategy_name,
                    "tier": a.setup_tier,
                    "setup_id": (a.metadata or {}).get("setup_id"),
                    "global_score": (a.metadata or {}).get("global_score"),
                    "router_evidence": (a.metadata or {}).get("router_evidence"),
                    "entry": a.entry,
                    "stop": a.stop,
                    "target": a.target,
                    "direction": a.direction,
                    "session": a.session,
                    "regime": (a.metadata or {}).get("regime"),
                    "structural_key": (a.metadata or {}).get("structural_key"),
                    "point_value": (a.metadata or {}).get("point_value", 5.0),
                    "quantity": a.quantity,
                    "expected_r": a.expected_r,
                    "confidence": a.confidence_score,
                    "strategy_local_score": (a.metadata or {}).get(
                        "strategy_local_score"
                    ),
                    "score_breakdown": (a.metadata or {}).get("score_breakdown"),
                    "config_version": (a.metadata or {}).get("config_version"),
                    "strategy_version": (a.metadata or {}).get("strategy_version"),
                    "market_timestamp": str(a.market_timestamp),
                    "received_timestamp": str(a.received_timestamp),
                    "agent_id": a.agent_id,
                },
                "winner": {
                    "symbol": b.symbol,
                    "strategy": b.strategy_name,
                    "tier": b.setup_tier,
                    "setup_id": (b.metadata or {}).get("setup_id"),
                    "global_score": (b.metadata or {}).get("global_score"),
                    "router_evidence": (b.metadata or {}).get("router_evidence"),
                },
                "reason": f"AGREEMENT_SUPERSEDED_BY_{b.strategy_name}",
            }
            for a, b in superseded
        ]
        # Paperable A/A+ killed by quality gates must appear in the ledger (not vanish)
        for s, reason in quality_rejected:
            if str(s.setup_tier).upper() not in {"A", "A+"}:
                continue
            superseded_rows.append(
                {
                    "loser": {
                        "symbol": s.symbol,
                        "strategy": s.strategy_name,
                        "tier": s.setup_tier,
                        "setup_id": (s.metadata or {}).get("setup_id"),
                        "global_score": (s.metadata or {}).get("global_score"),
                        "router_evidence": (s.metadata or {}).get("router_evidence"),
                        "entry": s.entry,
                        "stop": s.stop,
                        "target": s.target,
                        "direction": s.direction,
                        "session": s.session,
                        "regime": (s.metadata or {}).get("regime"),
                        "structural_key": (s.metadata or {}).get("structural_key"),
                        "point_value": (s.metadata or {}).get("point_value", 5.0),
                        "quantity": s.quantity,
                        "expected_r": s.expected_r,
                        "confidence": s.confidence_score,
                        "strategy_local_score": (s.metadata or {}).get(
                            "strategy_local_score"
                        ),
                        "score_breakdown": (s.metadata or {}).get("score_breakdown"),
                        "config_version": (s.metadata or {}).get("config_version"),
                        "strategy_version": (s.metadata or {}).get("strategy_version"),
                        "market_timestamp": str(s.market_timestamp),
                        "received_timestamp": str(s.received_timestamp),
                        "agent_id": s.agent_id,
                    },
                    "winner": {},
                    "reason": reason,
                }
            )

        return {
            "received_time": received.isoformat(),
            "session": session,
            "agent_id": self.agent_id,
            "symbol_reports": symbol_reports,
            "executable": executable,
            "journal_only": journal_only,
            "nonselected_valid": nonselected_valid,
            "quality_rejected": [
                {"symbol": s.symbol, "strategy": s.strategy_name, "tier": s.setup_tier, "reason": r}
                for s, r in quality_rejected
            ],
            "superseded": superseded_rows,
            "all_candidates": all_candidates,
            "last_evaluated_candidates": last_candidates,
            "suppressed": suppressed,
            "provider_health": self.provider.health().__dict__,
            "cycle_status": {
                "primary": cycle_status.primary,
                "detail": cycle_status.detail,
                "scan_state": cycle_status.scan_state,
            },
            "bar_interval": interval,
            "bar_interval_seconds": parse_interval_seconds(interval),
            "scheduler_note": "Scheduler interval is separate (poll_interval_minutes)",
        }

    def mark_setup_traded(self, setup: TradeSetup) -> None:
        fp = (setup.metadata or {}).get("setup_fingerprint") or (
            setup.metadata or {}
        ).get("setup_id")
        if not fp:
            fp = setup_fingerprint(
                symbol=setup.symbol,
                strategy=setup.strategy_name,
                direction=setup.direction,
                market_bar_ts=setup.market_timestamp,
                entry=setup.entry,
                level=(setup.metadata or {}).get("reference_level"),
            )
        sk = (setup.metadata or {}).get("structural_key") or structural_setup_key(
            symbol=setup.symbol,
            strategy=setup.strategy_name,
            direction=setup.direction,
            level=(setup.metadata or {}).get("reference_level"),
            entry=setup.entry,
        )
        meta = {
            "symbol": setup.symbol,
            "strategy": setup.strategy_name,
            "tier": setup.setup_tier,
            "agent_id": setup.agent_id,
        }
        self.identities.mark_traded(fp, meta)
        self.identities.mark_traded(sk, meta)
