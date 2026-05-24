"""
Sample public factors - basic factor examples for FactorFactory Open.

These are minimal implementations intended to demonstrate the factor system.
Each factor follows the registry pattern: register_factor() called at module load time.

Factor categories:
- Momentum: MOM_5D, MOM_20D, MOM_60D
- Size: LNCAP, TOTAL_MV
- Volatility: VOL_20D, VOL_60D
- Valuation: PE_SIMPLE, PB_SIMPLE
- Profitability: ROE, ROA
"""
import sys
import sqlite3
from pathlib import Path

import numpy as np

from fundfactory_core.factors.registry import register_factor
from fundfactory_core.config.settings import DB_PATH

# Add core to path for direct script execution
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

def _require_numeric_deps():
    """Lazily import numpy/pandas; raise clear error if missing."""
    import numpy as np
    import pandas as pd
    return np, pd


def _get_db_conn(readonly: bool = True):
    """Get a database connection."""
    if readonly:
        return sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    return sqlite3.connect(DB_PATH)


def _get_daily_data_for_factor(ts_codes: list, start_date: str, end_date: str):
    """Load daily data for factor calculation."""
    import pandas as pd
    if not ts_codes:
        return pd.DataFrame()
    placeholders = ",".join(["?"] * len(ts_codes))
    conn = _get_db_conn()
    df = pd.read_sql(f"""
        SELECT ts_code, trade_date, close, pct_chg, vol, amount
        FROM daily_data
        WHERE ts_code IN ({placeholders})
          AND trade_date >= ?
          AND trade_date <= ?
        ORDER BY ts_code, trade_date
    """, conn, params=ts_codes + [start_date, end_date])
    conn.close()
    return df


def _get_financial_data(end_date: str):
    """Load financial data for valuation/profitability factors."""
    import pandas as pd
    conn = _get_db_conn()
    df = pd.read_sql("""
        SELECT i.ts_code,
               i.end_date,
               i.n_income_attr_p,
               i.operate_profit,
               i.revenue,
               b.total_share,
               b.total_hldr_eqy_exc_min_int,
               b.total_assets,
               b.total_liab,
               b.accounts_receiv,
               b.inventories
        FROM income_statement i
        JOIN balance_sheet b ON i.ts_code = b.ts_code AND i.end_date = b.end_date
        WHERE i.end_date = ?
    """, conn, params=[end_date])
    conn.close()
    return df


# ============================================================
# Momentum Factors
# ============================================================

def _calc_mom(ts_code: str, trade_date: str, window: int) -> float:
    """Generic momentum calculation: return over past `window` trading days."""
    import pandas as pd
    conn = _get_db_conn()
    df = pd.read_sql("""
        SELECT pct_chg FROM daily_data
        WHERE ts_code = ? AND trade_date <= ?
        ORDER BY trade_date DESC
        LIMIT ?
    """, conn, params=[ts_code, trade_date, window])
    conn.close()
    if len(df) < window:
        return float("nan")
    return float((1 + df["pct_chg"].values / 100).prod() - 1) * 100


def _register_mom(name: str, factor_id: str, window: int, category: str):
    """Helper to register a momentum factor."""
    def calc(target_date: str, db_path: str = None):
        import numpy as np
        import pandas as pd
        conn = _get_db_conn()
        df = pd.read_sql("""
            SELECT DISTINCT ts_code FROM daily_data WHERE trade_date = ?
        """, conn, params=[target_date])
        conn.close()
        ts_codes = df["ts_code"].tolist()
        results = []
        for tc in ts_codes:
            val = _calc_mom(tc, target_date, window)
            if not np.isnan(val):
                results.append({"ts_code": tc, "factor_value": val})
        result_df = pd.DataFrame(results)
        result_df["calc_date"] = target_date
        result_df["factor_id"] = factor_id
        return result_df

    register_factor(factor_id, {
        "factor_id": factor_id,
        "name": name,
        "category": category,
        "description": f" cumulative return over the past {window} trading days",
        "direction": "higher_better",
        "lookback_days": window,
    }, calc)


