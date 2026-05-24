"""Additional price, volume, technical, and risk factors."""
from __future__ import annotations

import sqlite3

import numpy as np
import pandas as pd

from fundfactory_core.factors.registry import register_factor


def _db_path() -> str:
    from fundfactory_core.config import settings

    return settings.DB_PATH


def _connect(readonly: bool = True):
    path = _db_path()
    if readonly:
        return sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    return sqlite3.connect(path)


def _fetch_window(target_date: str, window: int) -> pd.DataFrame:
    conn = _connect()
    dates = pd.read_sql(
        """
        SELECT DISTINCT trade_date FROM daily_data
        WHERE trade_date <= ?
        ORDER BY trade_date DESC
        LIMIT ?
        """,
        conn,
        params=[target_date, window],
    )
    if len(dates) < window:
        conn.close()
        return pd.DataFrame()
    cutoff = dates.iloc[-1]["trade_date"]
    df = pd.read_sql(
        """
        SELECT ts_code, trade_date, open, high, low, close, pre_close, pct_chg, vol, amount
        FROM daily_data
        WHERE trade_date >= ? AND trade_date <= ?
        ORDER BY ts_code, trade_date
        """,
        conn,
        params=[cutoff, target_date],
    )
    conn.close()
    return df


def _finish(df: pd.DataFrame, factor_id: str, target_date: str) -> pd.DataFrame:
    if df.empty or "factor_value" not in df:
        return pd.DataFrame(columns=["ts_code", "factor_value", "factor_id", "calc_date"])
    out = df[["ts_code", "factor_value"]].copy()
    out["factor_value"] = pd.to_numeric(out["factor_value"], errors="coerce")
    out = out.replace([np.inf, -np.inf], np.nan).dropna(subset=["factor_value"])
    out["factor_id"] = factor_id
    out["calc_date"] = target_date
    return out[["ts_code", "factor_value", "factor_id", "calc_date"]]


def _shares() -> pd.DataFrame:
    conn = _connect()
    df = pd.read_sql(
        "SELECT ts_code, total_share FROM balance_sheet WHERE total_share IS NOT NULL",
        conn,
    )
    conn.close()
    return df.drop_duplicates("ts_code", keep="last")


def _calc_price_volume(factor_id: str, target_date: str) -> pd.DataFrame:
    lookback = _PV_FACTORS[factor_id][4]
    df = _fetch_window(target_date, max(lookback, 2))
    if df.empty:
        return _finish(df, factor_id, target_date)

    grouped = df.groupby("ts_code", sort=False)
    rows = []
    for ts_code, grp in grouped:
        if len(grp) < lookback:
            continue
        g = grp.tail(lookback).copy()
        ret = pd.to_numeric(g["pct_chg"], errors="coerce") / 100.0
        close = pd.to_numeric(g["close"], errors="coerce")
        high = pd.to_numeric(g["high"], errors="coerce")
        low = pd.to_numeric(g["low"], errors="coerce")
        pre_close = pd.to_numeric(g["pre_close"], errors="coerce")
        vol = pd.to_numeric(g["vol"], errors="coerce")
        amount = pd.to_numeric(g["amount"], errors="coerce")
        value = np.nan

        if factor_id.startswith("REV_"):
            value = -((1 + ret).prod() - 1) * 100
        elif factor_id == "MOM_120D":
            value = ((1 + ret).prod() - 1) * 100
        elif factor_id == "WEIGHTED_MOM_20D":
            weights = np.arange(1, len(ret) + 1)
            value = np.average(ret, weights=weights) * 100
        elif factor_id == "PRICE_ACCELERATION":
            recent = (1 + ret.tail(5)).prod() - 1
            prior = (1 + ret.iloc[-10:-5]).prod() - 1
            value = (recent - prior) * 100
        elif factor_id == "RETURN_CONSISTENCY_20D":
            value = (ret > 0).mean()
        elif factor_id == "MAX_RET":
            value = ret.max() * 100
        elif factor_id == "MIN_RET":
            value = ret.min() * 100
        elif factor_id == "CLOSE_TO_HIGH_20D":
            value = close.iloc[-1] / high.max()
        elif factor_id == "CLOSE_TO_LOW_20D":
            value = close.iloc[-1] / low.min()
        elif factor_id.startswith("MA_DEV_"):
            value = close.iloc[-1] / close.mean() - 1
        elif factor_id == "RSI_20D":
            gain = ret.clip(lower=0).mean()
            loss = (-ret.clip(upper=0)).mean()
            value = gain / (gain + loss) if gain + loss != 0 else np.nan
        elif factor_id == "WILLIAMS_R_20D":
            denom = high.max() - low.min()
            value = (high.max() - close.iloc[-1]) / denom if denom != 0 else np.nan
        elif factor_id == "ILLIQ":
            valid_amount = amount.replace(0, np.nan)
            value = (ret.abs() / valid_amount).mean()
        elif factor_id == "ATR_14" or factor_id == "ATR_20D":
            tr = pd.concat([(high - low), (high - pre_close).abs(), (low - pre_close).abs()], axis=1).max(axis=1)
            value = tr.mean()
        elif factor_id == "DOWNSIDE_VOL_20D":
            value = ret[ret < 0].std()
        elif factor_id == "INTRADAY_RANGE_20D":
            value = ((high - low) / close.replace(0, np.nan)).mean()
        elif factor_id == "HIGH_LOW_RATIO_20D":
            value = high.max() / low.min()
        elif factor_id == "UP_DOWN_VOL_RATIO":
            value = ret[ret > 0].std() / ret[ret < 0].std()
        elif factor_id == "TURNOVER_5D":
            value = vol.mean()

        rows.append({"ts_code": ts_code, "factor_value": value})

    out = pd.DataFrame(rows)
    if factor_id == "TURNOVER_5D" and not out.empty:
        out = out.merge(_shares(), on="ts_code", how="left")
        out["factor_value"] = out["factor_value"] / out["total_share"] * 100
    return _finish(out, factor_id, target_date)


