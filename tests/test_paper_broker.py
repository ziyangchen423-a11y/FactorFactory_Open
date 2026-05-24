"""
Tests for PaperBrokerAdapter.
"""
import pytest
from fundfactory_core.broker.base import (
    PaperBrokerAdapter,
)


class TestPaperBrokerAdapterInit:
    """初始化相关测试。"""

    def test_default_initial_cash(self):
        broker = PaperBrokerAdapter()
        acc = broker.get_account()
        assert acc.cash == 1_000_000.0
        assert acc.total_assets == 1_000_000.0

    def test_custom_initial_cash(self):
        broker = PaperBrokerAdapter(initial_cash=500_000.0)
        acc = broker.get_account()
        assert acc.cash == 500_000.0
        assert acc.total_assets == 500_000.0


class TestBuy:
    """买入相关测试。"""

    def test_buy_single_order(self):
        broker = PaperBrokerAdapter(initial_cash=1_000_000.0)
        order = broker.place_order("000001.SZ", "BUY", 100, 10.0)

        assert order.status == "FILLED"
        assert order.filled_price == 10.0
        assert order.shares == 100
        assert order.direction == "BUY"

    def test_buy_updates_cash(self):
        broker = PaperBrokerAdapter(initial_cash=1_000_000.0)
        broker.place_order("000001.SZ", "BUY", 100, 10.0)
        acc = broker.get_account()
        assert acc.cash == 1_000_000.0 - 100 * 10.0

    def test_buy_updates_position(self):
        broker = PaperBrokerAdapter(initial_cash=1_000_000.0)
        broker.place_order("000001.SZ", "BUY", 100, 10.0)
        positions = broker.get_positions()
        assert len(positions) == 1
        pos = positions[0]
        assert pos.ts_code == "000001.SZ"
        assert pos.shares == 100
        assert pos.avg_cost == 10.0

    def test_buy_multiple_same_stock(self):
        broker = PaperBrokerAdapter(initial_cash=1_000_000.0)
        broker.place_order("000001.SZ", "BUY", 100, 10.0)
        broker.place_order("000001.SZ", "BUY", 100, 12.0)

        positions = broker.get_positions()
        assert len(positions) == 1
        pos = positions[0]
        assert pos.shares == 200
        # 总成本 = 100*10 + 100*12 = 2200，平均 = 2200/200 = 11.0
        assert pos.avg_cost == 11.0

    def test_buy_creates_trade(self):
        broker = PaperBrokerAdapter(initial_cash=1_000_000.0)
        broker.place_order("000001.SZ", "BUY", 100, 10.0)
        trades = broker.get_trades()
        assert len(trades) == 1
        assert trades[0].amount == 100 * 10.0
        assert trades[0].direction == "BUY"

    def test_buy_invalid_price_rejected(self):
        broker = PaperBrokerAdapter(initial_cash=1_000_000.0)
        order = broker.place_order("000001.SZ", "BUY", 100, price=0.0)
        assert order.status == "REJECTED"


class TestSell:
    """卖出相关测试。"""

    def test_sell_reduces_position(self):
        broker = PaperBrokerAdapter(initial_cash=1_000_000.0)
        broker.place_order("000001.SZ", "BUY", 200, 10.0)
        broker.place_order("000001.SZ", "SELL", 100, 12.0)

        positions = broker.get_positions()
        assert len(positions) == 1
        assert positions[0].shares == 100

    def test_sell_increases_cash(self):
        broker = PaperBrokerAdapter(initial_cash=1_000_000.0)
        broker.place_order("000001.SZ", "BUY", 100, 10.0)
        cash_before = broker.get_account().cash
        broker.place_order("000001.SZ", "SELL", 100, 12.0)
        assert broker.get_account().cash == cash_before + 100 * 12.0

    def test_sell_clears_position(self):
        broker = PaperBrokerAdapter(initial_cash=1_000_000.0)
        broker.place_order("000001.SZ", "BUY", 100, 10.0)
        broker.place_order("000001.SZ", "SELL", 100, 12.0)
        assert len(broker.get_positions()) == 0

    def test_sell_creates_trade(self):
        broker = PaperBrokerAdapter(initial_cash=1_000_000.0)
        broker.place_order("000001.SZ", "BUY", 100, 10.0)
        broker.place_order("000001.SZ", "SELL", 100, 12.0)
        trades = broker.get_trades()
        assert len(trades) == 2
        assert trades[1].direction == "SELL"
        assert trades[1].amount == 100 * 12.0


class TestOrders:
    """订单相关测试。"""

    def test_get_orders_all(self):
        broker = PaperBrokerAdapter(initial_cash=1_000_000.0)
        broker.place_order("000001.SZ", "BUY", 100, 10.0)
        broker.place_order("000002.SZ", "BUY", 200, 20.0)
        orders = broker.get_orders()
        assert len(orders) == 2

    def test_get_orders_filter_by_status(self):
        broker = PaperBrokerAdapter(initial_cash=1_000_000.0)
        broker.place_order("000001.SZ", "BUY", 100, 0.0)  # REJECTED
        broker.place_order("000002.SZ", "BUY", 200, 20.0)  # FILLED
        filled = broker.get_orders(status="FILLED")
        rejected = broker.get_orders(status="REJECTED")
        assert len(filled) == 1
        assert len(rejected) == 1

    def test_cancel_order_not_found(self):
        broker = PaperBrokerAdapter()
        result = broker.cancel_order("PAPER_999")
        assert result is False


class TestSlippage:
    """滑点相关测试。"""

    def test_slippage_buy(self):
        broker = PaperBrokerAdapter(initial_cash=1_000_000.0, slippage=0.001)
        order = broker.place_order("000001.SZ", "BUY", 100, 10.0)
        # 买入滑点：+0.1%，成交价 = 10 * 1.001 = 10.01
        assert order.filled_price == pytest.approx(10.01, rel=1e-3)

    def test_slippage_sell(self):
        broker = PaperBrokerAdapter(initial_cash=1_000_000.0, slippage=0.001)
        broker.place_order("000001.SZ", "BUY", 100, 10.0)
        order = broker.place_order("000001.SZ", "SELL", 100, 10.0)
        # 卖出滑点：-0.1%，成交价 = 10 * 0.999 = 9.99
        assert order.filled_price == pytest.approx(9.99, rel=1e-3)


class TestAccountTotalAssets:
    """账户总资产计算。"""

    def test_total_assets_with_position(self):
        broker = PaperBrokerAdapter(initial_cash=1_000_000.0)
        broker.place_order("000001.SZ", "BUY", 100, 10.0)
        acc = broker.get_account()
        # 现金 990000 + 持仓成本 1000 = 991000 (成本法，按 avg_cost 计算持仓价值)
        # 买入成交价 = 10.0，持仓 avg_cost = 10.0，shares = 100
        # 注意：若无外部行情，total_assets 以持仓成本计量 = 初始资金 1000000
        assert acc.total_assets == 1_000_000.0