_register_mom("Momentum 5D", "MOM_5D", 5, "momentum")
_register_mom("Momentum 20D", "MOM_20D", 20, "momentum")
_register_mom("Momentum 60D", "MOM_60D", 60, "momentum")


# ============================================================
# Volatility Factors
# ============================================================

def _calc_vol(target_date: str, window: int):
    """Calculate volatility over past `window` days for all stocks on target_date."""
    import pandas as pd
    conn = _get_db_conn()
    cutoff_df = pd.read_sql("""
        SELECT DISTINCT trade_date FROM daily_data
        WHERE trade_date <= ?
        ORDER BY trade_date DESC
        LIMIT ?
    """, conn, params=[target_date, window])
    if len(cutoff_df) < window:
        conn.close()
        return pd.DataFrame()
    cutoff = cutoff_df.iloc[-1]["trade_date"]

    # SQLite has no built-in STD(); compute manually via E[X²]-E[X]²
    df = pd.read_sql("""
        SELECT ts_code,
               AVG(pct_chg) as mean_pct,
               AVG(pct_chg * pct_chg) as mean_sq_pct
        FROM daily_data
        WHERE trade_date >= ? AND trade_date <= ?
        GROUP BY ts_code
    """, conn, params=[cutoff, target_date])
    conn.close()
    if df.empty:
        return pd.DataFrame()
    df["factor_value"] = np.sqrt(np.maximum(df["mean_sq_pct"] - df["mean_pct"] ** 2, 0))
    df["factor_id"] = f"VOL_{window}D"
    df["calc_date"] = target_date
    return df


def _register_vol(name: str, factor_id: str, window: int):
    def calc(target_date: str, db_path: str = None):
        return _calc_vol(target_date, window)
    register_factor(factor_id, {
        "factor_id": factor_id,
        "name": name,
        "category": "volatility",
        "description": f" daily return volatility over the past {window} trading days",
        "direction": "lower_better",
        "lookback_days": window,
    }, calc)


_register_vol("Volatility 20D", "VOL_20D", 20)
_register_vol("Volatility 60D", "VOL_60D", 60)


# ============================================================
# Size Factors
# ============================================================

def calc_LNCAP(target_date: str, db_path: str = None):
    """
    LNCAP - Natural log of total market capitalization.
    = ln(close * total_share)
    """
    import numpy as np
    import pandas as pd
    conn = _get_db_conn()
    df = pd.read_sql("""
        SELECT d.ts_code,
               d.close,
               b.total_share
        FROM daily_data d
        JOIN balance_sheet b ON d.ts_code = b.ts_code
        WHERE d.trade_date = ?
          AND b.total_share IS NOT NULL
          AND d.close IS NOT NULL
    """, conn, params=[target_date])
    conn.close()
    if df.empty:
        return pd.DataFrame()
    df["factor_value"] = np.log(df["close"] * df["total_share"])
    df["factor_id"] = "LNCAP"
    df["calc_date"] = target_date
    df = df[["ts_code", "factor_value", "factor_id", "calc_date"]]
    return df


register_factor("LNCAP", {
    "factor_id": "LNCAP",
    "name": "Log Market Cap",
    "category": "size",
    "description": "Natural log of total market capitalization (close * total_share)",
    "direction": "neutral",
    "lookback_days": 0,
}, calc_LNCAP)


# ============================================================
# Valuation Factors
# ============================================================

def calc_PE_SIMPLE(target_date: str, db_path: str = None):
    """
    PE_SIMPLE - Price-to-earnings ratio (simplified).
    = close * total_share / n_income_attr_p
    """
    import numpy as np
    import pandas as pd
    conn = _get_db_conn()
    df = pd.read_sql("""
        SELECT d.ts_code,
               d.close,
               b.total_share,
               i.n_income_attr_p
        FROM daily_data d
        JOIN balance_sheet b ON d.ts_code = b.ts_code
        JOIN income_statement i ON d.ts_code = i.ts_code
        WHERE d.trade_date = ?
          AND b.total_share IS NOT NULL
          AND d.close IS NOT NULL
          AND i.n_income_attr_p > 0
    """, conn, params=[target_date])
    conn.close()
    if df.empty:
        return pd.DataFrame()
    df["market_cap"] = df["close"] * df["total_share"]
    df["factor_value"] = df["market_cap"] / df["n_income_attr_p"]
    df = df.replace([np.inf, -np.inf], np.nan)
    df["factor_id"] = "PE_SIMPLE"
    df["calc_date"] = target_date
    df = df[["ts_code", "factor_value", "factor_id", "calc_date"]]
    return df


