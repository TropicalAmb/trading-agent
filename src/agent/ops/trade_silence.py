"""Autonomous paper-trade silence / blocker diagnostics.

When no paper fill has occurred for a while during an open session, classify
likely blockers (research supersede, quality gates, stale heartbeat, etc.)
and persist an alert for the dashboard + watchdog — so the user does not have
to babysit.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from agent.schedule.sessions import futures_market_open


SEVERITY_OK = "OK"
SEVERITY_INFO = "INFO"
SEVERITY_WARN = "WARN"
SEVERITY_ALERT = "ALERT"

BLOCKER_RESEARCH_SUPERSEDE = "RESEARCH_SUPERSEDE_DOMINANT"
BLOCKER_QUALITY_GATE = "QUALITY_GATE_DOMINANT"
BLOCKER_RISK_PORTFOLIO = "RISK_OR_PORTFOLIO_BLOCKS"
BLOCKER_NO_EXECUTABLE = "NO_EXECUTABLE_CANDIDATES"
BLOCKER_HEALTHY_SELECTIVE_QUIET = "HEALTHY_SELECTIVE_QUIET"
BLOCKER_PIPELINE_DROUGHT = "PIPELINE_DROUGHT"
BLOCKER_DATA_STALE_STUCK = "DATA_STALE_STUCK"
BLOCKER_PREFLIGHT_FAIL = "PREFLIGHT_PAPER_PATH_FAIL"
BLOCKER_MARKET_CLOSED = "MARKET_CLOSED"
BLOCKER_STOPPED = "STOP_AGENT_SET"
BLOCKER_STALE_HEARTBEAT = "STALE_HEARTBEAT"
BLOCKER_EXEC_ERROR = "EXECUTION_ERROR_SEEN"
BLOCKER_CODE_BUG = "CODE_BUG_RESTART_WILL_NOT_FIX"
BLOCKER_CONFIG_ENTRY_GATE = "CONFIG_ENTRY_GATE"
BLOCKER_UNKNOWN = "UNKNOWN_SILENCE"

# Exceptions that a process restart cannot heal — need a code patch
_CODE_BUG_MARKERS = (
    "cannot access local variable",
    "unboundlocalerror",
    "nameerror",
    "syntaxerror",
    "indentationerror",
    "modulenotfounderror",
    "importerror",
    "attributeerror",
)


@dataclass
class TradeSilenceReport:
    ts: str
    severity: str
    summary: str
    minutes_since_last_paper: Optional[float]
    last_paper_opened_at: Optional[str]
    market_open: bool
    market_reason: str
    heartbeat_age_sec: Optional[float]
    shadow_open: int
    recent_rejects: int
    recent_executed: int
    top_reject_reasons: list[tuple[str, int]] = field(default_factory=list)
    blocker_codes: list[str] = field(default_factory=list)
    recommended_action: str = ""
    auto_restart_suggested: bool = False
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _parse_ts(value: Any) -> Optional[datetime]:
    if value is None or value == "":
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _age_sec(ts: Optional[datetime], now: datetime) -> Optional[float]:
    if ts is None:
        return None
    return (now - ts).total_seconds()


def _tail_jsonl(path: Path, limit: int = 250) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception:
        return []
    out: list[dict[str, Any]] = []
    for ln in lines[-limit:]:
        ln = ln.strip()
        if not ln:
            continue
        try:
            out.append(json.loads(ln))
        except Exception:
            continue
    return out


def _last_paper_open(blotter: dict[str, Any]) -> tuple[Optional[datetime], Optional[str]]:
    best: Optional[datetime] = None
    best_s: Optional[str] = None
    for t in blotter.get("trades") or []:
        # Prefer market open time
        raw = t.get("opened_at") or t.get("market_timestamp") or t.get("ts")
        dt = _parse_ts(raw)
        if dt is None:
            continue
        if best is None or dt > best:
            best = dt
            best_s = str(raw)
    for t in blotter.get("open_positions") or []:
        raw = t.get("opened_at") or t.get("market_timestamp")
        dt = _parse_ts(raw)
        if dt is None:
            continue
        if best is None or dt > best:
            best = dt
            best_s = str(raw)
    return best, best_s


def _is_code_bug_reason(reason: str) -> bool:
    r = (reason or "").lower()
    if "execution_error" not in r and "error:" not in r:
        return False
    return any(m in r for m in _CODE_BUG_MARKERS)


def _classify_reject(reason: str, *, strategy: str = "", cfg: dict[str, Any] | None = None) -> str:
    r = (reason or "").upper()
    if _is_code_bug_reason(reason):
        return BLOCKER_CODE_BUG
    if "AGREEMENT_SUPERSEDED_BY_" in r:
        research = {str(x) for x in ((cfg or {}).get("research_only_engines") or [])}
        loser = str(strategy or "")
        # Research-vs-research supersedes are ledger noise, not paper steal.
        if loser and loser in research:
            return "RESEARCH_NOISE"
        winner = r.split("AGREEMENT_SUPERSEDED_BY_", 1)[-1].strip().lower()
        # Normalize winner token to engine id (underscores already)
        if winner in research or any(w.replace("-", "_") == winner for w in research):
            return BLOCKER_RESEARCH_SUPERSEDE
        # Paperable beat by another paperable — not research steal
        return "AGREEMENT_PAPER"
    if any(
        x in r
        for x in (
            "REWARD",
            "MIN_REWARD",
            "EXPECTED_R",
            "MIXED",
            "POOR_LOCATION",
            "EXECUTION_QUALITY",
            "RESEARCH_ONLY",
        )
    ):
        return BLOCKER_QUALITY_GATE
    if any(
        x in r
        for x in (
            "RISK_LIMIT",
            "CORRELATED",
            "POSITION_EXISTS",
            "FAMILY",
            "DAILY_LOSS",
            "HALT",
        )
    ):
        return BLOCKER_RISK_PORTFOLIO
    if "EXECUTION_ERROR" in r or "ERROR:" in r:
        return BLOCKER_EXEC_ERROR
    return BLOCKER_UNKNOWN


def _specialists_only_paper_mode(cfg: dict[str, Any]) -> bool:
    """True when drought policy opts in and only paper_specialist_engines can fill."""
    dcfg = cfg.get("trade_drought_policy") or {}
    if not bool(dcfg.get("specialists_only_selective_quiet", False)):
        return False
    specs = {str(x) for x in (cfg.get("paper_specialist_engines") or [])}
    if not specs:
        return False
    research = {str(x) for x in (cfg.get("research_only_engines") or [])}
    engines = {str(x) for x in ((cfg.get("confluence") or {}).get("engines") or [])}
    paperable = {e for e in engines if e not in research}
    return bool(paperable) and paperable.issubset(specs)


def diagnose_trade_silence(
    *,
    root: Path,
    cfg: dict[str, Any],
    now: Optional[datetime] = None,
) -> TradeSilenceReport:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    wcfg = cfg.get("trade_silence_watch") or {}
    dcfg = cfg.get("trade_drought_policy") or {}
    # User lock: ~1.5h open-session drought = fault (not "healthy quiet")
    drought_m = float(dcfg.get("max_quiet_minutes", wcfg.get("warn_after_minutes", 90)))
    warn_m = drought_m
    alert_m = drought_m
    lookback = int(wcfg.get("lookback_decisions", 200))
    drought_enabled = bool(dcfg.get("enabled", True))
    decisions_path = Path(
        wcfg.get("decisions_path") or (root / "data" / "execution_decisions.jsonl")
    )
    if not decisions_path.is_absolute():
        decisions_path = root / decisions_path
    blotter_path = root / "data" / "paper_trades.json"
    sp = (cfg.get("shadow") or {}).get("path", "data/shadow_trades.json")
    shadow_path = Path(sp) if Path(sp).is_absolute() else root / sp
    stop_path = root / "data" / "STOP_AGENT"

    market_open, market_reason = futures_market_open(cfg, now)

    blotter: dict[str, Any] = {}
    if blotter_path.exists():
        try:
            blotter = json.loads(blotter_path.read_text(encoding="utf-8"))
        except Exception:
            blotter = {}

    hb = blotter.get("heartbeat") or {}
    hb_age = _age_sec(_parse_ts(hb.get("ts")), now)
    last_open_dt, last_open_s = _last_paper_open(blotter)

    # Silence clock resets when config_version changes (new quality regime),
    # so morning spray-era fills don't ALERT all evening after a selectivity deploy.
    regime_path = root / "data" / "trade_silence_regime.json"
    cfg_ver = str(cfg.get("config_version") or "")
    regime_start: Optional[datetime] = None
    try:
        if regime_path.exists():
            reg = json.loads(regime_path.read_text(encoding="utf-8"))
            if str(reg.get("config_version") or "") == cfg_ver:
                regime_start = _parse_ts(reg.get("started_at"))
        if regime_start is None and cfg_ver:
            regime_start = now
            regime_path.parent.mkdir(parents=True, exist_ok=True)
            regime_path.write_text(
                json.dumps(
                    {
                        "config_version": cfg_ver,
                        "started_at": now.isoformat(),
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
    except Exception:
        regime_start = None

    anchor = last_open_dt
    if regime_start is not None and (anchor is None or regime_start > anchor):
        anchor = regime_start
    mins_since = None
    if anchor is not None:
        mins_since = (now - anchor).total_seconds() / 60.0
    elif market_open:
        mins_since = alert_m + 1

    shadow_open = 0
    if shadow_path.exists():
        try:
            sh = json.loads(shadow_path.read_text(encoding="utf-8"))
            shadow_open = len(sh.get("open") or [])
        except Exception:
            shadow_open = 0

    rows = _tail_jsonl(decisions_path, lookback)
    # Silence context: since last paper open (or all tailed rows)
    since_open = rows
    if last_open_dt is not None:
        filtered = []
        for r in rows:
            rt = _parse_ts(r.get("cycle_ts") or r.get("ts") or r.get("timestamp"))
            if rt is None or rt >= last_open_dt:
                filtered.append(r)
        if filtered:
            since_open = filtered

    # Bug-pattern window: only *recent* rejects (avoid stale EMA supersede history)
    bug_window_m = float(wcfg.get("bug_window_minutes", 45))
    bug_cutoff = now - __import__("datetime").timedelta(minutes=bug_window_m)
    recent_bug: list[dict[str, Any]] = []
    for r in rows:
        rt = _parse_ts(r.get("cycle_ts") or r.get("ts") or r.get("timestamp"))
        if rt is not None and rt >= bug_cutoff:
            recent_bug.append(r)
    if not recent_bug:
        recent_bug = since_open[-40:] if since_open else []

    executed = [r for r in since_open if str(r.get("decision") or "").upper() == "EXECUTED"]
    rejected = [r for r in since_open if str(r.get("decision") or "").upper() == "REJECTED"]
    bug_rejected = [r for r in recent_bug if str(r.get("decision") or "").upper() == "REJECTED"]
    reason_counts = Counter(str(r.get("reason") or "UNKNOWN") for r in rejected)
    top_reasons = reason_counts.most_common(8)

    class_counts: Counter[str] = Counter()
    for r in bug_rejected:
        class_counts[
            _classify_reject(
                str(r.get("reason") or ""),
                strategy=str(r.get("strategy") or ""),
                cfg=cfg,
            )
        ] += 1

    blockers: list[str] = []
    severity = SEVERITY_OK
    summary = "Paper path OK (recent fill or market closed / intentional quiet)."
    action = "none"
    auto_restart = False
    scan_text = str(hb.get("scan_state") or hb.get("decision") or "")
    scan_upper = scan_text.upper()
    config_entry_gate = any(
        marker in scan_upper
        for marker in (
            "SKIP_FRIDAY_ENTRIES",
            "NY_OPEN_ENTRY_DELAY",
            "OUTSIDE ENABLED SESSION WINDOWS",
        )
    )

    if stop_path.exists():
        blockers = [BLOCKER_STOPPED]
        severity = SEVERITY_INFO
        summary = "STOP_AGENT is set — bot intentionally stopped."
        action = "Start Trading Agent when you want it running again."
    elif hb_age is not None and hb_age > float(
        (cfg.get("observability") or {}).get("scheduler_stuck_seconds", 150)
    ):
        blockers = [BLOCKER_STALE_HEARTBEAT]
        severity = SEVERITY_ALERT
        summary = f"Scheduler heartbeat stale ({hb_age:.0f}s) — agent may be hung."
        action = "Watchdog should restart supervisor; verify data/supervisor_status.json."
        auto_restart = True
    elif not market_open:
        blockers = [BLOCKER_MARKET_CLOSED]
        severity = SEVERITY_OK
        summary = f"Market closed ({market_reason}) — silence expected."
        action = "none"
    elif mins_since is not None and mins_since < warn_m:
        blockers = []
        severity = SEVERITY_OK
        summary = (
            f"Last paper/regime anchor {mins_since:.0f}m ago — "
            f"within {warn_m:.0f}m drought window."
        )
        action = "none"
    else:
        # Past drought threshold while market open → fault clock (never ease gates)
        silent_m = mins_since if mins_since is not None else alert_m + 1
        severity = SEVERITY_ALERT
        preflight_ok: bool | None = None
        preflight_err = ""
        try:
            import importlib.util

            spec = importlib.util.spec_from_file_location(
                "preflight_paper_path",
                root / "scripts" / "preflight_paper_path.py",
            )
            if spec is None or spec.loader is None:
                raise RuntimeError("preflight module missing")
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            mod.run_preflight(cfg)
            preflight_ok = True
        except Exception as exc:
            preflight_ok = False
            preflight_err = str(exc)

        if class_counts.get(BLOCKER_CODE_BUG, 0) >= 1:
            blockers.append(BLOCKER_CODE_BUG)
        if preflight_ok is False:
            blockers.append(BLOCKER_PREFLIGHT_FAIL)
            blockers.append(BLOCKER_CODE_BUG)
        if class_counts.get(BLOCKER_RESEARCH_SUPERSEDE, 0) >= max(
            3, len(bug_rejected) // 3 or 1
        ):
            blockers.append(BLOCKER_RESEARCH_SUPERSEDE)
        if class_counts.get(BLOCKER_EXEC_ERROR, 0) >= 1:
            blockers.append(BLOCKER_EXEC_ERROR)
        if class_counts.get(BLOCKER_QUALITY_GATE, 0) >= max(3, len(bug_rejected) // 4 or 1):
            blockers.append(BLOCKER_QUALITY_GATE)
        if class_counts.get(BLOCKER_RISK_PORTFOLIO, 0) >= max(3, len(bug_rejected) // 4 or 1):
            blockers.append(BLOCKER_RISK_PORTFOLIO)
        if "DATA_STALE" in scan_upper:
            blockers.append(BLOCKER_DATA_STALE_STUCK)
        if config_entry_gate:
            blockers.append(BLOCKER_CONFIG_ENTRY_GATE)
        if not blockers:
            # Path may be OK but still no paper — still a fault after 90m (user lock)
            # Exception: specialists-only paper — no-setup silence is intentional.
            if drought_enabled and not _specialists_only_paper_mode(cfg):
                blockers.append(BLOCKER_PIPELINE_DROUGHT)
            else:
                blockers.append(BLOCKER_HEALTHY_SELECTIVE_QUIET)

        if BLOCKER_HEALTHY_SELECTIVE_QUIET in blockers and len(blockers) == 1:
            specialist_names = " / ".join(
                str(x) for x in (cfg.get("paper_specialist_engines") or [])
            ) or "configured specialists"
            severity = SEVERITY_OK
            summary = (
                f"No paper fill for {silent_m:.0f}m — specialists-only selective quiet "
                f"({specialist_names}). Not a drought fault."
            )
            action = "none"
            auto_restart = False
        elif BLOCKER_CODE_BUG in blockers or BLOCKER_PREFLIGHT_FAIL in blockers:
            code_samples = [
                str(r.get("reason") or "")
                for r in bug_rejected
                if _is_code_bug_reason(str(r.get("reason") or ""))
            ][:2]
            summary = (
                f"No paper fill for {silent_m:.0f}m — CODE/PREFLIGHT FAIL "
                f"(restart will NOT fix). preflight_ok={preflight_ok} "
                f"err={preflight_err!r} samples={code_samples}"
            )
            action = (
                "CODE PATCH REQUIRED. Do not thrash-restart. "
                "Run scripts/preflight_paper_path.py; see DEBUG.md bug P."
            )
            auto_restart = False
        elif BLOCKER_CONFIG_ENTRY_GATE in blockers:
            summary = (
                f"No paper fill for {silent_m:.0f}m — market is open but a global "
                f"entry schedule gate is blocking the book ({scan_text})."
            )
            action = (
                "Configuration change required; restarting cannot remove an intentional "
                "entry gate. Keep exchange maintenance/weekend closures intact."
            )
            auto_restart = False
        elif BLOCKER_RESEARCH_SUPERSEDE in blockers:
            summary = (
                f"No paper fill for {silent_m:.0f}m — research/shadow engines superseding "
                f"paper setups. Rejects={len(rejected)} shadows_open={shadow_open}."
            )
            action = "Auto-restart once; verify ranker paperable pool (DEBUG.md bug M)."
            auto_restart = True
        elif BLOCKER_EXEC_ERROR in blockers:
            summary = (
                f"No paper fill for {silent_m:.0f}m — EXECUTION_ERROR in recent decisions."
            )
            action = "Watchdog may auto-restart once. If UnboundLocalError-class → CODE_BUG."
            auto_restart = True
        elif BLOCKER_DATA_STALE_STUCK in blockers:
            summary = (
                f"No paper fill for {silent_m:.0f}m — DATA_STALE while market open "
                f"(feed/cursor stuck)."
            )
            action = "Check Yahoo feed + bar cursor; watchdog may restart agent once."
            auto_restart = True
        elif BLOCKER_PIPELINE_DROUGHT in blockers:
            summary = (
                f"No paper fill for {silent_m:.0f}m (≥{drought_m:.0f}m drought fault). "
                f"Preflight OK; inspect engine votes + execution_decisions. "
                f"Do NOT loosen quality gates."
            )
            action = (
                "PIPELINE_DROUGHT: one cooldown restart to clear stuck runtime; "
                "then inspect votes/decisions. Gates stay; no EMA spray."
            )
            # One restart can clear hung cursors / wedged loops; cooldown prevents thrash
            auto_restart = True
        elif BLOCKER_QUALITY_GATE in blockers or BLOCKER_RISK_PORTFOLIO in blockers:
            summary = (
                f"No paper fill for {silent_m:.0f}m — rejects dominated by "
                f"{'quality' if BLOCKER_QUALITY_GATE in blockers else 'risk/portfolio'}."
            )
            action = (
                "Still a drought fault after 90m — one cooldown restart, then inspect "
                "top rejects; do not re-enable EMA spray or silently raise risk."
            )
            auto_restart = True
        else:
            summary = (
                f"No paper fill for {silent_m:.0f}m — unclear cause after drought threshold."
            )
            action = "One cooldown restart; then check blotter votes / last_evaluation / runtime log."
            auto_restart = True

    report = TradeSilenceReport(
        ts=now.isoformat(),
        severity=severity,
        summary=summary,
        minutes_since_last_paper=round(mins_since, 1) if mins_since is not None else None,
        last_paper_opened_at=last_open_s,
        market_open=market_open,
        market_reason=market_reason,
        heartbeat_age_sec=round(hb_age, 1) if hb_age is not None else None,
        shadow_open=shadow_open,
        recent_rejects=len(rejected),
        recent_executed=len(executed),
        top_reject_reasons=[(a, int(b)) for a, b in top_reasons],
        blocker_codes=blockers,
        recommended_action=action,
        auto_restart_suggested=auto_restart
        and bool(wcfg.get("auto_restart_on_bug_patterns", True)),
        details={
            "warn_after_minutes": warn_m,
            "alert_after_minutes": alert_m,
            "max_quiet_minutes": drought_m,
            "drought_enabled": drought_enabled,
            "specialists_only_selective_quiet": _specialists_only_paper_mode(cfg),
            "bug_window_minutes": bug_window_m,
            "bug_reject_count": len(bug_rejected),
            "class_counts": dict(class_counts),
            "config_entry_gate": config_entry_gate,
            "scan_state": hb.get("scan_state"),
            "decision": hb.get("decision"),
            "config_version": cfg.get("config_version"),
            "regime_started_at": regime_start.isoformat() if regime_start else None,
            "silence_anchor": "regime" if (
                regime_start and (last_open_dt is None or regime_start > last_open_dt)
            ) else "last_paper",
        },
    )
    return report


def persist_report(report: TradeSilenceReport, root: Path, cfg: dict[str, Any]) -> Path:
    wcfg = cfg.get("trade_silence_watch") or {}
    status_rel = wcfg.get("path", "data/trade_silence_status.json")
    log_rel = wcfg.get("log_path", "data/trade_silence.log")
    status_path = root / status_rel if not Path(status_rel).is_absolute() else Path(status_rel)
    log_path = root / log_rel if not Path(log_rel).is_absolute() else Path(log_rel)
    status_path.parent.mkdir(parents=True, exist_ok=True)
    status_path.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
    if report.severity in {SEVERITY_WARN, SEVERITY_ALERT}:
        with log_path.open("a", encoding="utf-8") as f:
            f.write(
                f"{report.ts} {report.severity} blockers={report.blocker_codes} "
                f"mins={report.minutes_since_last_paper} | {report.summary}\n"
            )
    return status_path


def run_trade_silence_watch(
    root: Path | str,
    cfg: dict[str, Any] | None = None,
    *,
    now: Optional[datetime] = None,
) -> TradeSilenceReport:
    root = Path(root)
    if cfg is None:
        from agent.config import load_settings

        cfg = load_settings(root / "config" / "settings.yaml")
    wcfg = cfg.get("trade_silence_watch") or {}
    if not bool(wcfg.get("enabled", True)):
        report = TradeSilenceReport(
            ts=datetime.now(timezone.utc).isoformat(),
            severity=SEVERITY_OK,
            summary="trade_silence_watch disabled",
            minutes_since_last_paper=None,
            last_paper_opened_at=None,
            market_open=False,
            market_reason="disabled",
            heartbeat_age_sec=None,
            shadow_open=0,
            recent_rejects=0,
            recent_executed=0,
        )
        return report
    report = diagnose_trade_silence(root=root, cfg=cfg, now=now)
    persist_report(report, root, cfg)
    return report
