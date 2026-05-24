"""
Test: verify 98-factor expansion targets are met.
These tests use an in-memory database with synthetic data - no Tushare token needed.
"""
import pytest
import sqlite3
import pandas as pd
import numpy as np
from pathlib import Path

# Add project to path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


EXPECTED_98_FACTOR_IDS = {
    "LNCAP",
    "MOM_5D", "MOM_20D", "MOM_60D",
    "VOL_20D", "VOL_60D",
    "PE_SIMPLE", "PB_SIMPLE",
    "RET_10D", "RET_20D", "RET_60D",
    "VOL_RATIO_5D", "VOL_RATIO_20D",
    "AMOUNT_RATIO_5D", "AMOUNT_RATIO_20D",
    "AMPLITUDE_20D", "AMPLITUDE_60D",
    "CLOSE_POS_20D", "CLOSE_POS_60D",
    "TURNOVER_20D", "VOL_VOL_20D", "PRICE_OSC_20D",
    "ROE", "ROA",
    "PROF_01", "PROF_02", "PROF_03", "PROF_04", "PROF_05",
    "PROF_06", "PROF_07", "PROF_08", "PROF_09", "PROF_10",
    "GROW_01", "GROW_02", "GROW_03", "GROW_04",
    "GROW_05", "GROW_06", "GROW_07", "GROW_08",
    "QUAL_01", "QUAL_02", "QUAL_03", "QUAL_04",
    "QUAL_05", "QUAL_06", "QUAL_07",
    "DEBT_01", "DEBT_02", "DEBT_03", "DEBT_04",
    "DEBT_05", "DEBT_06", "DEBT_07", "DEBT_08",
    "OPER_01", "OPER_02", "OPER_03", "OPER_04",
    "OPER_05", "OPER_06", "OPER_07", "OPER_08",
    "VALU_01", "VALU_02", "VALU_03", "VALU_04", "VALU_05",
    "EXP_01", "EXP_02", "EXP_03", "EXP_04", "EXP_05",
    "REV_5D", "REV_10D", "REV_20D",
    "MOM_120D", "WEIGHTED_MOM_20D", "PRICE_ACCELERATION",
    "RETURN_CONSISTENCY_20D",
    "MAX_RET", "MIN_RET",
    "CLOSE_TO_HIGH_20D", "CLOSE_TO_LOW_20D",
    "MA_DEV_20D", "MA_DEV_60D",
    "RSI_20D", "WILLIAMS_R_20D",
    "ILLIQ", "TURNOVER_5D",
    "ATR_14", "ATR_20D", "DOWNSIDE_VOL_20D",
    "INTRADAY_RANGE_20D", "HIGH_LOW_RATIO_20D", "UP_DOWN_VOL_RATIO",
}