register_factor("PE_SIMPLE", {
    "factor_id": "PE_SIMPLE",
    "name": "P/E Ratio (Simple)",
    "category": "valuation",
    "description": "Price-to-earnings ratio: market_cap / net income attributable to parent",
    "direction": "lower_better",
    "lookback_days": 0,
}, calc_PE_SIMPLE)


def calc_PB_SIMPLE(target_date: str, db_path: str = None):
    """
    PB_SIMPLE - Price-to-book ratio (simplified).
    = close * total_share / total_hldr_eqy_exc_min_int
    """
    import numpy as np
    import pandas as pd
    conn = _get_db_conn()
    df = pd.read_sql("""
        SELECT d.ts_code,
               d.close,
               b.total_share,
               b.total_hldr_eqy_exc_min_int
        FROM daily_data d
        JOIN balance_sheet b ON d.ts_code = b.ts_code
        WHERE d.trade_date = ?
          AND b.total_share IS NOT NULL
          AND b.total_hldr_eqy_exc_min_int > 0
          AND d.close IS NOT NULL
    """, conn, params=[target_date])
    conn.close()
    if df.empty:
        return pd.DataFrame()
    df["market_cap"] = df["close"] * df["total_share"]
    df["factor_value"] = df["market_cap"] / df["total_hldr_eqy_exc_min_int"]
    df = df.replace([np.inf, -np.inf], np.nan)
    df["factor_id"] = "PB_SIMPLE"
    df["calc_date"] = target_date
    df = df[["ts_code", "factor_value", "factor_id", "calc_date"]]
    return df


register_factor("PB_SIMPLE", {
    "factor_id": "PB_SIMPLE",
    "name": "P/B Ratio (Simple)",
    "category": "valuation",
    "description": "Price-to-book ratio: market_cap / total shareholders equity excl minority interest",
    "direction": "lower_better",
    "lookback_days": 0,
}, calc_PB_SIMPLE)


# ============================================================
# 量价类因子（纯依赖 daily_data）
# ============================================================

def _calc_ret(ts_code: str, trade_date: str, window: int) -> float:
    """通用单股票收益率计算：过去 window 交易日的累计收益率（百分比）。"""
    import pandas as pd
    conn = _get_db_conn()
    df = pd.read_sql("""
        SELECT pct_chg FROM daily_data
        WHERE ts_code = ? AND trade_date <= ?
        ORDER BY trade_date DESC
        LIMIT ?
    """, conn, params=[ts_code, trade_date, window])
    conn.close()
    if len(df) < window:
        return float("nan")
    return float((1 + df["pct_chg"].values / 100).prod() - 1) * 100


def _register_ret(name: str, factor_id: str, window: int, category: str = "momentum"):
    """注册一个收益率/动量类因子。"""
    def calc(target_date: str, db_path: str = None):
        import numpy as np
        import pandas as pd
        conn = _get_db_conn()
        df = pd.read_sql("""
            SELECT DISTINCT ts_code FROM daily_data WHERE trade_date = ?
        """, conn, params=[target_date])
        conn.close()
        ts_codes = df["ts_code"].tolist()
        results = []
        for tc in ts_codes:
            val = _calc_ret(tc, target_date, window)
            if not np.isnan(val):
                results.append({"ts_code": tc, "factor_value": val})
        result_df = pd.DataFrame(results)
        result_df["calc_date"] = target_date
        result_df["factor_id"] = factor_id
        return result_df

    register_factor(factor_id, {
        "factor_id": factor_id,
        "name": name,
        "category": category,
        "description": f"累计收益率，过去 {window} 个交易日",
        "direction": "higher_better",
        "lookback_days": window,
    }, calc)


