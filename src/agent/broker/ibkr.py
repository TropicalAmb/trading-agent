from __future__ import annotations

import logging
import math
from datetime import date, datetime, timezone
from typing import Any, Optional, Protocol

from agent.models import AccountSnapshot, CreditSpreadCandidate, OptionLeg, Side

logger = logging.getLogger(__name__)


class BrokerClient(Protocol):
    def connect(self) -> None: ...
    def disconnect(self) -> None: ...
    def is_connected(self) -> bool: ...
    def get_account_snapshot(self) -> AccountSnapshot: ...
    def get_spot(self, symbol: str) -> tuple[float, datetime]: ...
    def get_historical_closes(self, symbol: str, days: int) -> list[float]: ...
    def get_option_chain_snapshots(
        self, symbol: str, expiry: date
    ) -> list[dict[str, Any]]: ...
    def place_credit_spread(
        self, candidate: CreditSpreadCandidate, *, dry_run: bool = True
    ) -> dict[str, Any]: ...


class IBKRClient:
    """Interactive Brokers client via ib_insync (Gateway/TWS)."""

    def __init__(self, host: str, port: int, client_id: int, readonly: bool = False):
        self.host = host
        self.port = port
        self.client_id = client_id
        self.readonly = readonly
        self._ib = None

    def connect(self) -> None:
        from ib_insync import IB

        self._ib = IB()
        logger.info(
            "Connecting to IBKR at %s:%s clientId=%s",
            self.host,
            self.port,
            self.client_id,
        )
        self._ib.connect(
            self.host,
            self.port,
            clientId=self.client_id,
            readonly=self.readonly,
            timeout=15,
        )
        logger.info("IBKR connected: %s", self._ib.isConnected())

    def disconnect(self) -> None:
        if self._ib and self._ib.isConnected():
            self._ib.disconnect()
            logger.info("IBKR disconnected")

    def is_connected(self) -> bool:
        return bool(self._ib and self._ib.isConnected())

    def get_account_snapshot(self) -> AccountSnapshot:
        assert self._ib is not None
        account_values = self._ib.accountSummary()
        by_tag = {av.tag: av.value for av in account_values}

        def f(tag: str, default: float = 0.0) -> float:
            try:
                return float(by_tag.get(tag, default))
            except (TypeError, ValueError):
                return default

        positions = self._ib.positions()
        underlyings = sorted(
            {
                p.contract.symbol
                for p in positions
                if getattr(p, "position", 0) not in (0, 0.0)
            }
        )

        # Daily PnL best-effort
        realized = f("RealizedPnL")
        unrealized = f("UnrealizedPnL")
        equity = f("NetLiquidation") or f("EquityWithLoanValue")
        cash = f("TotalCashValue")
        bp = f("BuyingPower") or f("AvailableFunds")

        return AccountSnapshot(
            equity=equity,
            cash=cash,
            buying_power=bp,
            open_positions=len(underlyings),
            open_underlyings=underlyings,
            realized_pnl_today=realized,
            unrealized_pnl=unrealized,
            healthy=self.is_connected() and equity > 0,
        )

    def get_spot(self, symbol: str) -> tuple[float, datetime]:
        from ib_insync import Stock

        assert self._ib is not None
        contract = Stock(symbol, "SMART", "USD")
        self._ib.qualifyContracts(contract)
        tickers = self._ib.reqTickers(contract)
        if not tickers:
            raise RuntimeError(f"No ticker data for {symbol}")
        t = tickers[0]
        price = t.marketPrice()
        if price != price or price <= 0:  # NaN check
            price = t.close or t.last or 0.0
        if price <= 0:
            raise RuntimeError(f"Invalid spot for {symbol}: {price}")
        ts = datetime.now(timezone.utc)
        return float(price), ts

    def get_historical_closes(self, symbol: str, days: int = 30) -> list[float]:
        from ib_insync import Stock, util

        assert self._ib is not None
        contract = Stock(symbol, "SMART", "USD")
        self._ib.qualifyContracts(contract)
        bars = self._ib.reqHistoricalData(
            contract,
            endDateTime="",
            durationStr=f"{max(days, 5)} D",
            barSizeSetting="1 day",
            whatToShow="TRADES",
            useRTH=True,
            formatDate=1,
        )
        df = util.df(bars)
        if df is None or df.empty:
            return []
        return [float(x) for x in df["close"].tolist()]

    def list_option_expiries(self, symbol: str) -> list[date]:
        from ib_insync import Stock

        assert self._ib is not None
        stock = Stock(symbol, "SMART", "USD")
        self._ib.qualifyContracts(stock)
        params = self._ib.reqSecDefOptParams(stock.symbol, "", stock.secType, stock.conId)
        expiries: set[date] = set()
        for p in params:
            for e in p.expirations:
                try:
                    expiries.add(datetime.strptime(e, "%Y%m%d").date())
                except ValueError:
                    continue
        return sorted(expiries)

    def get_option_chain_snapshots(
        self, symbol: str, expiry: date
    ) -> list[dict[str, Any]]:
        """Return mid quotes for calls/puts on a given expiry (best-effort)."""
        from ib_insync import Option

        assert self._ib is not None
        expiries = self.list_option_expiries(symbol)
        if expiry not in expiries:
            # pick nearest available
            if not expiries:
                return []
            expiry = min(expiries, key=lambda d: abs((d - expiry).days))

        # Request a reasonable strike window around spot
        spot, _ = self.get_spot(symbol)
        # Build contracts via reqSecDefOptParams strikes
        stock_params = self._ib.reqSecDefOptParams(symbol, "", "STK", 0)
        strikes: set[float] = set()
        exp_str = expiry.strftime("%Y%m%d")
        for p in stock_params:
            if exp_str in p.expirations:
                strikes.update(float(s) for s in p.strikes)

        if not strikes:
            return []

        lo, hi = spot * 0.85, spot * 1.15
        use_strikes = sorted(s for s in strikes if lo <= s <= hi)[:40]
        contracts = []
        for strike in use_strikes:
            for right in ("C", "P"):
                contracts.append(
                    Option(symbol, exp_str, strike, right, "SMART", currency="USD")
                )
        qualified = self._ib.qualifyContracts(*contracts)
        tickers = self._ib.reqTickers(*qualified)
        out: list[dict[str, Any]] = []
        for t in tickers:
            c = t.contract
            bid = t.bid if t.bid and t.bid > 0 else None
            ask = t.ask if t.ask and t.ask > 0 else None
            mid = None
            if bid is not None and ask is not None:
                mid = (bid + ask) / 2.0
            elif t.last and t.last > 0:
                mid = float(t.last)
            out.append(
                {
                    "symbol": symbol,
                    "expiry": expiry,
                    "strike": float(c.strike),
                    "right": c.right,
                    "bid": bid,
                    "ask": ask,
                    "mid": mid,
                }
            )
        return out

    def place_credit_spread(
        self, candidate: CreditSpreadCandidate, *, dry_run: bool = True
    ) -> dict[str, Any]:
        from ib_insync import LimitOrder, Option, Order

        assert self._ib is not None

        def to_contract(leg: OptionLeg) -> Any:
            return Option(
                leg.symbol,
                leg.expiry.strftime("%Y%m%d"),
                leg.strike,
                leg.right,
                "SMART",
                currency="USD",
            )

        short_c = to_contract(candidate.short_leg)
        long_c = to_contract(candidate.long_leg)
        self._ib.qualifyContracts(short_c, long_c)

        qty = candidate.contracts
        # Credit spread: sell short, buy long for a net credit
        # Use BAG combo when possible; fallback to two legs for clarity/dry-run
        detail = {
            "underlying": candidate.underlying,
            "spread_type": candidate.spread_type.value,
            "credit": candidate.credit,
            "width": candidate.width,
            "quantity": qty,
            "short": short_c.localSymbol,
            "long": long_c.localSymbol,
        }

        if dry_run:
            logger.info("DRY RUN credit spread: %s", detail)
            return {
                "dry_run": True,
                "submitted": False,
                "order_id": None,
                "status": "DRY_RUN",
                "detail": detail,
            }

        # Combo bag order
        from ib_insync import ComboLeg, Contract

        bag = Contract()
        bag.symbol = candidate.underlying
        bag.secType = "BAG"
        bag.currency = "USD"
        bag.exchange = "SMART"
        leg1 = ComboLeg()
        leg1.conId = short_c.conId
        leg1.ratio = 1
        leg1.action = "SELL"
        leg1.exchange = "SMART"
        leg2 = ComboLeg()
        leg2.conId = long_c.conId
        leg2.ratio = 1
        leg2.action = "BUY"
        leg2.exchange = "SMART"
        bag.comboLegs = [leg1, leg2]

        # Limit at credit (positive credit → sell combo)
        limit_price = round(candidate.credit, 2)
        order = LimitOrder("SELL", qty, limit_price)
        order.transmit = True
        trade = self._ib.placeOrder(bag, order)
        self._ib.sleep(1)
        status = trade.orderStatus.status if trade else "UNKNOWN"
        oid = str(trade.order.orderId) if trade else None
        logger.info("Submitted credit spread order_id=%s status=%s", oid, status)
        return {
            "dry_run": False,
            "submitted": True,
            "order_id": oid,
            "status": status,
            "detail": detail,
        }

    def place_bracket_order(
        self, signal: Any, *, qty: int = 1, dry_run: bool = True
    ) -> dict[str, Any]:
        """Bracket order for futures/stocks: parent + stop + take-profit."""
        from ib_insync import Future, Stock, Order

        assert self._ib is not None
        detail = {
            "symbol": signal.symbol,
            "side": signal.side,
            "entry": signal.entry,
            "stop": signal.stop,
            "target": signal.target,
            "qty": qty,
        }
        if dry_run:
            logger.info("DRY RUN bracket: %s", detail)
            return {
                "dry_run": True,
                "submitted": False,
                "order_id": None,
                "status": "DRY_RUN",
                "detail": detail,
            }

        sym = signal.symbol.upper()
        if sym in {"MES", "MNQ", "ES", "NQ", "MGC", "MYM"}:
            contract = Future(sym, exchange="CME", currency="USD")
            # Qualify front month
            contracts = self._ib.reqContractDetails(contract)
            if not contracts:
                raise RuntimeError(f"No futures contract details for {sym}")
            contract = contracts[0].contract
        else:
            contract = Stock(sym, "SMART", "USD")
            self._ib.qualifyContracts(contract)

        action = "BUY" if signal.side == "BUY" else "SELL"
        reverse = "SELL" if action == "BUY" else "BUY"

        parent = Order()
        parent.action = action
        parent.totalQuantity = qty
        parent.orderType = "MKT"
        parent.transmit = False

        parent_trade = self._ib.placeOrder(contract, parent)
        self._ib.sleep(0.5)
        pid = parent_trade.order.orderId

        take = Order()
        take.action = reverse
        take.totalQuantity = qty
        take.orderType = "LMT"
        take.lmtPrice = round(float(signal.target), 2)
        take.parentId = pid
        take.transmit = False

        stop = Order()
        stop.action = reverse
        stop.totalQuantity = qty
        stop.orderType = "STP"
        stop.auxPrice = round(float(signal.stop), 2)
        stop.parentId = pid
        stop.transmit = True

        self._ib.placeOrder(contract, take)
        self._ib.placeOrder(contract, stop)
        self._ib.sleep(1)
        return {
            "dry_run": False,
            "submitted": True,
            "order_id": str(pid),
            "status": parent_trade.orderStatus.status,
            "detail": detail,
        }