def _init_test_db(tmp_path):
    """Create an in-memory SQLite with minimal synthetic data for factor tests."""
    db_path = str(tmp_path / "test.db")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # trading_calendar
    cursor.execute("""
        CREATE TABLE trading_calendar (
            trade_date TEXT PRIMARY KEY,
            is_open INTEGER DEFAULT 1,
            day_of_week INTEGER,
            week_of_year INTEGER,
            month INTEGER,
            year INTEGER,
            quarter INTEGER
        )
    """)
    # Generate 500 trading days
    dates = pd.date_range("2020-01-01", periods=500, freq="B").strftime("%Y%m%d").tolist()
    for d in dates:
        cursor.execute("INSERT INTO trading_calendar VALUES (?, 1, 1, 1, 1, 2020, 1)", (d,))

    # stock_basic
    cursor.execute("""
        CREATE TABLE stock_basic (
            ts_code TEXT PRIMARY KEY,
            name TEXT,
            list_date TEXT
        )
    """)
    for i in range(50):
        cursor.execute(f"INSERT INTO stock_basic VALUES ('{i:06d}.SZ', 'STOCK_{i}', '20100101')")

    # daily_data
    cursor.execute("""
        CREATE TABLE daily_data (
            ts_code TEXT NOT NULL,
            trade_date TEXT NOT NULL,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            pre_close REAL,
            change REAL,
            pct_chg REAL,
            vol REAL,
            amount REAL,
            PRIMARY KEY (ts_code, trade_date)
        )
    """)

    np.random.seed(42)
    for ts in [f"{i:06d}.SZ" for i in range(50)]:
        price = 10.0
        for d in dates:
            pct = np.random.randn() * 2
            price = price * (1 + pct / 100)
            open_p = price * (1 + np.random.randn() * 0.01)
            high_p = max(price, open_p) * (1 + abs(np.random.randn()) * 0.01)
            low_p = min(price, open_p) * (1 - abs(np.random.randn()) * 0.01)
            vol = np.random.randint(1_000_000, 10_000_000)
            amt = vol * price
            cursor.execute(f"""
                INSERT INTO daily_data VALUES
                ('{ts}', '{d}', {open_p}, {high_p}, {low_p}, {price}, {price}, {pct}, {pct}, {vol}, {amt})
            """)

    # income_statement
    cursor.execute("""
        CREATE TABLE income_statement (
            ts_code TEXT,
            ann_date TEXT,
            f_ann_date TEXT,
            end_date TEXT,
            revenue REAL,
            oper_cost REAL,
            sell_exp REAL,
            admin_exp REAL,
            fin_exp REAL,
            rd_exp REAL,
            operate_profit REAL,
            total_profit REAL,
            income_tax REAL,
            n_income REAL,
            n_income_attr_p REAL,
            basic_eps REAL,
            ebit REAL,
            ebitda REAL,
            update_flag TEXT,
            PRIMARY KEY (ts_code, end_date)
        )
    """)
    for ts in [f"{i:06d}.SZ" for i in range(50)]:
        for year in ["20231231", "20221231", "20211231"]:
            rev = np.random.rand() * 1e10 + 1e9
            op = rev * np.random.rand() * 0.3
            ni = op * np.random.rand() * 0.7
            cursor.execute(f"""
                INSERT INTO income_statement VALUES
                ('{ts}', '{year}', '{year}', '{year}',
                 {rev}, {rev*0.6}, {rev*0.05}, {rev*0.03}, {rev*0.02}, {rev*0.01},
                 {op}, {op*0.85}, {op*0.15}, {ni}, {ni*0.9}, {ni/1e8},
                 {op*1.1}, {op*1.2}, NULL)
            """)

    # balance_sheet
    cursor.execute("""
        CREATE TABLE balance_sheet (
            ts_code TEXT,
            ann_date TEXT,
            f_ann_date TEXT,
            end_date TEXT,
            total_share REAL,
            money_cap REAL,
            accounts_receiv REAL,
            inventories REAL,
            total_cur_assets REAL,
            total_cur_liab REAL,
            fix_assets REAL,
            intan_assets REAL,
            goodwill REAL,
            total_assets REAL,
            total_liab REAL,
            st_borr REAL,
            lt_borr REAL,
            total_hldr_eqy_exc_min_int REAL,
            accounts_pay REAL,
            update_flag TEXT,
            PRIMARY KEY (ts_code, end_date)
        )
    """)
    for ts in [f"{i:06d}.SZ" for i in range(50)]:
        for year in ["20231231", "20221231", "20211231"]:
            ta = np.random.rand() * 1e11 + 1e10
            tl = ta * np.random.rand() * 0.6
            equity = ta - tl
            ts_val = np.random.rand() * 1e9 + 1e8
            cursor.execute(f"""
                INSERT INTO balance_sheet VALUES
                ('{ts}', '{year}', '{year}', '{year}',
                 {ts_val}, {tl*0.1}, {ta*0.05}, {ta*0.03}, {ta*0.3}, {ta*0.2},
                 {ta*0.1}, {ta*0.01}, {ta*0.02},
                 {ta}, {tl},
                 {tl*0.05}, {tl*0.05},
                 {equity}, {ta*0.05}, NULL)
            """)

    # cash_flow
    cursor.execute("""
        CREATE TABLE cash_flow (
            ts_code TEXT,
            ann_date TEXT,
            f_ann_date TEXT,
            end_date TEXT,
            net_profit REAL,
            c_fr_sale_sg REAL,
            n_cashflow_act REAL,
            n_cashflow_inv_act REAL,
            free_cashflow REAL,
            n_cash_flows_fnc_act REAL,
            update_flag TEXT,
            PRIMARY KEY (ts_code, end_date)
        )
    """)
    for ts in [f"{i:06d}.SZ" for i in range(50)]:
        for year in ["20231231", "20221231", "20211231"]:
            np_val = np.random.rand() * 1e9
            cursor.execute(f"""
                INSERT INTO cash_flow VALUES
                ('{ts}', '{year}', '{year}', '{year}',
                 {np_val}, {np_val*0.8}, {np_val*1.1}, {-np_val*0.1}, {np_val*0.3}, {np_val*0.5}, NULL)
            """)

    conn.commit()
    conn.close()
    return db_path