def _register_vol_ratio(name: str, factor_id: str, window: int):
    """注册量比因子：当日成交量 / 过去 window 日均成交量。"""
    def calc(target_date: str, db_path: str = None):
        import pandas as pd
        conn = _get_db_conn()
        cutoff_df = pd.read_sql("""
            SELECT DISTINCT trade_date FROM daily_data
            WHERE trade_date <= ?
            ORDER BY trade_date DESC
            LIMIT ?
        """, conn, params=[target_date, window + 1])
        if len(cutoff_df) < window + 1:
            conn.close()
            return pd.DataFrame()
        cutoff = cutoff_df.iloc[-1]["trade_date"]
        df = pd.read_sql(f"""
            SELECT ts_code,
                   trade_date,
                   vol,
                   AVG(vol) OVER (
                       PARTITION BY ts_code
                       ORDER BY trade_date
                       ROWS BETWEEN {window-1} PRECEDING AND CURRENT ROW
                   ) as vol_ma
            FROM daily_data
            WHERE trade_date >= ? AND trade_date <= ?
        """, conn, params=[cutoff, target_date])
        conn.close()
        if df.empty:
            return pd.DataFrame()
        # 取每个 ts_code 当日行（最后一条）
        last = df.groupby("ts_code").last().reset_index()
        last["factor_value"] = last["vol"] / last["vol_ma"]
        last["factor_id"] = factor_id
        last["calc_date"] = target_date
        last = last.dropna(subset=["factor_value"])
        last = last[["ts_code", "factor_value", "factor_id", "calc_date"]]
        return last

    register_factor(factor_id, {
        "factor_id": factor_id,
        "name": name,
        "category": "volume",
        "description": f"量比：当日成交量 / 过去 {window} 日均成交量",
        "direction": "higher_better",
        "lookback_days": window,
    }, calc)


def _register_amount_ratio(name: str, factor_id: str, window: int):
    """注册金额比因子：当日成交额 / 过去 window 日均成交额。"""
    def calc(target_date: str, db_path: str = None):
        import pandas as pd
        conn = _get_db_conn()
        cutoff_df = pd.read_sql("""
            SELECT DISTINCT trade_date FROM daily_data
            WHERE trade_date <= ?
            ORDER BY trade_date DESC
            LIMIT ?
        """, conn, params=[target_date, window + 1])
        if len(cutoff_df) < window + 1:
            conn.close()
            return pd.DataFrame()
        cutoff = cutoff_df.iloc[-1]["trade_date"]
        df = pd.read_sql(f"""
            SELECT ts_code,
                   trade_date,
                   amount,
                   AVG(amount) OVER (
                       PARTITION BY ts_code
                       ORDER BY trade_date
                       ROWS BETWEEN {window-1} PRECEDING AND CURRENT ROW
                   ) as amount_ma
            FROM daily_data
            WHERE trade_date >= ? AND trade_date <= ?
        """, conn, params=[cutoff, target_date])
        conn.close()
        if df.empty:
            return pd.DataFrame()
        last = df.groupby("ts_code").last().reset_index()
        last["factor_value"] = last["amount"] / last["amount_ma"]
        last["factor_id"] = factor_id
        last["calc_date"] = target_date
        last = last.dropna(subset=["factor_value"])
        last = last[["ts_code", "factor_value", "factor_id", "calc_date"]]
        return last

    register_factor(factor_id, {
        "factor_id": factor_id,
        "name": name,
        "category": "volume",
        "description": f"额比：当日成交额 / 过去 {window} 日均成交额",
        "direction": "higher_better",
        "lookback_days": window,
    }, calc)


