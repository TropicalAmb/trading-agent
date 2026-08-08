# AGENTS.md

Before changing trading scope, risk, universe, quantity, sessions, tiering, or Windows supervision, read and obey:

1. [PROJECT_MEMORY.md](./PROJECT_MEMORY.md) — locked product preferences  
2. [DEBUG.md](./DEBUG.md) — bugs already fixed; do not reintroduce  
3. `.cursor/rules/trading-agent-memory.mdc` (`alwaysApply: true`)

## Hard rules

- Do not narrow symbols or max open positions unless the user explicitly asks.
- Do not silently change risk numbers, default quantity, or 1-minute poll interval.
- Do not restore mandatory multi-engine confluence or A+-only execution.
- Do not treat lone EMA pullback scores as automatic A/A+ trades.
- Do not flash console windows from watchdog/supervisor/scheduled tasks.
- Paper mode must never place live broker orders.
- When asked to fix the system: implement, test, and verify — do not only produce a plan.
