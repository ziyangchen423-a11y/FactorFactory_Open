"""
Tushare data provider implementation.

Fetches data from Tushare Pro API.
Requires TUSHARE_TOKEN to be set in environment or .env file.

Usage:
    from fundfactory_core.data_providers.tushare_provider import TushareProvider
    provider = TushareProvider(token="your_token_here")
"""
from typing import Optional

import pandas as pd

from fundfactory_core.data_providers.base import DataProvider
from fundfactory_core.config.settings import TUSHARE_TOKEN


class TushareProvider(DataProvider):
    """
    Tushare Pro data provider.

    Requires a Tushare Pro API token. Get one at https://tushare.pro/
    Set via TUSHARE_TOKEN environment variable or pass directly.
    """

    name = "tushare"

    def __init__(self, token: Optional[str] = None, timeout: int = 30):
        """
        Initialize Tushare provider.

        Args:
            token: Tushare Pro API token. Defaults to TUSHARE_TOKEN from settings.
            timeout: Request timeout in seconds.
        """
        self.token = token or TUSHARE_TOKEN
        if not self.token:
            raise ValueError(
                "TUSHARE_TOKEN is required. "
                "Set TUSHARE_TOKEN in .env or pass token to TushareProvider()."
            )
        self.timeout = timeout
        self._session = None

    def _call(self, api_name: str, params: dict, fields: str) -> pd.DataFrame:
        """
        Call Tushare Pro API.

        Args:
            api_name: Tushare API name (e.g. "trade_cal", "stock_basic")
            params: API parameters dict
            fields: Comma-separated list of fields to return

        Returns:
            DataFrame with the returned data
        """
        try:
            import tushare as ts
        except ImportError:
            raise ImportError(
                "tushare is not installed. Install with: pip install tushare"
            )

        pro = ts.pro_api(self.token)
        resp = pro.query(api_name, **params, fields=fields)
        return resp

    def _ts_code_to_symbol(self, ts_code: str) -> str:
        """Convert ts_code to Tushare API symbol format."""
        return ts_code

    def _standardize_date(self, date_val) -> str:
        """Convert date to YYYYMMDD string."""
        if pd.isna(date_val):
            return None
        if isinstance(date_val, (int, float)):
            date_val = str(int(date_val))
        if isinstance(date_val, str) and len(date_val) == 8:
            return date_val
        # Try parsing
        try:
            dt = pd.to_datetime(date_val)
            return dt.strftime("%Y%m%d")
        except Exception:
            return str(date_val)

    def _string_or_none(self, value) -> str | None:
        """Convert non-null scalar values to strings without numeric date coercion."""
        if pd.isna(value):
            return None
        return str(value)

    def _float_or_none(self, value) -> float | None:
        """Convert non-null numeric values to float."""
        return float(value) if pd.notna(value) else None

    def fetch_trading_calendar(self, start: str, end: str) -> list[dict]:
        """Fetch trading calendar."""
        df = self._call(
            "trade_cal",
            {"start_date": start, "end_date": end},
            "cal_date,is_open"
        )
        records = []
        for _, row in df.iterrows():
            cal_date = str(row["cal_date"])
            dt = pd.to_datetime(cal_date)
            records.append({
                "trade_date": cal_date,
                "is_open": int(row["is_open"]),
                "day_of_week": int(dt.dayofweek),
                "week_of_year": int(dt.isocalendar().week),
                "month": int(dt.month),
                "year": int(dt.year),
                "quarter": int((dt.month - 1) // 3) + 1,
            })
        return records

    def fetch_stock_basic(self) -> list[dict]:
        """Fetch stock basic info (all stocks)."""
        df = self._call(
            "stock_basic",
            {"trade_date": "", "list_status": "L"},
            "ts_code,name,list_date"
        )
        return [
            {
                "ts_code": str(row["ts_code"]),
                "name": str(row["name"]) if pd.notna(row["name"]) else "",
                "list_date": str(row["list_date"]) if pd.notna(row["list_date"]) else "",
            }
            for _, row in df.iterrows()
        ]

    def fetch_daily_data(self, ts_code: str, start: str, end: str) -> list[dict]:
        """Fetch daily K-line data."""
        df = self._call(
            "daily",
            {"ts_code": ts_code, "start_date": start, "end_date": end},
            "ts_code,trade_date,open,high,low,close,pre_close,change,pct_chg,vol,amount"
        )
        return [
            {
                "ts_code": str(row["ts_code"]),
                "trade_date": str(row["trade_date"]),
                "open": float(row["open"]) if pd.notna(row["open"]) else None,
                "high": float(row["high"]) if pd.notna(row["high"]) else None,
                "low": float(row["low"]) if pd.notna(row["low"]) else None,
                "close": float(row["close"]) if pd.notna(row["close"]) else None,
                "pre_close": float(row["pre_close"]) if pd.notna(row["pre_close"]) else None,
                "change": float(row["change"]) if pd.notna(row["change"]) else None,
                "pct_chg": float(row["pct_chg"]) if pd.notna(row["pct_chg"]) else None,
                "vol": float(row["vol"]) if pd.notna(row["vol"]) else None,
                "amount": float(row["amount"]) if pd.notna(row["amount"]) else None,
            }
            for _, row in df.iterrows()
        ]

    def fetch_adj_factor(self, ts_code: str, start: str, end: str) -> list[dict]:
        """Fetch adjustment factors."""
        df = self._call(
            "adj_factor",
            {"ts_code": ts_code, "start_date": start, "end_date": end},
            "ts_code,trade_date,adj_factor"
        )
        return [
            {
                "ts_code": str(row["ts_code"]),
                "trade_date": str(row["trade_date"]),
                "adj_factor": float(row["adj_factor"]) if pd.notna(row["adj_factor"]) else None,
            }
            for _, row in df.iterrows()
        ]

    def fetch_income_statement(self, ts_code: str, start: str, end: str) -> list[dict]:
        """Fetch income statement data (annual)."""
        df = self._call(
            "income",
            {"ts_code": ts_code, "start_date": start, "end_date": end},
            "ts_code,ann_date,f_ann_date,end_date,revenue,oper_cost,sell_exp,admin_exp,fin_exp,rd_exp,operate_profit,total_profit,income_tax,n_income,n_income_attr_p,basic_eps,ebit,ebitda,update_flag"
        )
        records = []
        for _, row in df.iterrows():
            rec = {"ts_code": str(row["ts_code"])}
            for col in ["ann_date", "f_ann_date", "end_date"]:
                rec[col] = self._standardize_date(row.get(col))
            for col in ["revenue", "oper_cost", "sell_exp", "admin_exp", "fin_exp",
                        "rd_exp", "operate_profit", "total_profit", "income_tax",
                        "n_income", "n_income_attr_p", "basic_eps", "ebit", "ebitda"]:
                val = row.get(col)
                rec[col] = self._float_or_none(val)
            rec["update_flag"] = self._string_or_none(row.get("update_flag"))
            records.append(rec)
        return records

    def fetch_balance_sheet(self, ts_code: str, start: str, end: str) -> list[dict]:
        """Fetch balance sheet data (annual)."""
        df = self._call(
            "balancesheet",
            {"ts_code": ts_code, "start_date": start, "end_date": end},
            "ts_code,ann_date,f_ann_date,end_date,total_share,money_cap,accounts_receiv,inventories,total_cur_assets,total_cur_liab,fix_assets,intan_assets,goodwill,total_assets,total_liab,st_borr,lt_borr,total_hldr_eqy_exc_min_int,accounts_pay,update_flag"
        )
        records = []
        for _, row in df.iterrows():
            rec = {"ts_code": str(row["ts_code"])}
            for col in ["ann_date", "f_ann_date", "end_date"]:
                rec[col] = self._standardize_date(row.get(col))
            for col in ["total_share", "money_cap", "accounts_receiv", "inventories",
                        "total_cur_assets", "total_cur_liab", "fix_assets", "intan_assets",
                        "goodwill", "total_assets", "total_liab", "st_borr", "lt_borr",
                        "total_hldr_eqy_exc_min_int", "accounts_pay"]:
                val = row.get(col)
                rec[col] = self._float_or_none(val)
            rec["update_flag"] = self._string_or_none(row.get("update_flag"))
            records.append(rec)
        return records

    def fetch_cash_flow(self, ts_code: str, start: str, end: str) -> list[dict]:
        """Fetch cash flow data (annual)."""
        df = self._call(
            "cashflow",
            {"ts_code": ts_code, "start_date": start, "end_date": end},
            "ts_code,ann_date,f_ann_date,end_date,net_profit,c_fr_sale_sg,n_cashflow_act,n_cashflow_inv_act,free_cashflow,n_cash_flows_fnc_act,update_flag"
        )
        records = []
        for _, row in df.iterrows():
            rec = {"ts_code": str(row["ts_code"])}
            for col in ["ann_date", "f_ann_date", "end_date"]:
                rec[col] = self._standardize_date(row.get(col))
            for col in ["net_profit", "c_fr_sale_sg", "n_cashflow_act", "n_cashflow_inv_act",
                        "free_cashflow", "n_cash_flows_fnc_act"]:
                val = row.get(col)
                rec[col] = self._float_or_none(val)
            rec["update_flag"] = self._string_or_none(row.get("update_flag"))
            records.append(rec)
        return records