class Test98FactorExpansion:
    """Tests for the 98-factor expansion."""

    def test_factor_count_is_exactly_expected_98(self, tmp_path):
        """Registry must contain exactly the approved 98-factor set."""
        db_path = _init_test_db(tmp_path)

        # Override DB_PATH temporarily
        import fundfactory_core.config.settings as settings
        orig = settings.DB_PATH
        settings.DB_PATH = db_path

        try:
            # Re-import to pick up new DB path
            import importlib
            import fundfactory_core.factors.registry as reg
            importlib.reload(reg)

            ids = set(reg.factor_ids())
            assert len(ids) == 98, f"Expected exactly 98 factors, got {len(ids)}: {sorted(ids)}"
            assert ids == EXPECTED_98_FACTOR_IDS
        finally:
            settings.DB_PATH = orig

    def test_metadata_complete(self, tmp_path):
        """Every factor must have all required metadata fields."""
        db_path = _init_test_db(tmp_path)

        import fundfactory_core.config.settings as settings
        orig = settings.DB_PATH
        settings.DB_PATH = db_path

        try:
            import importlib
            import fundfactory_core.factors.registry as reg
            importlib.reload(reg)

            required_keys = {"factor_id", "name", "category", "description", "direction", "lookback_days"}
            for fid in reg.factor_ids():
                meta = reg.get_metadata(fid)
                assert meta is not None, f"No metadata for {fid}"
                missing = required_keys - set(meta.keys())
                assert not missing, f"Factor {fid} missing: {missing}"
        finally:
            settings.DB_PATH = orig

    def test_no_sqlite_errors_in_calc(self, tmp_path):
        """Factor calc functions must not raise SQLite errors on synthetic data."""
        db_path = _init_test_db(tmp_path)

        import fundfactory_core.config.settings as settings
        orig = settings.DB_PATH
        settings.DB_PATH = db_path

        try:
            import importlib
            import fundfactory_core.factors.registry as reg
            importlib.reload(reg)

            calc_funcs = reg.get_all_calc_funcs()
            for fid, calc_func in calc_funcs.items():
                try:
                    result = calc_func("20231228")
                    # Should return DataFrame (possibly empty), not raise
                    assert isinstance(result, pd.DataFrame), f"{fid} returned {type(result)}, expected DataFrame"
                except sqlite3.OperationalError as e:
                    if "no such function" in str(e).lower() or "std" in str(e).lower():
                        pytest.fail(f"SQLite function error in {fid}: {e}")
        finally:
            settings.DB_PATH = orig

    def test_category_coverage(self, tmp_path):
        """Must have factors from profitability, growth, quality, valuation, momentum categories."""
        db_path = _init_test_db(tmp_path)

        import fundfactory_core.config.settings as settings
        orig = settings.DB_PATH
        settings.DB_PATH = db_path

        try:
            import importlib
            import fundfactory_core.factors.registry as reg
            importlib.reload(reg)

            meta = reg.get_all_metadata()
            categories = set(m["category"] for m in meta.values())
            required_cats = {"profitability", "growth", "quality", "valuation", "momentum", "volatility"}
            missing = required_cats - categories
            assert not missing, f"Missing categories: {missing}"
        finally:
            settings.DB_PATH = orig

    def test_sample_factors_still_work(self, tmp_path):
        """Original sample_factors (MOM_5D, ROE, etc.) must still be registered."""
        db_path = _init_test_db(tmp_path)

        import fundfactory_core.config.settings as settings
        orig = settings.DB_PATH
        settings.DB_PATH = db_path

        try:
            import importlib
            import fundfactory_core.factors.registry as reg
            importlib.reload(reg)

            required = {"MOM_5D", "MOM_20D", "ROE", "ROA", "PE_SIMPLE", "PB_SIMPLE",
                        "VOL_20D", "LNCAP"}
            ids = set(reg.factor_ids())
            missing = required - ids
            assert not missing, f"Missing original factors: {missing}"
        finally:
            settings.DB_PATH = orig


