"""Global execution kill switch — paper and live pilot."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

ExistingMode = Literal["MANAGE_EXISTING", "FLATTEN_AND_STOP"]


class ExecutionKillSwitch:
    """File-backed kill switch. When armed: no new orders."""

    def __init__(self, path: str | Path = "data/execution_kill_switch.json"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write(
                {
                    "armed": False,
                    "existing_position_mode": "MANAGE_EXISTING",
                    "armed_at": None,
                    "reason": "",
                    "source": "",
                }
            )

    def _write(self, state: dict[str, Any]) -> None:
        state["updated_at"] = datetime.now(timezone.utc).isoformat()
        self.path.write_text(json.dumps(state, indent=2), encoding="utf-8")

    def load(self) -> dict[str, Any]:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return {"armed": False, "existing_position_mode": "MANAGE_EXISTING"}

    def is_armed(self) -> bool:
        return bool(self.load().get("armed"))

    def existing_mode(self) -> str:
        return str(self.load().get("existing_position_mode") or "MANAGE_EXISTING")

    def arm(
        self,
        *,
        reason: str = "",
        source: str = "manual",
        existing_position_mode: ExistingMode = "MANAGE_EXISTING",
    ) -> dict[str, Any]:
        state = {
            "armed": True,
            "existing_position_mode": existing_position_mode,
            "armed_at": datetime.now(timezone.utc).isoformat(),
            "reason": reason,
            "source": source,
        }
        self._write(state)
        return state

    def disarm(self, *, source: str = "manual") -> dict[str, Any]:
        state = self.load()
        state.update(
            {
                "armed": False,
                "disarmed_at": datetime.now(timezone.utc).isoformat(),
                "source": source,
                "reason": "",
            }
        )
        self._write(state)
        return state

    def reject_new_orders_reason(self) -> str | None:
        if self.is_armed():
            return f"KILL_SWITCH:{self.load().get('reason') or 'armed'}"
        return None


def kill_switch_from_cfg(cfg: dict[str, Any]) -> ExecutionKillSwitch:
    path = (cfg.get("execution") or {}).get("kill_switch_path") or "data/execution_kill_switch.json"
    return ExecutionKillSwitch(path)