def _register_amplitude(name: str, factor_id: str, window: int):
    """注册振幅因子：过去 window 日（最高价-最低价）/ 均价。"""
    def calc(target_date: str, db_path: str = None):
        import pandas as pd
        conn = _get_db_conn()
        cutoff_df = pd.read_sql("""
            SELECT DISTINCT trade_date FROM daily_data
            WHERE trade_date <= ?
            ORDER BY trade_date DESC
            LIMIT ?
        """, conn, params=[target_date, window])
        if len(cutoff_df) < window:
            conn.close()
            return pd.DataFrame()
        cutoff = cutoff_df.iloc[-1]["trade_date"]
        df = pd.read_sql("""
            SELECT ts_code,
                   MAX(close) - MIN(close) as price_range,
                   AVG(close) as price_mean
            FROM daily_data
            WHERE trade_date >= ? AND trade_date <= ?
            GROUP BY ts_code
        """, conn, params=[cutoff, target_date])
        conn.close()
        if df.empty:
            return pd.DataFrame()
        df["factor_value"] = df["price_range"] / df["price_mean"]
        df["factor_id"] = factor_id
        df["calc_date"] = target_date
        df = df[["ts_code", "factor_value", "factor_id", "calc_date"]]
        return df

    register_factor(factor_id, {
        "factor_id": factor_id,
        "name": name,
        "category": "volatility",
        "description": f"振幅：过去 {window} 日（最高-最低）/ 均价的比值",
        "direction": "neutral",
        "lookback_days": window,
    }, calc)


def _register_close_position(name: str, factor_id: str, window: int):
    """注册收盘位置因子：(收盘价 - 最低价) / (最高价 - 最低价)，反映当日涨跌位置。"""
    def calc(target_date: str, db_path: str = None):
        import numpy as np
        import pandas as pd
        conn = _get_db_conn()
        # 需要过去 window 天内的最高和最低，用子查询
        cutoff_df = pd.read_sql("""
            SELECT DISTINCT trade_date FROM daily_data
            WHERE trade_date <= ?
            ORDER BY trade_date DESC
            LIMIT ?
        """, conn, params=[target_date, window])
        if len(cutoff_df) < window:
            conn.close()
            return pd.DataFrame()
        cutoff = cutoff_df.iloc[-1]["trade_date"]
        df = pd.read_sql(f"""
            SELECT ts_code,
                   trade_date,
                   close,
                   MAX(close) OVER (
                       PARTITION BY ts_code
                       ORDER BY trade_date
                       ROWS BETWEEN {window-1} PRECEDING AND CURRENT ROW
                   ) as high_price,
                   MIN(close) OVER (
                       PARTITION BY ts_code
                       ORDER BY trade_date
                       ROWS BETWEEN {window-1} PRECEDING AND CURRENT ROW
                   ) as low_price
            FROM daily_data
            WHERE trade_date >= ? AND trade_date <= ?
        """, conn, params=[cutoff, target_date])
        conn.close()
        if df.empty:
            return pd.DataFrame()
        last = df.groupby("ts_code").last().reset_index()
        denom = last["high_price"] - last["low_price"]
        last["factor_value"] = np.where(denom > 0,
                                        (last["close"] - last["low_price"]) / denom,
                                        np.nan)
        last["factor_id"] = factor_id
        last["calc_date"] = target_date
        last = last.dropna(subset=["factor_value"])
        last = last[["ts_code", "factor_value", "factor_id", "calc_date"]]
        return last

    register_factor(factor_id, {
        "factor_id": factor_id,
        "name": name,
        "category": "momentum",
        "description": f"收盘位置：(收盘价-最低价)/(最高价-最低价)，过去 {window} 日窗口",
        "direction": "higher_better",
        "lookback_days": window,
    }, calc)


def _register_turnover(name: str, factor_id: str, window: int):
    """注册换手率因子：过去 window 日平均日换手率（成交量/总股本）。"""
    def calc(target_date: str, db_path: str = None):
        import numpy as np
        import pandas as pd
        conn = _get_db_conn()
        cutoff_df = pd.read_sql("""
            SELECT DISTINCT trade_date FROM daily_data
            WHERE trade_date <= ?
            ORDER BY trade_date DESC
            LIMIT ?
        """, conn, params=[target_date, window])
        if len(cutoff_df) < window:
            conn.close()
            return pd.DataFrame()
        cutoff = cutoff_df.iloc[-1]["trade_date"]
        df = pd.read_sql("""
            SELECT ts_code, AVG(vol) as avg_vol
            FROM daily_data
            WHERE trade_date >= ? AND trade_date <= ?
            GROUP BY ts_code
        """, conn, params=[cutoff, target_date])
        # 获取总股本
        shares_df = pd.read_sql("""
            SELECT ts_code, total_share FROM balance_sheet
            WHERE total_share IS NOT NULL
        """, conn)
        conn.close()
        if df.empty:
            return pd.DataFrame()
        df = df.merge(shares_df, on="ts_code", how="left")
        df["factor_value"] = df["avg_vol"] / df["total_share"] * 100
        df = df.replace([np.inf, -np.inf], np.nan)
        df["factor_id"] = factor_id
        df["calc_date"] = target_date
        df = df[["ts_code", "factor_value", "factor_id", "calc_date"]]
        return df

    register_factor(factor_id, {
        "factor_id": factor_id,
        "name": name,
        "category": "liquidity",
        "description": f"日均换手率（%），过去 {window} 日平均成交量/总股本",
        "direction": "neutral",
        "lookback_days": window,
    }, calc)