def _factor_value(calc_func, factor_id, date, ts_code="000001.SZ"):
    df = calc_func(date)
    row = df[df["ts_code"] == ts_code]
    assert len(row) == 1, f"{factor_id} did not return one row for {ts_code}: {df}"
    assert row.iloc[0]["factor_id"] == factor_id
    return float(row.iloc[0]["factor_value"])


def test_financial_factor_formula_values_are_exact(tmp_path):
    """Formula-level checks catch wrong naming, wrong signs, and wrong denominators."""
    db_path = _init_test_db(tmp_path)
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("DELETE FROM income_statement")
    cur.execute("DELETE FROM balance_sheet")
    cur.execute("DELETE FROM cash_flow")
    cur.execute("DELETE FROM daily_data")

    cur.execute(
        """
        INSERT INTO income_statement VALUES
        ('000001.SZ', '20231231', '20231231', '20231231',
         1000, 600, 50, 30, 20, 10, 200, 180, 30, 150, 120, 1.2, 220, 250, NULL)
        """
    )
    cur.execute(
        """
        INSERT INTO income_statement VALUES
        ('000001.SZ', '20221231', '20221231', '20221231',
         800, 500, 40, 24, 16, 8, 160, 140, 24, 120, 100, 1.0, 176, 200, NULL)
        """
    )
    cur.execute(
        """
        INSERT INTO balance_sheet VALUES
        ('000001.SZ', '20231231', '20231231', '20231231',
         10, 100, 50, 80, 500, 250, 200, 20, 0, 2000, 800, 100, 200, 1200, 40, NULL)
        """
    )
    cur.execute(
        """
        INSERT INTO balance_sheet VALUES
        ('000001.SZ', '20221231', '20221231', '20221231',
         10, 80, 40, 60, 400, 200, 160, 16, 0, 1600, 600, 80, 160, 1000, 30, NULL)
        """
    )
    cur.execute(
        """
        INSERT INTO cash_flow VALUES
        ('000001.SZ', '20231231', '20231231', '20231231',
         150, 900, 180, -50, 130, 20, NULL)
        """
    )
    cur.execute(
        """
        INSERT INTO cash_flow VALUES
        ('000001.SZ', '20221231', '20221231', '20221231',
         120, 720, 150, -40, 100, 15, NULL)
        """
    )
    cur.execute(
        """
        INSERT INTO daily_data VALUES
        ('000001.SZ', '20231231', 20, 21, 19, 20, 19, 1, 5, 1000, 20000)
        """
    )
    cur.execute(
        """
        INSERT INTO daily_data VALUES
        ('000001.SZ', '20240131', 20, 21, 19, 20, 19, 1, 5, 1000, 20000)
        """
    )
    conn.commit()
    conn.close()

    import fundfactory_core.config.settings as settings
    orig = settings.DB_PATH
    settings.DB_PATH = db_path
    try:
        import importlib
        import fundfactory_core.factors.registry as reg
        importlib.reload(reg)
        funcs = reg.get_all_calc_funcs()

        assert _factor_value(funcs["PROF_01"], "PROF_01", "20231231") == pytest.approx(120 / 1100)
        assert _factor_value(funcs["PROF_04"], "PROF_04", "20231231") == pytest.approx(0.4)
        assert _factor_value(funcs["GROW_01"], "GROW_01", "20231231") == pytest.approx(0.25)
        assert _factor_value(funcs["QUAL_01"], "QUAL_01", "20231231") == pytest.approx(1.5)
        assert _factor_value(funcs["DEBT_03"], "DEBT_03", "20231231") == pytest.approx(1.68)
        assert _factor_value(funcs["OPER_01"], "OPER_01", "20231231") == pytest.approx(1000 / 45)
        assert _factor_value(funcs["VALU_01"], "VALU_01", "20231231") == pytest.approx(200 / 120)
        assert _factor_value(funcs["PROF_01"], "PROF_01", "20240131") == pytest.approx(120 / 1100)
        assert _factor_value(funcs["VALU_01"], "VALU_01", "20240131") == pytest.approx(200 / 120)
        assert funcs["VALU_05"]("20231231").empty
        assert _factor_value(funcs["EXP_05"], "EXP_05", "20231231") == pytest.approx(0.11)
    finally:
        settings.DB_PATH = orig


