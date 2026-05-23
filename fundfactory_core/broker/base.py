"""
Broker adapter interface and paper trading implementation.

BrokerAdapter is the abstract interface for broker integrations.
PaperBrokerAdapter provides a simulated broker for backtesting without real trading.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class Account:
    """Account information."""
    account_id: str
    cash: float
    total_assets: float


@dataclass
class Position:
    """Position information."""
    ts_code: str
    shares: int
    avg_cost: float


@dataclass
class Order:
    """Order information."""
    order_id: str
    ts_code: str
    direction: str  # BUY or SELL
    order_type: str  # MARKET, LIMIT
    price: float
    shares: int
    status: str  # PENDING, FILLED, CANCELLED
    filled_price: float = 0.0  # 实际成交价
    trade_id: str = ""  # 成交编号


@dataclass
class Trade:
    """Trade (成交) record."""
    trade_id: str
    order_id: str
    ts_code: str
    direction: str  # BUY or SELL
    price: float
    shares: int
    amount: float  # 成交金额 = price * shares


class BrokerAdapter(ABC):
    """Abstract broker adapter interface."""

    name: str = "base"

    @abstractmethod
    def get_account(self) -> Account:
        """Get current account info."""

    @abstractmethod
    def get_positions(self) -> list[Position]:
        """Get current positions."""

    @abstractmethod
    def place_order(self, ts_code: str, direction: str, shares: int, price: float = 0) -> Order:
        """Place an order. price=0 means market order."""

    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """Cancel an order."""

    @abstractmethod
    def get_orders(self, status: Optional[str] = None) -> list[Order]:
        """Get orders, optionally filtered by status."""


class PaperBrokerAdapter(BrokerAdapter):
    """
    Paper trading broker adapter for backtesting.

    Simulates order placement and execution without real market access.
    All orders execute at the requested price with configurable slippage.
    """

    name = "paper"

    def __init__(self, initial_cash: float = 1000000.0, slippage: float = 0.0):
        """
        Initialize paper broker.

        Args:
            initial_cash: Starting cash amount.
            slippage: Slippage ratio (e.g. 0.001 = 0.1%), applied on top of fill price.
        """
        self._cash = initial_cash
        self._initial_cash = initial_cash
        self._positions: dict[str, Position] = {}
        self._orders: list[Order] = []
        self._trades: list[Trade] = []
        self._order_counter = 0
        self._trade_counter = 0
        self._slippage = slippage

    def get_account(self) -> Account:
        total = self._cash + sum(p.shares * p.avg_cost for p in self._positions.values())
        return Account(
            account_id="PAPER",
            cash=self._cash,
            total_assets=total,
        )

    def get_positions(self) -> list[Position]:
        return list(self._positions.values())

    def get_trades(self) -> list[Trade]:
        """返回所有成交记录。"""
        return list(self._trades)

    def place_order(self, ts_code: str, direction: str, shares: int, price: float = 0) -> Order:
        self._order_counter += 1
        order_id = f"PAPER_{self._order_counter:06d}"

        # 计算成交价：市价单 price=0 时跳过撮合（有外部行情驱动场景可覆盖此逻辑）
        if price <= 0:
            # 价格 <= 0 视为无效，标记为 REJECTED
            order = Order(
                order_id=order_id,
                ts_code=ts_code,
                direction=direction,
                order_type="MARKET",
                price=0,
                shares=shares,
                status="REJECTED",
            )
            self._orders.append(order)
            return order

        # 加滑点
        filled_price = price * (1 + self._slippage) if direction == "BUY" else price * (1 - self._slippage)

        order = Order(
            order_id=order_id,
            ts_code=ts_code,
            direction=direction,
            order_type="LIMIT",
            price=filled_price,
            shares=shares,
            status="FILLED",
            filled_price=filled_price,
        )
        self._orders.append(order)

        # 成交记录
        self._trade_counter += 1
        trade = Trade(
            trade_id=f"TRADE_{self._trade_counter:06d}",
            order_id=order_id,
            ts_code=ts_code,
            direction=direction,
            price=filled_price,
            shares=shares,
            amount=filled_price * shares,
        )
        self._trades.append(trade)

        # 更新持仓和现金
        if direction == "BUY":
            pos = self._positions.get(ts_code)
            if pos:
                total_cost = pos.shares * pos.avg_cost + shares * filled_price
                new_shares = pos.shares + shares
                new_avg = total_cost / new_shares if new_shares > 0 else 0
                self._positions[ts_code] = Position(ts_code, new_shares, new_avg)
            else:
                self._positions[ts_code] = Position(ts_code, shares, filled_price)
            self._cash -= shares * filled_price
        elif direction == "SELL":
            pos = self._positions.get(ts_code)
            if pos:
                self._positions[ts_code] = Position(
                    ts_code, max(0, pos.shares - shares), pos.avg_cost
                )
                self._cash += shares * filled_price
                # 清零的持仓移除
                if self._positions[ts_code].shares == 0:
                    del self._positions[ts_code]

        return order

    def cancel_order(self, order_id: str) -> bool:
        for order in self._orders:
            if order.order_id == order_id and order.status == "PENDING":
                order.status = "CANCELLED"
                return True
        return False

    def get_orders(self, status: Optional[str] = None) -> list[Order]:
        if status:
            return [o for o in self._orders if o.status == status]
        return self._orders
