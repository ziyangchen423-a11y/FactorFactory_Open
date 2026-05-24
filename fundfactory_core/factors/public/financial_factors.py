"""Common financial factors for the open schema.

The open edition computes these directly from income_statement, balance_sheet,
cash_flow, and daily_data. A few classic definitions require fields not present
in the open schema; those are registered with explicit approximation metadata
and return either a documented proxy or an empty frame.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime

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


def _prev_year(date: str) -> str:
    try:
        return datetime.strptime(date, "%Y%m%d").replace(year=int(date[:4]) - 1).strftime("%Y%m%d")
    except ValueError:
        return str(int(date) - 10000)


def _safe_div(num, den):
    den = pd.to_numeric(den, errors="coerce").replace(0, np.nan)
    return pd.to_numeric(num, errors="coerce") / den


def _finish(df: pd.DataFrame, factor_id: str, target_date: str) -> pd.DataFrame:
    if df.empty or "factor_value" not in df:
        return pd.DataFrame(columns=["ts_code", "factor_value", "factor_id", "calc_date"])
    out = df[["ts_code", "factor_value"]].copy()
    out["factor_value"] = pd.to_numeric(out["factor_value"], errors="coerce")
    out = out.replace([np.inf, -np.inf], np.nan).dropna(subset=["factor_value"])
    out["factor_id"] = factor_id
    out["calc_date"] = target_date
    return out[["ts_code", "factor_value", "factor_id", "calc_date"]]


def _empty(factor_id: str, target_date: str) -> pd.DataFrame:
    return _finish(pd.DataFrame(columns=["ts_code", "factor_value"]), factor_id, target_date)


def _load_financial(target_date: str) -> pd.DataFrame:
    conn = _connect()
    latest = pd.read_sql(
        """
        SELECT MAX(end_date) AS end_date
        FROM income_statement
        WHERE end_date <= ?
        """,
        conn,
        params=[target_date],
    ).iloc[0]["end_date"]
    if latest is None:
        conn.close()
        return pd.DataFrame()
    prev = _prev_year(str(latest))
    df = pd.read_sql(
        """
        SELECT
            COALESCE(i.ts_code, b.ts_code, c.ts_code) AS ts_code,
            i.revenue, i.oper_cost, i.sell_exp, i.admin_exp, i.fin_exp, i.rd_exp,
            i.operate_profit, i.total_profit, i.income_tax, i.n_income,
            i.n_income_attr_p, i.basic_eps, i.ebit, i.ebitda,
            b.total_share, b.money_cap, b.accounts_receiv, b.inventories,
            b.total_cur_assets, b.total_cur_liab, b.fix_assets, b.intan_assets,
            b.goodwill, b.total_assets, b.total_liab, b.st_borr, b.lt_borr,
            b.total_hldr_eqy_exc_min_int, b.accounts_pay,
            c.net_profit, c.c_fr_sale_sg, c.n_cashflow_act, c.n_cashflow_inv_act,
            c.free_cashflow, c.n_cash_flows_fnc_act,
            ip.revenue AS p_revenue, ip.oper_cost AS p_oper_cost,
            ip.operate_profit AS p_operate_profit, ip.n_income_attr_p AS p_n_income_attr_p,
            bp.total_assets AS p_total_assets, bp.total_hldr_eqy_exc_min_int AS p_equity,
            bp.total_cur_assets AS p_total_cur_assets, bp.fix_assets AS p_fix_assets,
            bp.accounts_receiv AS p_accounts_receiv, bp.inventories AS p_inventories,
            bp.accounts_pay AS p_accounts_pay,
            cp.n_cashflow_act AS p_n_cashflow_act
        FROM income_statement i
        LEFT JOIN balance_sheet b ON i.ts_code = b.ts_code AND i.end_date = b.end_date
        LEFT JOIN cash_flow c ON i.ts_code = c.ts_code AND i.end_date = c.end_date
        LEFT JOIN income_statement ip ON i.ts_code = ip.ts_code AND ip.end_date = ?
        LEFT JOIN balance_sheet bp ON i.ts_code = bp.ts_code AND bp.end_date = ?
        LEFT JOIN cash_flow cp ON i.ts_code = cp.ts_code AND cp.end_date = ?
        WHERE i.end_date = ?
        """,
        conn,
        params=[prev, prev, prev, latest],
    )
    conn.close()
    return df


def _market_cap(target_date: str) -> pd.DataFrame:
    conn = _connect()
    df = pd.read_sql(
        """
        SELECT d.ts_code, d.close, b.total_share, d.close * b.total_share AS market_cap
        FROM daily_data d
        JOIN (
            SELECT ts_code, MAX(end_date) AS end_date
            FROM balance_sheet
            WHERE end_date <= ?
            GROUP BY ts_code
        ) latest ON d.ts_code = latest.ts_code
        JOIN balance_sheet b ON d.ts_code = b.ts_code AND b.end_date = latest.end_date
        WHERE d.trade_date = ?
          AND b.total_share IS NOT NULL AND d.close IS NOT NULL
        """,
        conn,
        params=[target_date, target_date],
    )
    conn.close()
    return df


def _avg(df: pd.DataFrame, cur: str, prev: str):
    return (pd.to_numeric(df[cur], errors="coerce") + pd.to_numeric(df[prev], errors="coerce")) / 2


def _calc_financial(factor_id: str, target_date: str) -> pd.DataFrame:
    df = _load_financial(target_date)
    if df.empty:
        return _empty(factor_id, target_date)

    equity_avg = _avg(df, "total_hldr_eqy_exc_min_int", "p_equity")
    assets_avg = _avg(df, "total_assets", "p_total_assets")
    ar_avg = _avg(df, "accounts_receiv", "p_accounts_receiv")
    inv_avg = _avg(df, "inventories", "p_inventories")
    ca_avg = _avg(df, "total_cur_assets", "p_total_cur_assets")
    fa_avg = _avg(df, "fix_assets", "p_fix_assets")
    ap_avg = _avg(df, "accounts_pay", "p_accounts_pay")

    gross_profit = df["revenue"] - df["oper_cost"]
    p_gross_profit = df["p_revenue"] - df["p_oper_cost"]
    cost_expense = (
        df["oper_cost"].fillna(0)
        + df["sell_exp"].fillna(0)
        + df["admin_exp"].fillna(0)
        + df["fin_exp"].fillna(0)
        + df["rd_exp"].fillna(0)
    )
    debt_interest = df["st_borr"].fillna(0) + df["lt_borr"].fillna(0)

    formulas = {
        "PROF_01": _safe_div(df["n_income_attr_p"], equity_avg),
        "PROF_02": _safe_div(df["n_income_attr_p"], assets_avg),
        "PROF_03": _safe_div(df["n_income_attr_p"].fillna(0) + df["fin_exp"].fillna(0), df["total_liab"].fillna(0) + df["total_hldr_eqy_exc_min_int"].fillna(0)),
        "PROF_04": _safe_div(gross_profit, df["revenue"]),
        "PROF_05": _safe_div(df["n_income_attr_p"], df["revenue"]),
        "PROF_06": _safe_div(df["operate_profit"], df["revenue"]),
        "PROF_07": _safe_div(df["ebit"], df["revenue"]),
        "PROF_08": _safe_div(df["ebitda"], df["revenue"]),
        "PROF_09": _safe_div(df["total_profit"], cost_expense),
        "PROF_10": _safe_div(df["n_income_attr_p"], equity_avg),
        "GROW_01": _safe_div(df["revenue"] - df["p_revenue"], df["p_revenue"].abs()),
        "GROW_02": _safe_div(df["n_income_attr_p"] - df["p_n_income_attr_p"], df["p_n_income_attr_p"].abs()),
        "GROW_03": _safe_div(df["n_income_attr_p"] - df["p_n_income_attr_p"], df["p_n_income_attr_p"].abs()),
        "GROW_04": _safe_div(df["operate_profit"] - df["p_operate_profit"], df["p_operate_profit"].abs()),
        "GROW_05": _safe_div(gross_profit - p_gross_profit, p_gross_profit.abs()),
        "GROW_06": _safe_div(df["total_assets"] - df["p_total_assets"], df["p_total_assets"].abs()),
        "GROW_07": _safe_div(df["total_hldr_eqy_exc_min_int"] - df["p_equity"], df["p_equity"].abs()),
        "GROW_08": _safe_div(df["n_cashflow_act"] - df["p_n_cashflow_act"], df["p_n_cashflow_act"].abs()),
        "QUAL_01": _safe_div(df["n_cashflow_act"], df["n_income_attr_p"]),
        "QUAL_02": _safe_div(df["c_fr_sale_sg"], df["revenue"]),
        "QUAL_03": _safe_div(df["n_cashflow_act"], df["operate_profit"]),
        "QUAL_05": _safe_div(df["n_income_attr_p"] - df["n_cashflow_act"], df["total_assets"]),
        "QUAL_06": _safe_div(df["n_income_attr_p"] - df["operate_profit"], df["n_income_attr_p"]),
        "QUAL_07": _safe_div(df["n_cashflow_act"], assets_avg),
        "DEBT_01": _safe_div(df["total_liab"], df["total_assets"]),
        "DEBT_02": _safe_div(df["total_cur_assets"], df["total_cur_liab"]),
        "DEBT_03": _safe_div(df["total_cur_assets"] - df["inventories"].fillna(0), df["total_cur_liab"]),
        "DEBT_04": _safe_div(df["money_cap"], df["total_cur_liab"]),
        "DEBT_05": _safe_div(df["ebit"], df["fin_exp"].abs()),
        "DEBT_06": _safe_div(debt_interest, df["total_assets"]),
        "DEBT_07": _safe_div(df["lt_borr"], df["total_assets"]),
        "DEBT_08": _safe_div(df["total_hldr_eqy_exc_min_int"], df["total_assets"]),
        "OPER_01": _safe_div(df["revenue"], ar_avg),
        "OPER_02": _safe_div(df["oper_cost"], inv_avg),
        "OPER_03": _safe_div(df["revenue"], ca_avg),
        "OPER_04": _safe_div(df["revenue"], fa_avg),
        "OPER_05": _safe_div(df["revenue"], assets_avg),
        "OPER_06": _safe_div(df["oper_cost"], ap_avg),
        "EXP_01": _safe_div(df["sell_exp"], df["revenue"]),
        "EXP_02": _safe_div(df["admin_exp"], df["revenue"]),
        "EXP_03": _safe_div(df["fin_exp"], df["revenue"]),
        "EXP_04": _safe_div(df["rd_exp"], df["revenue"]),
        "EXP_05": _safe_div(df["sell_exp"].fillna(0) + df["admin_exp"].fillna(0) + df["rd_exp"].fillna(0) + df["fin_exp"].fillna(0), df["revenue"]),
    }

    if factor_id == "OPER_07":
        formulas[factor_id] = _safe_div(365, formulas["OPER_01"]) + _safe_div(365, formulas["OPER_02"])
    if factor_id == "OPER_08":
        formulas[factor_id] = (_safe_div(365, formulas["OPER_01"]) + _safe_div(365, formulas["OPER_02"])) - _safe_div(365, formulas["OPER_06"])

    if factor_id == "QUAL_04":
        mc = _market_cap(target_date)
        m = df[["ts_code", "free_cashflow"]].merge(mc[["ts_code", "market_cap"]], on="ts_code", how="inner")
        m["factor_value"] = _safe_div(m["free_cashflow"], m["market_cap"])
        return _finish(m, factor_id, target_date)

    if factor_id.startswith("VALU_"):
        mc = _market_cap(target_date)
        m = df.merge(mc[["ts_code", "market_cap"]], on="ts_code", how="inner")
        if factor_id == "VALU_01":
            m["factor_value"] = _safe_div(m["market_cap"], m["n_income_attr_p"])
        elif factor_id == "VALU_02":
            m["factor_value"] = _safe_div(m["market_cap"], m["total_hldr_eqy_exc_min_int"])
        elif factor_id == "VALU_03":
            m["factor_value"] = _safe_div(m["market_cap"], m["revenue"])
        elif factor_id == "VALU_04":
            m["factor_value"] = _safe_div(m["market_cap"], m["n_cashflow_act"])
        else:
            return _empty(factor_id, target_date)
        return _finish(m, factor_id, target_date)

    out = df[["ts_code"]].copy()
    out["factor_value"] = formulas.get(factor_id)
    return _finish(out, factor_id, target_date)


def _make_calc(factor_id: str):
    def calc(target_date: str, db_path: str = None):
        return _calc_financial(factor_id, target_date)

    return calc


_FINANCIAL_FACTORS = {
    "PROF_01": ("净资产收益率", "profitability", "归母净利润 / 平均净资产", "higher_better", 0),
    "PROF_02": ("总资产收益率", "profitability", "归母净利润 / 平均总资产", "higher_better", 0),
    "PROF_03": ("投入资本回报率", "profitability", "净利润加财务费用 / 投入资本近似值", "higher_better", 0),
    "PROF_04": ("销售毛利率", "profitability", "营业收入减营业成本 / 营业收入", "higher_better", 0),
    "PROF_05": ("销售净利率", "profitability", "归母净利润 / 营业收入", "higher_better", 0),
    "PROF_06": ("营业利润率", "profitability", "营业利润 / 营业收入", "higher_better", 0),
    "PROF_07": ("EBIT率", "profitability", "EBIT / 营业收入", "higher_better", 0),
    "PROF_08": ("EBITDA率", "profitability", "EBITDA / 营业收入", "higher_better", 0),
    "PROF_09": ("成本费用利润率", "profitability", "利润总额 / 成本费用合计", "higher_better", 0),
    "PROF_10": ("扣非ROE近似", "profitability", "open schema 无扣非字段，暂以 ROE 近似", "higher_better", 0),
    "GROW_01": ("营业收入同比增长率", "growth", "营业收入同比增长", "higher_better", 365),
    "GROW_02": ("净利润同比增长率", "growth", "归母净利润同比增长", "higher_better", 365),
    "GROW_03": ("扣非净利润同比近似", "growth", "open schema 无扣非字段，暂以归母净利润同比近似", "higher_better", 365),
    "GROW_04": ("营业利润同比增长率", "growth", "营业利润同比增长", "higher_better", 365),
    "GROW_05": ("毛利润同比增长率", "growth", "毛利润同比增长", "higher_better", 365),
    "GROW_06": ("总资产同比增长率", "growth", "总资产同比增长", "neutral", 365),
    "GROW_07": ("净资产同比增长率", "growth", "归母权益同比增长", "higher_better", 365),
    "GROW_08": ("经营现金流同比增长率", "growth", "经营现金流同比增长", "higher_better", 365),
    "QUAL_01": ("现金流利润比", "quality", "经营现金流净额 / 归母净利润", "higher_better", 0),
    "QUAL_02": ("销售收现率", "quality", "销售商品收到现金 / 营业收入", "higher_better", 0),
    "QUAL_03": ("盈利现金比率", "quality", "经营现金流净额 / 营业利润", "higher_better", 0),
    "QUAL_04": ("自由现金流收益率", "quality", "自由现金流 / 总市值", "higher_better", 0),
    "QUAL_05": ("应计项目占比", "quality", "净利润减经营现金流 / 总资产", "lower_better", 0),
    "QUAL_06": ("非经常性损益占比近似", "quality", "open schema 无 adj_lossgain，以净利润与营业利润差额近似", "lower_better", 0),
    "QUAL_07": ("经营现金流总资产比", "quality", "经营现金流净额 / 平均总资产", "higher_better", 0),
    "DEBT_01": ("资产负债率", "leverage", "总负债 / 总资产", "lower_better", 0),
    "DEBT_02": ("流动比率", "leverage", "流动资产 / 流动负债", "higher_better", 0),
    "DEBT_03": ("速动比率", "leverage", "流动资产减存货 / 流动负债", "higher_better", 0),
    "DEBT_04": ("现金比率", "leverage", "货币资金 / 流动负债", "higher_better", 0),
    "DEBT_05": ("利息保障倍数", "leverage", "EBIT / 财务费用绝对值", "higher_better", 0),
    "DEBT_06": ("有息负债率", "leverage", "短期借款加长期借款 / 总资产", "lower_better", 0),
    "DEBT_07": ("长期负债比率", "leverage", "长期借款 / 总资产", "lower_better", 0),
    "DEBT_08": ("股东权益比率", "leverage", "归母权益 / 总资产", "higher_better", 0),
    "OPER_01": ("应收账款周转率", "operating", "营业收入 / 平均应收账款", "higher_better", 0),
    "OPER_02": ("存货周转率", "operating", "营业成本 / 平均存货", "higher_better", 0),
    "OPER_03": ("流动资产周转率", "operating", "营业收入 / 平均流动资产", "higher_better", 0),
    "OPER_04": ("固定资产周转率", "operating", "营业收入 / 平均固定资产", "higher_better", 0),
    "OPER_05": ("总资产周转率", "operating", "营业收入 / 平均总资产", "higher_better", 0),
    "OPER_06": ("应付账款周转率", "operating", "营业成本 / 平均应付账款", "neutral", 0),
    "OPER_07": ("营业周期", "operating", "应收账款周转天数 + 存货周转天数", "lower_better", 0),
    "OPER_08": ("现金周转周期", "operating", "营业周期 - 应付账款周转天数", "lower_better", 0),
    "VALU_01": ("市盈率", "valuation", "总市值 / 归母净利润，open 版使用当前报告期近似", "lower_better", 0),
    "VALU_02": ("市净率", "valuation", "总市值 / 归母权益", "lower_better", 0),
    "VALU_03": ("市销率", "valuation", "总市值 / 营业收入，open 版使用当前报告期近似", "lower_better", 0),
    "VALU_04": ("市现率", "valuation", "总市值 / 经营现金流净额", "lower_better", 0),
    "VALU_05": ("股息率占位", "valuation", "当前 open schema 无股息字段，暂返回空结果", "higher_better", 0),
    "EXP_01": ("销售费用率", "expense", "销售费用 / 营业收入", "lower_better", 0),
    "EXP_02": ("管理费用率", "expense", "管理费用 / 营业收入", "lower_better", 0),
    "EXP_03": ("财务费用率", "expense", "财务费用 / 营业收入", "lower_better", 0),
    "EXP_04": ("研发费用率", "expense", "研发费用 / 营业收入", "neutral", 0),
    "EXP_05": ("期间费用率", "expense", "销售管理研发财务费用合计 / 营业收入", "lower_better", 0),
}


for _fid, (_name, _category, _description, _direction, _lookback) in _FINANCIAL_FACTORS.items():
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
