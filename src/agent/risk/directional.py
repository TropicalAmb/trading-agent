from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from agent.models import AccountSnapshot
from agent.schedule.sessions import active_session_name, session_ok
from agent.strategy.sweep_retest import SweepSignal


class DirectionalRiskEngine:
    """Hard gates for sweep-retest directional trades."""

    def __init__(self, cfg: dict[str, Any]):
        self.cfg = cfg
        self._halted = False
        self._halt_reason: Optional[str] = None

    def evaluate(
        self,
        signal: SweepSignal | None,
        account: AccountSnapshot,
        open_symbols: list[str],
        *,
        skip_session_check: bool = False,
        now: datetime | None = None,
        open_sides: dict[str, str] | None = None,
        last_fill_ts: dict[str, datetime] | None = None,
    ) -> tuple[bool, list[str]]:
        reasons: list[str] = []
        risk = self.cfg.get("risk", {})
        now = now or datetime.now(timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)

        if self._halted:
            return False, [f"halted: {self._halt_reason}"]

        kill_pct = float(risk.get("daily_loss_kill_pct", 0.03))
        if account.equity > 0:
            loss_pct = -min(0.0, account.realized_pnl_today) / account.equity
            if loss_pct >= kill_pct:
                self._halted = True
                self._halt_reason = f"daily loss {loss_pct:.2%}"
                return False, [self._halt_reason]

        if not account.healthy:
            reasons.append("broker unhealthy")

        if not skip_session_check:
            ok_sess, sess_info = session_ok(self.cfg, now)
            if not ok_sess:
                reasons.append(sess_info)

        if signal is None:
            reasons.append("no signal")
            return False, reasons

        if signal.side not in {"BUY", "SELL"}:
            reasons.append("invalid side")

        if signal.stop <= 0 or signal.target <= 0:
            reasons.append("missing stop/target")

        if signal.side == "BUY" and not (signal.stop < signal.entry < signal.target):
            reasons.append("BUY requires stop < entry < target")
        if signal.side == "SELL" and not (signal.target < signal.entry < signal.stop):
            reasons.append("SELL requires target < entry < stop")

        # Finite hard ceiling — never skip when misconfigured to 0.
        from agent.execution.risk_budget import effective_max_risk_dollars

        hard_cap = effective_max_risk_dollars(
            self.cfg, equity=float(getattr(account, "equity", 0) or 0) or None
        )
        qty = max(1, int(getattr(signal, "quantity", 1) or 1))
        # Engines report per-contract dollars; convert to position risk
        position_risk = float(signal.risk_dollars) * qty
        if position_risk > hard_cap + 1e-9:
            reasons.append(
                f"RISK_LIMIT ${position_risk:.2f} > hard cap ${hard_cap:.2f}"
            )

        min_reward = float(self.cfg.get("sweep_retest", {}).get("min_reward_dollars", 100))
        if signal.reward_dollars < min_reward:
            reasons.append(
                f"reward ${signal.reward_dollars:.0f} < min ${min_reward:.0f}"
            )

        max_open = int(risk.get("max_open_positions", 50))
        if len(open_symbols) >= max_open:
            reasons.append(f"max open positions ({max_open})")
        if signal.symbol in open_symbols:
            reasons.append(f"already in {signal.symbol}")

        # Cooldown: avoid revenge re-entries on same symbol
        cool_m = float(risk.get("symbol_cooldown_minutes", 0) or 0)
        if cool_m > 0 and last_fill_ts and signal.symbol in last_fill_ts:
            last = last_fill_ts[signal.symbol]
            if last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            age_min = (now - last).total_seconds() / 60.0
            if age_min < cool_m:
                reasons.append(
                    f"cooldown {signal.symbol} {age_min:.0f}m < {cool_m:.0f}m"
                )

        # Block opposite direction on correlated group (MES vs MNQ etc.)
        if risk.get("block_opposite_correlated", False) and open_sides:
            for group in risk.get("correlation_groups", []):
                g = {str(x).upper() for x in group}
                if signal.symbol.upper() not in g:
                    continue
                for sym, side in open_sides.items():
                    if sym.upper() in g and side.upper() != signal.side.upper():
                        reasons.append(
                            f"opposite correlated {sym} {side} vs {signal.symbol} {signal.side}"
                        )
                        break

        min_conf = int(
            self.cfg.get("growth_plan", {})
            .get("active", {})
            .get(
                "min_confidence",
                self.cfg.get("sweep_retest", {}).get("min_confidence", 65),
            )
        )
        # Asia is thinner — require higher confidence (session_quality)
        sess = active_session_name(self.cfg, now) or "globex_open"
        sess_key = "ny" if str(sess).startswith("ny") else str(sess)
        extra = int(
            self.cfg.get("session_quality", {})
            .get(sess_key, {})
            .get("extra_min_confidence", 0)
        )
        need = min_conf + extra
        if signal.confidence < need:
            reasons.append(
                f"confidence {signal.confidence} < {need} ({sess_key} quality bar)"
            )

        return len(reasons) == 0, reasons
