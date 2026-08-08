# Interactive Brokers paper setup (do this with me)

**Goal:** Free paper account → our agent places simulated MES/MNQ trades.  
**Cost to start:** $0. No Tradovate $1k. No PickMyTrade.

```
Our agent (confluence strategy)
        ↓
IB Gateway (paper mode)
        ↓
Your IBKR paper account (fake money, real practice)
```

---

## Part 1 — You: open the account (browser)

1. Go to: https://www.interactivebrokers.com/en/home.php  
2. Click **Open account** → Individual  
3. Complete the application (SSN, address, etc. — this is normal KYC)  
4. You do **not** need to deposit money yet for paper, but the live account usually must be **approved** first  
5. Optional free path some people use: IBKR **TWS free trial** paper login (time-limited) from their download page if you want to test before full approval  

### After approval — enable paper

1. Log into **Client Portal**: https://www.interactivebrokers.com/portal  
2. **Settings** (gear) → **Paper Trading Account**  
3. Create a **paper username + password** (different from live)  
4. Save those — you’ll use them in IB Gateway  

### Trading permissions (paper mirrors live)

1. In Client Portal → **Settings** → **Trading Permissions**  
2. Enable **Futures** (US / CME) so paper can trade MES/MNQ  
3. If it asks for financial info, fill it honestly  

---

## Part 2 — You: install IB Gateway

1. Download **IB Gateway** (not full TWS if you want lighter):  
   https://www.interactivebrokers.com/en/trading/ibgateway-stable.php  
2. Install and open it  
3. Login with your **PAPER** username/password  
4. Choose **Paper Trading** / IB API  
5. Leave Gateway **running** (minimize is fine)

### Enable API

In Gateway: **Configure** → **Settings** → **API** → **Settings**

- Enable **ActiveX and Socket Clients**  
- **Socket port** for paper Gateway: usually **4002**  
- Uncheck **Read-Only API** (we need to place paper orders)  
- Check **Download open orders on connection** (helpful)  
- OK / Apply  

---

## Part 3 — Tell me you’re ready

Reply in chat with **exactly**:

`paper gateway running on 4002`

**Do not paste your password.**

Then I will:

1. Point the agent at IBKR (`broker_backend=ibkr`)  
2. Run a connection test  
3. Run one dry-run / paper cycle on MES  

---

## Part 4 — Everyday use (after it works)

1. Open **IB Gateway** (paper) and leave it open  
2. Run: `C:\Users\patri\trading-agent\scripts\Start-Agent.ps1`  
3. Watch paper P&L in Gateway / Client Portal  
4. When comfortable: fund live with a small amount and we switch ports carefully  

---

## Checklist

- [ ] IBKR account applied / approved  
- [ ] Paper username created  
- [ ] Futures permission enabled  
- [ ] IB Gateway installed  
- [ ] Logged into **paper**  
- [ ] API enabled, port **4002**  
- [ ] Told me: `paper gateway running on 4002`
