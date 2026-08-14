# AGENTS.md

Before changing trading scope, risk, universe, quantity, sessions, tiering, or Windows supervision, read and obey:

1. [PROJECT_MEMORY.md](./PROJECT_MEMORY.md) — locked product preferences  
2. [DEBUG.md](./DEBUG.md) — bugs already fixed; do not reintroduce  
3. `.cursor/rules/trading-agent-memory.mdc` (`alwaysApply: true`)

## Hard rules

- Do not narrow symbols or max open positions unless the user explicitly asks.
- Do not silently change risk numbers, default quantity, or 1-minute poll interval.
- Do not restore mandatory multi-engine confluence or A+-only execution.
- Do not treat lone EMA pullback scores as automatic A/A+ trades; `ema_pullback` is research_only unless user re-enables.
- Do not let research_only / SHADOW engines supersede paperable setups in agreement selection.
- Do not flash console windows from watchdog/supervisor/scheduled tasks.
- Paper mode must never place live broker orders.
- When asked to fix the system: implement, test, and verify — do not only produce a plan.
- **After every material change:** update **both** `PROJECT_MEMORY.md` and `DEBUG.md` in the same turn (stamps, traps, engine lists, gates). Stale memory is a regression.
- Do not name a local `risk` inside `live_main.cycle` — use `risk_engine` / `trade_risk_dollars`. Start must pass paper-path preflight.
- ≥90m open-session paper drought = fault (diagnose/escalate), except specialists-only selective quiet when only specialists can paper. Do **not** soft-relax quality gates or re-enable EMA/location spray to “fix” drought.
