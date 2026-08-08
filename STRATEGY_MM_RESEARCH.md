# Strategy + market-maker research (Aug 2026)

## Journal diagnosis (why results look bad)

Closed sample was tiny but loud:

| Issue | Evidence |
|---|---|
| Full-size products | ES −$100, GC +$350 then GC −$260 |
| Single-engine ORB spray | Many `CONFLUENCE x1 [vwap_orb]` fills |
| Correlated chaos | MNQ BUY while other indexes/gold SELL same minute |
| No cooldown | Re-sold GC minutes after a GC winner |

Net: not enough to condemn “confluence forever,” but enough to show the **current implementation** was trading noise on oversized contracts.

## What successful futures day traders emphasize

Patterns that show up across order-flow desks, VWAP desks, and SMC/liquidity frameworks (jargon differs; mechanics rhyme):

1. **Location first** — PDH/PDL, session highs/lows, equal highs/lows, VWAP, value area / POC. No middle-of-nowhere entries.
2. **Day type** — trend vs balance. ORB / breakout continuation only when the day is expanding; fade extremes / mean-revert on balance days.
3. **Liquidity sweep → reclaim** — pierce an obvious magnet (stops beyond PDH/PDL / equal highs), then accept back inside. Enter on the reclaim / displacement, **not** the first spike through the level.
4. **VWAP regime** — pullback continuation with trend when accepted away from VWAP; selective fade at statistical extremes only with confirmation.
5. **Session timing** — London / NY open / overlap windows carry most of the liquidity events; Asia is thinner for US index micros.
6. **Few A+ trades** — stack level + regime + trigger; size up only then. Spray trading is how retail dies.

Common professional model (stripped of YouTube branding):

```
liquidity raid (sweep) → structure shift / reclaim → entry on retest → stop beyond sweep wick → target next unswept pool / VWAP / prior opposite extreme
```

## Market makers / dealers (real mechanics)

- Job: provide two-sided liquidity, earn spread, **manage inventory**.
- Inventory skew: if long too much, lean offers lower / bids weaker to attract sellers and get flat. Looks like “pressure then bounce.”
- “Stop hunts” are usually **price seeking liquidity** at stop clusters beyond obvious highs/lows — not personal targeting of your account.
- Equal highs / equal lows = double-confirmed magnets → denser stop pools → higher sweep probability.
- Spreads widen and quote size shrinks in volatility; chasing every ORB print on delayed Yahoo data is especially bad.

**Practical takeaway for this agent:** prefer failed auction / sweep-reclaim at those magnets; avoid chasing the first break through the magnet; do not put stops exactly on the obvious level (buffer beyond the expected sweep wick).

## What we changed in the agent

| Change | Why |
|---|---|
| MES+MNQ focus book | Cleaner journal; less correlated spray |
| Must include liquidity/sweep engine | No VWAP-only agreement without a location raid |
| Min R:R 1.5; conf 72+ (Asia +8) | Fewer A+ only; thinner Asia gets a higher bar |
| Max 2 opens / $150 risk | Quality over quantity |
| Session P&L on paper view | Asia / London / NY expectancy separate |
| Stop beyond sweep wick | Avoid parking stops on the obvious magnet |

## Still imperfect (honest)

- Bars are Yahoo-delayed (~10–15m) — sweep timing will be blunt vs true order flow.
- No DOM / CVD / footprint yet — we approximate with OHLC + VWAP + PDH/PDL.
- Small sample size: need dozens of closed micros trades before judging expectancy.