def _make_calc(factor_id: str):
    def calc(target_date: str, db_path: str = None):
        return _calc_price_volume(factor_id, target_date)

    return calc


_PV_FACTORS = {
    "REV_5D": ("5日反转", "reversal", "过去5日累计收益取反", "higher_better", 5),
    "REV_10D": ("10日反转", "reversal", "过去10日累计收益取反", "higher_better", 10),
    "REV_20D": ("20日反转", "reversal", "过去20日累计收益取反", "higher_better", 20),
    "MOM_120D": ("120日动量", "momentum", "过去120日累计收益", "higher_better", 120),
    "WEIGHTED_MOM_20D": ("20日加权动量", "momentum", "越近权重越高的20日收益均值", "higher_better", 20),
    "PRICE_ACCELERATION": ("价格加速度", "momentum", "最近5日动量减前5日动量", "higher_better", 10),
    "RETURN_CONSISTENCY_20D": ("上涨天数占比", "momentum", "过去20日上涨天数比例", "higher_better", 20),
    "MAX_RET": ("最大日收益", "lottery", "过去20日最大单日收益", "neutral", 20),
    "MIN_RET": ("最小日收益", "lottery", "过去20日最小单日收益", "neutral", 20),
    "CLOSE_TO_HIGH_20D": ("距20日高点", "technical", "收盘价 / 20日最高价", "higher_better", 20),
    "CLOSE_TO_LOW_20D": ("距20日低点", "technical", "收盘价 / 20日最低价", "higher_better", 20),
    "MA_DEV_20D": ("20日均线偏离", "technical", "收盘价 / 20日均价 - 1", "neutral", 20),
    "MA_DEV_60D": ("60日均线偏离", "technical", "收盘价 / 60日均价 - 1", "neutral", 60),
    "RSI_20D": ("20日RSI", "technical", "上涨收益均值 / 上下波动均值", "neutral", 20),
    "WILLIAMS_R_20D": ("20日威廉指标", "technical", "最高价与收盘价位置关系", "neutral", 20),
    "ILLIQ": ("Amihud非流动性", "liquidity", "平均绝对收益 / 成交额", "lower_better", 20),
    "TURNOVER_5D": ("5日换手率", "liquidity", "5日平均成交量 / 总股本", "neutral", 5),
    "ATR_14": ("14日ATR", "volatility", "14日平均真实波幅", "neutral", 14),
    "ATR_20D": ("20日ATR", "volatility", "20日平均真实波幅", "neutral", 20),
    "DOWNSIDE_VOL_20D": ("20日下行波动率", "volatility", "负收益日标准差", "lower_better", 20),
    "INTRADAY_RANGE_20D": ("20日日内振幅", "volatility", "平均日内高低价振幅", "neutral", 20),
    "HIGH_LOW_RATIO_20D": ("20日高低价比", "volatility", "20日最高价 / 最低价", "neutral", 20),
    "UP_DOWN_VOL_RATIO": ("上下行波动比", "volatility", "上涨日波动 / 下跌日波动", "neutral", 20),
}


for _fid, (_name, _category, _description, _direction, _lookback) in _PV_FACTORS.items():
    register_factor(
        _fid,
        {
            "factor_id": _fid,
            "name": _name,
            "category": _category,
            "description": _description,
            "direction": _direction,
            "lookback_days": _lookback,
        },
        _make_calc(_fid),
    )
