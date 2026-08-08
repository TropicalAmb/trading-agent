from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

_ENV_PATTERN = re.compile(r"\$\{([A-Z0-9_]+)(?::([^}]*))?\}")


def _expand_env(value: Any) -> Any:
    if isinstance(value, str):

        def repl(match: re.Match[str]) -> str:
            key = match.group(1)
            default = match.group(2)
            env_val = os.getenv(key)
            if env_val is not None and env_val != "":
                return env_val
            return default if default is not None else ""

        return _ENV_PATTERN.sub(repl, value)
    if isinstance(value, dict):
        return {k: _expand_env(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_expand_env(v) for v in value]
    return value


def _coerce_types(cfg: dict[str, Any]) -> dict[str, Any]:
    """Coerce common numeric/bool fields after env expansion (env injects strings)."""
    broker = cfg.setdefault("broker", {})
    for key in ("port", "client_id", "connect_timeout_sec"):
        if key in broker and broker[key] is not None:
            broker[key] = int(broker[key])
    if "readonly" in broker:
        broker["readonly"] = str(broker["readonly"]).lower() in {"1", "true", "yes"}

    risk = cfg.setdefault("risk", {})
    for key in (
        "max_contracts_per_trade",
        "max_open_positions",
        "max_correlated_index_positions",
        "max_quote_age_sec",
    ):
        if key in risk:
            risk[key] = int(risk[key])
    for key in ("max_loss_pct_of_equity_per_trade", "daily_loss_kill_pct"):
        if key in risk:
            risk[key] = float(risk[key])

    strategy = cfg.setdefault("strategy", {})
    for key in ("min_dte", "max_dte", "trend_sma_period", "max_candidates_per_symbol"):
        if key in strategy:
            strategy[key] = int(strategy[key])
    for key in ("short_otm_pct", "spread_width", "min_credit_pct_of_width", "min_iv_rank"):
        if key in strategy:
            strategy[key] = float(strategy[key])

    execution = cfg.setdefault("execution", {})
    if "dry_run" in execution:
        execution["dry_run"] = str(execution["dry_run"]).lower() in {"1", "true", "yes"}

    advisor = cfg.setdefault("advisor", {})
    if "enabled" in advisor:
        advisor["enabled"] = str(advisor["enabled"]).lower() in {"1", "true", "yes"}
    if "require_claude" in advisor:
        advisor["require_claude"] = str(advisor["require_claude"]).lower() in {
            "1",
            "true",
            "yes",
        }
    if "max_tokens" in advisor:
        advisor["max_tokens"] = int(advisor["max_tokens"])

    return cfg


def load_settings(config_path: str | Path | None = None) -> dict[str, Any]:
    load_dotenv()
    path = Path(config_path or os.getenv("CONFIG_PATH", "config/settings.yaml"))
    if not path.is_absolute():
        # Resolve relative to repo root (two levels up from this file: src/agent -> repo)
        repo_root = Path(__file__).resolve().parents[2]
        candidate = repo_root / path
        path = candidate if candidate.exists() else Path.cwd() / path

    with path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    cfg = _coerce_types(_expand_env(raw))

    # Env overrides for critical safety switches
    mode = os.getenv("TRADING_MODE", cfg.get("mode", "paper")).lower()
    cfg["mode"] = mode
    cfg["allow_live_trading"] = os.getenv("ALLOW_LIVE_TRADING", "false").lower() in {
        "1",
        "true",
        "yes",
    }

    if "IBKR_HOST" in os.environ:
        cfg["broker"]["host"] = os.environ["IBKR_HOST"]
    if "IBKR_PORT" in os.environ:
        cfg["broker"]["port"] = int(os.environ["IBKR_PORT"])
    if "IBKR_CLIENT_ID" in os.environ:
        cfg["broker"]["client_id"] = int(os.environ["IBKR_CLIENT_ID"])

    journal = cfg.setdefault("journal", {})
    if os.getenv("JOURNAL_DB_PATH"):
        journal["db_path"] = os.environ["JOURNAL_DB_PATH"]

    return cfg


def assert_safe_to_trade(cfg: dict[str, Any]) -> None:
    if cfg.get("mode") == "live" and not cfg.get("allow_live_trading"):
        raise RuntimeError(
            "Live mode requested but ALLOW_LIVE_TRADING is not true. "
            "Refusing to start."
        )
