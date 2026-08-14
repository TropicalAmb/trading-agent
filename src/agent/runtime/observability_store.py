"""Persist last evaluated market context + candidates across NO_NEW_BAR ticks."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


class LastEvaluationStore:
    def __init__(self, path: str | Path = "data/last_evaluation.json"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._state: dict[str, Any] = {"symbols": {}, "last_evaluated_candidates": []}
        self._load()

    def _load(self) -> None:
        if self.path.exists():
            try:
                self._state = json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:
                self._state = {"symbols": {}, "last_evaluated_candidates": []}
        self._state.setdefault("symbols", {})
        self._state.setdefault("last_evaluated_candidates", [])

    def _save(self) -> None:
        self.path.write_text(json.dumps(self._state, indent=2, default=str), encoding="utf-8")

    def get_symbol(self, symbol: str) -> dict[str, Any]:
        return dict((self._state.get("symbols") or {}).get(symbol.upper()) or {})

    def update_symbol(self, symbol: str, payload: dict[str, Any]) -> None:
        row = self.get_symbol(symbol)
        # A BAR_PROCESSED payload with candidates=[] is authoritative and must
        # clear the prior setup. NO_NEW_BAR callers do not call update_symbol.
        incoming = dict(payload)
        if not incoming.get("regime") and row.get("regime"):
            incoming.pop("regime", None)
        if not incoming.get("market_context") and row.get("market_context"):
            incoming.pop("market_context", None)
        # Avoid clobbering a real regime with UNKNOWN from a thin frame
        new_rg = incoming.get("regime") or {}
        old_rg = row.get("regime") or {}
        if (
            isinstance(new_rg, dict)
            and str(new_rg.get("regime") or "").upper() == "UNKNOWN"
            and isinstance(old_rg, dict)
            and str(old_rg.get("regime") or "").upper() not in {"", "UNKNOWN"}
        ):
            incoming.pop("regime", None)
            incoming.pop("market_context", None)
        row.update(incoming)
        row["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._state.setdefault("symbols", {})[symbol.upper()] = row
        self._save()

    def set_last_candidates(
        self,
        cands: list[dict[str, Any]],
        *,
        market_bar: str | None,
        allow_empty: bool = False,
    ) -> None:
        if not cands and not allow_empty:
            return
        self._state["last_evaluated_candidates"] = list(cands)
        self._state["last_evaluated_market_bar"] = market_bar
        self._state["last_evaluated_at"] = datetime.now(timezone.utc).isoformat()
        self._save()

    def ensure_scope(
        self,
        *,
        config_version: str,
        active_strategies: list[str],
    ) -> None:
        """Remove cached candidates/engine votes outside the active config scope."""
        allowed = {str(x) for x in active_strategies}
        prior_version = str(self._state.get("config_version") or "")
        prior_active = {str(x) for x in (self._state.get("active_strategies") or [])}
        scope_changed = prior_version != str(config_version) or prior_active != allowed

        def keep(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
            return [
                row
                for row in rows
                if str(row.get("strategy") or row.get("strategy_name") or "") in allowed
            ]

        changed = scope_changed
        global_rows = list(self._state.get("last_evaluated_candidates") or [])
        filtered_global = [] if scope_changed else keep(global_rows)
        if filtered_global != global_rows:
            self._state["last_evaluated_candidates"] = filtered_global
            changed = True
        for symbol, raw in list((self._state.get("symbols") or {}).items()):
            row = dict(raw or {})
            old_candidates = list(row.get("candidates") or [])
            new_candidates = [] if scope_changed else keep(old_candidates)
            if new_candidates != old_candidates:
                row["candidates"] = new_candidates
                changed = True
            old_engines = dict(row.get("engines") or {})
            new_engines = {
                name: value for name, value in old_engines.items() if name in allowed
            }
            if new_engines != old_engines:
                row["engines"] = new_engines
                changed = True
            self._state.setdefault("symbols", {})[symbol] = row
        self._state["config_version"] = str(config_version)
        self._state["active_strategies"] = sorted(allowed)
        if changed:
            self._save()

    def last_candidates(self) -> list[dict[str, Any]]:
        return list(self._state.get("last_evaluated_candidates") or [])

    def snapshot(self) -> dict[str, Any]:
        return dict(self._state)

    def context_age_minutes(self, symbol: str) -> Optional[float]:
        row = self.get_symbol(symbol)
        ts = row.get("evaluated_at") or row.get("updated_at")
        if not ts:
            return None
        try:
            t = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
            if t.tzinfo is None:
                t = t.replace(tzinfo=timezone.utc)
            return round((datetime.now(timezone.utc) - t).total_seconds() / 60.0, 1)
        except Exception:
            return None