def _register_vol_volatility(name: str, factor_id: str, window: int):
    """注册成交量波动率因子：过去 window 日成交量的标准差/均值。"""
    def calc(target_date: str, db_path: str = None):
        import numpy as np
        import pandas as pd
        conn = _get_db_conn()
        cutoff_df = pd.read_sql("""
            SELECT DISTINCT trade_date FROM daily_data
            WHERE trade_date <= ?
            ORDER BY trade_date DESC
            LIMIT ?
        """, conn, params=[target_date, window])
        if len(cutoff_df) < window:
            conn.close()
            return pd.DataFrame()
        cutoff = cutoff_df.iloc[-1]["trade_date"]
        # SQLite has no built-in STD(); compute manually via E[X²]-E[X]²
        df = pd.read_sql("""
            SELECT ts_code,
                   AVG(vol) as mean_vol,
                   AVG(vol * vol) as mean_sq_vol
            FROM daily_data
            WHERE trade_date >= ? AND trade_date <= ?
            GROUP BY ts_code
        """, conn, params=[cutoff, target_date])
        conn.close()
        if df.empty:
            return pd.DataFrame()
        df["factor_value"] = np.sqrt(np.maximum(df["mean_sq_vol"] - df["mean_vol"] ** 2, 0)) / np.maximum(df["mean_vol"], 1e-9)
        df["factor_id"] = factor_id
        df["calc_date"] = target_date
        df = df[["ts_code", "factor_value", "factor_id", "calc_date"]]
        return df

    register_factor(factor_id, {
        "factor_id": factor_id,
        "name": name,
        "category": "volume",
        "description": f"成交量波动率（标准差/均值），过去 {window} 日",
        "direction": "neutral",
        "lookback_days": window,
    }, calc)


def _register_price_osc(name: str, factor_id: str, window: int):
    """注册价格摆动因子：收盘价 / 过去 window 日均价。"""
    def calc(target_date: str, db_path: str = None):
        import pandas as pd
        conn = _get_db_conn()
        cutoff_df = pd.read_sql("""
            SELECT DISTINCT trade_date FROM daily_data
            WHERE trade_date <= ?
            ORDER BY trade_date DESC
            LIMIT ?
        """, conn, params=[target_date, window])
        if len(cutoff_df) < window:
            conn.close()
            return pd.DataFrame()
        cutoff = cutoff_df.iloc[-1]["trade_date"]
        df = pd.read_sql(f"""
            SELECT ts_code,
                   trade_date,
                   close,
                   AVG(close) OVER (
                       PARTITION BY ts_code
                       ORDER BY trade_date
                       ROWS BETWEEN {window-1} PRECEDING AND CURRENT ROW
                   ) as ma_close
            FROM daily_data
            WHERE trade_date >= ? AND trade_date <= ?
        """, conn, params=[cutoff, target_date])
        conn.close()
        if df.empty:
            return pd.DataFrame()
        last = df.groupby("ts_code").last().reset_index()
        last["factor_value"] = last["close"] / last["ma_close"]
        last["factor_id"] = factor_id
        last["calc_date"] = target_date
        last = last.dropna(subset=["factor_value"])
        last = last[["ts_code", "factor_value", "factor_id", "calc_date"]]
        return last

    register_factor(factor_id, {
        "factor_id": factor_id,
        "name": name,
        "category": "momentum",
        "description": f"价格摆动：收盘价 / 过去 {window} 日均价",
        "direction": "higher_better",
        "lookback_days": window,
    }, calc)


