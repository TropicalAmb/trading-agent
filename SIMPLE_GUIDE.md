# Simple guide (read this if you’re confused)

## Who runs PowerShell — you or me?

| Task | Who |
|---|---|
| Writing/fixing the bot code | **Me (in Cursor)** |
| Running test commands while we build | **Me**, or you if you want |
| Putting **your Tradovate password** into `.env` | **Only you** (I should never see your password in chat) |
| After it’s connected and started | **The agent** places trades on your behalf |

**Autonomous means:** once the agent is running on your PC, **you do not click Buy/Sell**.  
You are not supposed to live in PowerShell every day. PowerShell is just how we *start* the program (like opening an app).

Later we can make a double-click `Start Agent` shortcut so you never think about PowerShell.

---

## What is an “alert”? Who does it alert?

**Not you (to go trade manually).**

```
TradingView alert  →  wakes the AGENT  →  agent places order at Tradovate
```

So the alert is a **signal to the robot**, not a text saying “hey human, go click buy.”

**Even better for autonomy:** we can run **without TradingView alerts at all**.  
The agent watches the market itself and trades when its rules fire.

Your alerts are optional “extra confirmation” if we turn confluence on.

---

## Where do trades happen?

On **your Tradovate account** (the money/P&L lives there).  
TopstepX is later, for funded. Different system.

---

## About “60% win rate feels low”

60% with winners ~2× the size of losers is **strong**, not weak:

- Win 6, lose 4  
- Win +$150 × 6 = +$900  
- Lose −$75 × 4 = −$300  
- Net ≈ **+$600** over 10 trades  

Chasing 90% win rate usually means tiny targets and one big loss wiping the week.

**What we’re doing to feel “higher performing”:**  
Only take trades when **several strategies agree** (confluence). Fewer trades, higher selectivity — closer to the 65–75% “high probability” style people talk about in 2026 ICT/confluence playbooks.