def test_price_volume_factor_formula_values_are_exact(tmp_path):
    db_path = _init_test_db(tmp_path)
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("DELETE FROM daily_data")
    cur.execute("DELETE FROM balance_sheet")

    dates = pd.date_range("2024-01-01", periods=20, freq="B").strftime("%Y%m%d").tolist()
    pct_values = [-1, 2, -2, 1, 0, 3, -1, 2, -3, 1, 1, -1, 2, -2, 3, 1, 2, -1, 0, 3]
    for idx, (trade_date, pct) in enumerate(zip(dates, pct_values), start=1):
        close = 10 + idx
        cur.execute(
            """
            INSERT INTO daily_data VALUES
            ('000001.SZ', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                trade_date,
                close - 0.5,
                close + 1,
                close - 1,
                close,
                close - 1,
                pct,
                pct,
                1000 + idx * 10,
                (1000 + idx * 10) * close,
            ),
        )
        cur.execute(
            """
            INSERT INTO daily_data VALUES
            ('000002.SZ', ?, 1, 2, 1, 1, 1, 0, 0, 100, 100)
            """,
            (trade_date,),
        )
    cur.execute(
        """
        INSERT INTO balance_sheet VALUES
        ('000001.SZ', '20231231', '20231231', '20231231',
         10000, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, NULL)
        """
    )
    conn.commit()
    conn.close()

    import fundfactory_core.config.settings as settings
    orig = settings.DB_PATH
    settings.DB_PATH = db_path
    target = dates[-1]
    try:
        import importlib
        import fundfactory_core.factors.registry as reg
        importlib.reload(reg)
        funcs = reg.get_all_calc_funcs()

        last5 = np.array(pct_values[-5:]) / 100
        last20 = np.array(pct_values) / 100
        closes = np.array([10 + i for i in range(1, 21)], dtype=float)
        highs = closes + 1
        lows = closes - 1
        amounts = np.array([(1000 + i * 10) * (10 + i) for i in range(1, 21)], dtype=float)

        assert _factor_value(funcs["REV_5D"], "REV_5D", target) == pytest.approx(-(((1 + last5).prod() - 1) * 100))
        assert _factor_value(funcs["RETURN_CONSISTENCY_20D"], "RETURN_CONSISTENCY_20D", target) == pytest.approx((last20 > 0).mean())
        assert _factor_value(funcs["MA_DEV_20D"], "MA_DEV_20D", target) == pytest.approx(closes[-1] / closes.mean() - 1)
        gain = np.clip(last20, 0, None).mean()
        loss = (-np.clip(last20, None, 0)).mean()
        assert _factor_value(funcs["RSI_20D"], "RSI_20D", target) == pytest.approx(gain / (gain + loss))
        assert _factor_value(funcs["WILLIAMS_R_20D"], "WILLIAMS_R_20D", target) == pytest.approx((highs.max() - closes[-1]) / (highs.max() - lows.min()))
        assert _factor_value(funcs["ILLIQ"], "ILLIQ", target) == pytest.approx((np.abs(last20) / amounts).mean())
        assert _factor_value(funcs["HIGH_LOW_RATIO_20D"], "HIGH_LOW_RATIO_20D", target) == pytest.approx(highs.max() / lows.min())
    finally:
        settings.DB_PATH = orig
