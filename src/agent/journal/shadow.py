"""Full hypothetical lifecycle for B (and challenger) shadow setups."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


def _parse_ts(raw: Any) -> Optional[datetime]:
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw.replace(tzinfo=None) if raw.tzinfo else raw
    try:
        t = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        return t.replace(tzinfo=None) if t.tzinfo else t
    except Exception:
        return None


class ShadowTracker:
    """Tracks SHADOW trades without affecting equity / open risk / limits."""

    def __init__(self, path: str | Path = "data/shadow_trades.json"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._state: dict[str, Any] = {"open": [], "closed": []}
        self._load()

    def _load(self) -> None:
        if self.path.exists():
            try:
                self._state = json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:
                self._state = {"open": [], "closed": []}
        self._state.setdefault("open", [])
        self._state.setdefault("closed", [])

    def _save(self) -> None:
        self.path.write_text(json.dumps(self._state, indent=2, default=str), encoding="utf-8")

    def has_open_structural(self, structural_key: str) -> bool:
        sk = str(structural_key or "")
        if not sk:
            return False
        for t in self._state.get("open") or []:
            if t.get("status") == "OPEN" and str(t.get("structural_key") or "") == sk:
                return True
        return False

    def open_shadow(self, row: dict[str, Any]) -> dict[str, Any] | None:
        """Open a shadow trade. Returns None if duplicate structural setup already open."""
        structural = str(row.get("structural_key") or row.get("setup_id") or "")
        setup_id = str(row.get("setup_id") or row.get("setup_fingerprint") or structural)
        if structural and self.has_open_structural(structural):
            return None
        # Also suppress identical setup_id still open
        if setup_id:
            for t in self._state.get("open") or []:
                if t.get("status") == "OPEN" and str(t.get("setup_id") or "") == setup_id:
                    return None

        trade = {
            "id": f"SHADOW-{len(self._state['open']) + len(self._state['closed']) + 1:05d}",
            "execution_mode": "SHADOW",
            "status": "OPEN",
            "opened_at": row.get("market_timestamp") or datetime.now(timezone.utc).isoformat(),
            "received_at": row.get("received_timestamp"),
            "symbol": row.get("symbol"),
            "side": row.get("side") or row.get("direction"),
            "strategy": row.get("strategy") or row.get("strategy_name"),
            "tier": row.get("tier") or row.get("setup_tier"),
            "entry": float(row["entry"]),
            "stop": float(row["stop"]),
            "target": float(row["target"]),
            "qty": int(row.get("qty") or row.get("quantity") or 1),
            "point_value": float(row.get("point_value") or 5.0),
            "regime": row.get("regime", "UNKNOWN"),
            "global_score": row.get("global_score"),
            "strategy_local_score": row.get("strategy_local_score"),
            "score_breakdown": row.get("score_breakdown"),
            "session": row.get("session"),
            "agent_id": row.get("agent_id", "agent_1"),
            "config_version": row.get("config_version"),
            "strategy_version": row.get("strategy_version"),
            "setup_id": setup_id,
            "structural_key": structural,
            "shadow_age_bars": 0,
            "shadow_age_minutes": 0.0,
            "mae_pts": 0.0,
            "mfe_pts": 0.0,
            "mae_r": 0.0,
            "mfe_r": 0.0,
            "mae_dollars": 0.0,
            "mfe_dollars": 0.0,
            "pnl_dollars": None,
            "result": "OPEN",
        }
        self._state["open"].append(trade)
        self._save()
        return trade

    def mark_prices(self, prices: dict[str, float], *, cfg: dict[str, Any] | None = None) -> None:
        """Backward-compatible close-only marks."""
        bars = {
            sym: {"high": float(px), "low": float(px), "close": float(px)}
            for sym, px in prices.items()
        }
        self.mark_bars(bars, cfg=cfg or {})

    def mark_bars(
        self,
        bars: dict[str, dict[str, Any]],
        *,
        cfg: dict[str, Any] | None = None,
        bar_interval_minutes: float = 5.0,
    ) -> None:
        """Advance MAE/MFE and resolve using bar high/low (completed bars)."""
        cfg = cfg or {}
        scfg = cfg.get("shadow") or {}
        max_bars = int(scfg.get("research_horizon_bars", 36))
        max_minutes = float(scfg.get("research_horizon_minutes", max_bars * bar_interval_minutes))
        dirty = False
        now = datetime.now(timezone.utc).replace(tzinfo=None)

        for t in list(self._state["open"]):
            if t.get("status") != "OPEN":
                continue
            sym = str(t.get("symbol") or "")
            b = bars.get(sym)
            if not b:
                continue
            high = float(b.get("high", b.get("close")))
            low = float(b.get("low", b.get("close")))
            close = float(b.get("close"))
            side = str(t["side"]).upper()
            entry = float(t["entry"])
            stop = float(t["stop"])
            target = float(t["target"])
            risk_pts = abs(entry - stop) or 1e-9
            pv = float(t.get("point_value") or 5.0)
            qty = int(t.get("qty") or 1)

            t["shadow_age_bars"] = int(t.get("shadow_age_bars") or 0) + 1
            # Age from bar cadence — do NOT use wall-clock vs market opened_at
            # (Yahoo delayed market timestamps would instantly hit research horizon)
            t["shadow_age_minutes"] = round(
                float(t["shadow_age_bars"]) * bar_interval_minutes, 1
            )

            if side == "BUY":
                fav = high - entry
                adv = entry - low
            else:
                fav = entry - low
                adv = high - entry
            t["mfe_pts"] = max(float(t.get("mfe_pts") or 0), max(0.0, fav))
            t["mae_pts"] = max(float(t.get("mae_pts") or 0), max(0.0, adv))
            t["mfe_r"] = round(t["mfe_pts"] / risk_pts, 3)
            t["mae_r"] = round(t["mae_pts"] / risk_pts, 3)
            t["mfe_dollars"] = round(t["mfe_pts"] * pv * qty, 2)
            t["mae_dollars"] = round(t["mae_pts"] * pv * qty, 2)
            dirty = True

            hit_stop = (side == "BUY" and low <= stop) or (side == "SELL" and high >= stop)
            hit_tgt = (side == "BUY" and high >= target) or (side == "SELL" and low <= target)
            if hit_stop and hit_tgt:
                # Ambiguous on bar extremes — assume stop (conservative for research)
                self._close(t, stop, "stop_ambiguous_bar")
                dirty = True
            elif hit_stop:
                self._close(t, stop, "stop")
                dirty = True
            elif hit_tgt:
                self._close(t, target, "target")
                dirty = True
            elif int(t["shadow_age_bars"]) >= max_bars or float(t["shadow_age_minutes"]) >= max_minutes:
                self._close(t, close, "research_horizon")
                dirty = True

        if dirty:
            self._state["open"] = [t for t in self._state["open"] if t.get("status") == "OPEN"]
            self._save()

    def _close(self, t: dict[str, Any], exit_px: float, reason: str) -> None:
        side = str(t["side"]).upper()
        entry = float(t["entry"])
        qty = int(t.get("qty") or 1)
        pv = float(t.get("point_value") or 5.0)
        if side == "BUY":
            pnl = (float(exit_px) - entry) * pv * qty
        else:
            pnl = (entry - float(exit_px)) * pv * qty
        risk_pts = abs(entry - float(t["stop"])) or 1e-9
        t["exit"] = float(exit_px)
        t["exit_reason"] = reason
        t["pnl_dollars"] = round(pnl, 2)
        t["r_achieved"] = round(
            ((float(exit_px) - entry) if side == "BUY" else (entry - float(exit_px)))
            / risk_pts,
            3,
        )
        t["closed_at"] = datetime.now(timezone.utc).isoformat()
        t["status"] = "CLOSED"
        t["result"] = "WIN" if pnl > 0 else ("LOSS" if pnl < 0 else "BE")
        t["execution_mode"] = "SHADOW"
        self._state.setdefault("closed", []).insert(0, dict(t))

    def all_closed(self) -> list[dict[str, Any]]:
        return [
            t
            for t in self._state.get("closed", [])
            if t.get("execution_mode") == "SHADOW"
        ]

    def summary(self) -> dict[str, Any]:
        closed = self.all_closed()
        pnl = sum(float(t.get("pnl_dollars") or 0) for t in closed)
        wins = sum(1 for t in closed if float(t.get("pnl_dollars") or 0) > 0)
        losses = sum(1 for t in closed if float(t.get("pnl_dollars") or 0) < 0)
        return {
            "count": len(closed),
            "open": len(self._state.get("open", [])),
            "hypothetical_pnl": round(pnl, 2),
            "wins": wins,
            "losses": losses,
            "win_rate": round(wins / max(wins + losses, 1), 3),
        }