class MockIBKRClient:
    """Offline/paper-dev mock so the loop can run without Gateway."""

    def __init__(self, equity: float = 100_000.0):
        self.equity = equity
        self._connected = False
        self._spots = {
            "SPY": 520.0,
            "QQQ": 450.0,
            "IWM": 200.0,
            "GLD": 230.0,
            "SLV": 28.0,
            "MES": 5200.0,
            "MNQ": 18500.0,
            "ES": 5200.0,
            "NQ": 18500.0,
        }

    def connect(self) -> None:
        self._connected = True
        logger.info("MockIBKR connected (equity=%.2f)", self.equity)

    def disconnect(self) -> None:
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected

    def get_account_snapshot(self) -> AccountSnapshot:
        return AccountSnapshot(
            equity=self.equity,
            cash=self.equity * 0.8,
            buying_power=self.equity * 2,
            open_positions=0,
            open_underlyings=[],
            realized_pnl_today=0.0,
            unrealized_pnl=0.0,
            healthy=self._connected,
            notes=["mock"],
        )

    def get_spot(self, symbol: str) -> tuple[float, datetime]:
        return self._spots.get(symbol, 100.0), datetime.now(timezone.utc)

    def get_historical_closes(self, symbol: str, days: int = 30) -> list[float]:
        spot = self._spots.get(symbol, 100.0)
        # Uptrend that ends at current spot so SMA trend filter is bullish
        return [spot * (0.96 + (0.04 * i / max(days - 1, 1))) for i in range(days)]

    def list_option_expiries(self, symbol: str) -> list[date]:
        today = date.today()
        return [date.fromordinal(today.toordinal() + d) for d in (14, 21, 28, 35)]

    def get_option_chain_snapshots(
        self, symbol: str, expiry: date
    ) -> list[dict[str, Any]]:
        spot, _ = self.get_spot(symbol)
        width_step = 1.0 if spot < 50 else (2.0 if spot < 200 else 5.0)
        # Snap spot to strike grid
        atm = round(spot / width_step) * width_step
        strikes = [atm + width_step * i for i in range(-8, 9)]
        out: list[dict[str, Any]] = []
        for strike in strikes:
            # Simple smile: ATM rich, OTM decays — enough credit for verticals
            atm_premium = max(1.5, spot * 0.018)
            for right in ("P", "C"):
                if right == "P":
                    intrinsic = max(0.0, strike - spot)
                    otm = max(0.0, (spot - strike) / spot)
                else:
                    intrinsic = max(0.0, spot - strike)
                    otm = max(0.0, (strike - spot) / spot)
                # Steeper OTM decay so vertical credits clear min_credit gates
                extr = atm_premium * max(0.05, math.exp(-otm * 28))
                mid = max(0.05, intrinsic + extr)
                out.append(
                    {
                        "symbol": symbol,
                        "expiry": expiry,
                        "strike": float(strike),
                        "right": right,
                        "bid": max(0.01, mid - 0.05),
                        "ask": mid + 0.05,
                        "mid": mid,
                    }
                )
        return out

    def place_credit_spread(
        self, candidate: CreditSpreadCandidate, *, dry_run: bool = True
    ) -> dict[str, Any]:
        detail = candidate.model_dump(mode="json")
        if dry_run:
            return {
                "dry_run": True,
                "submitted": False,
                "order_id": None,
                "status": "DRY_RUN",
                "detail": detail,
            }
        return {
            "dry_run": False,
            "submitted": True,
            "order_id": "MOCK-1",
            "status": "Submitted",
            "detail": detail,
        }

    def place_bracket_order(
        self, signal: Any, *, qty: int = 1, dry_run: bool = True
    ) -> dict[str, Any]:
        detail = {
            "symbol": getattr(signal, "symbol", None),
            "side": getattr(signal, "side", None),
            "entry": getattr(signal, "entry", None),
            "stop": getattr(signal, "stop", None),
            "target": getattr(signal, "target", None),
            "qty": qty,
            "reward_dollars": getattr(signal, "reward_dollars", None),
        }
        return {
            "dry_run": dry_run,
            "submitted": not dry_run,
            "order_id": None if dry_run else "MOCK-BRACKET-1",
            "status": "DRY_RUN" if dry_run else "Submitted",
            "detail": detail,
        }
