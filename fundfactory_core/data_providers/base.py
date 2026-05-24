"""
Base data provider interface.

All data providers must implement this interface.
"""
from abc import ABC, abstractmethod


class DataProvider(ABC):
    """Abstract base class for data providers."""

    name: str = "base"

    @abstractmethod
    def fetch_trading_calendar(self, start: str, end: str) -> list[dict]:
        """
        Fetch trading calendar data.

        Args:
            start: Start date in YYYYMMDD format.
            end: End date in YYYYMMDD format.

        Returns:
            List of dicts with keys: trade_date, is_open, day_of_week, week_of_year, month, year, quarter
        """

    @abstractmethod
    def fetch_stock_basic(self) -> list[dict]:
        """
        Fetch stock basic info.

        Returns:
            List of dicts with keys: ts_code, name, list_date
        """

    @abstractmethod
    def fetch_daily_data(self, ts_code: str, start: str, end: str) -> list[dict]:
        """
        Fetch daily K-line data for a single stock.

        Args:
            ts_code: Tushare stock code (e.g. "000001.SZ")
            start: Start date in YYYYMMDD format.
            end: End date in YYYYMMDD format.

        Returns:
            List of dicts with keys: ts_code, trade_date, open, high, low, close, pre_close, change, pct_chg, vol, amount
        """

    @abstractmethod
    def fetch_adj_factor(self, ts_code: str, start: str, end: str) -> list[dict]:
        """
        Fetch adjustment factors.

        Returns:
            List of dicts with keys: ts_code, trade_date, adj_factor
        """

    @abstractmethod
    def fetch_income_statement(self, ts_code: str, start: str, end: str) -> list[dict]:
        """
        Fetch income statement data.

        Returns:
            List of dicts with fields as defined in open_core.sql income_statement table.
        """

    @abstractmethod
    def fetch_balance_sheet(self, ts_code: str, start: str, end: str) -> list[dict]:
        """
        Fetch balance sheet data.
        """

    @abstractmethod
    def fetch_cash_flow(self, ts_code: str, start: str, end: str) -> list[dict]:
        """
        Fetch cash flow data.
        """