# ---- 注册新增因子 ----
_register_ret("收益率 10D", "RET_10D", 10)
_register_ret("收益率 20D", "RET_20D", 20)
_register_ret("收益率 60D", "RET_60D", 60)

_register_vol_ratio("量比 5D", "VOL_RATIO_5D", 5)
_register_vol_ratio("量比 20D", "VOL_RATIO_20D", 20)

_register_amount_ratio("额比 5D", "AMOUNT_RATIO_5D", 5)
_register_amount_ratio("额比 20D", "AMOUNT_RATIO_20D", 20)

_register_amplitude("振幅 20D", "AMPLITUDE_20D", 20)
_register_amplitude("振幅 60D", "AMPLITUDE_60D", 60)

_register_close_position("收盘位置 20D", "CLOSE_POS_20D", 20)
_register_close_position("收盘位置 60D", "CLOSE_POS_60D", 60)

_register_turnover("换手率 20D", "TURNOVER_20D", 20)

_register_vol_volatility("成交量波动 20D", "VOL_VOL_20D", 20)

_register_price_osc("价格摆动 20D", "PRICE_OSC_20D", 20)


# ============================================================
# Profitability Factors
# ============================================================

def calc_ROE(target_date: str, db_path: str = None):
    """
    ROE - Return on Equity.
    = n_income_attr_p / total_hldr_eqy_exc_min_int
    """
    import numpy as np
    import pandas as pd
    conn = _get_db_conn()
    df = pd.read_sql("""
        SELECT i.ts_code,
               i.n_income_attr_p,
               b.total_hldr_eqy_exc_min_int
        FROM income_statement i
        JOIN balance_sheet b ON i.ts_code = b.ts_code AND i.end_date = b.end_date
        WHERE i.end_date = ?
          AND b.total_hldr_eqy_exc_min_int > 0
          AND i.n_income_attr_p IS NOT NULL
    """, conn, params=[target_date])
    conn.close()
    if df.empty:
        return pd.DataFrame()
    df["factor_value"] = df["n_income_attr_p"] / df["total_hldr_eqy_exc_min_int"]
    df = df.replace([np.inf, -np.inf], np.nan)
    df["factor_id"] = "ROE"
    df["calc_date"] = target_date
    df = df[["ts_code", "factor_value", "factor_id", "calc_date"]]
    return df


register_factor("ROE", {
    "factor_id": "ROE",
    "name": "Return on Equity",
    "category": "profitability",
    "description": "Net income attributable to parent / total shareholders equity",
    "direction": "higher_better",
    "lookback_days": 0,
}, calc_ROE)


def calc_ROA(target_date: str, db_path: str = None):
    """
    ROA - Return on Assets.
    = n_income_attr_p / total_assets
    """
    import numpy as np
    import pandas as pd
    conn = _get_db_conn()
    df = pd.read_sql("""
        SELECT i.ts_code,
               i.n_income_attr_p,
               b.total_assets
        FROM income_statement i
        JOIN balance_sheet b ON i.ts_code = b.ts_code AND i.end_date = b.end_date
        WHERE i.end_date = ?
          AND b.total_assets > 0
          AND i.n_income_attr_p IS NOT NULL
    """, conn, params=[target_date])
    conn.close()
    if df.empty:
        return pd.DataFrame()
    df["factor_value"] = df["n_income_attr_p"] / df["total_assets"]
    df = df.replace([np.inf, -np.inf], np.nan)
    df["factor_id"] = "ROA"
    df["calc_date"] = target_date
    df = df[["ts_code", "factor_value", "factor_id", "calc_date"]]
    return df


register_factor("ROA", {
    "factor_id": "ROA",
    "name": "Return on Assets",
    "category": "profitability",
    "description": "Net income attributable to parent / total assets",
    "direction": "higher_better",
    "lookback_days": 0,
}, calc_ROA)
